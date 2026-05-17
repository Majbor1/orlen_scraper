import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import requests
import time
import math
import base64
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

st.set_page_config(page_title="Orlen AI Dashboard", page_icon="⛽", layout="wide")
st.title("Moniotr cen paliw")
st.markdown("Monitoruj szacowane ceny na stacjach, prognozy AI i limity rządowe.")

if 'trwa_aktualizacja' not in st.session_state:
    st.session_state.trwa_aktualizacja = False

if 'ostatnie_klikniecie' not in st.session_state:
    st.session_state.ostatnie_klikniecie = None

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

mozna_aktualizowac = True
komunikat_blokady = ""
data_treningu_wyswietlana = "Brak daty"
sekundy_od_aktualizacji = 999999

if predykcje and 'data_treningu' in predykcje:
    try:
        czas_oryginalny = pd.to_datetime(predykcje['data_treningu'])
        if czas_oryginalny.tzinfo is None:
            czas_oryginalny = czas_oryginalny.tz_localize('UTC')
            
        czas_polski = czas_oryginalny.tz_convert('Europe/Warsaw')
        data_treningu_wyswietlana = czas_polski.strftime("%Y-%m-%d %H:%M:%S")
        
        aktualny_czas_polski = pd.Timestamp.now(tz='Europe/Warsaw')
        sekundy_od_jsona = (aktualny_czas_polski - czas_polski).total_seconds()
        
        if sekundy_od_jsona >= 0:
            sekundy_od_aktualizacji = sekundy_od_jsona
    except Exception:
        data_treningu_wyswietlana = predykcje.get('data_treningu', 'Brak daty')

if st.session_state.ostatnie_klikniecie is not None:
    sekundy_od_kliku = (datetime.now() - st.session_state.ostatnie_klikniecie).total_seconds()
    if 0 <= sekundy_od_kliku < sekundy_od_aktualizacji:
        sekundy_od_aktualizacji = sekundy_od_kliku

if sekundy_od_aktualizacji < 600:
    mozna_aktualizowac = False
    minuty_do_konca = math.ceil((600 - sekundy_od_aktualizacji) / 60)
    komunikat_blokady = f"Następna aktualizacja możliwa za {minuty_do_konca} minut."

col_tytul, col_przycisk = st.columns([3, 1])

with col_tytul:
    st.subheader("Szacowane Ceny Detaliczne na JUTRO")
    if predykcje:
        st.caption(f"Ostatnia aktualizacja modelu: {data_treningu_wyswietlana}")

with col_przycisk:
    st.markdown("<br>", unsafe_allow_html=True) 
    
    if st.button("Wymuś aktualizację bazy", type="primary", use_container_width=True, disabled=not mozna_aktualizowac or st.session_state.trwa_aktualizacja):
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
                st.session_state.ostatnie_klikniecie = datetime.now()
                st.session_state.trwa_aktualizacja = True
                st.rerun()            
            else:
                st.error(f"❌ Błąd wysyłania: {resp.text}")
                
    if not mozna_aktualizowac and not st.session_state.trwa_aktualizacja:
        st.caption(komunikat_blokady)

if df.empty or predykcje is None:
    st.error("Brak danych głównych. Uruchom bota!")
    st.stop()

pojemnik_na_ceny = st.empty()
st.divider()

st.subheader("Analiza Trendu (Ostatnie 60 dni)")

wybrane_paliwo = st.selectbox("Wybierz paliwo do wyświetlenia na wykresie:", df['paliwo'].unique())
wyniki = predykcje['wyniki']
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

st.divider()
st.subheader("Baza Analizowanych Wiadomości")
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

st.divider()
tab1, tab2 = st.tabs(["Zapisz się", "Usuń subskrypcję"])

