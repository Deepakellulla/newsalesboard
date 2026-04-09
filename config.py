import os

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGODB_URI = os.environ.get("MONGODB_URI", "")
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]

BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "My Digital Store")
CURRENCY = os.environ.get("CURRENCY", "₹")
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")
LOW_STOCK = int(os.environ.get("LOW_STOCK", "3"))
REPORT_TIME = os.environ.get("REPORT_TIME", "21:00")
