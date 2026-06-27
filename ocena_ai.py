import pandas as pd
from google import genai
import time
import json
import os
from dotenv import load_dotenv

load_dotenv()

klucze_api = [os.getenv("GEMINI_API_KEY_1"), os.getenv("GEMINI_API_KEY_2")]
klucze_api = [k.strip() for k in klucze_api if k and k.strip()]

if not klucze_api:
    print("❌ Błąd! Brak kluczy API.")
    exit()

client = genai.Client(api_key=klucze_api[0])


plik_czyste = 'data/wiadomosci_orlen_CZYSTE.csv'
plik_ocenione = 'data/wiadomosci_orlen_Ocenione_AI.csv'

try:
    df_nowe = pd.read_csv(plik_czyste, encoding='utf-8')
except FileNotFoundError:
    print("Brak pliku")
    exit()

if os.path.exists(plik_ocenione):
    df_historia = pd.read_csv(plik_ocenione, encoding='utf-8')
    ocenione_linki = df_historia['link'].tolist()
else:
    df_historia = pd.DataFrame()
    ocenione_linki = []

df_do_oceny = df_nowe[~df_nowe['link'].isin(ocenione_linki)].copy()

if len(df_do_oceny) == 0:
    print("Baza AI jest aktualna!")
    if not df_historia.empty and 'data' in df_historia.columns:
        df_historia['data'] = pd.to_datetime(df_historia['data'], errors='coerce')
        df_historia = df_historia.sort_values(by='data', ascending=False)
        df_historia['data'] = df_historia['data'].dt.strftime('%Y-%m-%d')
        df_historia.to_csv(plik_ocenione, index=False, encoding='utf-8-sig')
    exit()

rozmiar_paczki = 3
paczki = [df_do_oceny.iloc[i:i + rozmiar_paczki] for i in range(0, len(df_do_oceny), rozmiar_paczki)]

prompt_bazowy = """
Oceń sentyment poniższych artykułów o firmie Orlen w skali od 0 do 10 dla dwóch kategorii:
1. 'panika' (problemy, awarie, spadki)
2. 'sukces' (zyski, inwestycje).

Zwróć odpowiedź TYLKO w formacie JSON (tablica obiektów, w tej samej kolejności co podane teksty).
Przykład: [{"panika": 2, "sukces": 8}, {"panika": 9, "sukces": 1}]

Teksty do analizy:
"""

for paczka in paczki:
    teksty = ""
    for i, row in paczka.iterrows():
        teksty += f"--- TEKST {i} ---\n{str(row['tytul'])} {str(row['tresc'])[:1000]}\n\n"
    
    zapytanie = prompt_bazowy + teksty
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=zapytanie,
        )
        
        wynik_txt = response.text.replace('```json', '').replace('```', '').strip()
        wyniki_json = json.loads(wynik_txt)
        
        for idx, (_, row) in enumerate(paczka.iterrows()):
            nowy_wiersz = row.copy()
            
            if idx < len(wyniki_json):
                nowy_wiersz['panika_ai'] = wyniki_json[idx].get('panika', 0)
                nowy_wiersz['sukces_ai'] = wyniki_json[idx].get('sukces', 0)
            else:
                nowy_wiersz['panika_ai'] = 0
                nowy_wiersz['sukces_ai'] = 0
                
            print(f"📰 Oceniono: {row['tytul'][:40]}... P:{nowy_wiersz['panika_ai']} S:{nowy_wiersz['sukces_ai']}")
            
            df_historia = pd.concat([df_historia, pd.DataFrame([nowy_wiersz])], ignore_index=True)
            
        df_historia['data'] = pd.to_datetime(df_historia['data'], errors='coerce')
        df_historia = df_historia.sort_values(by='data', ascending=False)
        df_historia['data'] = df_historia['data'].dt.strftime('%Y-%m-%d')
        df_historia = df_historia.reset_index(drop=True)
        
        df_historia.to_csv(plik_ocenione, index=False, encoding='utf-8')
        time.sleep(4) 
        
    except Exception as e:
        print(f"Błąd przy paczce (Pominięto, sprawdź logi): {e}")
        time.sleep(10)

print("\nPrzetwarzanie zakończone!")