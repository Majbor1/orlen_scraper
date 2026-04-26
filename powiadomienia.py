import requests
import json
import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

APP_TOKEN = os.getenv("APP_TOKEN")
USER_KEY = os.getenv("USER_KEY")

def wyslij_push():
    print("📲 Przygotowuję rozszerzone powiadomienie Pushover...")
    
    plik_json = 'data/historia_treningow.json'
    plik_hurt = 'data/orlen_master_table.csv'
    plik_max = 'data/cena_max.csv'
    
    if not os.path.exists(plik_json) or not os.path.exists(plik_hurt):
        print("❌ Brak wymaganych plików danych.")
        return

    # 1. Wczytujemy prognozy
    with open(plik_json, 'r', encoding='utf-8') as f:
        historia = json.load(f)
    najnowszy = historia[0]
    wyniki_ai = najnowszy['wyniki']
    
    # 2. Wczytujemy aktualne ceny hurtowe (do porównania)
    df_hurt = pd.read_csv(plik_hurt)
    
    # 3. Wczytujemy ceny maksymalne (jeśli istnieją)
    df_max = None
    if os.path.exists(plik_max):
        df_max = pd.read_csv(plik_max)

    wiadomosc = ""
    rekomendacja_ogolna = "✅ Stabilnie"
    
    # Wyznaczamy datę "jutra" dla limitów rządowych
    jutro_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    for paliwo, dane in wyniki_ai.items():
        prognoza_m3 = dane['prognoza_na_jutro']
        prognoza_l = round(prognoza_m3 / 1000, 2)
        
        # Pobieramy ostatnią znaną cenę dzisiejszą dla tego paliwa
        ostatnia_cena_hurt = df_hurt[df_hurt['paliwo'] == paliwo].iloc[-1]['cena_dzis']
        
        # Logika rekomendacji
        roznica = prognoza_m3 - ostatnia_cena_hurt
        if roznica > 5: # Wzrost o więcej niż 5 PLN/m3
            status = "🔴 KUPUJ TERAZ (Jutro drożej)"
            rekomendacja_ogolna = "⚠️ Tankuj dziś!"
        elif roznica < -5: # Spadek o więcej niż 5 PLN/m3
            status = "🟢 CZEKAJ (Jutro taniej)"
            rekomendacja_ogolna = "⚠️ Czekaj z tankowaniem"
        else:
            status = "🟡 BEZ ZMIAN"

        # Szukamy ceny maksymalnej w pliku rządowym
        limit_txt = ""
        if df_max is not None:
            # Mapowanie nazw paliw na kolumny w cena_max.csv
            kolumna_max = None
            p_lower = paliwo.lower()
            if '95' in p_lower: kolumna_max = 'cena_max_pb95'
            elif '98' in p_lower: kolumna_max = 'cena_max_pb98'
            elif 'on' in p_lower or 'diesel' in p_lower: kolumna_max = 'cena_max_on'
            
            if kolumna_max:
                limit_row = df_max[df_max['data'] == jutro_str]
                if not limit_row.empty:
                    val_max = limit_row.iloc[0][kolumna_max]
                    if pd.notna(val_max):
                        limit_txt = f" (Limit: {val_max} zł/l)"

        wiadomosc += f"⛽ {paliwo.upper()}\n"
        wiadomosc += f"⛽ Jutro: {prognoza_l} zł/l{limit_txt}\n"
        wiadomosc += f"⛽ {status}\n\n"
    
    # 4. Wysyłka do Pushover
    dzis_data = datetime.now().strftime("%Y-%m-%d")
    sciezka_wykresu = f'data/wykresy/wykres_z_dnia_{dzis_data}.png'
    
    payload = {
        "token": APP_TOKEN,
        "user": USER_KEY,
        "title": f"{rekomendacja_ogolna} | {dzis_data}",
        "message": wiadomosc,
        "priority": 1 if "Tankuj" in rekomendacja_ogolna else 0
    }
    
    try:
        if os.path.exists(sciezka_wykresu):
            with open(sciezka_wykresu, 'rb') as f:
                r = requests.post(
                    "https://api.pushover.net/1/messages.json",
                    data=payload,
                    files={"attachment": ("wykres.png", f, "image/png")}
                )
        else:
            r = requests.post("https://api.pushover.net/1/messages.json", data=payload)
            
        if r.status_code == 200:
            print("✅ Powiadomienie wysłane!")
        else:
            print(f"❌ Błąd API: {r.text}")
    except Exception as e:
        print(f"❌ Błąd: {e}")

if __name__ == "__main__":
    wyslij_push()