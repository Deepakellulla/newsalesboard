import asyncio
import logging
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS, BUSINESS_NAME
from database import init_db
from scheduler import start_scheduler

# Import handlers (registers them via decorators)
import admin
import customer

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)


async def main():
    # Validate required env vars
    if not API_ID or not API_HASH or not BOT_TOKEN:
        raise ValueError("❌ API_ID, API_HASH and BOT_TOKEN must be set in environment variables!")

    await init_db()

    app = Client(
        "salesbot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=dict(root=".")
    )

    async with app:
        log.info(f"✅ {BUSINESS_NAME} Bot started!")
        for admin_id in ADMIN_IDS:
            try:
                await app.send_message(admin_id, f"✅ **{BUSINESS_NAME} Bot started!**\nUse /admin to see all commands.")
            except Exception:
                pass
        start_scheduler(app)
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
