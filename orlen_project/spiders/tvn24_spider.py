import scrapy
from datetime import datetime, timedelta
from scrapy_playwright.page import PageMethod

class Tvn24Spider(scrapy.Spider):
    name = "tvn24_orlen"
    allowed_domains = ["tvn24.pl"]

    limit_czasowy = datetime.now() - timedelta(days=3)
    data_graniczna = limit_czasowy.strftime("%Y-%m-%d")

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
        # Usunięta paginacja, pobieramy tylko bieżącą stronę (ok. 20 najnowszych artykułów)
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