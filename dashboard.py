import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import requests
import time
import math
import requests
import base64
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

# ==========================================
# 1. KONFIGURACJA STRONY I PAMIĘCI SESJI
# ==========================================
st.set_page_config(page_title="Orlen AI Dashboard", page_icon="⛽", layout="wide")
st.title("⛽ Orlen AI - Interaktywny Panel Analityczny")
st.markdown("Monitoruj szacowane ceny na stacjach, prognozy AI i limity rządowe.")

# Pamięć sesji dla animacji
if 'trwa_aktualizacja' not in st.session_state:
    st.session_state.trwa_aktualizacja = False

# Pamięć sesji dla czasu kliknięcia (Rozwiązanie naszego problemu)
if 'ostatnie_klikniecie' not in st.session_state:
    st.session_state.ostatnie_klikniecie = None

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
# 3. ZAAWANSOWANA BLOKADA AKTUALIZACJI (JSON + SESJA)
# ==========================================
mozna_aktualizowac = True
komunikat_blokady = ""
data_treningu_wyswietlana = "Brak daty"

# Zakładamy domyślnie, że od aktualizacji minęło mnóstwo czasu
sekundy_od_aktualizacji = 999999

# A. Odczytujemy czas z pliku JSON z modelu AI
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
    except Exception as e:
        data_treningu_wyswietlana = predykcje.get('data_treningu', 'Brak daty')

# B. Odczytujemy czas kliknięcia przycisku (jeśli strona nie zdążyła pobrać nowego pliku)
if st.session_state.ostatnie_klikniecie is not None:
    sekundy_od_kliku = (datetime.now() - st.session_state.ostatnie_klikniecie).total_seconds()
    # Jeśli kliknięto przycisk niedawno (np. 120 sek temu), nadpisujemy stary czas z JSONa
    if 0 <= sekundy_od_kliku < sekundy_od_aktualizacji:
        sekundy_od_aktualizacji = sekundy_od_kliku

# C. Ostateczna decyzja o zablokowaniu przycisku
if sekundy_od_aktualizacji < 600:
    mozna_aktualizowac = False
    minuty_do_konca = math.ceil((600 - sekundy_od_aktualizacji) / 60)
    komunikat_blokady = f"Następna aktualizacja możliwa za {minuty_do_konca} minut."

# ==========================================
# 4. KARTY Z PODSUMOWANIEM I PRZYCISK AKTUALIZACJI
# ==========================================
col_tytul, col_przycisk = st.columns([3, 1])

with col_tytul:
    st.subheader("🔮 Szacowane Ceny Detaliczne na JUTRO")
    if predykcje:
        st.caption(f"Ostatnia aktualizacja modelu: {data_treningu_wyswietlana}")

with col_przycisk:
    st.markdown("<br>", unsafe_allow_html=True) 
    
    if st.button("🔄 Wymuś aktualizację bazy", type="primary", use_container_width=True, disabled=not mozna_aktualizowac or st.session_state.trwa_aktualizacja):
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
                # ZAPISUJEMY CZAS KLIKNIĘCIA DO PAMIĘCI
                st.session_state.ostatnie_klikniecie = datetime.now()
                st.session_state.trwa_aktualizacja = True
                st.rerun()            
            else:
                st.error(f"❌ Błąd wysyłania: {resp.text}")
                
    if not mozna_aktualizowac and not st.session_state.trwa_aktualizacja:
        st.caption(komunikat_blokady)

if df.empty or predykcje is None:
    st.error("❌ Brak danych głównych. Uruchom bota!")
    st.stop()

# Puste pudełko na układ cen
pojemnik_na_ceny = st.empty()
st.divider()

# ==========================================
# 5. INTERAKTYWNY WYKRES
# ==========================================
st.subheader("📈 Analiza Trendu (Ostatnie 60 dni)")

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

# ==========================================
# 6. BAZA ARTYKUŁÓW (WIDOK TABELI)
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
# 9. FORMULARZ ZAPISU NA POWIADOMIENIA (GitHub API)
# ==========================================
st.divider()
st.subheader("🔔 Zapisz się na powiadomienia o cenach!")

with st.expander("🔒 Jak dbamy o Twoje bezpieczeństwo? (Szyfrowanie Danych)"):
    st.markdown("""
    **Twoje dane są u nas w 100% bezpieczne.**
    
    Zaszyfrowane dane to poufne informacje przekształcone w nieczytelny ciąg znaków, które można bezpiecznie przechowywać w bazie i odczytać tylko za pomocą unikalnego, tajnego klucza serwera.
    
    W praktyce oznacza to, że Twój klucz Pushover jest natychmiast szyfrowany zaawansowanym algorytmem kryptograficznym, zanim jeszcze trafi do naszej bazy danych. Nikt – włączając w to administratorów systemu – nie ma możliwości odczytania Twojego oryginalnego, surowego klucza.
    """)

