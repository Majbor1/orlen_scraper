import scrapy
import json
import os
import pandas as pd
from datetime import datetime, timedelta

class HurtoweOrlenSpider(scrapy.Spider):
    name = "hurtowe_orlen"
    allowed_domains = ["tool.orlen.pl"] 
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    paliwa_id = [41, 42, 43]
    plik_wynikowy = 'data/ceny_orlen_zestawienie.csv'

    def __init__(self, *args, **kwargs):
        super(HurtoweOrlenSpider, self).__init__(*args, **kwargs)
        self.zebrane_dane = []

    def wyznacz_date_poczatkowa(self):
        """Sprawdza plik CSV i zwraca ostatnią znaną datę. W razie braku, zwraca -7 dni."""
        if os.path.exists(self.plik_wynikowy):
            try:
                df = pd.read_csv(self.plik_wynikowy)
                if not df.empty and 'data' in df.columns:
                    ostatnia_data = pd.to_datetime(df['data']).max()
                    self.logger.info(f"📅 Znaleziono bazę! Pobieram dane od: {ostatnia_data.strftime('%Y-%m-%d')}")
                    return ostatnia_data.strftime('%Y-%m-%d')
            except Exception as e:
                self.logger.error(f"⚠️ Błąd odczytu daty z CSV: {e}. Zastosuję domyślne 7 dni.")
        
        # Domyślnie 7 dni wstecz, jeśli plik nie istnieje lub jest uszkodzony
        siedem_dni_temu = datetime.now() - timedelta(days=7)
        return siedem_dni_temu.strftime('%Y-%m-%d')

    def start_requests(self):
        dzisiaj = datetime.now().strftime('%Y-%m-%d')
        data_od = self.wyznacz_date_poczatkowa() # <--- TUTAJ UŻYWAMY TWOJEGO POMYSŁU

        for pid in self.paliwa_id:
            url = f"https://tool.orlen.pl/api/wholesalefuelprices/ByProduct?productId={pid}&from={data_od}&to={dzisiaj}"
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        try:
            dane = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Nie udało się zdekodować JSON: {response.url}")
            return

        if not dane:
            return

        for item in dane:
            surowa_data = item.get('effectiveDate', '')
            czysta_data = surowa_data.split('T')[0] if 'T' in surowa_data else surowa_data

            self.zebrane_dane.append({
                'data': czysta_data,
                'paliwo': item.get('productName', 'Nieznane_Paliwo'),
                'cena_netto_pln_m3': item.get('value')
            })

    def closed(self, reason):
        df_nowe = pd.DataFrame(self.zebrane_dane)
        if df_nowe.empty:
            self.logger.info("Brak nowych danych do zapisu.")
            return

        if os.path.exists(self.plik_wynikowy):
            df_stare = pd.read_csv(self.plik_wynikowy)
            df_all = pd.concat([df_nowe, df_stare])
        else:
            df_all = df_nowe

        # Czyszczenie i usuwanie duplikatów
        df_all['data'] = pd.to_datetime(df_all['data'])
        df_all = df_all.drop_duplicates(subset=['data', 'paliwo'], keep='last')

        # Wypełnianie brakujących dni (ffill)
        df_final_lista = []
        data_koniec = pd.Timestamp(datetime.now().date())
        
        for paliwo in df_all['paliwo'].unique():
            temp = df_all[df_all['paliwo'] == paliwo].set_index('data')
            daty = pd.date_range(start=temp.index.min(), end=data_koniec, freq='D')
            temp = temp.reindex(daty).ffill().reset_index().rename(columns={'index': 'data'})
            temp['paliwo'] = paliwo
            df_final_lista.append(temp)

        df_final = pd.concat(df_final_lista).sort_values('data', ascending=False)
        df_final['data'] = df_final['data'].dt.strftime('%Y-%m-%d')
        df_final.to_csv(self.plik_wynikowy, index=False)
        self.logger.info(f"✅ Baza paliw zaktualizowana i zapisana!")