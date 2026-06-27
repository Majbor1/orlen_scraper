import pandas as pd
import os
import numpy as np

def uruchom_kalkulator(marza_pb95=0.15, marza_on=0.15):
    KOSZTY_OPERACYJNE_NETTO = 0.40 


    plik_hurt = 'data/orlen_master_table.csv' 
    plik_max = 'data/cena_max.csv'
    plik_wynik = 'data/ceny_na_stacjach.csv'

    if not os.path.exists(plik_hurt):
        print(f"Brak pliku z cenami hurtowymi!")
        return

    df = pd.read_csv(plik_hurt)
    df['data'] = pd.to_datetime(df['data'])

    df_max = None
    if os.path.exists(plik_max):
        df_max = pd.read_csv(plik_max)
        df_max['data'] = pd.to_datetime(df_max['data'])
        df = pd.merge(df, df_max, on='data', how='left')

    def przypisz_marze(rodzaj_paliwa):
        nazwa = str(rodzaj_paliwa).lower()
        if 'pb95' in nazwa: return marza_pb95
        elif 'onekodiesel' in nazwa or 'on' in nazwa: return marza_on
        else: return 0.15

    def wyciagnij_cene_max(row):
        if df_max is None: return None
        nazwa = str(row['paliwo']).lower()
        if 'pb95' in nazwa and 'cena_max_pb95' in row: return row['cena_max_pb95']
        elif ('onekodiesel' in nazwa or 'on' in nazwa) and 'cena_max_on' in row: return row['cena_max_on']
        elif 'pb98' in nazwa and 'cena_max_pb98' in row: return row['cena_max_pb98']
        return None

    df['marza_stacji'] = df['paliwo'].apply(przypisz_marze)
    df['minister_max'] = df.apply(wyciagnij_cene_max, axis=1)

    df['stawka_vat'] = np.where(df['minister_max'].notna(), 1.08, 1.23)
    
    df['pylon'] = (((df['cena_dzis'] / 1000) + KOSZTY_OPERACYJNE_NETTO + (df['marza_stacji']/1.23)) * df['stawka_vat'])
    df['pylon'] = df['pylon'].round(2)

    df_wynik = df[['data', 'paliwo', 'cena_dzis', 'stawka_vat', 'pylon', 'minister_max']].copy()
    #df_wynik = df_wynik.sort_values('data', ascending=False)
    df_wynik['data'] = df_wynik['data'].dt.strftime('%Y-%m-%d')
    df_wynik.to_csv(plik_wynik, index=False)
    
    print(f"Kalkulacja zakończona! Wyniki w: {plik_wynik}")
    
    ostatnia_data = df_wynik['data'].max() 
    dzisiejsze_ceny = df_wynik[df_wynik['data'] == ostatnia_data]
    print(f"\n--- PODGLĄD CEN NA DZIEŃ {ostatnia_data} ---")
    for index, row in dzisiejsze_ceny.iterrows():
        cena_max_str = f"(Max wg. rządu: {row['minister_max']} zł)" if pd.notna(row['minister_max']) else "(Brak limitu)"
        print(f" {row['paliwo'].ljust(12)}: {row['pylon']} PLN/l  {cena_max_str}")
    print("----------------------------------------------------------\n")

if __name__ == "__main__":
    uruchom_kalkulator()