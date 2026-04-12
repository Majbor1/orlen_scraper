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

df_ai['data'] = pd.to_datetime(df_ai['data'])
df_gielda['data'] = pd.to_datetime(df_gielda['data'])
df_ceny['data'] = pd.to_datetime(df_ceny['data'])

news_daily = df_ai.groupby('data').agg(
    szum_medialny=('link', 'count'),
    panika_ai=('panika_ai', 'mean'),
    sukces_ai=('sukces_ai', 'mean')
).reset_index()

df_ceny = df_ceny.rename(columns={'cena_netto_pln_m3': 'cena_dzis'})
df_ceny = df_ceny.sort_values(['paliwo', 'data'])
df_ceny['cena_jutro'] = df_ceny.groupby('paliwo')['cena_dzis'].shift(-1)

master = pd.merge(df_ceny, df_gielda, on='data', how='left')
master = pd.merge(master, news_daily, on='data', how='left')

master = master.sort_values(['paliwo', 'data']).ffill()

master['szum_medialny'] = master['szum_medialny'].fillna(0)
master['panika_ai'] = master['panika_ai'].fillna(0)
master['sukces_ai'] = master['sukces_ai'].fillna(0)

najstarszy_news = df_ai['data'].min()
master = master[master['data'] >= najstarszy_news]
master = master.dropna(subset=['cena_jutro'])

master.to_csv('data/orlen_master_table.csv', index=False, encoding='utf-8-sig')
print(f"✅ Sukces! Tabela Mistrzowska gotowa. Liczba rekordów: {len(master)}")