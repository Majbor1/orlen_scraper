import scrapy
from datetime import datetime, timedelta
import os
import pandas as pd

class BankierSpider(scrapy.Spider):
    name = "bankier_orlen"
    allowed_domains = ["bankier.pl"]
    max_pages = 2

    def __init__(self, *args, **kwargs):
        super(BankierSpider, self).__init__(*args, **kwargs)
        self.data_graniczna = self.wyznacz_date_graniczna()

    def wyznacz_date_graniczna(self):
        plik = 'data/wiadomosci_orlen_zestawienie.csv'
        if os.path.exists(plik):
            try:
                df = pd.read_csv(plik)
                df_zrodlo = df[df['zrodlo'] == 'Bankier']
                if not df_zrodlo.empty and 'data' in df_zrodlo.columns:
                    ostatnia_data = pd.to_datetime(df_zrodlo['data']).max()
                    self.logger.info(f"📅 Ostatnia data w bazie (Bankier): {ostatnia_data.strftime('%Y-%m-%d')}")
                    return ostatnia_data.strftime('%Y-%m-%d')
            except Exception as e:
                self.logger.warning(f"Błąd odczytu CSV: {e}")
        return (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

    def start_requests(self):
        yield scrapy.Request("https://www.bankier.pl/wyszukiwarka?qt=orlen", callback=self.parse_bankier, meta={'page': 1})

    def parse_bankier(self, response):
        current_page = response.meta['page']
        for article in response.css('article.article'):
            tytul = article.css('h2.entry-title a::text').get()
            link = article.css('h2.entry-title a::attr(href)').get()
            data_publikacji = article.css('time.entry-date::attr(datetime)').get()

            if tytul and data_publikacji and link:
                czysta_data = data_publikacji.split('T')[0] if 'T' in data_publikacji else data_publikacji.strip()
                pelny_link = response.urljoin(link)
                
                item = {'data': czysta_data[:10], 'zrodlo': 'Bankier', 'tytul': tytul.strip(), 'link': pelny_link}
                yield scrapy.Request(pelny_link, callback=self.parse_bankier_article, meta={'item': item})

        if current_page < self.max_pages:
            next_page = current_page + 1
            yield scrapy.Request(f"https://www.bankier.pl/wyszukiwarka?qt=orlen&page={next_page}", callback=self.parse_bankier, meta={'page': next_page})

    def parse_bankier_article(self, response):
        item = response.meta['item']
        if item['data'] < self.data_graniczna: return

        akapity = response.css('section.o-article-content p *::text, section.o-article-content p::text, div.article-content p::text, div#articleContainer p::text, section.article p::text').getall()
        
        item['tresc'] = " ".join([p.strip() for p in akapity if p.strip()])
        yield item