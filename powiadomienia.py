import os
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Wczytanie zmiennych środowiskowych z pliku .env
load_dotenv()

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

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

def wyslij_discord():
    print("📲 Przygotowuję analityczne powiadomienie na Discorda z rekomendacją...")
    
    # Ścieżki do plików z danymi
    plik_json = 'data/historia_treningow.json'
    plik_hurt = 'data/orlen_master_table.csv'
    plik_max = 'data/cena_max.csv'
    plik_stacje = 'data/ceny_na_stacjach.csv'
    sciezka_sub = 'data/subskrybenci.txt'
    
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

    # 4. Pobieranie VAT
    pobrany_vat = 8 
    if os.path.exists(plik_stacje):
        try:
            df_stacje = pd.read_csv(plik_stacje)
            if not df_stacje.empty and 'vat' in df_stacje.columns:
                ostatni_vat = df_stacje.iloc[-1]['vat']
                if pd.notna(ostatni_vat):
                    pobrany_vat = float(ostatni_vat)
        except Exception as e:
            print(f"⚠️ Błąd odczytu pliku stacji. Użyto domyślnego VAT 8%. Szczegóły: {e}")

    mnoznik_vat = 1 + (pobrany_vat / 100)

    # Przygotowanie dat do wyświetlania
    dzis_data = datetime.now()
    jutro_data = dzis_data + timedelta(days=1)
    dzis_str = dzis_data.strftime("%Y-%m-%d")
    jutro_str = jutro_data.strftime("%Y-%m-%d")

    rekomendacja_ogolna = "Analiza Rynku Paliw"

    KOSZTY_OPERACYJNE_NETTO = 0.40  
    MARZA_NETTO = 0.20              
    URL_STRONY = "https://orlen-ai.streamlit.app"

    # BUDOWA WIADOMOŚCI W FORMACIE MARKDOWN (DLA DISCORDA)
    wiadomosc_md = f"## 📊 {rekomendacja_ogolna} | {dzis_str}\n\n"

    for paliwo, dane in wyniki_ai.items():
        ostatni_wiersz = df_hurt[df_hurt['paliwo'] == paliwo].iloc[-1]
        
        hurt_dzis_l = ostatni_wiersz['cena_dzis'] / 1000
        hurt_jutro_l = dane['prognoza_na_jutro'] / 1000
        
        detal_dzis = (hurt_dzis_l + KOSZTY_OPERACYJNE_NETTO + MARZA_NETTO) * mnoznik_vat
        detal_jutro = (hurt_jutro_l + KOSZTY_OPERACYJNE_NETTO + MARZA_NETTO) * mnoznik_vat
        
        limit_dzis = pobierz_limit_rzadowy(df_max, dzis_str, paliwo)
        limit_jutro = pobierz_limit_rzadowy(df_max, jutro_str, paliwo)
        
        cena_ostateczna_dzis = min(detal_dzis, limit_dzis) if limit_dzis else detal_dzis
        cena_ostateczna_jutro = min(detal_jutro, limit_jutro) if limit_jutro else detal_jutro
        
        roznica = cena_ostateczna_jutro - cena_ostateczna_dzis
        
        if roznica > 0.02: 
            decyzja = f"🔴 **TANKUJ DZIŚ!** (Jutro drożej o {roznica:.2f} zł/l)"
        elif roznica < -0.02:
            decyzja = f"🟢 **CZEKAJ!** (Jutro taniej o {abs(roznica):.2f} zł/l)"
        else:
            decyzja = f"🟡 **BEZ ZMIAN** (Różnica: {roznica:+.2f} zł/l)"

        tekst_limit_dzis = f"{limit_dzis:.2f} zł/l" if limit_dzis else "Brak"
        tekst_limit_jutro = f"{limit_jutro:.2f} zł/l" if limit_jutro else "Brak"

        wiadomosc_md += f"### ⛽ {paliwo.upper()}\n"
        wiadomosc_md += f"👉 DECYZJA: {decyzja}\n"
        wiadomosc_md += f"**Cena maksymalna:**\n"
        wiadomosc_md += f"• Dziś ({dzis_str}): {tekst_limit_dzis}\n"
        wiadomosc_md += f"• Jutro ({jutro_str}): {tekst_limit_jutro}\n"
        wiadomosc_md += f"**Cena hurtowa (Orlen):**\n"
        wiadomosc_md += f"• Dziś: {hurt_dzis_l:.2f} zł/l\n"
        wiadomosc_md += f"• Prognoza: {hurt_jutro_l:.2f} zł/l\n"
        wiadomosc_md += f"**Cena detaliczna (VAT {int(pobrany_vat)}%):**\n"
        wiadomosc_md += f"• Dziś: {detal_dzis:.2f} zł/l\n"
        wiadomosc_md += f"• Jutro: {detal_jutro:.2f} zł/l\n"
        wiadomosc_md += "─────────────────\n"

    wiadomosc_md += f"\n🌐 **Otwórz Pełny Dashboard:**\n{URL_STRONY}"

    # ==========================================
    # WYSYŁKA DO SUBSKRYBENTÓW (DISCORD WEBHOOKS)
    # ==========================================
    # Admin ma swój webhook w .env
    lista_webhookow = [DISCORD_WEBHOOK] if DISCORD_WEBHOOK else []
    
    # Doczytywanie dodatkowych webhooków (subskrybentów ze strony)
    if ENCRYPTION_KEY and os.path.exists(sciezka_sub):
        fernet = Fernet(ENCRYPTION_KEY)
        with open(sciezka_sub, 'r', encoding='utf-8') as plik:
            for linia in plik:
                zaszyfrowany = linia.strip()
                if zaszyfrowany:
                    try:
                        odszyfrowany_pelny = fernet.decrypt(zaszyfrowany.encode()).decode()
                        if ":" in odszyfrowany_pelny:
                            # Wyciągamy sam adres url webhooka
                            klucz_finalny = odszyfrowany_pelny.split(":", 1)[1] 
                        else:
                            klucz_finalny = odszyfrowany_pelny 
                            
                        if klucz_finalny not in lista_webhookow and "discord.com/api/webhooks" in klucz_finalny:
                            lista_webhookow.append(klucz_finalny)
                    except:
                        continue

    print(f"🚀 Rozpoczynam wysyłkę do {len(lista_webhookow)} kanałów Discord...")

    for webhook_url in lista_webhookow:
        # Format danych akceptowany przez Discord API
        payload = {
            "username": "Orlen AI Bot",
            "content": wiadomosc_md
        }
        
        try:
            r = requests.post(webhook_url, json=payload)
            # Discord zwraca kod 204 No Content przy sukcesie wysyłki webhooka
            if r.status_code in [200, 204]:
                print(f"✅ Wysłano powiadomienie na Discorda!")
            else:
                print(f"❌ Błąd Discord API: {r.text}")
        except Exception as e:
            print(f"❌ Błąd komunikacji: {e}")

if __name__ == "__main__":
    wyslij_discord()