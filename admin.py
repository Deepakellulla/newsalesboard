from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_IDS, LOW_STOCK, BUSINESS_NAME, CURRENCY
from database import *
from utils import m, d, ds, receipt, stats_text
from datetime import datetime, timedelta
import pytz, io, openpyxl
import os

tz = pytz.timezone(os.environ.get("TIMEZONE", "Asia/Kolkata"))

def admin_filter(_, __, msg):
    return msg.from_user and msg.from_user.id in ADMIN_IDS

is_admin = filters.create(admin_filter)


# ── ADMIN MENU ────────────────────────────────────────────────
@Client.on_message(filters.command("admin") & is_admin)
async def admin_menu(_, msg: Message):
    text = (
        f"👑 **Admin Panel — {BUSINESS_NAME}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**💼 SALES**\n"
        f"`/sold @user product price cost [payment]` — Log sale\n"
        f"`/qs product price cost` — Quick sale (no buyer)\n"
        f"`/orders` — Recent orders\n"
        f"`/setstatus ORDID status` — Update order status\n"
        f"`/refund ORDID` — Refund order\n"
        f"`/search @user or ORDID` — Search orders\n\n"
        f"**📦 PRODUCTS**\n"
        f"`/ap name cost sell stock cat` — Add product\n"
        f"`/prods` — All products\n"
        f"`/stock product +/-qty` — Edit stock\n"
        f"`/lowstock` — Low stock alert\n"
        f"`/delprod name` — Delete product\n\n"
        f"**💰 FINANCE**\n"
        f"`/stats` — Today stats\n"
        f"`/statsw` — Weekly stats\n"
        f"`/statsm` — Monthly stats\n"
        f"`/statsa` — All time stats\n"
        f"`/addexp desc amount` — Log expense\n"
        f"`/exps` — Today expenses\n"
        f"`/adddebt @user amount product` — Add debt\n"
        f"`/debts` — Unpaid debts\n"
        f"`/payments` — Payment breakdown\n\n"
        f"**👥 CUSTOMERS**\n"
        f"`/customers` — Top customers\n"
        f"`/customer @user` — Customer profile\n"
        f"`/bl @user` — Blacklist\n"
        f"`/unbl @user` — Remove blacklist\n"
        f"`/vip @user` — Set VIP\n"
        f"`/note @user text` — Add note\n"
        f"`/wallet @user amount` — Add wallet credit\n"
        f"`/inactive` — Inactive 30d+\n\n"
        f"**🔑 CREDENTIALS**\n"
        f"`/addcred product email pass expiry` — Add cred\n"
        f"`/credstock` — Cred inventory\n"
        f"`/expcreds` — Expiring creds\n\n"
        f"**🎟️ COUPONS**\n"
        f"`/addcoupon CODE percent maxuses` — Create coupon\n"
        f"`/coupons` — All coupons\n\n"
        f"**🎫 SUPPORT**\n"
        f"`/tickets` — Open tickets\n"
        f"`/close TKTID` — Close ticket\n\n"
        f"**📊 REPORTS**\n"
        f"`/export` — Export Excel\n"
        f"`/topselling` — Best products\n"
        f"`/topcust` — Top buyers\n"
        f"`/broadcast msg` — Message all users\n"
    )
    await msg.reply(text)


# ── LOG SALE ──────────────────────────────────────────────────
@Client.on_message(filters.command("sold") & is_admin)
async def cmd_sold(_, msg: Message):
    args = msg.text.split()[1:]
    if len(args) < 4:
        return await msg.reply(
            "**Usage:** `/sold @buyer product sell cost [payment] [creds]`\n"
            "**Example:** `/sold @john netflix 149 80 upi email:pass`"
        )
    buyer, product = args[0], args[1]
    try:
        sell, cost = float(args[2]), float(args[3])
    except ValueError:
        return await msg.reply("❌ Price must be a number!")
    payment = args[4] if len(args) > 4 else "upi"
    creds = args[5] if len(args) > 5 else ""

    order_id, profit = await log_sale(buyer, product, sell, cost, payment, creds=creds)
    await msg.reply(receipt(order_id, product, sell, profit, buyer, payment, creds))

    # Notify buyer if registered
    user = await get_user_by_username(buyer)
    if user:
        try:
            await _.send_message(user["user_id"],
                                 customer_receipt(order_id, product, sell, buyer, payment, creds))
        except Exception:
            pass


