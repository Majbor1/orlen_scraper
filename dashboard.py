import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
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
        df_master['data'] = pd.to_datetime(df_master['data'])
    return df_master

@st.cache_data
def load_max_prices():
    df_max = pd.DataFrame()
    if os.path.exists('data/cena_max.csv'):
        df_max = pd.read_csv('data/cena_max.csv')
        df_max['data'] = pd.to_datetime(df_max['data'])
    return df_max

def load_predictions():
    if os.path.exists('data/historia_treningow.json'):
        with open('data/historia_treningow.json', 'r', encoding='utf-8') as f:
            historia = json.load(f)
            if len(historia) > 0:
                return historia[0]
    return None

df = load_data()
df_max = load_max_prices()
predykcje = load_predictions()

# ==========================================
# 3. ZABEZPIECZENIE
# ==========================================
if df.empty or predykcje is None:
    st.error("❌ Brak plików z danymi lub modelu AI! Upewnij się, że bot na GitHubie wykonał swoje zadanie.")
    st.stop()

# ==========================================
# 4. KARTY Z PODSUMOWANIEM (KPI) I PROGNOZĄ
# ==========================================
st.subheader("🔮 Prognozy modelu AI na JUTRO")
wyniki = predykcje['wyniki']
data_treningu = predykcje['data_treningu']
st.caption(f"Ostatnia aktualizacja modelu: {data_treningu}")

kolumny_kpi = st.columns(len(wyniki))
jutro_data = datetime.now() + timedelta(days=1)
jutro_str = jutro_data.strftime('%Y-%m-%d')

for (paliwo, dane), col in zip(wyniki.items(), kolumny_kpi):
    # Wyciągamy dzisiejszą cenę z pliku CSV (cena za litr)
    ostatni_wiersz = df[df['paliwo'] == paliwo].iloc[-1]
    cena_dzis_l = ostatni_wiersz['cena_dzis'] / 1000
    
    prognoza_l = dane['prognoza_na_jutro'] / 1000
    zmiana_l = prognoza_l - cena_dzis_l
    
    # Sprawdzanie limitów rządowych z Monitora Polskiego
    limit_info = ""
    if not df_max.empty:
        kolumna_max = None
        p_lower = paliwo.lower()
        if '95' in p_lower: kolumna_max = 'cena_max_pb95'
        elif '98' in p_lower: kolumna_max = 'cena_max_pb98'
        elif 'on' in p_lower or 'diesel' in p_lower: kolumna_max = 'cena_max_on'
        
        if kolumna_max:
            limit_row = df_max[df_max['data'] == jutro_str]
            if not limit_row.empty:
                val_max = limit_row.iloc[0][kolumna_max]
                if pd.notna(val_max):
                    limit_info = f" | 🛡️ Limit rządu: {val_max:.2f} zł/l"
    
    with col:
        st.metric(
            label=f"⛽ {paliwo.upper()}{limit_info}",
            value=f"{prognoza_l:.2f} zł/l",
            delta=f"{zmiana_l:.2f} zł/l (vs dziś)",
            delta_color="inverse" # Czerwony jak rośnie, Zielony jak maleje
        )

st.divider()

# ==========================================
# 5. SYMULATOR CEN DETALICZNYCH
# ==========================================
st.subheader("🧮 Interaktywny Kalkulator Stacji (Cena na pylonie)")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("**Ustaw marżę stacji (zł/litr)**")
    marza_pb95 = st.slider("Marża dla Pb95 i Pb98", min_value=0.0, max_value=0.50, value=0.15, step=0.01)
    marza_on = st.slider("Marża dla ON (Diesel)", min_value=0.0, max_value=0.50, value=0.15, step=0.01)
    st.info("Koszty operacyjne (logistyka, obsługa) są ustawione na 0.40 zł/l.")

with col2:
    KOSZTY_OPERACYJNE_NETTO = 0.40 
    wyniki_detaliczne = []
    
    for paliwo in df['paliwo'].unique():
        cena_hurt_l = df[df['paliwo'] == paliwo].iloc[-1]['cena_dzis'] / 1000
        marza = marza_on if 'on' in paliwo.lower() or 'diesel' in paliwo.lower() else marza_pb95
        
        cena_netto = cena_hurt_l + KOSZTY_OPERACYJNE_NETTO + (marza / 1.23)
        cena_brutto = round(cena_netto * 1.23, 2)
        
        wyniki_detaliczne.append({
            "Paliwo": paliwo.upper(),
            "Hurt (zł/l)": f"{cena_hurt_l:.2f}",
            "Twoja Marża": f"{marza:.2f}",
            "CENA NA PYLONIE": f"{cena_brutto:.2f} zł"
        })
    
    st.dataframe(wyniki_detaliczne, use_container_width=True, hide_index=True)

st.divider()

# ==========================================
# 6. INTERAKTYWNY WYKRES
# ==========================================
st.subheader("📈 Analiza Trendu (Ostatnie 60 dni)")

wybrane_paliwo = st.selectbox("Wybierz paliwo do wyświetlenia na wykresie:", df['paliwo'].unique())

df_wykres = df[df['paliwo'] == wybrane_paliwo].copy()
df_wykres = df_wykres.tail(60)

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
# 7. SENTYMENT AI
# ==========================================
with st.expander("🤖 Rozwiń, aby zobaczyć wpływ mediów i analizę sentymentu (Gemini AI)"):
    st.markdown("Poniższy wykres pokazuje nastroje w wiadomościach biznesowych (Panika vs Sukces), które model bierze pod uwagę przy prognozowaniu.")
    fig_ai = px.bar(
        df_wykres, x='data', y=['panika_ai', 'sukces_ai'], 
        barmode='group',
        title="Sentyment AI: Panika (czerwony) vs Sukces (zielony)",
        color_discrete_map={'panika_ai': '#ff4b4b', 'sukces_ai': '#09ab3b'}
    )
    st.plotly_chart(fig_ai, use_container_width=True)