from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import *
from utils import m, d, ds, customer_receipt
from config import ADMIN_IDS, BUSINESS_NAME
from datetime import datetime
import pytz, os

tz = pytz.timezone(os.environ.get("TIMEZONE", "Asia/Kolkata"))

# ── START ─────────────────────────────────────────────────────
@Client.on_message(filters.command("start") & filters.private)
async def cmd_start(_, msg: Message):
    user = msg.from_user
    await register_user(user.id, user.username or "")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ Products", callback_data="browse"),
         InlineKeyboardButton("📦 My Orders", callback_data="myorders")],
        [InlineKeyboardButton("📋 Subscriptions", callback_data="mysubs"),
         InlineKeyboardButton("👤 My Profile", callback_data="myprofile")],
        [InlineKeyboardButton("💰 Wallet", callback_data="mywallet"),
         InlineKeyboardButton("🎟️ Coupon", callback_data="coupon")],
        [InlineKeyboardButton("🆘 Support", callback_data="support"),
         InlineKeyboardButton("❓ FAQ", callback_data="faq")],
    ])
    await msg.reply(
        f"👋 Welcome to **{BUSINESS_NAME}**!\n\n"
        f"We offer premium OTTs, Software & VPNs\nat the best prices. 🔥\n\n"
        f"Use the menu below 👇",
        reply_markup=kb
    )


@Client.on_message(filters.command("menu") & filters.private)
async def cmd_menu(_, msg: Message):
    await cmd_start(_, msg)


# ── PRODUCTS ──────────────────────────────────────────────────
async def show_products(client, target, edit=False):
    prods = await get_products()
    if not prods:
        text = "😔 No products available right now. Check back soon!"
    else:
        cats = {}
        for p in prods:
            cats.setdefault(p.get("category", "general").title(), []).append(p)
        text = f"🛍️ **{BUSINESS_NAME} — Products**\n━━━━━━━━━━━━━━━━━━━━\n"
        for cat, items in cats.items():
            text += f"\n📁 **{cat}**\n"
            for p in items:
                icon = "🟢" if p["stock"] > 0 else "🔴 (Out of Stock)"
                text += f"{icon} **{p['display']}** — {m(p['sell'])}\n"
        text += "\n━━━━━━━━━━━━━━━━━━━━\n💬 Contact admin to order!"

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="mainmenu")]])
    if edit:
        await target.edit_message_text(text, reply_markup=kb)
    else:
        await target.reply(text, reply_markup=kb)


@Client.on_message(filters.command("products") & filters.private)
async def cmd_products(client, msg: Message):
    await show_products(client, msg)


# ── MY ORDERS ─────────────────────────────────────────────────
async def show_myorders(client, target, edit=False):
    user = target.from_user
    username = user.username or str(user.id)
    sales = await search_sales(buyer=username, limit=15)
    if not sales:
        text = "📦 You have no orders yet!"
    else:
        text = "📦 **Your Orders**\n━━━━━━━━━━━━━━━━━━━━\n"
        for s in sales:
            icon = "✅" if s["status"] == "delivered" else "🔄" if s["status"] == "pending" else "❌"
            ref = " 🔴" if s.get("refunded") else ""
            text += f"{icon} `{s['order_id']}` | {s['product'].title()} | {m(s['sell'])} | {ds(s['created_at'])}{ref}\n"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="mainmenu")]])
    if edit:
        await target.edit_message_text(text, reply_markup=kb)
    else:
        await target.reply(text, reply_markup=kb)


@Client.on_message(filters.command("myorders") & filters.private)
async def cmd_myorders(client, msg: Message):
    await show_myorders(client, msg)


