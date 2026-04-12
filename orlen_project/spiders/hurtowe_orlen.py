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
        nazwa_pliku = 'data/ceny_orlen_zestawienie.csv'
        istniejace_klucze = set()

        # 1. Zbieramy klucze z już istniejącego pliku (żeby uniknąć duplikatów przy dopisywaniu)
        if os.path.isfile(nazwa_pliku):
            with open(nazwa_pliku, mode='r', encoding='utf-8') as plik:
                reader = csv.DictReader(plik)
                for row in reader:
                    istniejace_klucze.add((row['data'], row['paliwo']))

        # 2. Wybieramy TYLKO te dane, których jeszcze nie ma w starym pliku
        nowe_dane = []
        for d in self.zebrane_dane:
            klucz = (d['data'], d['paliwo'])
            if klucz not in istniejace_klucze:
                nowe_dane.append(d)
                # Zapobiega duplikatom w samej nowej pobranej paczce
                istniejace_klucze.add(klucz) 

        # 3. Jeśli mamy coś nowego, dopisujemy na sam dół pliku (mode='a')
        if nowe_dane:
            plik_istnieje = os.path.isfile(nazwa_pliku)
            with open(nazwa_pliku, mode='a', encoding='utf-8', newline='') as plik:
                writer = csv.DictWriter(plik, fieldnames=['data', 'paliwo', 'cena_netto_pln_m3'])
                
                # Jeśli plik w ogóle nie istniał, najpierw dajemy nagłówki
                if not plik_istnieje:
                    writer.writeheader()
                    
                writer.writerows(nowe_dane)
                
            self.logger.info(f"✅ Dopisano {len(nowe_dane)} nowych rekordów do bazy.")
        else:
            self.logger.info("ℹ️ Brak nowych cen. Baza jest aktualna.")