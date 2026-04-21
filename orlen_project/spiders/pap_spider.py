import scrapy
from datetime import datetime, timedelta
from scrapy_playwright.page import PageMethod
import os
import pandas as pd

class PapSpider(scrapy.Spider):
    name = "pap_orlen"
    allowed_domains = ["pap.pl"]
    max_pages = 2

    def __init__(self, *args, **kwargs):
        super(PapSpider, self).__init__(*args, **kwargs)
        self.data_graniczna = self.wyznacz_date_graniczna()

    def wyznacz_date_graniczna(self):
        plik = 'data/wiadomosci_orlen_zestawienie.csv'
        if os.path.exists(plik):
            try:
                df = pd.read_csv(plik)
                df_zrodlo = df[df['zrodlo'] == 'PAP']
                if not df_zrodlo.empty and 'data' in df_zrodlo.columns:
                    ostatnia_data = pd.to_datetime(df_zrodlo['data']).max()
                    self.logger.info(f"📅 Ostatnia data w bazie (PAP): {ostatnia_data.strftime('%Y-%m-%d')}")
                    return ostatnia_data.strftime('%Y-%m-%d')
            except Exception as e:
                self.logger.warning(f"Błąd odczytu CSV: {e}")
        return (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

    def start_requests(self):
        yield scrapy.Request(
            "https://www.pap.pl/wyszukiwanie/orlen", 
            callback=self.parse_pap,
            meta={'page': 0, 'playwright': True, 'playwright_page_methods': [PageMethod("wait_for_selector", "a.newsLink", timeout=15000)]}
        )

    def parse_pap(self, response):
        current_page = response.meta['page']
        links = response.css('.col-9 a.newsLink::attr(href), .region-content a.newsLink::attr(href)').getall()
        unikalne_linki = list(set([l for l in links if l and len(l) > 25]))

        for link in unikalne_linki:
            full_link = response.urljoin(link)
            yield scrapy.Request(
                full_link, callback=self.parse_pap_article,
                meta={'zrodlo': 'PAP', 'link': full_link, 'playwright': True, 'playwright_page_methods': [PageMethod("wait_for_selector", "article#article", timeout=15000)]}
            )

        if current_page < self.max_pages - 1:
            next_page = current_page + 1
            yield scrapy.Request(
                f"https://www.pap.pl/wyszukiwanie/orlen?page={next_page}", callback=self.parse_pap,
                meta={'page': next_page, 'playwright': True, 'playwright_page_methods': [PageMethod("wait_for_selector", ".newsLink", timeout=15000)]}
            )

    def parse_pap_article(self, response):
        article_selector = response.css('article#article')
        raw_date = article_selector.css('.articleInfo .date::text').get()
        
        if raw_date and len(raw_date.strip()) >= 10:
            d = raw_date.strip()[:10]
            czysta_data = f"{d[6:10]}-{d[3:5]}-{d[0:2]}"
        else: return

        if czysta_data < self.data_graniczna: return

        tytul_lista = article_selector.css('.articleTitle *::text').getall()
        tresc_akapity = article_selector.css('p *::text, h2::text').getall()

        yield {
            'data': czysta_data,
            'zrodlo': response.meta['zrodlo'],
            'tytul': ' '.join([t.strip() for t in tytul_lista if t.strip()]),
            'tresc': ' '.join([a.strip() for a in tresc_akapity if a.strip()]),
            'link': response.meta['link']
        }