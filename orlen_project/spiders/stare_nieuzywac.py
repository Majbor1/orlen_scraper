import scrapy
import csv
import os
from datetime import datetime, timedelta
from scrapy_playwright.page import PageMethod


class NewsOrlenSpider(scrapy.Spider):
    name = "news_orlen"
    allowed_domains = ["bankier.pl", "tvn24.pl", "pap.pl"]

    dzisiaj = datetime.now()
    limit_czasowy = dzisiaj - timedelta(days=4)
    data_graniczna = limit_czasowy.strftime("%Y-%m-%d")

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'TWISTED_REACTOR': "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,  
        }
    }

    def __init__(self, *args, **kwargs):
        super(NewsOrlenSpider, self).__init__(*args, **kwargs)
        self.zebrane_dane = []
        self.max_pages = 2
        
    def start_requests(self):
        yield scrapy.Request(
             url="https://www.bankier.pl/wyszukiwarka?qt=orlen", 
             callback=self.parse_bankier,
             meta={'page': 1} 
        )
        
        yield scrapy.Request(
            url="https://www.pap.pl/wyszukiwanie/orlen", 
            callback=self.parse_pap,
            meta={
                'page': 0, 
                'playwright': True,
                'playwright_page_methods': [
                    PageMethod("wait_for_selector", "a.newsLink", timeout=15000) 
                ]
            } 
        )

        yield scrapy.Request(
            url="https://tvn24.pl/szukaj/s-1?q=p:orlen,t:article", 
            callback=self.parse_tvn24,
            meta={
                'playwright': True,
                'playwright_page_methods': [
                    PageMethod("wait_for_load_state", "domcontentloaded"),
                    # Scrollujemy w dół, żeby pobudzić stronę do załadowania artykułów
                    PageMethod("evaluate", "window.scrollBy(0, 2000);"),
                    PageMethod("wait_for_timeout", 1500),
                    PageMethod("evaluate", "window.scrollBy(0, 2000);"),
                    PageMethod("wait_for_timeout", 1500),
                ]
            }
        )

    def parse_bankier(self, response):
        current_page = response.meta['page']
        self.logger.info(f"Parsuję LISTĘ Bankiera - strona {current_page}")
        
        articles = response.css('article.article')

        for article in articles:
            tytul = article.css('h2.entry-title a::text').get()
            link = article.css('h2.entry-title a::attr(href)').get()
            data_publikacji = article.css('time.entry-date::attr(datetime)').get()

            if tytul and data_publikacji and link:
                czysta_data = data_publikacji.split('T')[0] if 'T' in data_publikacji else data_publikacji.strip()
                pelny_link = f"https://www.bankier.pl{link}" if link and link.startswith('/') else link

                # Pakujemy dotychczasowe dane do słownika
                item = {
                    'data': czysta_data[:10],
                    'zrodlo': 'Bankier',
                    'tytul': tytul.strip().replace('\n', ''),
                    'link': pelny_link
                }

                # ZAMIAST ZAPISYWAĆ, WYSYŁAMY PAJĄKA DO ŚRODKA ARTYKUŁU!
                # Przekazujemy nasz 'item' w parametrze meta
                yield scrapy.Request(
                    url=pelny_link, 
                    callback=self.parse_bankier_article, 
                    meta={'item': item}
                )

        # Paginacja listy
        if current_page < self.max_pages:
            nast_strona = f"https://www.bankier.pl/wyszukiwarka?qt=orlen&page={current_page + 1}"
            yield scrapy.Request(url=nast_strona, callback=self.parse_bankier, meta={'page': current_page + 1})

    # --- NOWA FUNKCJA: PARSOWANIE WNĘTRZA ARTYKUŁU ---
    def parse_bankier_article(self, response):
        item = response.meta['item']
        self.logger.info(f"Pobieram treść: {item['tytul'][:30]}...")

        akapity = response.css('div.article-content p::text, div#articleContainer p::text, section.article p::text, div.o-article-content p::text').getall()
        if not akapity:
             akapity = response.css('article p::text').getall()

        tresc_zlepiona = " ".join([p.strip() for p in akapity if p.strip()])
        
        # --- NOWOŚĆ: Agresywne czyszczenie tekstu ---
        # 1. Zamieniamy wszystkie niewidzialne Entery (\n, \r) i tabulacje (\t) na zwykłe spacje
        tresc_czysta = tresc_zlepiona.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        
        # 2. Usuwamy ewentualne podwójne/potrójne spacje, żeby tekst był idealnie gładki
        tresc_czysta = " ".join(tresc_czysta.split())
        
        # Przypisujemy wyczyszczoną treść
        item['tresc'] = tresc_czysta
        
        self.zebrane_dane.append(item)

    def parse_pap(self, response):
        current_page = response.meta['page']
        self.logger.info(f"Parsuję LISTĘ PAP - strona {current_page}")

        # Używamy tej czystej klasy, na którą Playwright przed chwilą cierpliwie czekał
        links = response.css('.col-9 a.newsLink::attr(href), .region-content a.newsLink::attr(href)').getall()
        
        # Filtrujemy linki: usuwamy duplikaty oraz linki menu (prawdziwy link do artykułu jest bardzo długi, więc np. > 25 znaków)
        unikalne_linki = list(set([
            link for link in links 
            if link and len(link) > 25 
        ]))
        # --------------------------------

        self.logger.info(f"🔥 Znalazłem {len(unikalne_linki)} unikalnych linków na stronie {current_page}")

        # 2. Wysyłamy pająka do wnętrza każdego artykułu
        for link in unikalne_linki:
            full_link = response.urljoin(link)
            yield scrapy.Request(
                url=full_link,
                callback=self.parse_pap_article,
                meta={
                    'zrodlo': 'PAP', 
                    'link': full_link,
                    # --- DODAJEMY TE DWIE LINIJKI ---
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod("wait_for_selector", "article#article", timeout=15000)
                    ]
                    # -------------------------------
                }
            )

        # 3. Paginacja zostaje tak jak była:
        if current_page < self.max_pages - 1:
            next_page = current_page + 1
            next_url = f"https://www.pap.pl/wyszukiwanie/orlen?page={next_page}"
            yield scrapy.Request(
                next_url, 
                callback=self.parse_pap, 
                meta={
                    'page': next_page, 
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod("wait_for_selector", ".newsLink", timeout=15000)
                    ]
                }
            )

    def parse_pap_article(self, response):
        dane = response.meta
        
        # Używamy kontenera z Twoich zajęć!
        article_selector = response.css('article#article')
        
        # 1. Tytuł (z klasy articleTitle)
        tytul_lista = article_selector.css('.articleTitle *::text').getall()
        tytul = ' '.join([t.strip() for t in tytul_lista if t.strip()])
        
        # 2. Data (z klasy articleInfo -> date)
        # HTML z PAP wygląda tak: "21.03.2026 14:13"
        raw_date = article_selector.css('.articleInfo .date::text').get()
        if raw_date and len(raw_date.strip()) >= 10:
            d = raw_date.strip()[:10]  # wycina "21.03.2026"
            # Formatyzujemy na "2026-03-21", żeby pasowało do Bankiera
            czysta_data = f"{d[6:10]}-{d[3:5]}-{d[0:2]}"
        else:
            czysta_data = "brak_daty"
            
        # 3. Treść z akapitów
        tresc_akapity = article_selector.css('p *::text, h2::text').getall()
        tresc = ' '.join([akap.strip() for akap in tresc_akapity if akap.strip()])
        
        # Zapisujemy do głównej bazy!
        self.zebrane_dane.append({
            'data': czysta_data,
            'zrodlo': dane['zrodlo'],
            'tytul': tytul if tytul else 'brak_tytulu',
            'tresc': tresc if tresc else 'brak_tresci',
            'link': dane['link']
        })

    def parse_tvn24(self, response):
        # Na potrzeby optymalizacji wycięto paginację - pobieramy tylko najświeższą, 1. stronę.
        self.logger.info("=== PARSUJĘ TVN24 TYLKO STRONA 1 ===")
        
        wszystkie_linki = response.css('a::attr(href)').getall()
        czyste_linki = set()
        
        for link in wszystkie_linki:
            if not link: continue
            if '-st' in link and link[-1].isdigit():
                full_link = response.urljoin(link)
                if any(zakazane in full_link for zakazane in ['eurosport', 'tvn24go', 'pogoda']):
                    continue
                czyste_linki.add(full_link)

        # 1. Wysyłamy pająka do artykułów z obecnej strony
        for full_link in czyste_linki:
            yield scrapy.Request(
                url=full_link,
                callback=self.parse_tvn24_article,
                meta={
                    'zrodlo': 'TVN24',
                    'link': full_link,
                    'playwright': True,
                    # ZMIANA: Czekamy na załadowanie, żeby ukryta data się pojawiła!
                    'playwright_page_methods': [
                        PageMethod("wait_for_load_state", "domcontentloaded")
                    ]
                }
            )
        
        # --- USUNIĘTO PAGINACJĘ TVN24 ZGODNIE Z PROŚBĄ ---

    # FUNKCJA CZYTAJĄCA WNĘTRZE ARTYKUŁU
    def parse_tvn24_article(self, response):
        dane = response.meta
        
        # 1. PANCERNE WYCIĄGANIE TYTUŁU Z TAGÓW SEO (Koniec z "Redakcja poleca"!)
        tytul = response.css('meta[property="og:title"]::attr(content)').get()
        if not tytul:
            tytul = response.css('title::text').get(default='Brak tytułu').strip()
            
        # Usuwamy ewentualny dopisek " | TVN24 Biznes" z tytułu
        tytul = tytul.split(' | ')[0]
            
        # 2. Maszynowe wyciąganie daty z tagów SEO
        raw_date = response.css('meta[property="article:published_time"]::attr(content)').get()
        if raw_date:
            czysta_data = raw_date[:10]
        else:
            time_tag = response.css('time::attr(datetime)').get()
            czysta_data = time_tag[:10] if time_tag else "brak_daty"

        # 3. BEZPIECZNIK DATY (Teraz puszcza wszystko do roku wstecz)
        if czysta_data != "brak_daty" and czysta_data < self.data_graniczna:
             self.logger.info(f"⛔ Artykuł za stary ({czysta_data}). Pomijam.")
             return

        # 4. Wyciąganie treści
        tresc_akapity = response.css('[data-lead]::text, [data-paragraph]::text').getall()
        tresc = ' '.join([akap.strip() for akap in tresc_akapity if akap.strip()])
        
        # 5. Zapis do bazy
        self.zebrane_dane.append({
            'data': czysta_data,
            'zrodlo': dane['zrodlo'],
            'tytul': tytul.strip(),
            'tresc': tresc if tresc else 'brak_tresci',
            'link': dane['link']
        })
        self.logger.info(f"✅ Dodano do pliku: {tytul[:40]}... (Data: {czysta_data})")


    def closed(self, reason):
        if not self.zebrane_dane:
            self.logger.info("Brak nowych artykułów do zapisania.")
            return

        nazwa_pliku = 'wiadomosci_orlen_zestawienie.csv'
        
        # 1. --- CZYSZCZENIE NOWYCH DANYCH ---
        nowe_dane = []
        for wiersz in self.zebrane_dane:
            # Usuwamy "entery" z tekstu, żeby nie łamały wierszy w CSV
            wiersz['tytul'] = wiersz['tytul'].replace('\n', ' ').replace('\r', ' ').strip()
            wiersz['tresc'] = wiersz['tresc'].replace('\n', ' ').replace('\r', ' ').strip()
            nowe_dane.append(wiersz)

        # Używamy słownika, w którym kluczem jest LINK. 
        # Słownik naturalnie usuwa duplikaty - jeśli wejdzie ten sam link, po prostu go zaktualizuje.
        wszystkie_dane = {}
        
        # 2. --- WCZYTYWANIE STARYCH DANYCH (Jeśli plik istnieje) ---
        if os.path.exists(nazwa_pliku):
            with open(nazwa_pliku, mode='r', encoding='utf-8-sig') as plik_csv:
                reader = csv.DictReader(plik_csv)
                for wiersz in reader:
                    wszystkie_dane[wiersz['link']] = wiersz
                    
        # 3. --- DODAWANIE NOWYCH DANYCH ---
        for wiersz in nowe_dane:
            wszystkie_dane[wiersz['link']] = wiersz
            
        # 4. --- SORTOWANIE (Najnowsze na górze) ---
        # Zamieniamy słownik z powrotem na listę i sortujemy
        dane_do_zapisu = list(wszystkie_dane.values())
        dane_do_zapisu.sort(key=lambda x: x['data'], reverse=True) # reverse=True daje najnowsze daty u góry
        
        # 5. --- BEZPIECZNY ZAPIS DO PLIKU CSV ---
        pola = ['data', 'zrodlo', 'tytul', 'tresc', 'link']
        with open(nazwa_pliku, mode='w', newline='', encoding='utf-8-sig') as plik_csv:
            # QUOTE_ALL zapobiega psuciu tabeli przez przecinki w tekście
            writer = csv.DictWriter(plik_csv, fieldnames=pola, quoting=csv.QUOTE_ALL)
            
            writer.writeheader()
            writer.writerows(dane_do_zapisu)
            
        self.logger.info(f"✅ BAZA ZAKTUALIZOWANA! W pliku {nazwa_pliku} jest teraz {len(dane_do_zapisu)} unikalnych, posortowanych artykułów.")