# ── MY SUBSCRIPTIONS ──────────────────────────────────────────
async def show_mysubs(client, target, edit=False):
    user = target.from_user
    username = user.username or str(user.id)
    subs = await user_subs(username)
    if not subs:
        text = "📋 No active subscriptions tracked yet."
    else:
        text = "📋 **Your Subscriptions**\n━━━━━━━━━━━━━━━━━━━━\n"
        now_dt = datetime.now(tz)
        for s in subs:
            exp = s.get("expiry")
            if exp:
                days = (exp - now_dt).days
                if days < 0:
                    icon, info = "🔴", "Expired!"
                elif days <= 3:
                    icon, info = "⚠️", f"{days}d left"
                else:
                    icon, info = "🟢", f"{days}d left"
            else:
                icon, info = "🟢", "Active"
            text += f"{icon} **{s['product'].title()}** | Expires: {ds(exp)} ({info})\n"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="mainmenu")]])
    if edit:
        await target.edit_message_text(text, reply_markup=kb)
    else:
        await target.reply(text, reply_markup=kb)


@Client.on_message(filters.command("mysubs") & filters.private)
async def cmd_mysubs(client, msg: Message):
    await show_mysubs(client, msg)


# ── MY PROFILE ────────────────────────────────────────────────
async def show_profile(client, target, edit=False):
    user = target.from_user
    username = user.username or str(user.id)
    c = await get_customer(username)
    if not c:
        text = "👤 No purchases yet. Browse our products to get started!"
    else:
        status = "👑 VIP Member" if c.get("vip") else "🛍️ Customer"
        text = (
            f"👤 **My Profile**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Username     : @{c['username']}\n"
            f"Status       : {status}\n"
            f"Total Orders : {c['orders']}\n"
            f"Total Spent  : {m(c['total_spent'])}\n"
            f"💰 Wallet    : {m(c.get('wallet', 0))}\n"
            f"Member Since : {ds(c['joined'])}\n"
            f"Last Purchase: {ds(c.get('last_buy'))}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="mainmenu")]])
    if edit:
        await target.edit_message_text(text, reply_markup=kb)
    else:
        await target.reply(text, reply_markup=kb)


@Client.on_message(filters.command("myprofile") & filters.private)
async def cmd_myprofile(client, msg: Message):
    await show_profile(client, msg)


# ── WALLET ────────────────────────────────────────────────────
async def show_wallet(client, target, edit=False):
    user = target.from_user
    username = user.username or str(user.id)
    c = await get_customer(username)
    bal = c.get("wallet", 0) if c else 0
    text = f"💰 **Your Wallet Balance**\n━━━━━━━━━━━━━━━━━━━━\n{m(bal)}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="mainmenu")]])
    if edit:
        await target.edit_message_text(text, reply_markup=kb)
    else:
        await target.reply(text, reply_markup=kb)


# ── COUPON CHECK ──────────────────────────────────────────────
async def show_coupon_prompt(client, target, edit=False):
    text = "🎟️ Send your coupon code as a message:\n\nExample: `SAVE20`"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="mainmenu")]])
    if edit:
        await target.edit_message_text(text, reply_markup=kb)
    else:
        await target.reply(text, reply_markup=kb)


@Client.on_message(filters.command("coupon") & filters.private)
async def cmd_coupon(_, msg: Message):
    args = msg.text.split()[1:]
    if not args:
        return await msg.reply("**Usage:** `/coupon COUPONCODE`")
    code = args[0].upper()
    c = await validate_coupon(code)
    if c:
        await msg.reply(
            f"✅ **Coupon `{code}` is valid!**\n\n"
            f"💰 Discount: **{c['percent']}% off**\n\n"
            f"Share this code with admin when placing your order."
        )
    else:
        await msg.reply("❌ Invalid or expired coupon code!")


# ── SUPPORT ───────────────────────────────────────────────────
@Client.on_message(filters.command("support") & filters.private)
async def cmd_support(_, msg: Message):
    args = msg.text.split(None, 1)
    if len(args) < 2:
        return await msg.reply(
            "**Usage:** `/support your issue here`\n\n"
            "**Example:** `/support My Netflix credentials are not working`"
        )
    user = msg.from_user
    username = user.username or str(user.id)
    issue = args[1]
    ticket_id = await create_ticket(user.id, username, issue)
    await msg.reply(
        f"✅ **Ticket `{ticket_id}` Created!**\n\n"
        f"Issue: _{issue[:100]}_\n\n"
        f"We'll get back to you shortly. 🙏"
    )
    for admin_id in ADMIN_IDS:
        try:
            await _.send_message(
                admin_id,
                f"🎫 **New Support Ticket!**\n\n"
                f"Ticket: `{ticket_id}`\n"
                f"From: @{username}\n"
                f"Issue: {issue}\n\n"
                f"Use `/close {ticket_id}` to resolve."
            )
        except Exception:
            pass


