import scrapy
import json
import os
import csv
from datetime import datetime, timedelta

class HurtoweOrlenSpider(scrapy.Spider):
    name = "hurtowe_orlen"
    allowed_domains = ["tool.orlen.pl"] 
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    paliwa_id = [41,42,43]

    def __init__(self, *args, **kwargs):
        super(HurtoweOrlenSpider, self).__init__(*args, **kwargs)
        self.zebrane_dane = []

    def start_requests(self):
        dzisiaj = datetime.now()
        # Skrypt pobiera dane tylko z ostatnich 7 dni
        siedem_dni_temu = dzisiaj - timedelta(days=7)
        
        data_od = siedem_dni_temu.strftime('%Y-%m-%d')
        data_do = dzisiaj.strftime('%Y-%m-%d')

        for pid in self.paliwa_id:
            url = f"https://tool.orlen.pl/api/wholesalefuelprices/ByProduct?productId={pid}&from={data_od}&to={data_do}"
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        try:
            dane = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Nie udało się zdekodować JSON z linku: {response.url}")
            return

        if not dane:
            return

        for item in dane:
            nazwa_paliwa = item.get('productName', 'Nieznane_Paliwo')
            
            surowa_data = item.get('effectiveDate', '')
            czysta_data = surowa_data.split('T')[0] if 'T' in surowa_data else surowa_data

            self.zebrane_dane.append({
                'data': czysta_data,
                'paliwo': nazwa_paliwa,
                'cena_netto_pln_m3': item.get('value')
            })

    def closed(self, reason):
        import pandas as pd
        # Używamy datetime (masz już zaimportowane na górze pliku)
        nazwa_pliku = 'data/ceny_orlen_zestawienie.csv'
        
        # 1. Tworzymy DataFrame z nowo pobranych danych
        df_nowe = pd.DataFrame(self.zebrane_dane)
        if df_nowe.empty:
            self.logger.info("Brak nowych danych do zapisu.")
            return

        # 2. Wczytujemy starą bazę
        if os.path.exists(nazwa_pliku):
            df_stare = pd.read_csv(nazwa_pliku)
            df_all = pd.concat([df_nowe, df_stare])
        else:
            df_all = df_nowe

        # 3. Czyścimy i formatujemy
        df_all['data'] = pd.to_datetime(df_all['data'])
        df_all = df_all.drop_duplicates(subset=['data', 'paliwo'], keep='first')

        # ===============================================================
        # 4. UZupełniamy braki (Forward Fill) z wymuszonym kalendarzem
        # ===============================================================
        df_final_lista = []
        
        # ZMIANA: Ustalamy "twardy" koniec kalendarza na dzisiejszy dzień
        data_koniec = pd.Timestamp(datetime.now().date())
        
        for paliwo in df_all['paliwo'].unique():
            temp = df_all[df_all['paliwo'] == paliwo].set_index('data')
            
            # Tworzymy ciągły zakres dat od pierwszej znanej daty aż do DZISIAJ
            # Jeśli Orlen milczy od soboty, Pandas wygeneruje puste pola dla niedzieli i poniedziałku
            daty = pd.date_range(start=temp.index.min(), end=data_koniec, freq='D')
            
            # Wypełniamy luki starą ceną, wyciągamy datę z indeksu i naprawiamy kolumny
            temp = temp.reindex(daty).ffill().reset_index().rename(columns={'index': 'data'})
            temp['paliwo'] = paliwo
            df_final_lista.append(temp)

        # 5. Łączymy wszystkie paliwa, sortujemy od najnowszego i zapisujemy
        df_final = pd.concat(df_final_lista).sort_values('data', ascending=False)
        df_final['data'] = df_final['data'].dt.strftime('%Y-%m-%d')
        
        df_final.to_csv(nazwa_pliku, index=False)
        self.logger.info(f"✅ Baza paliw zaktualizowana i uzupełniona (ffill) aż do dnia dzisiejszego.")