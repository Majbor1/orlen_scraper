import scrapy
import json
import os
import csv  # <-- DODANY IMPORT do samodzielnego zapisu pliku
from datetime import datetime, timedelta

class HurtoweOrlenSpider(scrapy.Spider):
    name = "hurtowe_orlen"
    allowed_domains = ["tool.orlen.pl"] 
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    paliwa_id = [41,42,43]

    # Inicjalizujemy pustą listę, w której przechowamy wszystkie pobrane ceny
    def __init__(self, *args, **kwargs):
        super(HurtoweOrlenSpider, self).__init__(*args, **kwargs)
        self.zebrane_dane = []

    def start_requests(self):
        dzisiaj = datetime.now()
        # ZMIANA: Zawsze pobieramy dane z ostatnich 7 dni. 
        # Dzięki temu nawet jak nie włączysz komputera przez 3 dni, skrypt nadrobi zaległości!
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

            # Zamiast 'yield', DODAJEMY dane do naszej listy w pamięci
            self.zebrane_dane.append({
                'data': czysta_data,
                'paliwo': nazwa_paliwa,
                'cena_netto_pln_m3': item.get('value')
            })

    # Ta metoda uruchamia się automatycznie TYLKO RAZ, na samym końcu działania skrapera
    def closed(self, reason):
        nazwa_pliku = 'data/ceny_orlen_zestawienie.csv'
        wszystkie_dane = []
        
        # 1. Wczytujemy historię z OneDrive (jeśli plik istnieje)
        if os.path.isfile(nazwa_pliku):
            with open(nazwa_pliku, mode='r', encoding='utf-8') as plik:
                reader = csv.DictReader(plik)
                wszystkie_dane = list(reader)

        # 2. Dodajemy nowo pobrane dni
        wszystkie_dane.extend(self.zebrane_dane)

        # 3. MAGIA: Usuwamy duplikaty. 
        # Używamy kombinacji (data + paliwo) jako unikalnego klucza. Słownik sam nadpisze duplikaty!
        unikalne = {(d['data'], d['paliwo']): d for d in wszystkie_dane}
        
        # Sortujemy chronologicznie
        unikalne_lista = sorted(unikalne.values(), key=lambda x: x['data'], reverse=True)

        # 4. Zapisujemy zaktualizowany, czysty plik (mode='w', bo nadpisujemy całość od nowa)
        with open(nazwa_pliku, mode='w', encoding='utf-8', newline='') as plik:
            writer = csv.DictWriter(plik, fieldnames=['data', 'paliwo', 'cena_netto_pln_m3'])
            writer.writeheader()
            writer.writerows(unikalne_lista)
            
        self.logger.info(f"Zaktualizowano bazę. Plik ma teraz {len(unikalne_lista)} unikalnych rekordów.")