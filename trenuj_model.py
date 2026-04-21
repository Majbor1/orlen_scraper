import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Qt5Agg') 
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit 
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
# 2. GŁÓWNY PROCES TRENINGU MODELU (Z WALIDACJĄ CZASOWĄ)
# =======================================================
print("🧠 Trenuję modele z użyciem CECH OPÓŹNIONYCH oraz TimeSeriesSplit...\n")

try:
    df = pd.read_csv('data/orlen_master_table.csv')
except FileNotFoundError:
    print("❌ Nie znaleziono pliku! Upewnij się, że Tabela Mistrzowska jest w folderze 'data'.")
    exit()

df['data'] = pd.to_datetime(df['data'])
df = df.sort_values('data', ascending=True).reset_index(drop=True)

# -------------------------------------------------------
# Cechy opóźnione (historia cen wstecz - Lag Features)
# -------------------------------------------------------
df['cena_wczoraj'] = df.groupby('paliwo')['cena_dzis'].shift(1)
df['cena_3_dni_temu'] = df.groupby('paliwo')['cena_dzis'].shift(3)

# Definiujemy cechy używane do nauki
cechy = ['cena_dzis', 'cena_wczoraj', 'cena_3_dni_temu', 'szum_medialny', 'panika_ai', 'sukces_ai', 'ropa_brent_usd', 'usd_pln']

paliwa = df['paliwo'].unique()
plt.figure(figsize=(12, 10))

aktualne_wyniki_modelu = {}

for i, paliwo in enumerate(paliwa, 1):
    df_p_full = df[df['paliwo'] == paliwo].copy()
    
    # Przesunięta zmienna docelowa (cena, która będzie jutro)
    if 'cena_jutro' not in df_p_full.columns:
        df_p_full['cena_jutro'] = df_p_full['cena_dzis'].shift(-1)
        
    # Wyciągamy ostatni wiersz przed usunięciem NaN, bo on ma dzisiejsze cechy i posłuży do przewidzenia "jutra"
    ostatni_wiersz_cechy = df_p_full[cechy].iloc[-1:] 
    ostatnia_data = df_p_full['data'].iloc[-1]
    
    # Do nauki i testów odrzucamy wiersze bez historii oraz zupełnie ostatni dzień (bo nie znamy jeszcze jego "jutra")
    df_p = df_p_full.dropna(subset=['cena_jutro', 'cena_wczoraj', 'cena_3_dni_temu']).copy()
    df_p = df_p.reset_index(drop=True)
    
    # -------------------------------------------------------
    # Profesjonalna walidacja: TimeSeriesSplit (kroki w czasie)
    # -------------------------------------------------------
    tscv = TimeSeriesSplit(n_splits=5)
    bledy_z_krokow = []
    
    X = df_p[cechy]
    y = df_p['cena_jutro']
    daty_historyczne = df_p['data']
    
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    
    # Model uczy się krokowo idąc w przyszłość (5 etapów)
    for train_index, test_index in tscv.split(X):
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]
        
        model.fit(X_train, y_train)
        prognozy_testowe = model.predict(X_test)
        blad = mean_absolute_error(y_test, prognozy_testowe)
        bledy_z_krokow.append(blad)
        
    blad_sredni_tscv = np.mean(bledy_z_krokow)
    print(f"⛽ {paliwo}: Średni błąd MAE (z 5 testów czasowych) = {blad_sredni_tscv:.2f} PLN/m3")
    
    # =======================================================
    # FINAŁ: TRENUJEMY MODEL NA WSZYSTKIM I PRZEWIDUJEMY JUTRO
    # =======================================================
    # Uczymy model ostatecznie na całej znanej historii do wczoraj
    model.fit(X, y)
    
    data_jutro = ostatnia_data + timedelta(days=1)
    # Prognozujemy używając cech z dzisiaj
    prognoza_na_jutro = model.predict(ostatni_wiersz_cechy)[0]
    print(f"   🔮 PROGNOZA NA JUTRO ({data_jutro.strftime('%Y-%m-%d')}): {prognoza_na_jutro:.2f} PLN/m3")
    
    # Analiza wpływu poszczególnych cech (na zaktualizowanym, pełnym modelu)
    waznosc = model.feature_importances_
    wplyw_slownik = {}
    
    for c, w in zip(cechy, waznosc):
        wplyw = w * 100
        if wplyw > 0.1: wplyw_slownik[c] = round(wplyw, 1)
        if w > 0.01: print(f"   Wpływ '{c}': {wplyw:.1f}%")
    print("-" * 30)
    
    aktualne_wyniki_modelu[paliwo] = {
        "mae": round(blad_sredni_tscv, 2),
        "prognoza_na_jutro": round(prognoza_na_jutro, 2),
        "wplyw_cech": wplyw_slownik
    }
    
    # =======================================================
    # RYSOWANIE WYKRESU
    # =======================================================
    plt.subplot(len(paliwa), 1, i)
    
    # Ograniczymy wykres do ostatnich 60 dni, żeby było wyraźniej widać
    limit_dni = -60
    
    # Generujemy dopasowanie modelu dla celów wizualizacji trendu
    wszystkie_prognozy_historyczne = model.predict(X)
    
    plt.plot(daty_historyczne.iloc[limit_dni:], y.iloc[limit_dni:].values, label='Rzeczywistość', color='blue', marker='.')
    plt.plot(daty_historyczne.iloc[limit_dni:], wszystkie_prognozy_historyczne[limit_dni:], label='Dopasowanie Modelu', color='orange', linestyle='--', alpha=0.7)
    
    # Rysujemy prognozę na jutro
    ostatnia_znana_cena = y.iloc[-1]
    plt.plot([daty_historyczne.iloc[-1], data_jutro], [ostatnia_znana_cena, prognoza_na_jutro], 
             color='red', linestyle='-', marker='o', markersize=6, label='PROGNOZA NA JUTRO')
    
    plt.title(f'Predykcja dla {paliwo} (Ostatnie 60 dni + Jutro)', fontsize=12)
    plt.ylabel('Cena (PLN/m3)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Oś X
    daty_wykres = list(daty_historyczne.iloc[limit_dni:]) + [data_jutro]
    # Zmniejszamy gęstość etykiet na osi X, biorąc co 5 dzień, by się nie zlały
    daty_etykiety = daty_wykres[::5] 
    if data_jutro not in daty_etykiety:
        daty_etykiety.append(data_jutro)
        
    plt.xticks(daty_etykiety, [d.strftime('%Y-%m-%d') for d in daty_etykiety], rotation=45, ha='right', fontsize=9)

plt.tight_layout()

# Zapisanie JSON i Wykresów
zapisz_szczegoly_do_json(aktualne_wyniki_modelu)
dzis = datetime.now().strftime("%Y-%m-%d")
nazwa_wykresu = f'wykres_z_dnia_{dzis}.png'
output_dir = 'data/wykresy'
os.makedirs(output_dir, exist_ok=True)
plt.savefig(os.path.join(output_dir, f'{nazwa_wykresu}'), dpi=300)

print(f"\n📈 ZAPISANO WYKRESY: Otwórz '{nazwa_wykresu}' i zobacz trend!")
plt.show()