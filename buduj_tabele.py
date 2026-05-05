import pandas as pd
import numpy as np

print("🚀 Buduję Inteligentną Tabelę Mistrzowską (AI + Giełda + Paliwa)...")

try:
    df_ai = pd.read_csv('data/wiadomosci_orlen_Ocenione_AI.csv', encoding='utf-8-sig')
    df_gielda = pd.read_csv('data/dane_gieldowe.csv')
    df_ceny = pd.read_csv('data/ceny_orlen_zestawienie.csv')
except FileNotFoundError as e:
    print(f"❌ Brakuje pliku! Błąd: {e}")
    exit()

# 1. Konwersja na format daty (Datetime)
df_ai['data'] = pd.to_datetime(df_ai['data'])
df_gielda['data'] = pd.to_datetime(df_gielda['data'])
df_ceny['data'] = pd.to_datetime(df_ceny['data'])

# 2. Agregacja wiadomości
news_daily = df_ai.groupby('data').agg(
    szum_medialny=('link', 'count'),
    panika_ai=('panika_ai', 'mean'),
    sukces_ai=('sukces_ai', 'mean')
).reset_index()

df_ceny = df_ceny.rename(columns={'cena_netto_pln_m3': 'cena_dzis'})

# =================================================================
# NOWOŚĆ: Budowa pełnego kalendarza odpornego na weekendy i święta
# =================================================================

# Znajdujemy absolutnie najstarszą i najświeższą datę ze wszystkich naszych danych
min_date = df_ceny['data'].min()
max_date = max(df_ceny['data'].max(), df_ai['data'].max(), df_gielda['data'].max())

# Generujemy ciągłą listę dat bez dziur
all_dates = pd.date_range(start=min_date, end=max_date)
paliwa = df_ceny['paliwo'].unique()

# Tworzymy szkielet naszej nowej, idealnej tabeli (Każdy dzień przypisany do każdego paliwa)
idx = pd.MultiIndex.from_product([all_dates, paliwa], names=['data', 'paliwo'])
master_calendar = pd.DataFrame(index=idx).reset_index()

# Wstawiamy w ten szkielet nasze ceny hurtowe
master = pd.merge(master_calendar, df_ceny, on=['data', 'paliwo'], how='left')

# Wypełniamy puste miejsca po weekendach cenami z poprzedzającego piątku (funkcja ffill)
master = master.sort_values(['paliwo', 'data'])
master['cena_dzis'] = master.groupby('paliwo')['cena_dzis'].ffill()

if 'vat' in master.columns:
    master['vat'] = master.groupby('paliwo')['vat'].ffill()

# =================================================================
# 3. Łączenie pozostałych danych do naszego ciągłego kalendarza
# =================================================================
master = pd.merge(master, df_gielda, on='data', how='left')
master = pd.merge(master, news_daily, on='data', how='left')

# Wypełnianie braków: z giełdy kopiujemy z dnia poprzedniego, a tam, gdzie nie było newsów, wstawiamy zera
master = master.sort_values(['paliwo', 'data']).ffill()

master['szum_medialny'] = master['szum_medialny'].fillna(0)
master['panika_ai'] = master['panika_ai'].fillna(0)
master['sukces_ai'] = master['sukces_ai'].fillna(0)

# 4. Wyliczenie ceny na jutro (shift)
master['cena_jutro'] = master.groupby('paliwo')['cena_dzis'].shift(-1)

# Celowo nie używamy już funkcji dropna(), aby nasz ostatni, najnowszy dzień
# zawsze znalazł się w bazie i zasilił panel na Twojej stronie internetowej!

# 5. Ograniczenie do najstarszego newsa w bazie
najstarszy_news = df_ai['data'].min()
master = master[master['data'] >= najstarszy_news]

master.to_csv('data/orlen_master_table.csv', index=False, encoding='utf-8-sig')
print(f"✅ Sukces! Tabela Mistrzowska gotowa. Liczba rekordów: {len(master)}")