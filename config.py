import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "calendar_bot.db")
TIMEZONE_API_KEY = os.getenv("TIMEZONE_API_KEY", "YOUR_API_KEY")