@Client.on_message(filters.command("qs") & is_admin)
async def cmd_quicksale(_, msg: Message):
    args = msg.text.split()[1:]
    if len(args) < 3:
        return await msg.reply("**Usage:** `/qs product sell cost`")
    try:
        sell, cost = float(args[1]), float(args[2])
    except ValueError:
        return await msg.reply("❌ Price must be a number!")
    order_id, profit = await log_sale("unknown", args[0], sell, cost)
    await msg.reply(f"✅ Quick sale logged!\n`{order_id}` | {args[0].title()} | Profit: {m(profit)}")


# ── ORDERS ────────────────────────────────────────────────────
@Client.on_message(filters.command("orders") & is_admin)
async def cmd_orders(_, msg: Message):
    sales = await all_sales(10)
    if not sales:
        return await msg.reply("No sales yet!")
    text = "📋 **Recent Orders**\n━━━━━━━━━━━━━━━━━━━━\n"
    for s in sales:
        icon = "✅" if s["status"] == "delivered" else "🔄" if s["status"] == "pending" else "❌"
        ref = " 🔴" if s.get("refunded") else ""
        text += f"{icon} `{s['order_id']}` | @{s['buyer_username']} | {s['product'].title()} | {m(s['sell'])}{ref}\n"
    await msg.reply(text)


@Client.on_message(filters.command("setstatus") & is_admin)
async def cmd_setstatus(_, msg: Message):
    args = msg.text.split()[1:]
    if len(args) < 2:
        return await msg.reply("**Usage:** `/setstatus ORDID status`\nStatuses: pending, processing, delivered, completed")
    await update_sale_status(args[0], args[1])
    await msg.reply(f"✅ `{args[0].upper()}` → **{args[1]}**")


@Client.on_message(filters.command("refund") & is_admin)
async def cmd_refund(_, msg: Message):
    args = msg.text.split()[1:]
    if not args:
        return await msg.reply("**Usage:** `/refund ORDID`")
    sale = await refund_sale(args[0])
    if sale:
        await msg.reply(f"🔴 Refunded `{sale['order_id']}`\nProduct: {sale['product'].title()} | Amount: {m(sale['sell'])}")
    else:
        await msg.reply("❌ Order not found or already refunded!")


@Client.on_message(filters.command("search") & is_admin)
async def cmd_search(_, msg: Message):
    args = msg.text.split()[1:]
    if not args:
        return await msg.reply("**Usage:** `/search @user` or `/search ORDID` or `/search product`")
    q = args[0]
    if q.startswith("@"):
        sales = await search_sales(buyer=q)
    elif q.upper().startswith("ORD"):
        sales = await search_sales(order_id=q)
    else:
        sales = await search_sales(product=q)
    if not sales:
        return await msg.reply("No results found!")
    text = f"🔍 **Results for {q}**\n━━━━━━━━━━━━━━━━━━━━\n"
    for s in sales:
        text += f"`{s['order_id']}` | @{s['buyer_username']} | {s['product'].title()} | {m(s['sell'])} | {ds(s['created_at'])}\n"
    await msg.reply(text)


# ── PRODUCTS ──────────────────────────────────────────────────
@Client.on_message(filters.command("ap") & is_admin)
async def cmd_addproduct(_, msg: Message):
    args = msg.text.split()[1:]
    if len(args) < 3:
        return await msg.reply(
            "**Usage:** `/ap name cost sell [stock] [category]`\n"
            "**Example:** `/ap Netflix 70 149 10 ott`"
        )
    name = args[0]
    try:
        cost, sell = float(args[1]), float(args[2])
    except ValueError:
        return await msg.reply("❌ Price must be a number!")
    stock = int(args[3]) if len(args) > 3 else 0
    cat = args[4] if len(args) > 4 else "general"
    await add_product(name, cost, sell, stock, cat)
    await msg.reply(f"✅ **{name}** added!\nCost: {m(cost)} | Sell: {m(sell)} | Stock: {stock} | Cat: {cat}")


