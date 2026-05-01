import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import requests
import time
from datetime import datetime, timedelta

# ==========================================
# 1. KONFIGURACJA STRONY
# ==========================================
st.set_page_config(page_title="Orlen AI Dashboard", page_icon="⛽", layout="wide")
st.title("⛽ Orlen AI - Interaktywny Panel Analityczny")
st.markdown("Monitoruj ceny hurtowe, prognozy Sztucznej Inteligencji i limity rządowe.")

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
# 3. BLOKADA AKTUALIZACJI (COOLDOWN 2H)
# ==========================================
mozna_aktualizowac = True
komunikat_blokady = ""

if os.path.exists('data/orlen_master_table.csv'):
    czas_modyfikacji = os.path.getmtime('data/orlen_master_table.csv')
    ostatnia_aktualizacja = datetime.fromtimestamp(czas_modyfikacji)
    czas_od_aktualizacji = datetime.now() - ostatnia_aktualizacja
    
    if czas_od_aktualizacji.total_seconds() < 3000:
        mozna_aktualizowac = False
        minuty_do_konca = int((3000 - czas_od_aktualizacji.total_seconds()))
        komunikat_blokady = f"Następna aktualizacja możliwa za {minuty_do_konca} minut."

# ==========================================
# 4. KARTY Z PODSUMOWANIEM I PRZYCISK AKTUALIZACJI
# ==========================================
col_tytul, col_przycisk = st.columns([3, 1])

with col_tytul:
    st.subheader("CENY PALIWA")
    if predykcje:
        st.caption(f"Ostatnia aktualizacja modelu: {predykcje.get('data_treningu', 'Brak daty')}")

with col_przycisk:
    st.markdown("<br>", unsafe_allow_html=True) 
    
    if st.button("🔄 Wymuś aktualizację bazy", type="primary", use_container_width=True, disabled=not mozna_aktualizowac):
        token = st.secrets.get("GITHUB_TOKEN")
        if not token:
            st.error("Brak GITHUB_TOKEN w ustawieniach Streamlit!")
        else:
            url = "https://api.github.com/repos/Majbor1/orlen_scraper/actions/workflows/strona_bot.yml/dispatches"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {token}"
            }
            data = {"ref": "main"}
            resp = requests.post(url, headers=headers, json=data)
            
            if resp.status_code == 204:
                status_placeholder = st.empty()
                for i in range(120):
                    kropki = "." * ((i % 3) + 1)
                    status_placeholder.info(f"Pobieranie najnowszych danych{kropki}")
                    time.sleep(3)
                
                st.cache_data.clear() 
                st.rerun()            
            else:
                st.error(f"❌ Błąd wysyłania: {resp.text}")
                
    if not mozna_aktualizowac:
        st.caption(komunikat_blokady)

if df.empty or predykcje is None:
    st.error("❌ Brak danych głównych. Uruchom bota!")
    st.stop()

# Generowanie kafelków z cenami
wyniki = predykcje['wyniki']
kolumny_kpi = st.columns(len(wyniki))
jutro_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

for (paliwo, dane), col in zip(wyniki.items(), kolumny_kpi):
    ostatni_wiersz = df[df['paliwo'] == paliwo].iloc[-1]
    cena_dzis_l = ostatni_wiersz['cena_dzis'] / 1000
    prognoza_l = dane['prognoza_na_jutro'] / 1000
    zmiana_l = prognoza_l - cena_dzis_l
    
    limit_val = None
    if not df_max.empty:
        p_lower = paliwo.lower()
        kolumna_max = 'cena_max_pb95' if '95' in p_lower else ('cena_max_pb98' if '98' in p_lower else 'cena_max_on')
        limit_row = df_max[df_max['data'] == jutro_str]
        if not limit_row.empty:
            val = limit_row.iloc[0].get(kolumna_max)
            if pd.notna(val):
                limit_val = val
    
    with col:
        if limit_val is not None:
            st.metric(
                label=f"🛡️ {paliwo.upper()} (Limit na jutro)",
                value=f"{limit_val:.2f} zł/l",
                delta=f"{zmiana_l:+.2f} zł/l (zmiana hurtowa)",
                delta_color="inverse" 
            )
            st.caption(f"Cena hurtowaurt dziś: **{cena_dzis_l:.2f} zł/l**")
            st.caption(f"Szacowana cena hurtowa jutro: **{prognoza_l:.2f} zł/l**")
        else:
            st.metric(
                label=f"🔮 {paliwo.upper()} (Hurt na jutro AI)",
                value=f"{prognoza_l:.2f} zł/l",
                delta=f"{zmiana_l:+.2f} zł/l (vs dziś)",
                delta_color="inverse"
            )
            st.caption(f"Cena hurtowa dziś: **{cena_dzis_l:.2f} zł/l**")

