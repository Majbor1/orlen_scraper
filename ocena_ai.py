import pandas as pd
from google import genai
import time
import re
import os

# ==========================================
KLUCZ_API = "AIzaSyBGumMOzqu1lApuIUBoW_1I2zOZDl4qD1A"
# ==========================================

client = genai.Client(api_key=KLUCZ_API)

print("🤖 Uruchamiam Sztuczną Inteligencję (Wersja Pancerna z zapisem w locie)...\n")

plik_czyste = 'data/wiadomosci_orlen_CZYSTE.csv'
plik_ocenione = 'data/wiadomosci_orlen_Ocenione_AI.csv'

# Wczytujemy zeskrapowane artykuły
try:
    df_nowe = pd.read_csv(plik_czyste, encoding='utf-8-sig')
except FileNotFoundError:
    print("❌ Brak pliku z czystymi artykułami.")
    exit()

# Sprawdzamy, co już mamy ocenione
if os.path.exists(plik_ocenione):
    df_historia = pd.read_csv(plik_ocenione, encoding='utf-8-sig')
    ocenione_linki = df_historia['link'].tolist()
else:
    df_historia = pd.DataFrame()
    ocenione_linki = []

# Bierzemy TYLKO te artykuły, których jeszcze nie ocenialiśmy
df_do_oceny = df_nowe[~df_nowe['link'].isin(ocenione_linki)].copy()

if len(df_do_oceny) == 0:
    print("✅ Baza AI jest aktualna! Wszystkie artykuły zostały już ocenione.")
    exit()

print(f"⏳ Zostało do oceny: {len(df_do_oceny)} artykułów. Używamy stabilnego modelu 2.0...\n")

prompt_bazowy = """
Jesteś profesjonalnym analitykiem giełdowym sektora paliwowego. Przeczytaj poniższy artykuł o firmie Orlen.
Zrozum jego kontekst i oceń w skali od 0 do 10 (tylko liczby całkowite):
1. Poziom 'Paniki' (straty, problemy, awarie, spadki cen, afery, ryzyko inwestycyjne).
2. Poziom 'Sukcesu' (zyski, udane fuzje, zielona energia, rozwój, dobre prognozy).

Zwróć odpowiedź DOKŁADNIE w takim formacie i nic więcej:
Panika: [liczba], Sukces: [liczba]

Oto tekst do analizy:
"""

for index, row in df_do_oceny.iterrows():
    tekst = str(row['tytul']) + "\n" + str(row['tresc'])
    tekst = tekst[:3500] 
    probne_zapytanie = prompt_bazowy + tekst
    
    sukces = False
    
    while not sukces:
        try:
            # UŻYWAMY WERSJI 2.0 (Limit to 1500 zapytań dziennie!)
            response = client.models.generate_content(
                model='gemini-3.1-flash-lite-preview',
                contents=probne_zapytanie,
            )
            wynik = response.text.strip()
            
            panika_match = re.search(r'Panika.*?(\d+)', wynik, re.IGNORECASE)
            sukces_match = re.search(r'Sukces.*?(\d+)', wynik, re.IGNORECASE)
            
            czesc_panika = int(panika_match.group(1)) if panika_match else 0
            czesc_sukces = int(sukces_match.group(1)) if sukces_match else 0
            
            krotki_tytul = row['tytul'][:50].ljust(50) + "..."
            print(f"📰 {krotki_tytul} -> 🧠 P: {czesc_panika} | S: {czesc_sukces}")
            
            # --- ZAPISUJEMY W LOCIE ---
            nowy_wiersz = row.copy()
            nowy_wiersz['panika_ai'] = czesc_panika
            nowy_wiersz['sukces_ai'] = czesc_sukces
            
            # Dodajemy oceniony wiersz do historii i natychmiast zapisujemy na dysk
            df_historia = pd.concat([df_historia, pd.DataFrame([nowy_wiersz])], ignore_index=True)
            df_historia.to_csv(plik_ocenione, index=False, encoding='utf-8-sig')
            
            sukces = True 
            time.sleep(10) # Odczekanie przed kolejnym zapytaniem
            
        except Exception as e:
            blad_txt = str(e)
            #print(f"🔍 PEŁNY BŁĄD OD GOOGLE: {blad_txt}")
            if '429' in blad_txt or 'RESOURCE_EXHAUSTED' in blad_txt:
                print("🚦 Chwilowy limit częstotliwości (RPM). Czekam 45 sekund...")
                time.sleep(45)
            else:
                print(f"❌ Inny błąd: {blad_txt}")
                break

print("\n✅ Wszystkie zaległe artykuły zostały przetworzone!")