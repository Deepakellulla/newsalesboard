import os
import pytz
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")
tz = pytz.timezone(TIMEZONE)

client = None
db = None


async def init_db():
    global client, db
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise ValueError("❌ MONGODB_URI not set in environment variables!")
    print(f"🔗 Connecting to MongoDB...")
    client = AsyncIOMotorClient(
        uri,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        tls=True,
        tlsAllowInvalidCertificates=False
    )
    db = client["salesbot"]
    await client.admin.command("ping")
    print("✅ MongoDB connected!")
    await db.sales.create_index("order_id", unique=True)
    await db.sales.create_index("buyer_username")
    await db.customers.create_index("username", unique=True)
    await db.products.create_index("name", unique=True)
    await db.tickets.create_index("ticket_id", unique=True)
    print("✅ Indexes created.")


def now():
    return datetime.now(tz)


# ── COUNTERS ──────────────────────────────────────────────────
async def next_id(name):
    doc = await db.counters.find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}},
        upsert=True, return_document=True
    )
    return doc["seq"]


async def gen_order_id():
    n = await next_id("order")
    return f"ORD{n:05d}"


async def gen_ticket_id():
    n = await next_id("ticket")
    return f"TKT{n:04d}"


# ── PRODUCTS ──────────────────────────────────────────────────
async def add_product(name, cost, sell, stock=0, category="general"):
    await db.products.update_one(
        {"name": name.lower()},
        {"$set": {"name": name.lower(), "display": name, "cost": cost,
                  "sell": sell, "stock": stock, "category": category, "active": True}},
        upsert=True
    )


async def get_products(active_only=True):
    q = {"active": True} if active_only else {}
    return await db.products.find(q).sort("category", 1).to_list(None)


async def get_product(name):
    return await db.products.find_one({"name": name.lower()})


async def update_stock(name, delta):
    await db.products.update_one({"name": name.lower()}, {"$inc": {"stock": delta}})


async def low_stock_products(threshold):
    return await db.products.find({"stock": {"$lte": threshold}, "active": True}).to_list(None)


async def delete_product(name):
    await db.products.update_one({"name": name.lower()}, {"$set": {"active": False}})


# ── SALES ─────────────────────────────────────────────────────
async def log_sale(buyer, product, sell, cost, payment="upi", duration=None, creds="", notes=""):
    order_id = await gen_order_id()
    profit = sell - cost
    await db.sales.insert_one({
        "order_id": order_id,
        "buyer_username": buyer.lstrip("@").lower(),
        "product": product.lower(),
        "sell": sell, "cost": cost, "profit": profit,
        "payment": payment, "duration": duration,
        "creds": creds, "notes": notes,
        "status": "delivered", "refunded": False,
        "created_at": now()
    })
    await update_stock(product, -1)
    await upsert_customer(buyer, sell)
    return order_id, profit


async def get_sale(order_id):
    return await db.sales.find_one({"order_id": order_id.upper()})


async def refund_sale(order_id):
    sale = await get_sale(order_id)
    if sale and not sale.get("refunded"):
        await db.sales.update_one({"order_id": order_id.upper()},
                                  {"$set": {"refunded": True, "status": "refunded"}})
        await update_stock(sale["product"], 1)
        return sale
    return None


async def update_sale_status(order_id, status):
    await db.sales.update_one({"order_id": order_id.upper()}, {"$set": {"status": status}})


async def search_sales(buyer=None, product=None, order_id=None, limit=10):
    q = {}
    if buyer:
        q["buyer_username"] = buyer.lstrip("@").lower()
    if product:
        q["product"] = product.lower()
    if order_id:
        q["order_id"] = order_id.upper()
    return await db.sales.find(q).sort("created_at", -1).limit(limit).to_list(None)


async def all_sales(limit=50):
    return await db.sales.find().sort("created_at", -1).limit(limit).to_list(None)