with st.form("formularz_subskrypcji", clear_on_submit=True):
    nowy_klucz = st.text_input("Wklej swój Pushover User Key:", type="password") 
    przycisk_zapisu = st.form_submit_button("Zaszyfruj i zapisz mnie!", type="primary")

    if przycisk_zapisu:
        if len(nowy_klucz) >= 15:
            try:
                # 1. Pobranie kluczy systemowych
                klucz_szyfrujacy = st.secrets["ENCRYPTION_KEY"]
                admin_key = st.secrets["USER_KEY"] # Pobieramy Twój tajny klucz z env/secrets
                fernet = Fernet(klucz_szyfrujacy)
                
                # 2. Ustawienia API GitHuba
                github_token = st.secrets["GITHUB_TOKEN"]
                repozytorium = "Majbor1/orlen_scraper" 
                sciezka_pliku = "data/subskrybenci.txt"
                
                url_api = f"https://api.github.com/repos/{repozytorium}/contents/{sciezka_pliku}"
                naglowki = {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json"
                }

                # --- LOGIKA WERYFIKACJI ---
                
                # A. Sprawdzenie, czy to nie jest klucz Administratora
                if nowy_klucz == admin_key:
                    st.info("💡 Jesteś administratorem tego systemu. Twoje urządzenie jest już na liście głównej i nie musi się dodatkowo zapisywać!")
                
                else:
                    # B. Pobranie pliku z GitHuba i sprawdzenie duplikatów
                    odpowiedz_get = requests.get(url_api, headers=naglowki)
                    obecny_tekst = ""
                    sha_pliku = None
                    czy_klucz_juz_istnieje = False

                    if odpowiedz_get.status_code == 200:
                        dane_pliku = odpowiedz_get.json()
                        sha_pliku = dane_pliku['sha']
                        obecny_tekst = base64.b64decode(dane_pliku['content']).decode('utf-8')
                        
                        istniejace_linie = obecny_tekst.splitlines()
                        for linia in istniejace_linie:
                            if linia.strip():
                                try:
                                    odkodowany_z_bazy = fernet.decrypt(linia.encode()).decode()
                                    if odkodowany_z_bazy == nowy_klucz:
                                        czy_klucz_juz_istnieje = True
                                        break
                                except:
                                    pass

                    if czy_klucz_juz_istnieje:
                        st.warning("⚠️ Ten klucz jest już zapisany w naszej bazie!")
                    else:
                        # C. Zapis nowego klucza (skoro nie jest adminem i nie ma go w bazie)
                        zaszyfrowany_klucz = fernet.encrypt(nowy_klucz.encode()).decode()
                        nowy_tekst = obecny_tekst + zaszyfrowany_klucz + "\n"
                        
                        tekst_zakodowany = base64.b64encode(nowy_tekst.encode('utf-8')).decode('utf-8')
                        dane_do_wyslania = {
                            "message": "Strona: Dodano nowego subskrybenta",
                            "content": tekst_zakodowany,
                            "branch": "main"
                        }
                        if sha_pliku:
                            dane_do_wyslania["sha"] = sha_pliku
                            
                        odpowiedz_put = requests.put(url_api, headers=naglowki, json=dane_do_wyslania)
                        
                        if odpowiedz_put.status_code in [200, 201]:
                            st.success("🎉 Super! Twój klucz został zaszyfrowany i dopisany do listy powiadomień.")
                        else:
                            st.error(f"❌ Błąd zapisu: {odpowiedz_put.json().get('message')}")
                
            except KeyError as e:
                st.error(f"❌ Błąd konfiguracji: Brak klucza {e} w ustawieniach (Secrets)!")
            except Exception as e:
                st.error(f"❌ Wystąpił błąd: {e}")
        else:
            st.error("❌ Klucz jest za krótki. Sprawdź go ponownie.")

# ==========================================
# 8. MAGICZNA LOGIKA ŁADOWANIA ORAZ PANELE Z DECYZJAMI W STYLU POWIADOMIEŃ
# ==========================================
dzis_str = datetime.now().strftime('%Y-%m-%d')
jutro_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

if st.session_state.trwa_aktualizacja:
    for i in range(1, 121):
        kropki = ". " * ((i % 3) + 1)
        pojemnik_na_ceny.info(f"⏳ Pobieranie najnowszych danych z rynku: {i} sek {kropki}")
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
            # 1. Obliczenia Hurtowe
            ostatni_wiersz = df[df['paliwo'] == paliwo].iloc[-1]
            hurt_dzis_l = ostatni_wiersz['cena_dzis'] / 1000
            hurt_jutro_l = dane['prognoza_na_jutro'] / 1000
            
            # 2. Pobieranie VAT
            pobrany_vat = ostatni_wiersz.get('vat', 8)
            if pd.isna(pobrany_vat): pobrany_vat = 8
            mnoznik_vat = 1 + (float(pobrany_vat) / 100)
            
            # 3. Szacowany Detal
            detal_dzis = (hurt_dzis_l + KOSZTY_OPERACYJNE_NETTO + MARZA_NETTO) * mnoznik_vat
            detal_jutro = (hurt_jutro_l + KOSZTY_OPERACYJNE_NETTO + MARZA_NETTO) * mnoznik_vat
            
            # 4. Sprawdzanie limitów państwowych na dziś i na jutro
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
            
            # 5. Ustalenie Ceny Ostatecznej
            cena_ostateczna_dzis = min(detal_dzis, limit_dzis) if limit_dzis else detal_dzis
            cena_ostateczna_jutro = min(detal_jutro, limit_jutro) if limit_jutro else detal_jutro
            
            roznica = cena_ostateczna_jutro - cena_ostateczna_dzis
            
            # 6. Teksty zastępcze dla braku limitu
            tekst_limit_dzis = f"{limit_dzis:.2f} zł/l" if limit_dzis else "Brak"
            tekst_limit_jutro = f"{limit_jutro:.2f} zł/l" if limit_jutro else "Brak"
            
            # WYSWIETLANIE W KOLUMNIE
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