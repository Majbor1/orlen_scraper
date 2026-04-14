import pandas as pd
import matplotlib
matplotlib.use('Qt5Agg') # <--- Mówimy: "Użyj profesjonalnego okienka Qt5 zamiast zepsutego Tkinter"
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from datetime import datetime
import os

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
    for c, w in zip(cechy, waznosc):
        if w > 0.01: # Pokazujemy tylko te, które miały ponad 1% wpływu
            print(f"   Wpływ '{c}': {w*100:.1f}%")
    print("-" * 30)
    
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
dzis = datetime.now().strftime("%Y-%m-%d")
nazwa_wykresu = f'wykres_z_dnia_{dzis}.png'
output_dir = 'data/wykresy'
os.makedirs(output_dir, exist_ok=True)
plt.savefig(os.path.join(output_dir, f'{nazwa_wykresu}'), dpi=300)
plt.show()
print(f"\n📈 ZAPISANO WYKRESY: Otwórz '{nazwa_wykresu}' i zobacz różnicę!")