@Client.on_message(filters.command("prods") & is_admin)
async def cmd_prods(_, msg: Message):
    prods = await get_products()
    if not prods:
        return await msg.reply("No products yet!")
    cats = {}
    for p in prods:
        cats.setdefault(p.get("category", "general").title(), []).append(p)
    text = "📦 **All Products**\n━━━━━━━━━━━━━━━━━━━━\n"
    for cat, items in cats.items():
        text += f"\n📁 **{cat}**\n"
        for p in items:
            icon = "🔴" if p["stock"] <= LOW_STOCK else "🟢"
            text += f"{icon} **{p['display']}** | Cost: {m(p['cost'])} | Sell: {m(p['sell'])} | Stock: {p['stock']}\n"
    await msg.reply(text)


@Client.on_message(filters.command("stock") & is_admin)
async def cmd_stock(_, msg: Message):
    args = msg.text.split()[1:]
    if len(args) < 2:
        return await msg.reply("**Usage:** `/stock productname +5` or `-3`")
    try:
        delta = int(args[1])
    except ValueError:
        return await msg.reply("❌ Use +5 or -3 format!")
    await update_stock(args[0], delta)
    p = await get_product(args[0])
    if p:
        await msg.reply(f"✅ **{args[0].title()}** stock updated → **{p['stock']}** units")


@Client.on_message(filters.command("lowstock") & is_admin)
async def cmd_lowstock(_, msg: Message):
    items = await low_stock_products(LOW_STOCK)
    if not items:
        return await msg.reply("✅ All products have good stock!")
    text = f"⚠️ **Low Stock (≤{LOW_STOCK})**\n━━━━━━━━━━━━━━━━━━━━\n"
    for p in items:
        text += f"🔴 **{p['display']}** — {p['stock']} left\n"
    await msg.reply(text)


@Client.on_message(filters.command("delprod") & is_admin)
async def cmd_delprod(_, msg: Message):
    args = msg.text.split()[1:]
    if not args:
        return await msg.reply("**Usage:** `/delprod productname`")
    await delete_product(" ".join(args))
    await msg.reply(f"🗑️ **{' '.join(args).title()}** removed!")


# ── STATS ─────────────────────────────────────────────────────
@Client.on_message(filters.command("stats") & is_admin)
async def cmd_stats(_, msg: Message):
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    s = await sales_stats(start=today)
    e = await expense_total(start=today)
    await msg.reply(stats_text("Today's", s, e))


@Client.on_message(filters.command("statsw") & is_admin)
async def cmd_statsw(_, msg: Message):
    start = datetime.now(tz) - timedelta(days=7)
    s = await sales_stats(start=start)
    e = await expense_total(start=start)
    await msg.reply(stats_text("Weekly", s, e))


@Client.on_message(filters.command("statsm") & is_admin)
async def cmd_statsm(_, msg: Message):
    start = datetime.now(tz) - timedelta(days=30)
    s = await sales_stats(start=start)
    e = await expense_total(start=start)
    await msg.reply(stats_text("Monthly", s, e))


@Client.on_message(filters.command("statsa") & is_admin)
async def cmd_statsa(_, msg: Message):
    s = await sales_stats()
    e = await expense_total()
    await msg.reply(stats_text("All Time", s, e))


@Client.on_message(filters.command("payments") & is_admin)
async def cmd_payments(_, msg: Message):
    stats = await payment_stats()
    text = "💳 **Payment Breakdown**\n━━━━━━━━━━━━━━━━━━━━\n"
    for s in stats:
        text += f"• {s['_id'].upper()}: {s['count']} orders | {m(s['total'])}\n"
    await msg.reply(text)


# ── CUSTOMERS ─────────────────────────────────────────────────
@Client.on_message(filters.command("customers") & is_admin)
async def cmd_customers(_, msg: Message):
    custs = await top_customers(10)
    if not custs:
        return await msg.reply("No customers yet!")
    text = "👥 **Top Customers**\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, c in enumerate(custs, 1):
        vip = "👑" if c.get("vip") else ""
        text += f"{i}. @{c['username']} {vip} | {c['orders']} orders | {m(c['total_spent'])}\n"
    await msg.reply(text)


