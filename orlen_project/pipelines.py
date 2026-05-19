import csv
import os

class NewsMergePipeline:
    def __init__(self):
        os.makedirs('data', exist_ok=True) 
        self.nazwa_pliku = 'data/wiadomosci_orlen_zestawienie.csv'

    def open_spider(self, spider):
        self.wszystkie_dane = {}
        self.dodano_nowe_dane = False 
        
        if os.path.exists(self.nazwa_pliku):
            with open(self.nazwa_pliku, mode='r', encoding='utf-8') as plik_csv:
                reader = csv.DictReader(plik_csv)
                for wiersz in reader:
                    self.wszystkie_dane[wiersz['link']] = wiersz

    def process_item(self, item, spider):
        if 'tytul' not in item or 'link' not in item:
            return item

        item['tytul'] = str(item.get('tytul', '')).replace('\n', ' ').replace('\r', ' ').strip()
        

        if 'tresc' in item and item['tresc']:
            item['tresc'] = str(item['tresc']).replace('\n', ' ').replace('\r', ' ').strip()
        
        self.wszystkie_dane[item['link']] = item
        self.dodano_nowe_dane = True 
        
        return item


    def close_spider(self, spider):
        if not self.wszystkie_dane or not self.dodano_nowe_dane:
            spider.logger.info(f"{spider.name}' - brak artykułów")
            return

        dane_do_zapisu = list(self.wszystkie_dane.values())
        dane_do_zapisu.sort(key=lambda x: x.get('data', ''), reverse=True) 
        
        pola = ['data', 'zrodlo', 'tytul', 'tresc', 'link']
        with open(self.nazwa_pliku, mode='w', newline='', encoding='utf-8') as plik_csv:
            writer = csv.DictWriter(plik_csv, fieldnames=pola, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(dane_do_zapisu)
            
        spider.logger.info(f"Pipeline zakończył pracę. Baza: {len(dane_do_zapisu)} artykułów.")