async def sales_stats(start=None):
    match = {"refunded": False}
    if start:
        match["created_at"] = {"$gte": start}
    pipe = [{"$match": match}, {"$group": {
        "_id": None,
        "revenue": {"$sum": "$sell"},
        "cost": {"$sum": "$cost"},
        "profit": {"$sum": "$profit"},
        "orders": {"$sum": 1}
    }}]
    r = await db.sales.aggregate(pipe).to_list(None)
    return r[0] if r else {"revenue": 0, "cost": 0, "profit": 0, "orders": 0}


async def best_products(limit=5, start=None):
    match = {"refunded": False}
    if start:
        match["created_at"] = {"$gte": start}
    pipe = [
        {"$match": match},
        {"$group": {"_id": "$product", "count": {"$sum": 1}, "revenue": {"$sum": "$sell"}}},
        {"$sort": {"count": -1}}, {"$limit": limit}
    ]
    return await db.sales.aggregate(pipe).to_list(None)


async def payment_stats(start=None):
    match = {"refunded": False}
    if start:
        match["created_at"] = {"$gte": start}
    pipe = [
        {"$match": match},
        {"$group": {"_id": "$payment", "count": {"$sum": 1}, "total": {"$sum": "$sell"}}},
        {"$sort": {"count": -1}}
    ]
    return await db.sales.aggregate(pipe).to_list(None)


# ── CUSTOMERS ─────────────────────────────────────────────────
async def upsert_customer(username, amount):
    u = username.lstrip("@").lower()
    await db.customers.update_one(
        {"username": u},
        {"$inc": {"total_spent": amount, "orders": 1},
         "$set": {"last_buy": now()},
         "$setOnInsert": {"joined": now(), "blacklisted": False,
                          "vip": False, "note": "", "wallet": 0}},
        upsert=True
    )


async def get_customer(username):
    return await db.customers.find_one({"username": username.lstrip("@").lower()})


async def top_customers(limit=10):
    return await db.customers.find({"blacklisted": False}).sort("total_spent", -1).limit(limit).to_list(None)


async def all_customers():
    return await db.customers.find().sort("total_spent", -1).to_list(None)


async def inactive_customers(days=30):
    cutoff = now() - timedelta(days=days)
    return await db.customers.find({"last_buy": {"$lt": cutoff}}).to_list(None)


async def set_blacklist(username, val):
    await db.customers.update_one({"username": username.lstrip("@").lower()},
                                  {"$set": {"blacklisted": val}})


async def set_vip(username, val):
    await db.customers.update_one({"username": username.lstrip("@").lower()},
                                  {"$set": {"vip": val}})


async def set_note(username, note):
    await db.customers.update_one({"username": username.lstrip("@").lower()},
                                  {"$set": {"note": note}})


async def add_wallet(username, amount):
    await db.customers.update_one({"username": username.lstrip("@").lower()},
                                  {"$inc": {"wallet": amount}})


# ── EXPENSES ──────────────────────────────────────────────────
async def log_expense(desc, amount, category="misc"):
    await db.expenses.insert_one({"desc": desc, "amount": amount,
                                  "category": category, "created_at": now()})


