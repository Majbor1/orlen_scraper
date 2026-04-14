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
echo [2.5/6] Czyszczenie i filtrowanie zeskrapowanych tekstow...
python czyszczenie_danych.py

echo.
echo [3/6] Gemini czyta nowosci (tylko te jeszcze nieocenione!)...
python ocena_ai.py

echo.
echo [4/6] Pobieram dzisiejsze zamkniecie gieldy (Ropa/USD)...
python gielda.py

echo.
echo [5/6] Aktualizuje Tabele Mistrzowska...
python buduj_tabele.py

echo.
echo [6/6] Trenuje model AI na swiezych danych i rysuje wykres...
python trenuj_model.py

echo.
echo =========================================
echo  ZAKONCZONO POMYSLNIE! 
echo =========================================

:: Wychodzimy ze srodowiska
call deactivate

:: Zostawiam PAUSE, zebys mogl przeczytac wyniki (blad MAE) zanim okno zniknie!
:: Jak juz wszystko bedzie dzialac idealnie, mozesz usunac slowo 'pause'.
pause