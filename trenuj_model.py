import pandas as pd
import matplotlib
matplotlib.use('Qt5Agg') # Używamy profesjonalnego okienka Qt5
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from datetime import datetime, timedelta
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
        
    print(f"💾 Zapisano historię błędów, wagi cech i PROGNOZY do pliku: {plik_json}")
# =======================================================

print("🧠 Trenuję modele na NOWYCH danych (Giełda + Oceny Sentymentu AI)...\n")

try:
    df = pd.read_csv('data/orlen_master_table.csv')
except FileNotFoundError:
    print("❌ Nie znaleziono pliku! Upewnij się, że Tabela Mistrzowska jest w folderze 'data'.")
    exit()

df['data'] = pd.to_datetime(df['data'])
df = df.sort_values('data', ascending=True).reset_index(drop=True)

# Definiujemy cechy używane do nauki
cechy = ['cena_dzis', 'szum_medialny', 'panika_ai', 'sukces_ai', 'ropa_brent_usd', 'usd_pln']

paliwa = df['paliwo'].unique()
plt.figure(figsize=(12, 10))

aktualne_wyniki_modelu = {}

for i, paliwo in enumerate(paliwa, 1):
    # Wyciągamy dane dla konkretnego paliwa
    df_p_full = df[df['paliwo'] == paliwo].copy()
    
    # Przygotowujemy przesuniętą zmienną docelową (cena, która będzie jutro)
    if 'cena_jutro' not in df_p_full.columns:
        df_p_full['cena_jutro'] = df_p_full['cena_dzis'].shift(-1)
        
    # Do treningu odrzucamy absolutnie ostatni wiersz, bo nie znamy jeszcze jego "jutra"
    df_p = df_p_full.dropna(subset=['cena_jutro']).copy()
    
    indeks_podzialu = int(len(df_p) * 0.8)
    
    # Zbiór treningowy
    X_trening = df_p[cechy].iloc[:indeks_podzialu]
    y_trening = df_p['cena_jutro'].iloc[:indeks_podzialu]
    
    # Zbiór testowy
    X_test = df_p[cechy].iloc[indeks_podzialu:]
    y_test = df_p['cena_jutro'].iloc[indeks_podzialu:]
    daty_testowe = df_p['data'].iloc[indeks_podzialu:]
    
    # Trenujemy model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_trening, y_trening)
    prognozy = model.predict(X_test)
    
    blad_sredni = mean_absolute_error(y_test, prognozy)
    print(f"⛽ {paliwo}: Średni błąd MAE = {blad_sredni:.2f} PLN/m3")
    
    # =======================================================
    # PREDYKCJA NA JUTRO
    # =======================================================
    # Bierzemy zupełnie ostatni znany wiersz z głównej bazy
    ostatni_wiersz_cechy = df_p_full[cechy].iloc[-1:] 
    ostatnia_data = daty_testowe.iloc[-1]
    data_jutro = ostatnia_data + timedelta(days=1)
    
    ostatnia_prognoza = prognozy[-1] # Punkt startowy dla czerwonej linii
    
    prognoza_na_jutro = model.predict(ostatni_wiersz_cechy)[0]
    print(f"   🔮 PROGNOZA NA JUTRO ({data_jutro.strftime('%Y-%m-%d')}): {prognoza_na_jutro:.2f} PLN/m3")
    
    # Analiza wpływu cech
    waznosc = model.feature_importances_
    wplyw_slownik = {}
    
    for c, w in zip(cechy, waznosc):
        wplyw = w * 100
        if wplyw > 0.1:
            wplyw_slownik[c] = round(wplyw, 1)
        if w > 0.01: 
            print(f"   Wpływ '{c}': {wplyw:.1f}%")
    print("-" * 30)
    
    # Zapisujemy do głównego słownika json
    aktualne_wyniki_modelu[paliwo] = {
        "mae": round(blad_sredni, 2),
        "prognoza_na_jutro": round(prognoza_na_jutro, 2),
        "wplyw_cech": wplyw_slownik
    }
    
    # =======================================================
    # RYSOWANIE WYKRESU
    # =======================================================
    plt.subplot(len(paliwa), 1, i)
    plt.plot(daty_testowe, y_test.values, label='Rzeczywistość', color='blue', marker='o')
    plt.plot(daty_testowe, prognozy, label='Model AI (Test)', color='orange', linestyle='--')
    
    # Rysowanie minimalistycznej prognozy na jutro (Z czerwonej kropki, od linii AI)
    plt.plot([ostatnia_data, data_jutro], [ostatnia_prognoza, prognoza_na_jutro], 
             color='red', linestyle=':', marker='o', markersize=6, label='PROGNOZA NA JUTRO')
    
    plt.title(f'Predykcja dla {paliwo}', fontsize=12)
    plt.ylabel('Cena (PLN/m3)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Formatowanie i wydłużanie osi X o nowy dzień
    wszystkie_daty = list(daty_testowe) + [data_jutro]
    plt.xticks(wszystkie_daty, [d.strftime('%Y-%m-%d') for d in wszystkie_daty], rotation=45, ha='right', fontsize=9)

plt.tight_layout()

# Zrzut danych do JSON-a 
zapisz_szczegoly_do_json(aktualne_wyniki_modelu)

# Zapisanie wykresu
dzis = datetime.now().strftime("%Y-%m-%d")
nazwa_wykresu = f'wykres_z_dnia_{dzis}.png'
output_dir = 'data/wykresy'
os.makedirs(output_dir, exist_ok=True)
plt.savefig(os.path.join(output_dir, f'{nazwa_wykresu}'), dpi=300)

print(f"\n📈 ZAPISANO WYKRESY: Otwórz '{nazwa_wykresu}' i zobacz trend!")
plt.show() # Wyświetla okno wykresu po zakończeniu