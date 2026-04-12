import pandas as pd
import re

print("🧹 Uruchamiam proces czyszczenia bazy danych...\n")

# 1. Wczytanie pełnej bazy
plik_wejsciowy = 'data/wiadomosci_orlen_zestawienie.csv'
plik_wyjsciowy = 'data/wiadomosci_orlen_CZYSTE.csv'

try:
    df = pd.read_csv(plik_wejsciowy, encoding='utf-8-sig')
    print(f"Wczytano {len(df)} artykułów przed czyszczeniem.")
except FileNotFoundError:
    print(f"❌ Nie znaleziono pliku {plik_wejsciowy}!")
    exit()

# Przygotowujemy tekst do analizy (małe litery, żeby łatwiej szukać)
# Używamy fillna(''), żeby skrypt nie zawiesił się na pustych artykułach
df['tekst_do_analizy'] = (df['tytul'] + " " + df['tresc']).fillna('').str.lower()

# =======================================================
# KROK 1: CZARNA LISTA (Wycinamy sport i sponsoring)
# =======================================================
# Dodaj tu więcej słów, jeśli zauważysz w logach inne "śmieci"
czarna_lista = [
    'sponsor', 'siatkówk', 'siatkarz', 'piłk', 'rajd', 'f1', 'formula 1',
    'robert kubica', 'wyścig', 'kibic', 'zmagania', 'turniej', 'zawodnik',
    'mistrzostw', 'olimpiad', 'medal', 'puchar', 'reprezentacj', 'sztafet'
]

# Tworzymy wyrażenie regularne, które znajdzie którekolwiek ze słów (słowo1|słowo2|słowo3...)
pattern_czarny = '|'.join(czarna_lista)

# Znajdujemy wiersze, które ZAWIERAJĄ słowa z czarnej listy (to nasze "śmieci")
maska_smieci = df['tekst_do_analizy'].str.contains(pattern_czarny, regex=True, na=False)

# =======================================================
# KROK 2: BIAŁA LISTA (Wymagamy kontekstu biznesowego)
# =======================================================
# Artykuł musi zawierać przynajmniej jedno z tych słów
biala_lista = [
    'paliw', 'cen', 'ropa', 'baryłk', 'zysk', 'strat', 'prezes', 'zarząd',
    'marż', 'giełd', 'akcj', 'dywidend', 'podatek', 'inwestycj', 'fuzj',
    'lotos', 'pgnig', 'obajtek', 'hurt', 'detal'
]

pattern_bialy = '|'.join(biala_lista)

# Znajdujemy wiersze, które ZAWIERAJĄ słowa z białej listy
maska_biznes = df['tekst_do_analizy'].str.contains(pattern_bialy, regex=True, na=False)


# =======================================================
# KROK 3: FILTROWANIE
# =======================================================
# Zostawiamy tylko te artykuły, które:
# NIE SĄ śmieciami (~maska_smieci) ORAZ MAJĄ kontekst biznesowy (maska_biznes)
df_czyste = df[~maska_smieci & maska_biznes].copy()

# Usuwamy kolumnę pomocniczą
df_czyste = df_czyste.drop(columns=['tekst_do_analizy'])

# =======================================================
# PODSUMOWANIE I ZAPIS
# =======================================================
ile_wycieto = len(df) - len(df_czyste)
print(f"\n✂️ Bezlitośnie wycięto: {ile_wycieto} artykułów (sport, sponsoring, brak biznesu).")
print(f"💎 Zostało: {len(df_czyste)} czystych, merytorycznych artykułów.")

# Zapisujemy wyczyszczoną bazę do nowego pliku
df_czyste.to_csv(plik_wyjsciowy, index=False, encoding='utf-8-sig', quoting=1) # quoting=1 to odpowiednik QUOTE_ALL
print(f"\n✅ Zapisano czystą bazę do pliku: {plik_wyjsciowy}")