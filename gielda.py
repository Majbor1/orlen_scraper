import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta

def pobierz_dane_gieldowe():
    nazwa_pliku = 'data/dane_gieldowe.csv'
    print("📈 Pobieram najnowsze dane giełdowe (Ropa Brent + USD/PLN)...")

    # 1. Ustalamy zakres: ostatnie 7 dni
    koniec = datetime.now()
    start = koniec - timedelta(days=7)
    
    # 2. Pobieramy dane z Yahoo Finance
    # BZ=F to ropa Brent, USDPLN=X to kurs dolara
    try:
        ropa = yf.download("BZ=F", start=start, end=koniec, interval="1d")
        dolar = yf.download("USDPLN=X", start=start, end=koniec, interval="1d")
        
        if ropa.empty or dolar.empty:
            print("⚠️ Brak nowych danych na giełdzie (może to weekend lub święto).")
            return
            
        # Przygotowujemy nowe dane
        nowe_dane = pd.DataFrame({
            'ropa_brent_usd': ropa['Close'].iloc[:, 0] if hasattr(ropa['Close'], 'columns') else ropa['Close'],
            'usd_pln': dolar['Close'].iloc[:, 0] if hasattr(dolar['Close'], 'columns') else dolar['Close']
        })
        nowe_dane.index = nowe_dane.index.date
        nowe_dane.index.name = 'data'
        nowe_dane = nowe_dane.reset_index()
        nowe_dane['data'] = nowe_dane['data'].astype(str)

    except Exception as e:
        print(f"❌ Błąd podczas pobierania z API: {e}")
        return

    # 3. Łączymy z historią
    if os.path.exists(nazwa_pliku):
        stara_baza = pd.read_csv(nazwa_pliku)
        stara_baza['data'] = stara_baza['data'].astype(str)
        
        # Łączymy i usuwamy duplikaty (zachowując nowsze wersje w razie zmian)
        df_final = pd.concat([nowe_dane, stara_baza]).drop_duplicates(subset=['data'], keep='first')
    else:
        df_final = nowe_dane

    # 4. Sortujemy: Najnowsze na górze (ascending=False)
    df_final['data'] = pd.to_datetime(df_final['data'])
    df_final = df_final.sort_values('data', ascending=False)
    
    # Zapisujemy
    os.makedirs('data', exist_ok=True)
    df_final.to_csv(nazwa_pliku, index=False)
    
    print(f"✅ Baza giełdowa zaktualizowana. Łącznie rekordów: {len(df_final)}")

if __name__ == "__main__":
    pobierz_dane_gieldowe()