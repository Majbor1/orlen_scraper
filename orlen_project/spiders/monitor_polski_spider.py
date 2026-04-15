import scrapy
from scrapy_playwright.page import PageMethod
import pdfplumber
import io
import re
import os
import csv
from datetime import datetime, timedelta
import pandas as pd # <--- Dodany Pandas do obsługi kalendarza

class CenaMaxMpSpider(scrapy.Spider):
    name = "cena_max_mp"
    
    def start_requests(self):
        # 🎯 LINK SNAJPERSKI (Wszystkie obwieszczenia na jednej stronie)
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
        
        self.logger.info("🕵️‍♂️ Skanuję tabelę w poszukiwaniu WSZYSTKICH pasujących dokumentów...")
        
        xpath_pdf = "//tr[td[a[contains(text(), 'maksymalnej ceny paliw')]]]//a[img[contains(@src, 'file_pdf')]]/@href"
        linki_pdf = response.xpath(xpath_pdf).getall()
        
        await page.close()

        if linki_pdf:
            self.logger.info(f"🔗 Znalazłem {len(linki_pdf)} dokumentów PDF! Uruchamiam masowe pobieranie...")
            for link in linki_pdf:
                pelny_link = response.urljoin(link)
                yield scrapy.Request(pelny_link, callback=self.parse_pdf)
        else:
            self.logger.error("❌ Brak wyników. Sprawdź, czy tabela na stronie nie jest pusta.")

    def parse_pdf(self, response):
        if b"%PDF" not in response.body[:5]:
            return

        pdf_stream = io.BytesIO(response.body)
        pelny_tekst = ""
        
        try:
            with pdfplumber.open(pdf_stream) as pdf:
                for strona in pdf.pages:
                    tekst_strony = strona.extract_text()
                    if tekst_strony:
                        pelny_tekst += tekst_strony + "\n"
        except Exception:
            return

        # Wyciąganie cen
        wzor_95 = re.search(r'bezołowiowej\s*95.*?powiększona o podatek.*?wynosi\s*(\d+[,.]\d+)', pelny_tekst, re.IGNORECASE | re.DOTALL)
        wzor_98 = re.search(r'bezołowiowej\s*98.*?powiększona o podatek.*?wynosi\s*(\d+[,.]\d+)', pelny_tekst, re.IGNORECASE | re.DOTALL)
        wzor_on = re.search(r'oleju\s*napędowego.*?powiększona o podatek.*?wynosi\s*(\d+[,.]\d+)', pelny_tekst, re.IGNORECASE | re.DOTALL)

        cena_95 = float(wzor_95.group(1).replace(',', '.')) if wzor_95 else None
        cena_98 = float(wzor_98.group(1).replace(',', '.')) if wzor_98 else None
        cena_on = float(wzor_on.group(1).replace(',', '.')) if wzor_on else None

        if not (cena_95 or cena_98 or cena_on):
            return

        # Obliczanie daty
        miesiace = {
            'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4, 'maja': 5, 'czerwca': 6,
            'lipca': 7, 'sierpnia': 8, 'września': 9, 'października': 10, 'listopada': 11, 'grudnia': 12
        }
        wzor_daty = re.search(r'dnia\s+(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})\s*r', pelny_tekst, re.IGNORECASE)
        
        if wzor_daty:
            dzien = int(wzor_daty.group(1))
            miesiac_str = wzor_daty.group(2).lower()
            rok = int(wzor_daty.group(3))
            miesiac = miesiace.get(miesiac_str, datetime.now().month)
            try:
                data_obwieszczenia = datetime(rok, miesiac, dzien)
            except ValueError:
                data_obwieszczenia = datetime.now()
        else:
            data_obwieszczenia = datetime.now()

        data_wejscia = (data_obwieszczenia + timedelta(days=1)).strftime("%Y-%m-%d")

        # Zapis i sprawdzanie duplikatów
        plik_csv = 'data/cena_max.csv'
        zapisane_daty = set()
        
        if os.path.isfile(plik_csv):
            with open(plik_csv, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and row[0] != 'data':
                        zapisane_daty.add(row[0])

        if data_wejscia in zapisane_daty:
            self.logger.info(f"⏭️ Pomijam datę {data_wejscia} (już zarchiwizowana).")
            return

        plik_jest_pusty = not os.path.isfile(plik_csv) or os.path.getsize(plik_csv) == 0
        
        with open(plik_csv, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            if plik_jest_pusty:
                writer.writerow(['data', 'cena_max_pb95', 'cena_max_pb98', 'cena_max_on'])
            writer.writerow([data_wejscia, cena_95, cena_98, cena_on])

        self.logger.info(f"✅ ZAPISANO NOWĄ CENĘ MAX: {data_wejscia}")

    # =========================================================================
    # NOWOŚĆ: Ta funkcja odpala się automatycznie na samym końcu działania pająka
    # =========================================================================
    def closed(self, reason):
        self.logger.info("🛠️ Pająk skończył pobieranie. Odpalam moduł naprawy kalendarza (Pandas)...")
        plik = 'data/cena_max.csv'

        if not os.path.exists(plik):
            os._exit(0)

        try:
            # 1. Wczytujemy bazę
            df = pd.read_csv(plik)
            if df.empty:
                os._exit(0)
            df['data'] = pd.to_datetime(df['data'])

            # 2. Usuwamy duplikaty i sortujemy ROSNĄCO (tylko na potrzeby matematyki)
            df = df.drop_duplicates(subset=['data']).sort_values('data', ascending=True)
            df = df.set_index('data')

            # 3. Tworzymy pełny kalendarz od pierwszej znanej daty aż do "jutra"
            data_start = df.index.min()
            data_koniec = max(df.index.max(), pd.Timestamp((datetime.now() + timedelta(days=1)).date()))
            pelny_kalendarz = pd.date_range(start=data_start, end=data_koniec, freq='D')

            # 4. Wypełniamy puste luki ostatnią znaną ceną (Forward Fill działa w przód)
            df = df.reindex(pelny_kalendarz)
            df = df.ffill()

            # 5. Formatujemy z powrotem do kolumn
            df.index.name = 'data'
            df = df.reset_index()

            # --- ZMIANA: ODWRACAMY TABELĘ DO GÓRY NOGAMI ---
            # Teraz najnowsza data (jutro/dziś) będzie na samym szczycie pliku
            df = df.sort_values('data', ascending=False)
            
            # Zamieniamy daty z powrotem na ładny tekst i zapisujemy
            df['data'] = df['data'].dt.strftime('%Y-%m-%d')
            df.to_csv(plik, index=False)

            self.logger.info(f"✅ KALENDARZ NAPRAWIONY! Baza ma {len(df)} dni ciągłej historii (Najnowsze na górze).")
            
        except Exception as e:
            self.logger.error(f"❌ Wystąpił błąd podczas naprawy pliku CSV: {e}")
            
        finally:
            # Ostateczne twarde zamknięcie skryptu (zabija wiszącego Playwrighta)
            os._exit(0)