@Client.on_message(filters.command("customer") & is_admin)
async def cmd_customer(_, msg: Message):
    args = msg.text.split()[1:]
    if not args:
        return await msg.reply("**Usage:** `/customer @username`")
    c = await get_customer(args[0])
    if not c:
        return await msg.reply("❌ Customer not found!")
    sales = await search_sales(buyer=args[0], limit=5)
    vip = "👑 VIP" if c.get("vip") else ""
    bl = "🚫 BLACKLISTED" if c.get("blacklisted") else ""
    text = (
        f"👤 **Customer Profile**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Username  : @{c['username']} {vip} {bl}\n"
        f"Orders    : {c['orders']}\n"
        f"Spent     : {m(c['total_spent'])}\n"
        f"Wallet    : {m(c.get('wallet', 0))}\n"
        f"Joined    : {ds(c['joined'])}\n"
        f"Last Buy  : {ds(c.get('last_buy'))}\n"
        f"Note      : {c.get('note') or 'None'}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**Recent Orders**\n"
    )
    for s in sales:
        text += f"• `{s['order_id']}` {s['product'].title()} — {m(s['sell'])}\n"
    await msg.reply(text)


@Client.on_message(filters.command("bl") & is_admin)
async def cmd_bl(_, msg: Message):
    args = msg.text.split()[1:]
    if not args:
        return
    await set_blacklist(args[0], True)
    await msg.reply(f"🚫 @{args[0].lstrip('@')} blacklisted!")


@Client.on_message(filters.command("unbl") & is_admin)
async def cmd_unbl(_, msg: Message):
    args = msg.text.split()[1:]
    if not args:
        return
    await set_blacklist(args[0], False)
    await msg.reply(f"✅ @{args[0].lstrip('@')} removed from blacklist!")


@Client.on_message(filters.command("vip") & is_admin)
async def cmd_vip(_, msg: Message):
    args = msg.text.split()[1:]
    if not args:
        return
    await set_vip(args[0], True)
    await msg.reply(f"👑 @{args[0].lstrip('@')} is now VIP!")


@Client.on_message(filters.command("note") & is_admin)
async def cmd_note(_, msg: Message):
    args = msg.text.split()[1:]
    if len(args) < 2:
        return await msg.reply("**Usage:** `/note @user text`")
    await set_note(args[0], " ".join(args[1:]))
    await msg.reply(f"📝 Note saved for @{args[0].lstrip('@')}!")


@Client.on_message(filters.command("wallet") & is_admin)
async def cmd_wallet_admin(_, msg: Message):
    args = msg.text.split()[1:]
    if len(args) < 2:
        return await msg.reply("**Usage:** `/wallet @user amount`")
    try:
        amount = float(args[1])
    except ValueError:
        return await msg.reply("❌ Amount must be a number!")
    await add_wallet(args[0], amount)
    await msg.reply(f"💰 {m(amount)} added to @{args[0].lstrip('@')}'s wallet!")


@Client.on_message(filters.command("inactive") & is_admin)
async def cmd_inactive(_, msg: Message):
    custs = await inactive_customers(30)
    if not custs:
        return await msg.reply("No inactive customers!")
    text = "😴 **Inactive Customers (30d+)**\n━━━━━━━━━━━━━━━━━━━━\n"
    for c in custs[:15]:
        text += f"• @{c['username']} | Last: {ds(c.get('last_buy'))}\n"
    await msg.reply(text)


# ── EXPENSES ──────────────────────────────────────────────────
@Client.on_message(filters.command("addexp") & is_admin)
async def cmd_addexp(_, msg: Message):
    args = msg.text.split()[1:]
    if len(args) < 2:
        return await msg.reply("**Usage:** `/addexp description amount`")
    try:
        amount = float(args[-1])
        desc = " ".join(args[:-1])
    except ValueError:
        return await msg.reply("❌ Amount must be a number!")
    await log_expense(desc, amount)
    await msg.reply(f"💸 Expense logged: **{desc}** — {m(amount)}")


