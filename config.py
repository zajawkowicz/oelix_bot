import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8203814122:AAG7lbjz1iKBIL2c8wrX2LF5XBdHWXAk8p0").strip().strip('"').strip("'")
CHAT_ID = os.getenv("CHAT_ID", "5040524806").strip().strip('"').strip("'")
OLX_SEARCH_URL = os.getenv("OLX_SEARCH_URL", "https://www.olx.pl/gdansk/q-iphone/").strip().strip('"').strip("'")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 180))
# Walidacja zmiennych
if not TELEGRAM_TOKEN or not CHAT_ID or not OLX_SEARCH_URL:
    raise SystemExit("❌ Missing one of required variables: TELEGRAM_TOKEN, CHAT_ID, OLX_SEARCH_URL")