@Client.on_message(filters.command("mytickets") & filters.private)
async def cmd_mytickets(_, msg: Message):
    user = msg.from_user
    username = user.username or str(user.id)
    tickets = await user_tickets(username)
    if not tickets:
        return await msg.reply("🎫 You have no support tickets!")
    text = "🎫 **Your Tickets**\n━━━━━━━━━━━━━━━━━━━━\n"
    for t in tickets:
        icon = "✅" if t["status"] == "resolved" else "🔄"
        text += f"{icon} `{t['ticket_id']}` | {t['issue'][:40]}... | {t['status'].title()}\n"
    await msg.reply(text)


# ── FAQ ───────────────────────────────────────────────────────
async def show_faq(target, edit=False):
    text = (
        f"❓ **FAQ — {BUSINESS_NAME}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**Q: How to place an order?**\n"
        f"A: Contact admin directly on Telegram.\n\n"
        f"**Q: Payment methods?**\n"
        f"A: UPI, Cash, Crypto, Bank Transfer.\n\n"
        f"**Q: How fast is delivery?**\n"
        f"A: Within minutes after payment confirmation.\n\n"
        f"**Q: Credentials not working?**\n"
        f"A: Use `/support` to raise a ticket.\n\n"
        f"**Q: How to check my subscriptions?**\n"
        f"A: Use `/mysubs` to see all active subs.\n\n"
        f"**Q: Can I get a refund?**\n"
        f"A: Contact admin. Handled case by case.\n\n"
        f"**Q: What is Wallet?**\n"
        f"A: Store credit added by admin, used for discounts on next purchase.\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📞 Still have questions? Use `/support`"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="mainmenu")]])
    if edit:
        await target.edit_message_text(text, reply_markup=kb)
    else:
        await target.reply(text, reply_markup=kb)


@Client.on_message(filters.command("faq") & filters.private)
async def cmd_faq(_, msg: Message):
    await show_faq(msg)


# ── CALLBACK HANDLER ──────────────────────────────────────────
@Client.on_callback_query()
async def callbacks(client, cb: CallbackQuery):
    data = cb.data
    await cb.answer()

    if data == "browse":
        await show_products(client, cb, edit=True)

    elif data == "myorders":
        await show_myorders(client, cb, edit=True)

    elif data == "mysubs":
        await show_mysubs(client, cb, edit=True)

    elif data == "myprofile":
        await show_profile(client, cb, edit=True)

    elif data == "mywallet":
        await show_wallet(client, cb, edit=True)

    elif data == "coupon":
        await show_coupon_prompt(client, cb, edit=True)

    elif data == "support":
        await cb.edit_message_text(
            "🆘 **Support**\n\nUse the command below:\n\n"
            "`/support your issue here`\n\n"
            "Example:\n`/support My Netflix is not working`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="mainmenu")]])
        )

    elif data == "faq":
        await show_faq(cb, edit=True)

    elif data == "mainmenu":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍️ Products", callback_data="browse"),
             InlineKeyboardButton("📦 My Orders", callback_data="myorders")],
            [InlineKeyboardButton("📋 Subscriptions", callback_data="mysubs"),
             InlineKeyboardButton("👤 My Profile", callback_data="myprofile")],
            [InlineKeyboardButton("💰 Wallet", callback_data="mywallet"),
             InlineKeyboardButton("🎟️ Coupon", callback_data="coupon")],
            [InlineKeyboardButton("🆘 Support", callback_data="support"),
             InlineKeyboardButton("❓ FAQ", callback_data="faq")],
        ])
        await cb.edit_message_text(
            f"👋 Welcome to **{BUSINESS_NAME}**!\n\nUse the menu below 👇",
            reply_markup=kb
        )