@Client.on_message(filters.command("exps") & is_admin)
async def cmd_exps(_, msg: Message):
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    exps = await get_expenses(start=today)
    total = await expense_total(start=today)
    if not exps:
        return await msg.reply("No expenses today!")
    text = "💸 **Today's Expenses**\n━━━━━━━━━━━━━━━━━━━━\n"
    for e in exps:
        text += f"• {e['desc']} — {m(e['amount'])}\n"
    text += f"━━━━━━━━━━━━━━━━━━━━\n**Total:** {m(total)}"
    await msg.reply(text)


# ── DEBTS ─────────────────────────────────────────────────────
@Client.on_message(filters.command("adddebt") & is_admin)
async def cmd_adddebt(_, msg: Message):
    args = msg.text.split()[1:]
    if len(args) < 3:
        return await msg.reply("**Usage:** `/adddebt @user amount product`")
    try:
        amount = float(args[1])
    except ValueError:
        return await msg.reply("❌ Amount must be a number!")
    await add_debt(args[0], amount, args[2])
    await msg.reply(f"📌 Debt: @{args[0].lstrip('@')} owes {m(amount)} for {args[2].title()}")


@Client.on_message(filters.command("debts") & is_admin)
async def cmd_debts(_, msg: Message):
    debts = await unpaid_debts()
    if not debts:
        return await msg.reply("✅ No unpaid debts!")
    text = "📌 **Unpaid Debts**\n━━━━━━━━━━━━━━━━━━━━\n"
    total = 0
    for d in debts:
        text += f"• @{d['username']} | {d['product'].title()} | {m(d['amount'])}\n"
        total += d["amount"]
    text += f"━━━━━━━━━━━━━━━━━━━━\n**Total Owed:** {m(total)}"
    await msg.reply(text)


# ── CREDENTIALS ───────────────────────────────────────────────
@Client.on_message(filters.command("addcred") & is_admin)
async def cmd_addcred(_, msg: Message):
    args = msg.text.split()[1:]
    if len(args) < 3:
        return await msg.reply("**Usage:** `/addcred product email password [expiry YYYY-MM-DD]`")
    product, email, password = args[0], args[1], args[2]
    expiry = None
    if len(args) > 3:
        try:
            expiry = tz.localize(datetime.strptime(args[3], "%Y-%m-%d"))
        except ValueError:
            pass
    await add_cred(product, email, password, expiry)
    await msg.reply(f"🔑 Credential added for **{product.title()}**!")


@Client.on_message(filters.command("credstock") & is_admin)
async def cmd_credstock(_, msg: Message):
    stock = await cred_stock()
    if not stock:
        return await msg.reply("No credentials stored!")
    text = "🔑 **Credential Stock**\n━━━━━━━━━━━━━━━━━━━━\n"
    for s in stock:
        text += f"• {s['_id'].title()}: {s['free']} free / {s['total']} total\n"
    await msg.reply(text)


@Client.on_message(filters.command("expcreds") & is_admin)
async def cmd_expcreds(_, msg: Message):
    creds = await expiring_creds(3)
    if not creds:
        return await msg.reply("✅ No credentials expiring soon!")
    text = "⚠️ **Expiring Credentials (3 days)**\n━━━━━━━━━━━━━━━━━━━━\n"
    for c in creds:
        text += f"• {c['product'].title()} | {c['email']} | Expires: {ds(c.get('expiry'))} | @{c.get('assigned_to', '?')}\n"
    await msg.reply(text)


# ── COUPONS ───────────────────────────────────────────────────
@Client.on_message(filters.command("addcoupon") & is_admin)
async def cmd_addcoupon(_, msg: Message):
    args = msg.text.split()[1:]
    if len(args) < 2:
        return await msg.reply("**Usage:** `/addcoupon CODE percent [maxuses]`")
    code, percent = args[0].upper(), float(args[1])
    max_uses = int(args[2]) if len(args) > 2 else None
    await add_coupon(code, percent, max_uses)
    await msg.reply(f"🎟️ Coupon `{code}` created! {percent}% off" +
                    (f", max {max_uses} uses" if max_uses else ""))


