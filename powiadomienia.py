import os
import requests
from cryptography.fernet import Fernet

def wyslij_powiadomienia(tytul, wiadomosc):
    app_token = os.environ.get("APP_TOKEN")
    moj_klucz = os.environ.get("USER_KEY")
    klucz_szyfrujacy = os.environ.get("ENCRYPTION_KEY")

    if not all([app_token, klucz_szyfrujacy]):
        print("❌ Błąd: Brakuje kluczy w zmiennych środowiskowych.")
        return

    lista_odbiorcow = [moj_klucz] if moj_klucz else []
    fernet = Fernet(klucz_szyfrujacy)
    sciezka_pliku = 'data/subskrybenci.txt'

    print("🔍 Sprawdzam plik z zaszyfrowanymi subskrybentami...")
    
    # Odczytywanie zaszyfrowanych kluczy z pliku tekstowego
    if os.path.exists(sciezka_pliku):
        with open(sciezka_pliku, 'r', encoding='utf-8') as plik:
            zaszyfrowane_klucze = plik.readlines()
            
        for zaszyfrowany_klucz in zaszyfrowane_klucze:
            zaszyfrowany_klucz = zaszyfrowany_klucz.strip() # Usuwamy białe znaki i enter (\n)
            if zaszyfrowany_klucz:
                try:
                    odszyfrowany_klucz = fernet.decrypt(zaszyfrowany_klucz.encode()).decode()
                    if odszyfrowany_klucz not in lista_odbiorcow:
                        lista_odbiorcow.append(odszyfrowany_klucz)
                except Exception as e:
                    print(f"❌ Błąd odszyfrowywania klucza z pliku: {e}")
    else:
        print("ℹ️ Brak pliku subskrybenci.txt. Powiadomienie trafi tylko na główny klucz.")

    print(f"🚀 Rozpoczynam wysyłanie powiadomień do {len(lista_odbiorcow)} urządzeń...")
    
    for klucz_odbiorcy in lista_odbiorcow:
        if klucz_odbiorcy:
            dane = {
                "token": app_token,
                "user": klucz_odbiorcy,
                "title": tytul,
                "message": wiadomosc,
                "html": 1
            }
            try:
                resp = requests.post("https://api.pushover.net/1/messages.json", data=dane)
                if resp.status_code == 200:
                    print(f"✅ Wysłano do: ...{klucz_odbiorcy[-4:]}")
                else:
                    print(f"❌ Błąd wysyłania do ...{klucz_odbiorcy[-4:]}: {resp.text}")
            except Exception as e:
                print(f"❌ Błąd połączenia przy wysyłaniu: {e}")

if __name__ == "__main__":
    wyslij_powiadomienia("Prognoza Orlen AI", "Sprawdź nowe przewidywania cen paliw!")