"""Seed the ERP database + additive migrations for legacy tables (idempotent)."""
import json
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Base, engine, SessionLocal
from models import User, Store, MasterSKU, SKUMapping, Order, InboundLog, Setting
from auth import hash_password


ADDITIVE_MIGRATIONS = [
    # Store
    "ALTER TABLE stores ADD COLUMN IF NOT EXISTS partner_id VARCHAR(64)",
    "ALTER TABLE stores ADD COLUMN IF NOT EXISTS partner_key VARCHAR(255)",
    "ALTER TABLE stores ADD COLUMN IF NOT EXISTS shop_id VARCHAR(64)",
    "ALTER TABLE stores ADD COLUMN IF NOT EXISTS sync_enabled BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE stores ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ",
    "ALTER TABLE stores ADD COLUMN IF NOT EXISTS last_sync_status VARCHAR(255)",
    # MasterSKU
    "ALTER TABLE master_skus ADD COLUMN IF NOT EXISTS reorder_threshold INTEGER NOT NULL DEFAULT 50",
    # Orders
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS buyer_name VARCHAR(128)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS buyer_address TEXT",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS tracking_number VARCHAR(64)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS timeline_json TEXT",
]


BUYERS = [
    ("Adit Pratama",   "Jl. Kemang Raya 42, Jakarta Selatan 12730, Indonesia"),
    ("Nur Aisyah",     "Blok G-3-15, Jalan Cheras Perdana, Kuala Lumpur 43200, Malaysia"),
    ("Charlie Reyes",  "1234 Ayala Ave, Makati, Metro Manila 1226, Philippines"),
    ("Danielle Tan",   "Blk 128 Bedok North Ave 4 #08-215, Singapore 460128"),
    ("Ethan Wong",     "88 Nathan Road, Tsim Sha Tsui, Kowloon, Hong Kong"),
    ("Farah Idris",    "34 Jalan Bukit Bintang, Kuala Lumpur 55100, Malaysia"),
]


def _timeline_for(status: str, order_date: datetime) -> list[dict]:
    seq = ["pending", "packed", "shipped", "delivered"]
    events = []
    t = order_date
    for s in seq:
        events.append({"at": t.isoformat(), "status": s, "note": None})
        if s == status:
            break
        t = t + timedelta(hours=random.randint(4, 20))
    if status == "cancelled":
        events = [
            {"at": order_date.isoformat(), "status": "pending", "note": None},
            {"at": (order_date + timedelta(hours=2)).isoformat(), "status": "cancelled", "note": "Buyer cancelled"},
        ]
    return events


