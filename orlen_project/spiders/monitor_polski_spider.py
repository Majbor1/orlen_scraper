import scrapy
from scrapy.exceptions import CloseSpider # <--- Dodajemy "Hamulec awaryjny" ze Scrapy
from scrapy_playwright.page import PageMethod
import pdfplumber
import io
import re
import os
import csv
from datetime import datetime, timedelta
import pandas as pd

class CenaMaxMpSpider(scrapy.Spider):
    name = "cena_max_mp"
    plik_csv = 'data/cena_max.csv'
    
    def __init__(self, *args, **kwargs):
        super(CenaMaxMpSpider, self).__init__(*args, **kwargs)
        self.zapisane_daty = set()
        
        if os.path.isfile(self.plik_csv):
            try:
                with open(self.plik_csv, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if row and row[0] != 'data':
                            self.zapisane_daty.add(row[0])
                self.logger.info(f"Startuję. W pamięci mam już {len(self.zapisane_daty)} zarchiwizowanych dat.")
            except Exception as e:
                self.logger.error(f"Błąd odczytu pliku z historią: {e}")

    def start_requests(self):
        url = "https://monitorpolski.gov.pl/szukaj?pSize=50&pNumber=1&sKey=year&title=w+sprawie+maksymalnej+ceny+paliw+ciek%C5%82ych+na+stacji+paliw&text=#list" 
        
        yield scrapy.Request(
            url,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "table"), 
                ],
            },
            callback=self.parse_lista
        )

    async def parse_lista(self, response):
        page = response.meta["playwright_page"]
        self.logger.info("Skanuję tabelę w poszukiwaniu dokumentów...")
        
        xpath_pdf = "//tr[td[a[contains(text(), 'maksymalnej ceny paliw')]]]//a[img[contains(@src, 'file_pdf')]]/@href"
        linki_pdf = response.xpath(xpath_pdf).getall()
        await page.close()

        if linki_pdf:
            self.logger.info(f"Znalazłem {len(linki_pdf)} linków. Zaczynam sprawdzanie...")
            
            # Wymuszamy kolejność! Priority sprawia, że pobierze najpierw dokument z samej góry
            for idx, link in enumerate(linki_pdf):
                pelny_link = response.urljoin(link)
                yield scrapy.Request(pelny_link, callback=self.parse_pdf, priority=100-idx)
        else:
            self.logger.error("Brak wyników na stronie.")

    def parse_pdf(self, response):
        if b"%PDF" not in response.body[:5]: return

        pdf_stream = io.BytesIO(response.body)
        pelny_tekst = ""
        
        try:
            with pdfplumber.open(pdf_stream) as pdf:
                for strona in pdf.pages:
                    tekst = strona.extract_text()
                    if tekst: pelny_tekst += tekst + "\n"
        except Exception:
            return

        wzor_95 = re.search(r'bezołowiowej\s*95.*?powiększona o podatek.*?wynosi\s*(\d+[,.]\d+)', pelny_tekst, re.IGNORECASE | re.DOTALL)
        wzor_98 = re.search(r'bezołowiowej\s*98.*?powiększona o podatek.*?wynosi\s*(\d+[,.]\d+)', pelny_tekst, re.IGNORECASE | re.DOTALL)
        wzor_on = re.search(r'oleju\s*napędowego.*?powiększona o podatek.*?wynosi\s*(\d+[,.]\d+)', pelny_tekst, re.IGNORECASE | re.DOTALL)

        cena_95 = float(wzor_95.group(1).replace(',', '.')) if wzor_95 else None
        cena_98 = float(wzor_98.group(1).replace(',', '.')) if wzor_98 else None
        cena_on = float(wzor_on.group(1).replace(',', '.')) if wzor_on else None

        if not (cena_95 or cena_98 or cena_on): return

        miesiace = {'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4, 'maja': 5, 'czerwca': 6, 'lipca': 7, 'sierpnia': 8, 'września': 9, 'października': 10, 'listopada': 11, 'grudnia': 12}
        wzor_daty = re.search(r'dnia\s+(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})\s*r', pelny_tekst, re.IGNORECASE)
        
        if wzor_daty:
            dzien, miesiac_str, rok = int(wzor_daty.group(1)), wzor_daty.group(2).lower(), int(wzor_daty.group(3))
            try:
                data_obwieszczenia = datetime(rok, miesiace.get(miesiac_str, datetime.now().month), dzien)
            except ValueError:
                data_obwieszczenia = datetime.now()
        else:
            data_obwieszczenia = datetime.now()

        data_wejscia = (data_obwieszczenia + timedelta(days=1)).strftime("%Y-%m-%d")

        if data_wejscia in self.zapisane_daty:
            self.logger.info(f"Znalazłem zarchiwizowaną datę ({data_wejscia}). PRZERYWAM pobieranie starszych plików!")
            raise CloseSpider(reason='Baza aktualna')

        plik_jest_pusty = not os.path.isfile(self.plik_csv) or os.path.getsize(self.plik_csv) == 0
        
        with open(self.plik_csv, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            if plik_jest_pusty: writer.writerow(['data', 'cena_max_pb95', 'cena_max_pb98', 'cena_max_on'])
            writer.writerow([data_wejscia, cena_95, cena_98, cena_on])

        self.zapisane_daty.add(data_wejscia)
        self.logger.info(f"ZAPISANO NOWĄ CENĘ MAX: {data_wejscia}")

    def closed(self, reason):
        self.logger.info(f"🛠️ Pająk zakończył pracę (Powód: {reason}). Odpalam moduł kalendarza...")
        
        if not os.path.exists(self.plik_csv):
            os._exit(0)

        try:
            df = pd.read_csv(self.plik_csv)
            if df.empty: os._exit(0)
            df['data'] = pd.to_datetime(df['data'])
            df = df.drop_duplicates(subset=['data']).sort_values('data', ascending=True).set_index('data')

            data_start = df.index.min()
            data_koniec = max(df.index.max(), pd.Timestamp((datetime.now() + timedelta(days=1)).date()))
            pelny_kalendarz = pd.date_range(start=data_start, end=data_koniec, freq='D')

            df = df.reindex(pelny_kalendarz).ffill()
            df.index.name = 'data'
            df = df.reset_index().sort_values('data', ascending=False)
            df['data'] = df['data'].dt.strftime('%Y-%m-%d')
            df.to_csv(self.plik_csv, index=False)

            self.logger.info(f"KALENDARZ NAPRAWIONY! Baza ma {len(df)} dni ciągłej historii.")
        except Exception as e:
            self.logger.error(f"Wystąpił błąd podczas naprawy pliku CSV: {e}")
        finally:
            os._exit(0)