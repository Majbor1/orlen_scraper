import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import requests
from datetime import datetime, timedelta

# ==========================================
# 1. KONFIGURACJA STRONY
# ==========================================
st.set_page_config(page_title="Orlen AI Dashboard", page_icon="⛽", layout="wide")
st.title("⛽ Orlen AI - Interaktywny Panel Analityczny")
st.markdown("Monitoruj ceny hurtowe, prognozy Sztucznej Inteligencji i symuluj ceny detaliczne na stacjach.")

# ==========================================
# 2. FUNKCJE WCZYTUJĄCE DANE
# ==========================================
@st.cache_data
def load_data():
    df_master = pd.DataFrame()
    if os.path.exists('data/orlen_master_table.csv'):
        df_master = pd.read_csv('data/orlen_master_table.csv')
        df_master['data'] = pd.to_datetime(df_master['data'], errors='coerce')
        df_master = df_master.dropna(subset=['data'])
    return df_master

@st.cache_data
def load_max_prices():
    df_max = pd.DataFrame()
    if os.path.exists('data/cena_max.csv'):
        df_max = pd.read_csv('data/cena_max.csv')
        df_max['data'] = pd.to_datetime(df_max['data'], errors='coerce')
        df_max = df_max.dropna(subset=['data'])
    return df_max

def load_predictions():
    if os.path.exists('data/historia_treningow.json'):
        try:
            with open('data/historia_treningow.json', 'r', encoding='utf-8') as f:
                historia = json.load(f)
                if isinstance(historia, list) and len(historia) > 0:
                    return historia[0]
        except json.JSONDecodeError:
            return None
    return None

@st.cache_data
def load_news():
    # Wczytujemy plik z OCENAMI z AI
    plik = 'data/wiadomosci_orlen_Ocenione_AI.csv'
    if os.path.exists(plik):
        df_news = pd.read_csv(plik)
        if 'data' in df_news.columns:
            df_news['data'] = pd.to_datetime(df_news['data'], errors='coerce')
            df_news = df_news.sort_values(by='data', ascending=False)
            df_news['data'] = df_news['data'].dt.strftime('%Y-%m-%d')
        return df_news
    return pd.DataFrame()

df = load_data()
df_max = load_max_prices()
predykcje = load_predictions()
df_news = load_news()

# ==========================================
# 3. KARTY Z PODSUMOWANIEM I PRZYCISK AKTUALIZACJI
# ==========================================
col_tytul, col_przycisk = st.columns([3, 1])

with col_tytul:
    st.subheader("🔮 Prognozy modelu AI na JUTRO")
    if predykcje:
        st.caption(f"Ostatnia aktualizacja modelu: {predykcje.get('data_treningu', 'Brak daty')}")

with col_przycisk:
    # MAGICZNY PRZYCISK DO ODPALANIA GITHUBA
    st.markdown("<br>", unsafe_allow_html=True) # Odstęp
    if st.button("🔄 Wymuś aktualizację bazy", type="primary", use_container_width=True):
        token = st.secrets.get("GITHUB_TOKEN")
        if not token:
            st.error("Brak GITHUB_TOKEN w ustawieniach Streamlit!")
        else:
            with st.spinner("Wysyłam sygnał do bota..."):
                url = "https://api.github.com/repos/Majbor1/orlen_scraper/actions/workflows/orlen_bot.yml/dispatches"
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "Authorization": f"token {token}"
                }
                data = {"ref": "main"}
                resp = requests.post(url, headers=headers, json=data)
                if resp.status_code == 204:
                    st.success("✅ Bot wystartował! Odśwież stronę za kilka minut.")
                else:
                    st.error(f"❌ Błąd: {resp.text}")

if df.empty or predykcje is None:
    st.error("❌ Brak danych głównych. Uruchom bota!")
    st.stop()

wyniki = predykcje['wyniki']
kolumny_kpi = st.columns(len(wyniki))
jutro_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

for (paliwo, dane), col in zip(wyniki.items(), kolumny_kpi):
    ostatni_wiersz = df[df['paliwo'] == paliwo].iloc[-1]
    cena_dzis_l = ostatni_wiersz['cena_dzis'] / 1000
    prognoza_l = dane['prognoza_na_jutro'] / 1000
    zmiana_l = prognoza_l - cena_dzis_l
    
    limit_info = ""
    if not df_max.empty:
        p_lower = paliwo.lower()
        kolumna_max = 'cena_max_pb95' if '95' in p_lower else ('cena_max_pb98' if '98' in p_lower else 'cena_max_on')
        limit_row = df_max[df_max['data'] == jutro_str]
        if not limit_row.empty and pd.notna(limit_row.iloc[0].get(kolumna_max)):
            limit_info = f" | 🛡️ Max: {limit_row.iloc[0][kolumna_max]:.2f} zł/l"
    
    with col:
        st.metric(
            label=f"⛽ {paliwo.upper()}{limit_info}",
            value=f"{prognoza_l:.2f} zł/l",
            delta=f"{zmiana_l:.2f} zł/l (vs dziś)",
            delta_color="inverse"
        )