def _seed(db: Session) -> None:
    # ---- Admin user ----
    if not db.query(User).filter(User.username == "admin").first():
        db.add(User(username="admin", hashed_password=hash_password("admin")))
        db.commit()

    # ---- Settings row ----
    if not db.query(Setting).filter(Setting.id == 1).first():
        db.add(Setting(id=1, slack_webhook_url=None))
        db.commit()

    # ---- Stores ----
    if db.query(Store).count() == 0:
        db.add_all([
            Store(platform_name="shopee", store_name="Shopee Main SG",   api_key="sh_main_key",  api_secret="sh_main_secret",  access_token="sh_main_token"),
            Store(platform_name="shopee", store_name="Shopee Outlet MY", api_key="sh_out_key",   api_secret="sh_out_secret",   access_token="sh_out_token"),
            Store(platform_name="tiktok", store_name="TikTok Flagship ID", api_key="tt_flag_key", api_secret="tt_flag_secret", access_token="tt_flag_token"),
            Store(platform_name="tiktok", store_name="TikTok Live PH",     api_key="tt_live_key", api_secret="tt_live_secret", access_token="tt_live_token"),
        ])
        db.commit()

    # ---- Master SKUs ----
    if db.query(MasterSKU).count() == 0:
        db.add_all([
            MasterSKU(master_sku_code="SKU-TEE-BLK-M",   product_name="Essential Tee Black M",   real_stock=320, average_base_cost=4.20, reorder_threshold=80),
            MasterSKU(master_sku_code="SKU-TEE-WHT-L",   product_name="Essential Tee White L",   real_stock=180, average_base_cost=4.10, reorder_threshold=60),
            MasterSKU(master_sku_code="SKU-HOOD-NVY-M",  product_name="Classic Hoodie Navy M",   real_stock=95,  average_base_cost=11.80, reorder_threshold=40),
            MasterSKU(master_sku_code="SKU-CAP-CAM-U",   product_name="Camo Cap Unisex",         real_stock=240, average_base_cost=2.90, reorder_threshold=80),
            MasterSKU(master_sku_code="SKU-SOCK-BLK-P3", product_name="Crew Socks Black 3-Pack", real_stock=520, average_base_cost=1.70, reorder_threshold=150),
            MasterSKU(master_sku_code="SKU-BAG-CVS-M",   product_name="Canvas Tote Bag M",       real_stock=140, average_base_cost=3.60, reorder_threshold=60),
            MasterSKU(master_sku_code="SKU-WATCH-STL-U", product_name="Steel Minimalist Watch",  real_stock=42,  average_base_cost=18.20, reorder_threshold=25),
            MasterSKU(master_sku_code="SKU-EARBUD-BT5",  product_name="Wireless Earbuds BT5",    real_stock=76,  average_base_cost=9.40, reorder_threshold=30),
        ])
        db.commit()

    # ---- Mappings ----
    if db.query(SKUMapping).count() == 0:
        stores = db.query(Store).all()
        skus = db.query(MasterSKU).all()
        for store in stores:
            prefix = "SHP" if store.platform_name == "shopee" else "TT"
            for sku in skus:
                db.add(SKUMapping(
                    store_id=store.id, master_sku_id=sku.id,
                    marketplace_sku_code=f"{prefix}-{store.id}-{sku.master_sku_code.split('-', 1)[1]}",
                ))
        db.commit()

    # ---- Dummy orders with buyer + tracking + timeline ----
    if db.query(Order).count() == 0:
        stores = db.query(Store).all()
        skus = db.query(MasterSKU).all()
        statuses = ["pending", "packed", "shipped", "delivered", "cancelled"]
        random.seed(42)
        now = datetime.now(timezone.utc)
        for i in range(60):
            store = random.choice(stores)
            picked = random.sample(skus, k=random.randint(1, 3))
            items, revenue, cogs = [], 0.0, 0.0
            for s in picked:
                qty = random.randint(1, 4)
                unit_price = round(s.average_base_cost * random.uniform(2.2, 3.6), 2)
                items.append({"master_sku_code": s.master_sku_code, "product_name": s.product_name, "quantity": qty, "unit_price": unit_price})
                revenue += unit_price * qty
                cogs += s.average_base_cost * qty
            order_date = now - timedelta(days=random.randint(0, 13), hours=random.randint(0, 23))
            status = random.choice(statuses)
            buyer_name, buyer_addr = random.choice(BUYERS)
            db.add(Order(
                store_id=store.id,
                marketplace_order_id=f"{store.platform_name.upper()}-{store.id}-{random.randint(100000, 999999)}",
                status=status,
                total_revenue=round(revenue, 2),
                total_cogs=round(cogs, 2),
                order_date=order_date,
                items_json=json.dumps(items),
                buyer_name=buyer_name,
                buyer_address=buyer_addr,
                tracking_number=f"TRK{random.randint(10**11, 10**12 - 1)}" if status != "cancelled" else None,
                timeline_json=json.dumps(_timeline_for(status, order_date)),
            ))
        db.commit()

    # ---- Backfill missing buyer/tracking/timeline on any legacy rows ----
    random.seed(7)
    legacy = db.query(Order).filter((Order.buyer_name.is_(None)) | (Order.timeline_json.is_(None))).all()
    for o in legacy:
        if not o.buyer_name:
            n, a = random.choice(BUYERS)
            o.buyer_name = n
            o.buyer_address = a
        if not o.tracking_number and o.status != "cancelled":
            o.tracking_number = f"TRK{random.randint(10**11, 10**12 - 1)}"
        if not o.timeline_json:
            o.timeline_json = json.dumps(_timeline_for(o.status, o.order_date))
    if legacy:
        db.commit()

    # ---- Sample inbound log ----
    if db.query(InboundLog).count() == 0:
        first_sku = db.query(MasterSKU).first()
        if first_sku:
            db.add(InboundLog(master_sku_id=first_sku.id, quantity=100, base_cost=4.00, shipping_cost=50.0, final_cogs=4.50))
            db.commit()


def run() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for stmt in ADDITIVE_MIGRATIONS:
            conn.execute(text(stmt))
    db = SessionLocal()
    try:
        _seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    run()
    print("Seeded successfully.")
