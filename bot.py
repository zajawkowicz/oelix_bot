import requests
import sqlite3
import time
import datetime
import asyncio
from bs4 import BeautifulSoup
from telegram import Bot
from config import TELEGRAM_TOKEN, CHAT_ID, OLX_SEARCH_URL, CHECK_INTERVAL

# Inicjalizacja bota
bot = Bot(token=TELEGRAM_TOKEN)

# SQLite baza
conn = sqlite3.connect("sent_offers.db")
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS sent
             (
                 id
                 TEXT
                 PRIMARY
                 KEY,
                 url
                 TEXT,
                 title
                 TEXT,
                 ts
                 INTEGER
             )""")
conn.commit()


# --- DODANO NOWĄ FUNKCJĘ DO DIAGNOSTYKI ---
def check_scraper_selectors(soup):
    print("\n--- Diagnostyka selektorów ---")
    cards = soup.select("div[data-cy='l-card']")
    print(f"Znaleziono {len(cards)} kart ogłoszeń (div[data-cy='l-card']).")
    if not cards:
        print("!!! OSTRZEŻENIE: Główny selektor ogłoszeń nic nie znalazł. Prawdopodobnie OLX zmienił strukturę strony.")
    else:
        print("Główny selektor wydaje się działać poprawnie.")
    print("--- Koniec diagnostyki ---\n")


def fetch_offers():
    print(f"Pobieranie ofert z {OLX_SEARCH_URL}...")
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    r = requests.get(OLX_SEARCH_URL, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # --- DODANO WYWOŁANIE FUNKCJI DIAGNOSTYCZNEJ ---
    check_scraper_selectors(soup)

    offers = []
    for ad in soup.select("div[data-cy='l-card']"):
        a_tag = ad.find("a", href=True)
        if not a_tag:
            continue
        url = a_tag["href"]
        if url.startswith("/"):
            url = "https://www.olx.pl" + url
        title_tag = ad.select_one("h4")
        title = title_tag.get_text(strip=True) if title_tag else a_tag.get_text(strip=True)

        price_tag = ad.select_one("p[data-testid='ad-price']")
        price = price_tag.get_text(strip=True) if price_tag else "Brak ceny"

        loc_tag = ad.select_one("p[data-testid='location-date']")
        location = loc_tag.get_text(strip=True) if loc_tag else "Brak lokalizacji"

        img_tag = ad.find("img")
        img_url = img_tag.get("src") if img_tag else None

        if img_url and img_url.startswith("//"):
            img_url = "https:" + img_url

        if not img_url or img_url.strip() == "":
            img_url = None

        offer_id = url.split("-")[-1].replace(".html", "")

        offers.append({
            "id": offer_id,
            "title": title,
            "url": url,
            "price": price,
            "location": location,
            "img": img_url
        })
    # --- DODANO PRINT ---
    print(f"Zakończono pobieranie. Znaleziono łącznie {len(offers)} ofert na stronie.")
    return offers


def already_sent(offer_id):
    c.execute("SELECT 1 FROM sent WHERE id=?", (offer_id,))
    return c.fetchone() is not None


def mark_sent(offer):
    c.execute("INSERT OR IGNORE INTO sent (id,url,title,ts) VALUES (?,?,?,?)",
              (offer["id"], offer["url"], offer["title"], int(time.time())))
    conn.commit()


def check_delivery_on_offer_page(offer_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(offer_url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        delivery_span = soup.find("span", class_="css-e0wl68")
        if delivery_span:
            text = delivery_span.get_text(strip=True)
            if "Pakiet Ochronny" in text or "Dostępna przesyłka" in text or "Przesyłka OLX" in text:
                return f"Dostępna przesyłka OLX ({text})"
            else:
                return f"Inna informacja o przesyłce: {text}"
        else:
            return "Brak przesyłki OLX"
    except Exception as e:
        print(f"Błąd podczas sprawdzania przesyłki dla {offer_url}: {e}")
        return "Brak przesyłki OLX"


async def send_offer(offer):
    caption = (
        f"📌 *{offer['title']}*\n"
        f"💰 {offer['price']}\n"
        f"📍 {offer['location']}\n"
        f"🚚 {offer['delivery']}\n"
        f"🔗 {offer['url']}"
    )
    if offer["img"]:
        try:
            await bot.send_photo(chat_id=CHAT_ID, photo=offer["img"], caption=caption, parse_mode="Markdown")
        except Exception as e:
            print("Błąd przy wysyłaniu zdjęcia:", e)
            await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode="Markdown")
    else:
        await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode="Markdown")


async def main():
    print(f"Bot wystartował. Sprawdzanie co {CHECK_INTERVAL} sekund.")
    while True:
        try:
            # --- DODANO PRINT ---
            print("\n--- Rozpoczynam nowy cykl sprawdzania ---")
            offers = fetch_offers()

            if not offers:
                print("Nie znaleziono żadnych ofert w tym cyklu. Czekam na następny...")

            for o in offers:
                if not already_sent(o["id"]):
                    # --- DODANO PRINT ---
                    print(f"✅ Znaleziono NOWĄ ofertę: {o['title']}")
                    o["delivery"] = check_delivery_on_offer_page(o["url"])

                    print("   Wysyłanie powiadomienia na Telegram...")
                    await send_offer(o)
                    mark_sent(o)
                    print(f"   Oznaczono ofertę {o['id']} jako wysłaną.")

                    await asyncio.sleep(2)
                else:
                    # --- DODANO PRINT ---
                    print(f"🔎 Pomijam już wysłaną ofertę: {o['title']}")

        except Exception as e:
            print(f"🚨 Wystąpił krytyczny błąd w pętli głównej: {e}")

        now = datetime.datetime.now()
        print(f"--- Cykl zakończony. Czekam {CHECK_INTERVAL} sekund. ---")
        print(now.strftime("--- Godzina zakończenia cyklu %H:%M:%S. ---"))

        def countdown(time_sec):
            while time_sec:
                mins, secs = divmod(time_sec, 60)
                timeformat = '{:02d}:{:02d}'.format(mins, secs)
                print(timeformat, end='\r')
                time.sleep(1)
                time_sec -= 1
        countdown(180)
        print(f"--- Bot czekał {CHECK_INTERVAL} sekund. ---")
        # await asyncio.sleep(CHECK_INTERVAL)
#         tutaj była funckja czekania ale mamy licznik wiec wyjebane


if __name__ == "__main__":
    # Upewnij się, że plik config.py jest poprawnie załadowany
    try:
        from config import TELEGRAM_TOKEN, CHAT_ID, OLX_SEARCH_URL

        print("Konfiguracja załadowana pomyślnie.")
    except Exception as e:
        print(f"Błąd podczas ładowania konfiguracji: {e}")
        exit()  # Zakończ, jeśli konfiguracja jest błędna

    asyncio.run(main())