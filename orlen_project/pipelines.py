import csv
import os

class NewsMergePipeline:
    def __init__(self):
        # Ta linijka upewni się, że folder istnieje, by uniknąć błędów
        os.makedirs('data', exist_ok=True) 
        # Tu dodajemy ścieżkę:
        self.nazwa_pliku = 'data/wiadomosci_orlen_zestawienie.csv'

    # Odpala się zawsze, gdy jakikolwiek pająk zaczyna pracę
    def open_spider(self, spider):
        self.wszystkie_dane = {}
        # Wczytujemy historyczne dane z pliku
        if os.path.exists(self.nazwa_pliku):
            with open(self.nazwa_pliku, mode='r', encoding='utf-8-sig') as plik_csv:
                reader = csv.DictReader(plik_csv)
                for wiersz in reader:
                    self.wszystkie_dane[wiersz['link']] = wiersz

    # Przechwytuje każdy pojedynczy artykuł "wypluty" przez pająka
    def process_item(self, item, spider):
        # Agresywne czyszczenie przeniesione do Pipeline'u!
        item['tytul'] = item['tytul'].replace('\n', ' ').replace('\r', ' ').strip()
        item['tresc'] = item['tresc'].replace('\n', ' ').replace('\r', ' ').strip()
        
        # Zapis do słownika (kluczem jest link = brak duplikatów)
        self.wszystkie_dane[item['link']] = item
        return item

    # Odpala się, gdy pająk kończy pracę
    def close_spider(self, spider):
        if not self.wszystkie_dane:
            return

        # Sortujemy od najnowszych
        dane_do_zapisu = list(self.wszystkie_dane.values())
        dane_do_zapisu.sort(key=lambda x: x['data'], reverse=True)
        
        # Zapisujemy z powrotem do tego samego pliku
        pola = ['data', 'zrodlo', 'tytul', 'tresc', 'link']
        with open(self.nazwa_pliku, mode='w', newline='', encoding='utf-8-sig') as plik_csv:
            writer = csv.DictWriter(plik_csv, fieldnames=pola, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(dane_do_zapisu)
            
        spider.logger.info(f"✅ Rurociąg zakończył pracę. Baza: {len(dane_do_zapisu)} posortowanych artykułów.")