st.divider()

# ==========================================
# 4. NAPRAWIONY SYMULATOR CEN DETALICZNYCH
# ==========================================
st.subheader("🧮 Interaktywny Kalkulator Stacji (Cena na pylonie)")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("**Ustaw marżę stacji (zł/litr netto)**")
    marza_pb95 = st.slider("Marża dla benzyny", min_value=0.0, max_value=0.50, value=0.15, step=0.01)
    marza_on = st.slider("Marża dla Diesla", min_value=0.0, max_value=0.50, value=0.15, step=0.01)
    st.info("Koszty operacyjne (utrzymanie stacji, prąd, pensje) ustawiono na stałe: 0.40 zł/l netto.")

with col2:
    KOSZTY_OPERACYJNE_NETTO = 0.40 
    wyniki_detaliczne = []
    
    for paliwo in df['paliwo'].unique():
        # Pobieramy najnowszą cenę dla danego paliwa
        cena_hurt_l = df[df['paliwo'] == paliwo]['cena_dzis'].iloc[-1] / 1000
        marza = marza_on if 'on' in paliwo.lower() or 'diesel' in paliwo.lower() else marza_pb95
        
        # Logika: (Hurt + Koszty + Twoja Marża) + 23% VAT
        cena_netto = cena_hurt_l + KOSZTY_OPERACYJNE_NETTO + marza
        cena_brutto = cena_netto * 1.23
        
        wyniki_detaliczne.append({
            "Paliwo": paliwo.upper(),
            "Hurt Netto (zł/l)": f"{cena_hurt_l:.2f}",
            "Twoja Marża Netto": f"{marza:.2f}",
            "CENA NA PYLONIE": f"{cena_brutto:.2f} zł"
        })
    
    st.dataframe(wyniki_detaliczne, use_container_width=True, hide_index=True)

st.divider()

# ==========================================
# 5. INTERAKTYWNY WYKRES
# ==========================================
st.subheader("📈 Analiza Trendu (Ostatnie 60 dni)")

wybrane_paliwo = st.selectbox("Wybierz paliwo do wyświetlenia na wykresie:", df['paliwo'].unique())

df_wykres = df[df['paliwo'] == wybrane_paliwo].copy().tail(60)

fig = px.line(
    df_wykres, x='data', y='cena_dzis', 
    title=f"Cena Hurtowa - {wybrane_paliwo.upper()} (zł/m3)",
    markers=True,
    labels={'cena_dzis': 'Cena (PLN/m3)', 'data': 'Data'}
)

ostatnia_data = df_wykres['data'].iloc[-1]
jutro_wykres = ostatnia_data + pd.Timedelta(days=1)
jutro_cena = wyniki[wybrane_paliwo]['prognoza_na_jutro']

fig.add_trace(go.Scatter(
    x=[ostatnia_data, jutro_wykres], 
    y=[df_wykres['cena_dzis'].iloc[-1], jutro_cena],
    mode='lines+markers',
    name='Prognoza AI',
    line=dict(color='red', width=3, dash='dot'),
    marker=dict(size=10)
))

st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 6. BAZA ARTYKUŁÓW Z OCENAMI AI
# ==========================================
st.divider()
st.subheader("📰 Baza Analizowanych Wiadomości")
st.markdown("Surowe artykuły przeczytane i ocenione przez model AI (chronologicznie).")

if not df_news.empty:
    # Wyrzucamy pełną treść artykułu z tabeli dla czytelności (jest za długa na widok tabeli)
    kolumny_do_pokazania = [c for c in df_news.columns if c != 'tresc']
    
    st.dataframe(
        df_news[kolumny_do_pokazania],
        use_container_width=True, 
        hide_index=True,          
        height=400,
        column_config={
            "link": st.column_config.LinkColumn("Otwórz artykuł"),
            "panika_ai": st.column_config.ProgressColumn("Panika", format="%d", min_value=0, max_value=10),
            "sukces_ai": st.column_config.ProgressColumn("Sukces", format="%d", min_value=0, max_value=10)
        }
    )
else:
    st.info("Brak artykułów w bazie ocen.")