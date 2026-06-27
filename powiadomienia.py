import os
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

APP_TOKEN = os.getenv("APP_TOKEN")
USER_KEY = os.getenv("USER_KEY")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

def pobierz_limit_rzadowy(df_max, data_str, paliwo):
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
    if not APP_TOKEN:
        print("Błąd: Brakuje APP_TOKEN w env.")
        return

    plik_json = 'data/historia_treningow.json'
    plik_hurt = 'data/orlen_master_table.csv'
    plik_max = 'data/cena_max.csv'
    plik_stacje = 'data/ceny_na_stacjach.csv'
    sciezka_sub = 'data/subskrybenci.txt'
    
    if not os.path.exists(plik_json) or not os.path.exists(plik_hurt):
        print("Brak plików z danymi.")
        return

    with open(plik_json, 'r', encoding='utf-8') as f:
        historia = json.load(f)
    najnowszy = historia[0]
    wyniki_ai = najnowszy['wyniki']
    
    df_hurt = pd.read_csv(plik_hurt)
    df_hurt['data'] = pd.to_datetime(df_hurt['data'], errors='coerce')
    
    df_max = None
    if os.path.exists(plik_max):
        df_max = pd.read_csv(plik_max)
        df_max['data'] = pd.to_datetime(df_max['data'], errors='coerce').dt.strftime('%Y-%m-%d')

    pobrany_vat = 8
    
    if os.path.exists(plik_stacje):
        try:
            df_stacje = pd.read_csv(plik_stacje)
            if not df_stacje.empty and 'vat' in df_stacje.columns:
                ostatni_vat = df_stacje.iloc[-1]['vat']
                if pd.notna(ostatni_vat):
                    pobrany_vat = float(ostatni_vat)
        except Exception as e:
            print(f"Błąd odczytu pliku stacji: {e}")

    mnoznik_vat = 1 + (pobrany_vat / 100)

    dzis_data = datetime.now()
    jutro_data = dzis_data + timedelta(days=1)
    dzis_str = dzis_data.strftime("%Y-%m-%d")
    jutro_str = jutro_data.strftime("%Y-%m-%d")

    wiadomosc_html = ""
    rekomendacja_ogolna = "Analiza Rynku Paliw"

    KOSZTY_OPERACYJNE_NETTO = 0.40  
    MARZA_NETTO = 0.20              
    URL_STRONY = "https://orlen-ai.streamlit.app"

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
            decyzja = f"🔴 <font color='#ff0000'><b>TANKUJ DZIŚ! (Jutro drożej o {roznica:.2f} zł/l)</b></font>"
            rekomendacja_ogolna = "Tankuj dziś!"
        elif roznica < -0.02:
            decyzja = f"🟢 <font color='#00ff00'><b>CZEKAJ! (Jutro taniej o {abs(roznica):.2f} zł/l)</b></font>"
        else:
            decyzja = f"🟡 <b>BEZ ZMIAN</b> (Różnica: {roznica:+.2f} zł/l)"

        tekst_limit_dzis = f"{limit_dzis:.2f} zł/l" if limit_dzis else "Brak"
        tekst_limit_jutro = f"{limit_jutro:.2f} zł/l" if limit_jutro else "Brak"

        wiadomosc_html += f"<h3>⛽ {paliwo.upper()}</h3>"
        wiadomosc_html += f"DECYZJA: {decyzja}<br><br>"
        wiadomosc_html += f"<b>Cena maksymalna:</b><br>"
        wiadomosc_html += f"• Dziś ({dzis_str}): {tekst_limit_dzis}<br>"
        wiadomosc_html += f"• Jutro ({jutro_str}): {tekst_limit_jutro}<br><br>"
        wiadomosc_html += f"<b>Cena hurtowa (Orlen):</b><br>"
        wiadomosc_html += f"• Dziś: {hurt_dzis_l:.2f} zł/l<br>"
        wiadomosc_html += f"• Prognoza: {hurt_jutro_l:.2f} zł/l<br><br>"
        wiadomosc_html += f"<b>Cena detaliczna (VAT {int(pobrany_vat)}%):</b><br>"
        wiadomosc_html += f"• Dziś: {detal_dzis:.2f} zł/l<br>"
        wiadomosc_html += f"• Jutro: {detal_jutro:.2f} zł/l<br>"
        wiadomosc_html += "<hr>"

    lista_odbiorcow = [USER_KEY] if USER_KEY else []
    
    if ENCRYPTION_KEY and os.path.exists(sciezka_sub):
        fernet = Fernet(ENCRYPTION_KEY)
        with open(sciezka_sub, 'r', encoding='utf-8') as plik:
            for linia in plik:
                zaszyfrowany = linia.strip()
                if zaszyfrowany:
                    try:
                        odszyfrowany_pelny = fernet.decrypt(zaszyfrowany.encode()).decode()
                        if ":" in odszyfrowany_pelny:
                            klucz_finalny = odszyfrowany_pelny.split(":")[1]
                        else:
                            klucz_finalny = odszyfrowany_pelny 
                            
                        if klucz_finalny not in lista_odbiorcow:
                            lista_odbiorcow.append(klucz_finalny)
                    except:
                        continue

    for key in lista_odbiorcow:
        payload = {
            "token": APP_TOKEN,
            "user": key,
            "title": f"{rekomendacja_ogolna} | {dzis_str}",
            "message": wiadomosc_html,
            "html": 1, 
            "url": URL_STRONY, 
            "url_title": "Otwórz Pełny Dashboard",
            "priority": 1 if "Tankuj" in rekomendacja_ogolna else 0
        }
        
        try:
            r = requests.post("https://api.pushover.net/1/messages.json", data=payload)
            if r.status_code == 200:
                pass
            else:
                print(f"Błąd Pushover: {r.text}")
        except Exception as e:
            print(f"Błąd komunikacji: {e}")

if __name__ == "__main__":
    wyslij_push()