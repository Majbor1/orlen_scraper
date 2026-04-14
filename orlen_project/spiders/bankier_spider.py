import scrapy
from datetime import datetime, timedelta

class BankierSpider(scrapy.Spider):
    name = "bankier_orlen"
    allowed_domains = ["bankier.pl"]

    limit_czasowy = datetime.now() - timedelta(days=3)
    data_graniczna = limit_czasowy.strftime("%Y-%m-%d")
    max_pages = 2

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

        akapity = response.css('div.article-content p::text, div#articleContainer p::text, section.article p::text').getall()
        item['tresc'] = " ".join([p.strip() for p in akapity if p.strip()])
        yield item # Wysyła dane do pipelines.py!