@echo off
echo =========================================
echo  URUCHAMIAM SYSTEM PREDYKCYJNY ORLEN
echo =========================================

:: Bezpieczne i wymuszone wejscie do folderu
cd /d "%USERPROFILE%\OneDrive - uek.krakow.pl\orlen_scraper"

:: Automatyczne wykrywanie wlasciwego srodowiska
if exist ".venv_pc\Scripts\activate.bat" (
    echo [System] Wykryto PC - ladowanie .venv_pc...
    call .venv_pc\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo [System] Wykryto Laptop - ladowanie .venv...
    call .venv\Scripts\activate.bat
) else (
    echo [Blad] Krytyczny: Nie znaleziono zadnego srodowiska wirtualnego!
    pause
    exit /b 1
)

echo.
echo [1/8] Pobieranie dzisiejszych cen hurtowych Orlen...
python -m scrapy crawl hurtowe_orlen

echo.
echo [2/8] Pobieranie ceny maksymalnej z Monitora Polskiego
python -m scrapy crawl cena_max_mp

echo.
echo [3/8] Pobieranie wiadomosci ze wszystkich portali...
python -m scrapy crawl bankier_orlen
python -m scrapy crawl pap_orlen
python -m scrapy crawl tvn24_orlen

echo.
echo [4/8] Czyszczenie i filtrowanie zeskrapowanych tekstow...
python czyszczenie_danych.py

echo.
echo [5/8] Gemini czyta nowosci (tylko te jeszcze nieocenione!)...
python ocena_ai.py

echo.
echo [6/8] Pobieram dzisiejsze zamkniecie gieldy (Ropa/USD)...
python gielda.py

echo.
echo [7/8] Aktualizuje Tabele Mistrzowska...
python buduj_tabele.py

echo.
echo [8/8] Trenuje model AI na swiezych danych i rysuje wykres...
python trenuj_model.py

echo.
echo =========================================
echo  ZAKONCZONO POMYSLNIE! 
echo =========================================

:: Wychodzimy ze srodowiska
call deactivate

pause