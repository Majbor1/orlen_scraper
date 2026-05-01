import requests
import json
import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Wczytanie zmiennych środowiskowych (kluczy API) z pliku .env
load_dotenv()

APP_TOKEN = os.getenv("APP_TOKEN")
USER_KEY = os.getenv("USER_KEY")

def pobierz_limit_rzadowy(df_max, data_str, paliwo):
    """
    Funkcja pomocnicza do wyciągania limitu państwowego.
    Sprawdza DataFrame pod kątem konkretnej daty i paliwa.
    """
    if df_max is None or df_max.empty:
        return None
        
    p_lower = paliwo.lower()
    if '95' in p_lower:
        kolumna = 'cena_max_pb95'
    elif '98' in p_lower:
        kolumna = 'cena_max_pb98'
    else:
        kolumna = 'cena_max_on'

    row = df_max[df_max['data'] == data_str]
    if not row.empty and kolumna in row.columns:
        val = row.iloc[0][kolumna]
        if pd.notna(val):
            return float(val)
    return None

def wyslij_push():
    print("📲 Przygotowuję rozbudowane powiadomienie Pushover z rekomendacją...")
    
    # Ścieżki do plików z danymi
    plik_json = 'data/historia_treningow.json'
    plik_hurt = 'data/orlen_master_table.csv'
    plik_max = 'data/cena_max.csv'
    plik_stacje = 'data/ceny_na_stacjach.csv' # Nowa ścieżka do pliku z VAT
    
    if not os.path.exists(plik_json) or not os.path.exists(plik_hurt):
        print("❌ Brak plików z danymi hurtowymi lub predykcjami.")
        return

    # 1. Wczytanie predykcji AI
    with open(plik_json, 'r', encoding='utf-8') as f:
        historia = json.load(f)
    najnowszy = historia[0]
    wyniki_ai = najnowszy['wyniki']
    
    # 2. Wczytanie historii hurtowej
    df_hurt = pd.read_csv(plik_hurt)
    df_hurt['data'] = pd.to_datetime(df_hurt['data'], errors='coerce')
    
    # 3. Wczytanie bazy limitów rządowych
    df_max = None
    if os.path.exists(plik_max):
        df_max = pd.read_csv(plik_max)
        df_max['data'] = pd.to_datetime(df_max['data'], errors='coerce').dt.strftime('%Y-%m-%d')

    # ==========================================
    # POBIERANIE PODATKU VAT Z PLIKU STACJI
    # ==========================================
    pobrany_vat = 8 # Ustawiamy awaryjną wartość domyślną 8%
    
    if os.path.exists(plik_stacje):
        try:
            df_stacje = pd.read_csv(plik_stacje)
            # Sprawdzamy, czy plik nie jest pusty i czy ma kolumnę 'vat'
            if not df_stacje.empty and 'vat' in df_stacje.columns:
                # iloc[-1] pobiera ostatni wiersz (najświeższe dane) z tabeli
                ostatni_vat = df_stacje.iloc[-1]['vat']
                if pd.notna(ostatni_vat):
                    pobrany_vat = float(ostatni_vat)
        except Exception as e:
            print(f"⚠️ Błąd podczas odczytu pliku stacji. Użyto domyślnego VAT 8%. Szczegóły: {e}")

    # Przeliczenie liczby (np. 8) na mnożnik (1.08)
    mnoznik_vat = 1 + (pobrany_vat / 100)
    # ==========================================

    # Przygotowanie dat do wyświetlania
    dzis_data = datetime.now()
    jutro_data = dzis_data + timedelta(days=1)
    dzis_str = dzis_data.strftime("%Y-%m-%d")
    jutro_str = jutro_data.strftime("%Y-%m-%d")

    wiadomosc = ""
    rekomendacja_ogolna = "Analiza Rynku Paliw"

    # ==========================================
    # USTAWIENIA KALKULATORA DETALICZNEGO
    # ==========================================
    # Zmienne netto oznaczające dodatkowe koszty i zyski stacji. 
    # Możesz je swobodnie modyfikować w zależności od sytuacji na rynku.
    KOSZTY_OPERACYJNE_NETTO = 0.40  
    MARZA_NETTO = 0.20              
    URL_STRONY = "https://fuel-predictions.streamlit.app/" 
    # ==========================================

    for paliwo, dane in wyniki_ai.items():
        ostatni_wiersz = df_hurt[df_hurt['paliwo'] == paliwo].iloc[-1]
        
        # A. Obliczenia Hurtowe (PLN/litr)
        hurt_dzis_l = ostatni_wiersz['cena_dzis'] / 1000
        hurt_jutro_l = dane['prognoza_na_jutro'] / 1000
        
        # B. Szacowany Detal (Nasza symulacja pylonu wykorzystująca dynamiczny mnoznik_vat)
        detal_dzis = (hurt_dzis_l + KOSZTY_OPERACYJNE_NETTO + MARZA_NETTO) * mnoznik_vat
        detal_jutro = (hurt_jutro_l + KOSZTY_OPERACYJNE_NETTO + MARZA_NETTO) * mnoznik_vat
        
        # C. Limity Państwowe
        limit_dzis = pobierz_limit_rzadowy(df_max, dzis_str, paliwo)
        limit_jutro = pobierz_limit_rzadowy(df_max, jutro_str, paliwo)
        
        # D. LOGIKA DECYZYJNA: CENA OSTATECZNA
        # Wybieramy mniejszą wartość za pomocą funkcji min() z Pythona
        cena_ostateczna_dzis = min(detal_dzis, limit_dzis) if limit_dzis else detal_dzis
        cena_ostateczna_jutro = min(detal_jutro, limit_jutro) if limit_jutro else detal_jutro
        
        roznica = cena_ostateczna_jutro - cena_ostateczna_dzis
        
        # Generowanie rekomendacji
        if roznica > 0.02: # Tolerancja wahań: 2 grosze
            decyzja = f"🔴 TANKUJ DZIŚ! (Jutro drożej o {roznica:.2f} zł/l)"
            rekomendacja_ogolna = "Tankuj dziś!"
        elif roznica < -0.02:
            decyzja = f"🟢 CZEKAJ! (Jutro taniej o {abs(roznica):.2f} zł/l)"
        else:
            decyzja = f"🟡 BEZ ZMIAN (Różnica: {roznica:+.2f} zł/l)"

        # E. Budowanie czytelnej wiadomości
        tekst_limit_dzis = f"{limit_dzis:.2f} zł/l" if limit_dzis else "Brak"
        tekst_limit_jutro = f"{limit_jutro:.2f} zł/l" if limit_jutro else "Brak"

        wiadomosc += f" {paliwo.upper()}\n"
        wiadomosc += f" DECYZJA: {decyzja}\n\n"
        
        wiadomosc += f" Cena maksymalna:\n"
        wiadomosc += f" • Dziś ({dzis_str}): {tekst_limit_dzis}\n"
        wiadomosc += f" • Jutro: ({jutro_str}): {tekst_limit_jutro}\n\n"
        
        wiadomosc += f" Cena hurtowa (Orlen):\n"
        wiadomosc += f" • Dziś: {hurt_dzis_l:.2f} zł/l\n"
        wiadomosc += f" • Szacowana na jutro: {hurt_jutro_l:.2f} zł/l\n\n"
        
        wiadomosc += f" Cena detaliczna (Z VAT {int(pobrany_vat)}%):\n"
        wiadomosc += f" • Dziś: {detal_dzis:.2f} zł/l\n"
        wiadomosc += f" • Jutro: {detal_jutro:.2f} zł/l\n"
        wiadomosc += "───────────────\n"

    # Dodanie linku do panelu ułatwiającego szybki dostęp do wykresów
    wiadomosc += f"🌐 Wykresy i szczegóły analityczne:\n{URL_STRONY}"

    # 5. Wysyłka do API Pushover (Tylko struktura tekstowa bez załączników graficznych)
    payload = {
        "token": APP_TOKEN,
        "user": USER_KEY,
        "title": f"📊 {rekomendacja_ogolna} | {dzis_str}",
        "message": wiadomosc,
        "html": 0,
        "priority": 1 if "Tankuj" in rekomendacja_ogolna else 0
    }
    
    try:
        r = requests.post("https://api.pushover.net/1/messages.json", data=payload)
            
        if r.status_code == 200:
            print("✅ Błyskawiczne powiadomienie wysłane pomyślnie!")
        else:
            print(f"❌ Błąd serwera Pushover: {r.text}")
    except Exception as e:
        print(f"❌ Wystąpił błąd podczas wysyłania API: {e}")

if __name__ == "__main__":
    wyslij_push()