import scrapy
from datetime import datetime, timedelta
from scrapy_playwright.page import PageMethod
import os
import pandas as pd

class Tvn24Spider(scrapy.Spider):
    name = "tvn24_orlen"
    allowed_domains = ["tvn24.pl"]

    def __init__(self, *args, **kwargs):
        super(Tvn24Spider, self).__init__(*args, **kwargs)
        self.data_graniczna = self.wyznacz_date_graniczna()

    def wyznacz_date_graniczna(self):
        plik = 'data/wiadomosci_orlen_zestawienie.csv'
        if os.path.exists(plik):
            try:
                df = pd.read_csv(plik)
                df_zrodlo = df[df['zrodlo'] == 'TVN24']
                if not df_zrodlo.empty and 'data' in df_zrodlo.columns:
                    ostatnia_data = pd.to_datetime(df_zrodlo['data']).max()
                    self.logger.info(f"Ostatnia data w bazie (TVN24): {ostatnia_data.strftime('%Y-%m-%d')}")
                    return ostatnia_data.strftime('%Y-%m-%d')
            except Exception as e:
                self.logger.warning(f"Błąd odczytu CSV: {e}")
        return (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

    def start_requests(self):
        yield scrapy.Request(
            "https://tvn24.pl/szukaj/s-1?q=p:orlen,t:article", 
            callback=self.parse_tvn24,
            meta={'playwright': True, 'playwright_page_methods': [
                PageMethod("wait_for_load_state", "domcontentloaded"),
                PageMethod("evaluate", "window.scrollBy(0, 2000);"),
                PageMethod("wait_for_timeout", 1500),
                PageMethod("evaluate", "window.scrollBy(0, 2000);"),
                PageMethod("wait_for_timeout", 1500),
            ]}
        )

    def parse_tvn24(self, response):
        czyste_linki = set()
        for link in response.css('a::attr(href)').getall():
            if link and '-st' in link and link[-1].isdigit():
                full_link = response.urljoin(link)
                if not any(x in full_link for x in ['eurosport', 'tvn24go', 'pogoda']):
                    czyste_linki.add(full_link)

        for full_link in czyste_linki:
            yield scrapy.Request(
                full_link, callback=self.parse_tvn24_article,
                meta={'zrodlo': 'TVN24', 'link': full_link, 'playwright': True, 'playwright_page_methods': [PageMethod("wait_for_load_state", "domcontentloaded")]}
            )

    def parse_tvn24_article(self, response):
        tytul = response.css('meta[property="og:title"]::attr(content)').get()
        if not tytul: tytul = response.css('title::text').get(default='')
            
        raw_date = response.css('meta[property="article:published_time"]::attr(content)').get()
        if raw_date:
            czysta_data = raw_date[:10]
        else:
            time_tag = response.css('time::attr(datetime)').get()
            czysta_data = time_tag[:10] if time_tag else "brak_daty"

        if czysta_data == "brak_daty" or czysta_data < self.data_graniczna: return

        tresc = " ".join(response.css('[data-paragraph]::text, [data-lead]::text').getall())
        
        yield {
            'data': czysta_data,
            'zrodlo': response.meta['zrodlo'],
            'tytul': tytul.split(' | ')[0].strip(),
            'tresc': tresc,
            'link': response.meta['link']
        }