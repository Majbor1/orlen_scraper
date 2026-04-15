import pandas as pd
import matplotlib
matplotlib.use('Qt5Agg') # <--- Mówimy: "Użyj profesjonalnego okienka Qt5 zamiast zepsutego Tkinter"
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from datetime import datetime
import os
import json

# =======================================================
# 1. FUNKCJA ZAPISUJĄCA WYNIKI DO JSON
# =======================================================
def zapisz_szczegoly_do_json(wyniki_slownik):
    plik_json = 'data/historia_treningow.json'
    
    nowy_wpis = {
        "data_treningu": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "wyniki": wyniki_slownik
    }
    
    historia = []
    if os.path.exists(plik_json):
        try:
            with open(plik_json, 'r', encoding='utf-8') as f:
                historia = json.load(f)
        except Exception as e:
            print(f"⚠️ Uwaga: Błąd odczytu {plik_json} ({e}). Tworzę nowy plik.")
            
    historia.insert(0, nowy_wpis) # Dodajemy najnowsze na górę
    
    with open(plik_json, 'w', encoding='utf-8') as f:
        json.dump(historia, f, indent=4, ensure_ascii=False)
        
    print(f"💾 Zapisano historię błędów MAE i wagi cech do pliku: {plik_json}")
# =======================================================

print("🧠 Trenuję modele na NOWYCH danych (Giełda + Oceny Sentymentu AI)...\n")

try:
    # Wczytujemy z nowego folderu data
    df = pd.read_csv('data/orlen_master_table.csv')
except FileNotFoundError:
    print("❌ Nie znaleziono pliku! Upewnij się, że Tabela Mistrzowska jest w folderze 'data'.")
    exit()

df['data'] = pd.to_datetime(df['data'])
df = df.sort_values('data', ascending=True).reset_index(drop=True)

# NOWE CECHY: Zamiast "wskaznik_paniki" mamy "panika_ai", dodaliśmy też giełdę!
cechy = ['cena_dzis', 'szum_medialny', 'panika_ai', 'sukces_ai', 'ropa_brent_usd', 'usd_pln']

paliwa = df['paliwo'].unique()
plt.figure(figsize=(12, 10))

# Tworzymy pusty słownik, który na końcu zrzucimy do JSON
aktualne_wyniki_modelu = {}

for i, paliwo in enumerate(paliwa, 1):
    df_p = df[df['paliwo'] == paliwo].copy()
    
    indeks_podzialu = int(len(df_p) * 0.8)
    
    X_trening = df_p[cechy].iloc[:indeks_podzialu]
    y_trening = df_p['cena_jutro'].iloc[:indeks_podzialu]
    
    X_test = df_p[cechy].iloc[indeks_podzialu:]
    y_test = df_p['cena_jutro'].iloc[indeks_podzialu:]
    daty_testowe = df_p['data'].iloc[indeks_podzialu:]
    
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_trening, y_trening)
    prognozy = model.predict(X_test)
    
    blad_sredni = mean_absolute_error(y_test, prognozy)
    print(f"⛽ {paliwo}: Średni błąd MAE = {blad_sredni:.2f} PLN/m3")
    
    # Podglądamy, na co model najbardziej zwracał uwagę (Feature Importance)
    waznosc = model.feature_importances_
    wplyw_slownik = {} # Słownik pomocniczy dla tego konkretnego paliwa
    
    for c, w in zip(cechy, waznosc):
        wplyw = w * 100
        # Zapisujemy do słownika wszystko co ma >0.1% wpływu
        if wplyw > 0.1:
            wplyw_slownik[c] = round(wplyw, 1)
        # Na ekranie pokazujemy tak jak chciałeś (powyżej 1%)
        if w > 0.01: 
            print(f"   Wpływ '{c}': {wplyw:.1f}%")
    print("-" * 30)
    
    # Pakujemy dane dla tego paliwa do głównego słownika json
    aktualne_wyniki_modelu[paliwo] = {
        "mae": round(blad_sredni, 2),
        "wplyw_cech": wplyw_slownik
    }
    
    plt.subplot(len(paliwa), 1, i)
    plt.plot(daty_testowe, y_test.values, label='Rzeczywistość', color='blue', marker='o')
    plt.plot(daty_testowe, prognozy, label='Model AI', color='orange', linestyle='--')
    plt.title(f'Predykcja dla {paliwo}', fontsize=12)
    plt.ylabel('Cena (PLN/m3)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # --- DODAJ TĘ LINIJKĘ: Wymusza pokazanie każdej daty i pochyla tekst o 45 stopni ---
    plt.xticks(daty_testowe, daty_testowe.dt.strftime('%Y-%m-%d'), rotation=45, ha='right', fontsize=9)

plt.tight_layout()

# Zrzut danych do JSON-a tuż przed rysowaniem obrazków
zapisz_szczegoly_do_json(aktualne_wyniki_modelu)

dzis = datetime.now().strftime("%Y-%m-%d")
nazwa_wykresu = f'wykres_z_dnia_{dzis}.png'
output_dir = 'data/wykresy'
os.makedirs(output_dir, exist_ok=True)
plt.savefig(os.path.join(output_dir, f'{nazwa_wykresu}'), dpi=300)

print(f"\n📈 ZAPISANO WYKRESY: Otwórz '{nazwa_wykresu}' i zobacz różnicę!")
plt.show() # Na samym końcu zostawiamy wyświetlanie