st.divider()

# ==========================================
# 5. SYMULATOR CEN DETALICZNYCH
# ==========================================
st.subheader("Interaktywny Kalkulator Stacji (Cena na pylonie)")

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
        ostatni_wiersz = df[df['paliwo'] == paliwo].iloc[-1]
        cena_hurt_l = ostatni_wiersz['cena_dzis'] / 1000
        marza = marza_on if 'on' in paliwo.lower() or 'diesel' in paliwo.lower() else marza_pb95
        
        pobrany_vat = ostatni_wiersz.get('vat', 8)
        if pd.isna(pobrany_vat): pobrany_vat = 8
        mnoznik_vat = 1 + (float(pobrany_vat) / 100)
        
        cena_netto = cena_hurt_l + KOSZTY_OPERACYJNE_NETTO + marza
        cena_brutto = cena_netto * mnoznik_vat
        
        limit_val = None
        if not df_max.empty:
            p_lower = paliwo.lower()
            kolumna_max = 'cena_max_pb95' if '95' in p_lower else ('cena_max_pb98' if '98' in p_lower else 'cena_max_on')
            limit_row = df_max[df_max['data'] == jutro_str]
            if not limit_row.empty:
                val = limit_row.iloc[0].get(kolumna_max)
                if pd.notna(val):
                    limit_val = val

        row_data = {
            "Paliwo": paliwo.upper(),
            "Hurt Netto (zł/l)": f"{cena_hurt_l:.2f}",
            "Twoja Marża Netto": f"{marza:.2f}",
            f"CENA NA PYLONIE ({int(pobrany_vat)}% VAT)": f"{cena_brutto:.2f} zł"
        }

        if limit_val is not None:
            roznica = limit_val - cena_brutto
            row_data["Limit Rządowy"] = f"{limit_val:.2f} zł"
            row_data["Zapas do limitu"] = f"{roznica:.2f} zł"

        wyniki_detaliczne.append(row_data)
    
    st.dataframe(wyniki_detaliczne, use_container_width=True, hide_index=True)

st.divider()

# ==========================================
# 6. INTERAKTYWNY WYKRES
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
# 7. BAZA ARTYKUŁÓW (WIDOK TABELI)
# ==========================================
st.divider()
st.subheader("📰 Baza Analizowanych Wiadomości")
st.markdown("Lista artykułów, na podstawie których AI analizowało nastroje rynkowe.")

if not df_news.empty:
    kolumny_do_pokazania = ['data', 'tytul', 'link']
    dostepne_kolumny = [c for c in kolumny_do_pokazania if c in df_news.columns]
    
    st.dataframe(
        df_news[dostepne_kolumny],
        use_container_width=True, 
        hide_index=True,          
        height=400,
        column_config={
            "data": st.column_config.TextColumn("Data publikacji"),
            "tytul": st.column_config.TextColumn("Tytuł artykułu"),
            "link": st.column_config.LinkColumn("Źródło (Otwórz artykuł)")
        }
    )
else:
    st.info("Brak artykułów w bazie ocen.")

# ==========================================
# 8. STOPKA (FOOTER)
# ==========================================
st.markdown("<br><br>", unsafe_allow_html=True) # Dodaje trochę pustego miejsca przed stopką
st.divider()
# Wstrzykujemy kod HTML z atrybutem unsafe_allow_html=True, aby Streamlit wyrenderował odpowiednie kolory i marginesy
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        <small>Author: <b>Marcin Majborski</b> | Wszelkie prawa zastrzeżone &copy; 2026</small>
    </div>
    """,
    unsafe_allow_html=True
)