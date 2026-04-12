import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os

print("🌍 Łączę się z Yahoo Finance...")


os.makedirs('data', exist_ok=True)
symbole = ["BZ=F", "PLN=X"]
dane = yf.download(symbole, start=(datetime.now() - timedelta(days=366)).strftime('%Y-%m-%d'), end=datetime.today().strftime('%Y-%m-%d'))

df = dane['Close'].reset_index()
df.columns = ['data', 'ropa_brent_usd', 'usd_pln']
df['data'] = pd.to_datetime(df['data']).dt.strftime('%Y-%m-%d')
df = df.ffill().dropna()

nazwa_pliku = "data/dane_gieldowe.csv"
df.to_csv(nazwa_pliku, index=False)

print(f"✅ Sukces! Pobrano historię giełdową. Zapisano jako {nazwa_pliku}")