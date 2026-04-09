from datetime import datetime
import pytz
import os

CURRENCY = os.environ.get("CURRENCY", "₹")
BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "My Digital Store")
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")
tz = pytz.timezone(TIMEZONE)


def m(amount):
    """Format money"""
    return f"{CURRENCY}{amount:,.2f}"


def d(dt):
    """Format datetime"""
    if not dt:
        return "N/A"
    if hasattr(dt, "tzinfo") and dt.tzinfo is None:
        dt = tz.localize(dt)
    return dt.strftime("%d %b %Y %I:%M %p")


def ds(dt):
    """Format date short"""
    if not dt:
        return "N/A"
    return dt.strftime("%d %b %Y")


def receipt(order_id, product, sell, profit, buyer, payment, creds=""):
    text = (
        f"🧾 **RECEIPT — {BUSINESS_NAME}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Order ID : `{order_id}`\n"
        f"🛍️ Product  : {product.title()}\n"
        f"👤 Buyer    : @{buyer.lstrip('@')}\n"
        f"💳 Payment  : {payment.upper()}\n"
        f"💰 Amount   : {m(sell)}\n"
        f"📈 Profit   : {m(profit)}\n"
        f"📅 Date     : {d(datetime.now(tz))}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    if creds:
        text += f"🔑 Creds    : `{creds}`\n━━━━━━━━━━━━━━━━━━━━\n"
    text += "✅ Delivered!"
    return text


def customer_receipt(order_id, product, sell, buyer, payment, creds=""):
    text = (
        f"🧾 **ORDER CONFIRMED — {BUSINESS_NAME}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Order ID : `{order_id}`\n"
        f"🛍️ Product  : {product.title()}\n"
        f"💳 Payment  : {payment.upper()}\n"
        f"💰 Amount   : {m(sell)}\n"
        f"📅 Date     : {d(datetime.now(tz))}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    if creds:
        text += f"🔑 Your Login:\n`{creds}`\n━━━━━━━━━━━━━━━━━━━━\n"
    text += "✅ Thank you! Use /support if any issues."
    return text


def stats_text(label, s, expenses=0):
    net = s["profit"] - expenses
    return (
        f"📊 **{label} Stats**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Orders       : {s['orders']}\n"
        f"💵 Revenue      : {m(s['revenue'])}\n"
        f"💸 Cost         : {m(s['cost'])}\n"
        f"📈 Gross Profit : {m(s['profit'])}\n"
        f"🧾 Expenses     : {m(expenses)}\n"
        f"💰 Net Profit   : {m(net)}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
