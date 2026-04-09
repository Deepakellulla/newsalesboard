from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import *
from utils import m, ds, stats_text
from config import ADMIN_IDS, LOW_STOCK, REPORT_TIME, TIMEZONE
from datetime import datetime, timedelta
import pytz

tz = pytz.timezone(TIMEZONE)
scheduler = AsyncIOScheduler(timezone=tz)


def start_scheduler(bot):
    hour, minute = REPORT_TIME.split(":")

    # ── DAILY REPORT ────────────────────────────────────────
    @scheduler.scheduled_job(CronTrigger(hour=int(hour), minute=int(minute)))
    async def daily_report():
        today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        s = await sales_stats(start=today)
        e = await expense_total(start=today)
        best = await best_products(3, start=today)
        top = "".join([f"  • {p['_id'].title()}: {p['count']} sold\n" for p in best]) or "  No sales yet\n"
        report = (
            f"📊 **Daily Report — {datetime.now(tz).strftime('%d %b %Y')}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{stats_text('Today', s, e)}\n\n"
            f"🏆 **Top Products:**\n{top}"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, report)
            except Exception:
                pass

    # ── LOW STOCK CHECK ─────────────────────────────────────
    @scheduler.scheduled_job(CronTrigger(hour=10, minute=0))
    async def check_low_stock():
        items = await low_stock_products(LOW_STOCK)
        if not items:
            return
        text = f"⚠️ **Low Stock Alert!**\n━━━━━━━━━━━━━━━━━━━━\n"
        for p in items:
            text += f"🔴 {p['display']} — {p['stock']} left\n"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                pass

    # ── SUBSCRIPTION EXPIRY REMINDERS ───────────────────────
    @scheduler.scheduled_job(CronTrigger(hour=9, minute=0))
    async def sub_reminders():
        subs = await expiring_subs(days=3)
        for s in subs:
            user = await get_user_by_username(s["username"])
            if user:
                days_left = (s["expiry"] - datetime.now(tz)).days
                try:
                    await bot.send_message(
                        user["user_id"],
                        f"⚠️ **Subscription Expiring Soon!**\n\n"
                        f"Your **{s['product'].title()}** expires in **{days_left} day(s)**!\n\n"
                        f"Contact admin to renew. 🙏"
                    )
                    await mark_reminded(str(s["_id"]))
                except Exception:
                    pass
            for admin_id in ADMIN_IDS:
                try:
                    days_left = (s["expiry"] - datetime.now(tz)).days
                    await bot.send_message(
                        admin_id,
                        f"🔔 **Renewal Alert**\n"
                        f"@{s['username']}'s {s['product'].title()} expires in {days_left} days!\n"
                        f"Order: `{s.get('order_id', 'N/A')}`"
                    )
                except Exception:
                    pass

    # ── CREDENTIAL EXPIRY ALERT ─────────────────────────────
    @scheduler.scheduled_job(CronTrigger(hour=8, minute=0))
    async def cred_alerts():
        creds = await expiring_creds(3)
        if not creds:
            return
        text = "🔑 **Credentials Expiring Soon!**\n━━━━━━━━━━━━━━━━━━━━\n"
        for c in creds:
            days = (c["expiry"] - datetime.now(tz)).days
            text += f"• {c['product'].title()} | {c['email']} | {days}d | @{c.get('assigned_to', '?')}\n"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                pass

    # ── WEEKLY DEBT REMINDER ────────────────────────────────
    @scheduler.scheduled_job(CronTrigger(day_of_week="mon", hour=10, minute=0))
    async def debt_reminder():
        debts = await unpaid_debts()
        if not debts:
            return
        total = sum(d["amount"] for d in debts)
        text = "📌 **Weekly Debt Reminder**\n━━━━━━━━━━━━━━━━━━━━\n"
        for d in debts:
            text += f"• @{d['username']} | {d['product'].title()} | {m(d['amount'])}\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n**Total Owed:** {m(total)}"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                pass

    scheduler.start()
    print("✅ Scheduler started.")