with tab1:
    st.subheader("Zapisz się na powiadomienia")
    with st.form("form_zapis", clear_on_submit=True):
        nowy_nick = st.text_input("Login:")
        nowy_klucz = st.text_input("Klucz Pushover User Key:", type="password")
        submit_zapis = st.form_submit_button("Zaszyfruj i zapisz mnie!")

    if submit_zapis:
        if len(nowy_nick) > 2 and len(nowy_klucz) >= 15:
            try:
                klucz_szyfrujacy = st.secrets["ENCRYPTION_KEY"]
                admin_key = st.secrets.get("USER_KEY", "")
                fernet = Fernet(klucz_szyfrujacy)
                
                if nowy_klucz == admin_key:
                    st.info("Jesteś już zapisany!")
                else:
                    github_token = st.secrets["GITHUB_TOKEN"]
                    repo = "Majbor1/orlen_scraper"
                    path = "data/subskrybenci.txt"
                    url = f"https://api.github.com/repos/{repo}/contents/{path}"
                    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}

                    res_get = requests.get(url, headers=headers)
                    obecny_tekst = ""
                    sha = None
                    duplikat = False

                    if res_get.status_code == 200:
                        data = res_get.json()
                        sha = data['sha']
                        obecny_tekst = base64.b64decode(data['content']).decode('utf-8')
                        
                        for linia in obecny_tekst.splitlines():
                            try:
                                dec = fernet.decrypt(linia.encode()).decode()
                                if ":" in dec and dec.split(":")[1] == nowy_klucz:
                                    duplikat = True
                                    break
                            except: pass

                    if duplikat:
                        st.warning("Ten klucz jest już w bazie!")
                    else:
                        format_zapisu = f"{nowy_nick}:{nowy_klucz}"
                        zaszyfrowany = fernet.encrypt(format_zapisu.encode()).decode()
                        nowy_kontent = obecny_tekst + zaszyfrowany + "\n"
                        
                        payload = {
                            "message": f"Dodano subskrybenta: {nowy_nick}",
                            "content": base64.b64encode(nowy_kontent.encode()).decode(),
                            "branch": "main"
                        }
                        if sha: payload["sha"] = sha
                            
                        res_put = requests.put(url, headers=headers, json=payload)
                        if res_put.status_code in [200, 201]:
                            st.success(f"🎉 Gotowe {nowy_nick}! Zostałeś dopisany do bazy.")
                        else:
                            st.error(f"Błąd GitHuba: {res_put.json().get('message')}")
            except Exception as e: st.error(f"Błąd: {e}")
        else: st.warning("Uzupełnij poprawnie oba pola!")

with tab2:
    st.subheader("Usuń swoją subskrypcję")
    with st.form("form_usun", clear_on_submit=True):
        usun_nick = st.text_input("Twój Nick:")
        usun_klucz = st.text_input("Twój Klucz Pushover:", type="password")
        submit_usun = st.form_submit_button("Usuń mnie z bazy", type="secondary")

    if submit_usun:
        try:
            klucz_szyfrujacy = st.secrets["ENCRYPTION_KEY"]
            fernet = Fernet(klucz_szyfrujacy)
            github_token = st.secrets["GITHUB_TOKEN"]
            repo = "Majbor1/orlen_scraper"
            path = "data/subskrybenci.txt"
            url = f"https://api.github.com/repos/{repo}/contents/{path}"
            headers = {"Authorization": f"token {github_token}"}

            res_get = requests.get(url, headers=headers)
            if res_get.status_code == 200:
                data = res_get.json()
                sha = data['sha']
                linie = base64.b64decode(data['content']).decode('utf-8').splitlines()
                
                nowe_linie = []
                znaleziono = False
                szukana_para = f"{usun_nick}:{usun_klucz}"

                for linia in linie:
                    if not linia.strip(): continue
                    try:
                        dec = fernet.decrypt(linia.encode()).decode()
                        if dec == szukana_para:
                            znaleziono = True
                        else:
                            nowe_linie.append(linia)
                    except: nowe_linie.append(linia)

                if znaleziono:
                    nowy_kontent = "\n".join(nowe_linie) + "\n" if nowe_linie else ""
                    payload = {
                        "message": f"Usunięto subskrybenta: {usun_nick}",
                        "content": base64.b64encode(nowy_kontent.encode()).decode(),
                        "sha": sha,
                        "branch": "main"
                    }
                    requests.put(url, headers=headers, json=payload)
                    st.success(f"Subskrypcja dla '{usun_nick}' została usunięta.")
                else:
                    st.error("Nie znaleziono takiej pary Nick:Klucz w bazie.")
            else:
                st.error("Błąd połączenia z bazą.")
        except Exception as e: st.error(f"Błąd: {e}")

