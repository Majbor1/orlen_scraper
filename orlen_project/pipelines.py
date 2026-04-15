import csv
import os

class NewsMergePipeline:
    def __init__(self):
        # Ta linijka upewni się, że folder istnieje, by uniknąć błędów
        os.makedirs('data', exist_ok=True) 
        self.nazwa_pliku = 'data/wiadomosci_orlen_zestawienie.csv'

    # Odpala się zawsze, gdy jakikolwiek pająk zaczyna pracę
    def open_spider(self, spider):
        self.wszystkie_dane = {}
        # ZMIANA 1: Flaga, która mówi nam, czy ten konkretny pająk faktycznie pobierał artykuły
        self.dodano_nowe_dane = False 
        
        # Wczytujemy historyczne dane z pliku
        if os.path.exists(self.nazwa_pliku):
            with open(self.nazwa_pliku, mode='r', encoding='utf-8-sig') as plik_csv:
                reader = csv.DictReader(plik_csv)
                for wiersz in reader:
                    self.wszystkie_dane[wiersz['link']] = wiersz

    # Przechwytuje każdą pojedynczą porcję danych "wyplutą" przez pająka
    def process_item(self, item, spider):
        # ZMIANA 2: BRAMKARZ 
        # Sprawdzamy czy to w ogóle jest artykuł z wiadomościami.
        # Jeśli element nie ma pola 'tytul' lub 'link' (np. to są ceny hurtowe),
        # po prostu przepuszczamy go dalej i nie dotykamy!
        if 'tytul' not in item or 'link' not in item:
            return item

        # Skoro dotarliśmy tutaj, to mamy do czynienia z artykułem prasowym.
        # Agresywne czyszczenie tekstu
        item['tytul'] = str(item.get('tytul', '')).replace('\n', ' ').replace('\r', ' ').strip()
        
        # Zabezpieczenie, jeśli jakiś artykuł ma pustą treść (None)
        if 'tresc' in item and item['tresc']:
            item['tresc'] = str(item['tresc']).replace('\n', ' ').replace('\r', ' ').strip()
        
        # Zapis do słownika (kluczem jest link = brak duplikatów)
        self.wszystkie_dane[item['link']] = item
        self.dodano_nowe_dane = True # Sygnał: "Uwaga, mamy nowe wiadomości!"
        
        return item

    # Odpala się, gdy pająk kończy pracę
    def close_spider(self, spider):
        # ZMIANA 3: Jeśli dany pająk nie przetworzył ani jednego artykułu 
        # (bo był to np. pająk od cen), zamykamy po cichu, bez ruszania i nadpisywania pliku CSV.
        if not self.wszystkie_dane or not self.dodano_nowe_dane:
            spider.logger.info(f"🛑 Pająk '{spider.name}' pominął Rurociąg Prasowy (brak artykułów).")
            return

        # Sortujemy od najnowszych
        dane_do_zapisu = list(self.wszystkie_dane.values())
        # Bezpieczne sortowanie na wypadek brakującej daty
        dane_do_zapisu.sort(key=lambda x: x.get('data', ''), reverse=True) 
        
        # Zapisujemy z powrotem do tego samego pliku
        pola = ['data', 'zrodlo', 'tytul', 'tresc', 'link']
        with open(self.nazwa_pliku, mode='w', newline='', encoding='utf-8-sig') as plik_csv:
            writer = csv.DictWriter(plik_csv, fieldnames=pola, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(dane_do_zapisu)
            
        spider.logger.info(f"✅ Rurociąg Prasowy zakończył pracę. Baza: {len(dane_do_zapisu)} artykułów.")