import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta

def pobierz_dane_gieldowe():
    nazwa_pliku = 'data/dane_gieldowe.csv'

    koniec = datetime.now()
    start = koniec - timedelta(days=7)
    
    try:
        ropa = yf.download("BZ=F", start=start, end=koniec, interval="1d")
        dolar = yf.download("USDPLN=X", start=start, end=koniec, interval="1d")
        
        nowe_dane = pd.DataFrame({
            'ropa_brent_usd': ropa['Close'].iloc[:, 0] if hasattr(ropa['Close'], 'columns') else ropa['Close'],
            'usd_pln': dolar['Close'].iloc[:, 0] if hasattr(dolar['Close'], 'columns') else dolar['Close']
        })
        nowe_dane.index = pd.to_datetime(nowe_dane.index)
        
        pelny_zakres = pd.date_range(start=nowe_dane.index.min(), end=nowe_dane.index.max(), freq='D')
        nowe_dane = nowe_dane.reindex(pelny_zakres)
        
        nowe_dane = nowe_dane.ffill()
        
        nowe_dane = nowe_dane.reset_index().rename(columns={'index': 'data'})
        nowe_dane['data'] = nowe_dane['data'].dt.strftime('%Y-%m-%d')

    except Exception as e:
        print(f"❌ Błąd: {e}")
        return

    if os.path.exists(nazwa_pliku):
        stara_baza = pd.read_csv(nazwa_pliku)
        df_final = pd.concat([nowe_dane, stara_baza]).drop_duplicates(subset=['data'], keep='first')
    else:
        df_final = nowe_dane

    df_final = df_final.sort_values('data', ascending=False)
    df_final.to_csv(nazwa_pliku, index=False)
    print(f"Giełda zaktualizowana ")

if __name__ == "__main__":
    pobierz_dane_gieldowe()