import pandas as pd
import re

plik_wejsciowy = 'data/wiadomosci_orlen_zestawienie.csv'
plik_wyjsciowy = 'data/wiadomosci_orlen_CZYSTE.csv'

try:
    df = pd.read_csv(plik_wejsciowy, encoding='utf-8-sig')
    print(f"Wczytano {len(df)} artykułów przed czyszczeniem.")
except FileNotFoundError:
    print(f"Nie znaleziono pliku {plik_wejsciowy}!")
    exit()

df['tekst_do_analizy'] = (df['tytul'] + " " + df['tresc']).fillna('').str.lower()

czarna_lista = [
    'sponsor', 'siatkówk', 'siatkarz', 'piłk', 'rajd', 'f1', 'formula 1',
    'robert kubica', 'wyścig', 'kibic', 'zmagania', 'turniej', 'zawodnik',
    'mistrzostw', 'olimpiad', 'medal', 'puchar', 'reprezentacj', 'sztafet'
]

pattern_czarny = '|'.join(czarna_lista)


maska_smieci = df['tekst_do_analizy'].str.contains(pattern_czarny, regex=True, na=False)

biala_lista = [
    'paliw', 'cen', 'ropa', 'baryłk', 'zysk', 'strat', 'prezes', 'zarząd',
    'marż', 'giełd', 'akcj', 'dywidend', 'podatek', 'inwestycj', 'fuzj',
    'lotos', 'pgnig', 'obajtek', 'hurt', 'detal'
]

pattern_bialy = '|'.join(biala_lista)

maska_biznes = df['tekst_do_analizy'].str.contains(pattern_bialy, regex=True, na=False)

df_czyste = df[~maska_smieci & maska_biznes].copy()

df_czyste = df_czyste.drop(columns=['tekst_do_analizy'])

ile_wycieto = len(df) - len(df_czyste)
print(f"\n Bezlitośnie wycięto: {ile_wycieto} artykułów (sport, sponsoring, brak biznesu).")
print(f"💎 Zostało: {len(df_czyste)} czystych, merytorycznych artykułów.")


df_czyste.to_csv(plik_wyjsciowy, index=False, encoding='utf-8-sig', quoting=1) 
print(f"\nZapisano czystą bazę do pliku: {plik_wyjsciowy}")