@Client.on_message(filters.command("coupons") & is_admin)
async def cmd_coupons(_, msg: Message):
    coupons = await all_coupons()
    if not coupons:
        return await msg.reply("No active coupons!")
    text = "🎟️ **Active Coupons**\n━━━━━━━━━━━━━━━━━━━━\n"
    for c in coupons:
        uses = f"{c['uses']}/{c['max_uses']}" if c.get("max_uses") else f"{c['uses']}/∞"
        text += f"• `{c['code']}` — {c['percent']}% off | Uses: {uses}\n"
    await msg.reply(text)


# ── TICKETS ───────────────────────────────────────────────────
@Client.on_message(filters.command("tickets") & is_admin)
async def cmd_tickets(_, msg: Message):
    tickets = await open_tickets()
    if not tickets:
        return await msg.reply("✅ No open tickets!")
    text = "🎫 **Open Tickets**\n━━━━━━━━━━━━━━━━━━━━\n"
    for t in tickets:
        text += f"• `{t['ticket_id']}` | @{t['username']} | {t['issue'][:50]}\n"
    text += "\nUse `/close TKTID` to resolve"
    await msg.reply(text)


@Client.on_message(filters.command("close") & is_admin)
async def cmd_close(client, msg: Message):
    args = msg.text.split()[1:]
    if not args:
        return await msg.reply("**Usage:** `/close TKTID`")
    ticket = await close_ticket(args[0])
    if ticket:
        await msg.reply(f"✅ Ticket `{args[0].upper()}` resolved!")
        user = await get_user_by_username(ticket["username"])
        if user:
            try:
                await client.send_message(
                    user["user_id"],
                    f"✅ Your support ticket `{args[0].upper()}` has been resolved!\nThank you for your patience. 🙏"
                )
            except Exception:
                pass
    else:
        await msg.reply("❌ Ticket not found!")


# ── BROADCAST ─────────────────────────────────────────────────
@Client.on_message(filters.command("broadcast") & is_admin)
async def cmd_broadcast(client, msg: Message):
    args = msg.text.split(None, 1)
    if len(args) < 2:
        return await msg.reply("**Usage:** `/broadcast your message here`")
    message = args[1]
    user_ids = await all_user_ids()
    sent = failed = 0
    status = await msg.reply(f"📢 Broadcasting to {len(user_ids)} users...")
    for uid in user_ids:
        try:
            await client.send_message(uid, f"📢 **{BUSINESS_NAME}**\n\n{message}")
            sent += 1
        except Exception:
            failed += 1
    await status.edit(f"📢 Broadcast done!\n✅ {sent} sent | ❌ {failed} failed")


# ── REPORTS ───────────────────────────────────────────────────
@Client.on_message(filters.command("topselling") & is_admin)
async def cmd_topselling(_, msg: Message):
    prods = await best_products(5)
    text = "🏆 **Top Selling Products**\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, p in enumerate(prods, 1):
        text += f"{i}. **{p['_id'].title()}** — {p['count']} sold | {m(p['revenue'])}\n"
    await msg.reply(text)


@Client.on_message(filters.command("topcust") & is_admin)
async def cmd_topcust(_, msg: Message):
    custs = await top_customers(10)
    text = "🏆 **Top Customers**\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, c in enumerate(custs, 1):
        vip = "👑" if c.get("vip") else ""
        text += f"{i}. @{c['username']} {vip} | {c['orders']} orders | {m(c['total_spent'])}\n"
    await msg.reply(text)


@Client.on_message(filters.command("export") & is_admin)
async def cmd_export(_, msg: Message):
    await msg.reply("⏳ Generating Excel report...")
    sales = await all_sales(1000)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["Order ID", "Buyer", "Product", "Sell", "Cost", "Profit", "Payment", "Status", "Date"])
    for s in sales:
        ws.append([s["order_id"], s["buyer_username"], s["product"].title(),
                   s["sell"], s["cost"], s["profit"],
                   s.get("payment", ""), s["status"], ds(s["created_at"])])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    await msg.reply_document(
        buf,
        file_name=f"sales_{datetime.now(tz).strftime('%Y%m%d')}.xlsx",
        caption="📊 Sales Export Ready!"
    )