async def expense_total(start=None):
    match = {}
    if start:
        match["created_at"] = {"$gte": start}
    pipe = [{"$match": match}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
    r = await db.expenses.aggregate(pipe).to_list(None)
    return r[0]["total"] if r else 0


async def get_expenses(start=None):
    q = {}
    if start:
        q["created_at"] = {"$gte": start}
    return await db.expenses.find(q).sort("created_at", -1).to_list(None)


# ── DEBTS ─────────────────────────────────────────────────────
async def add_debt(username, amount, product, notes=""):
    await db.debts.insert_one({
        "username": username.lstrip("@").lower(),
        "amount": amount, "product": product,
        "notes": notes, "paid": False, "created_at": now()
    })


async def unpaid_debts():
    return await db.debts.find({"paid": False}).sort("created_at", -1).to_list(None)


async def mark_debt_paid(debt_id):
    from bson import ObjectId
    await db.debts.update_one({"_id": ObjectId(debt_id)}, {"$set": {"paid": True}})


# ── CREDENTIALS ───────────────────────────────────────────────
async def add_cred(product, email, password, expiry=None):
    await db.creds.insert_one({
        "product": product.lower(), "email": email,
        "password": password, "expiry": expiry,
        "assigned": False, "assigned_to": None,
        "assigned_at": None, "added_at": now()
    })


async def assign_cred(product, username):
    cred = await db.creds.find_one({"product": product.lower(), "assigned": False})
    if cred:
        await db.creds.update_one({"_id": cred["_id"]},
                                  {"$set": {"assigned": True,
                                            "assigned_to": username.lstrip("@").lower(),
                                            "assigned_at": now()}})
        return cred
    return None


async def cred_stock():
    pipe = [
        {"$group": {"_id": "$product",
                    "total": {"$sum": 1},
                    "free": {"$sum": {"$cond": [{"$eq": ["$assigned", False]}, 1, 0]}}}},
        {"$sort": {"_id": 1}}
    ]
    return await db.creds.aggregate(pipe).to_list(None)


async def expiring_creds(days=3):
    cutoff = now() + timedelta(days=days)
    return await db.creds.find({"expiry": {"$lte": cutoff}, "assigned": True}).to_list(None)


# ── SUBSCRIPTIONS ─────────────────────────────────────────────
async def add_subscription(username, product, expiry, order_id):
    await db.subs.update_one(
        {"username": username.lstrip("@").lower(), "product": product.lower()},
        {"$set": {"username": username.lstrip("@").lower(), "product": product.lower(),
                  "expiry": expiry, "order_id": order_id,
                  "reminded": False, "updated_at": now()}},
        upsert=True
    )


async def expiring_subs(days=3):
    cutoff = now() + timedelta(days=days)
    return await db.subs.find({"expiry": {"$gte": now(), "$lte": cutoff},
                               "reminded": False}).to_list(None)


async def user_subs(username):
    return await db.subs.find({"username": username.lstrip("@").lower()}).to_list(None)


async def mark_reminded(sub_id):
    from bson import ObjectId
    await db.subs.update_one({"_id": ObjectId(sub_id)}, {"$set": {"reminded": True}})


# ── COUPONS ───────────────────────────────────────────────────
async def add_coupon(code, percent, max_uses=None, expiry=None):
    await db.coupons.insert_one({
        "code": code.upper(), "percent": percent,
        "max_uses": max_uses, "uses": 0,
        "expiry": expiry, "active": True, "created_at": now()
    })


async def validate_coupon(code):
    c = await db.coupons.find_one({"code": code.upper(), "active": True})
    if not c:
        return None
    if c.get("expiry") and c["expiry"] < now():
        return None
    if c.get("max_uses") and c["uses"] >= c["max_uses"]:
        return None
    return c


async def use_coupon(code):
    await db.coupons.update_one({"code": code.upper()}, {"$inc": {"uses": 1}})


async def all_coupons():
    return await db.coupons.find({"active": True}).to_list(None)


# ── TICKETS ───────────────────────────────────────────────────
async def create_ticket(user_id, username, issue):
    tid = await gen_ticket_id()
    await db.tickets.insert_one({
        "ticket_id": tid, "user_id": user_id,
        "username": username.lstrip("@").lower(),
        "issue": issue, "status": "open",
        "created_at": now(), "resolved_at": None
    })
    return tid


async def open_tickets():
    return await db.tickets.find({"status": "open"}).sort("created_at", 1).to_list(None)


async def close_ticket(ticket_id):
    return await db.tickets.find_one_and_update(
        {"ticket_id": ticket_id.upper()},
        {"$set": {"status": "resolved", "resolved_at": now()}}
    )


async def user_tickets(username):
    return await db.tickets.find(
        {"username": username.lstrip("@").lower()}
    ).sort("created_at", -1).to_list(None)


# ── USERS ─────────────────────────────────────────────────────
async def register_user(user_id, username):
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"username": (username or "").lower(), "last_seen": now()},
         "$setOnInsert": {"joined": now()}},
        upsert=True
    )


async def all_user_ids():
    users = await db.users.find({}, {"user_id": 1}).to_list(None)
    return [u["user_id"] for u in users]


async def get_user_by_username(username):
    return await db.users.find_one({"username": username.lstrip("@").lower()})