dzis_str = datetime.now().strftime('%Y-%m-%d')
jutro_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

if st.session_state.trwa_aktualizacja:
    for i in range(1, 121):
        kropki = ". " * ((i % 3) + 1)
        pojemnik_na_ceny.info(f"Pobieranie najnowszych danych z rynku: {i} sek {kropki}")
        time.sleep(1) 
    
    st.session_state.trwa_aktualizacja = False
    st.cache_data.clear()
    st.rerun()
else:
    with pojemnik_na_ceny.container():
        kolumny_kpi = st.columns(len(wyniki))
        
        KOSZTY_OPERACYJNE_NETTO = 0.40
        MARZA_NETTO = 0.20
        
        for (paliwo, dane), col in zip(wyniki.items(), kolumny_kpi):
            ostatni_wiersz = df[df['paliwo'] == paliwo].iloc[-1]
            hurt_dzis_l = ostatni_wiersz['cena_dzis'] / 1000
            hurt_jutro_l = dane['prognoza_na_jutro'] / 1000
            
            pobrany_vat = ostatni_wiersz.get('vat', 8)
            if pd.isna(pobrany_vat): pobrany_vat = 8
            mnoznik_vat = 1 + (float(pobrany_vat) / 100)
            
            detal_dzis = (hurt_dzis_l + KOSZTY_OPERACYJNE_NETTO + MARZA_NETTO) * mnoznik_vat
            detal_jutro = (hurt_jutro_l + KOSZTY_OPERACYJNE_NETTO + MARZA_NETTO) * mnoznik_vat
            
            limit_dzis = None
            limit_jutro = None
            
            if not df_max.empty:
                p_lower = paliwo.lower()
                kolumna_max = 'cena_max_pb95' if '95' in p_lower else ('cena_max_pb98' if '98' in p_lower else 'cena_max_on')
                
                row_dzis = df_max[df_max['data'] == dzis_str]
                if not row_dzis.empty:
                    val = row_dzis.iloc[0].get(kolumna_max)
                    if pd.notna(val): limit_dzis = val
                        
                row_jutro = df_max[df_max['data'] == jutro_str]
                if not row_jutro.empty:
                    val = row_jutro.iloc[0].get(kolumna_max)
                    if pd.notna(val): limit_jutro = val
            
            cena_ostateczna_dzis = min(detal_dzis, limit_dzis) if limit_dzis else detal_dzis
            cena_ostateczna_jutro = min(detal_jutro, limit_jutro) if limit_jutro else detal_jutro
            
            roznica = cena_ostateczna_jutro - cena_ostateczna_dzis
            
            tekst_limit_dzis = f"{limit_dzis:.2f} zł/l" if limit_dzis else "Brak"
            tekst_limit_jutro = f"{limit_jutro:.2f} zł/l" if limit_jutro else "Brak"
            
            with col:
                st.markdown(f"### ⛽ {paliwo.upper()}")
                
                if roznica > 0.02:
                    st.error(f"**👉 DECYZJA:** 🔴 TANKUJ DZIŚ! (Jutro drożej o {roznica:.2f} zł/l)")
                elif roznica < -0.02:
                    st.success(f"**👉 DECYZJA:** 🟢 CZEKAJ! (Jutro taniej o {abs(roznica):.2f} zł/l)")
                else:
                    st.warning(f"**👉 DECYZJA:** 🟡 BEZ ZMIAN (Różnica: {roznica:+.2f} zł/l)")
                
                st.markdown(f"""
                ** Cena maksymalna:**
                * **Dziś ({dzis_str}):** {tekst_limit_dzis}
                * **Jutro ({jutro_str}):** {tekst_limit_jutro}

                **Cena hurtowa (Orlen):**
                * **Dziś:** {hurt_dzis_l:.2f} zł/l
                * **Jutro (AI estyma):** {hurt_jutro_l:.2f} zł/l

                ** Szacowana cena detaliczna (Z VAT {int(pobrany_vat)}%):**
                * **Dziś:** {detal_dzis:.2f} zł/l
                * **Jutro:** {detal_jutro:.2f} zł/l
                """)