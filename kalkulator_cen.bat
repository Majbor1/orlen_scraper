@echo off
echo =========================================
echo  URUCHAMIAM kalkulator detaliczny CEN
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
echo [2/3] Pobieranie ceny maksymalnej z Monitora Polskiego
python -m scrapy crawl cena_max_mp

echo.
echo [2/3] Trenuje model AI na swiezych danych i rysuje wykres...
python kalkulator_detaliczny.py

echo.
echo =========================================
echo  ZAKONCZONO POMYSLNIE! 
echo =========================================

