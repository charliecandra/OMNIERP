"""Seed the ERP database with an admin user, stores, SKUs, mappings and dummy orders.

Idempotent: safe to run repeatedly. Called automatically on backend startup.
"""
import json
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database import Base, engine, SessionLocal
from models import User, Store, MasterSKU, SKUMapping, Order, InboundLog
from auth import hash_password


def _seed(db: Session) -> None:
    # ---- Admin user ----
    if not db.query(User).filter(User.username == "admin").first():
        db.add(User(username="admin", hashed_password=hash_password("admin")))
        db.commit()

    # ---- Stores (2 Shopee + 2 TikTok) ----
    if db.query(Store).count() == 0:
        stores = [
            Store(platform_name="shopee", store_name="Shopee Main SG", api_key="sh_main_key", api_secret="sh_main_secret", access_token="sh_main_token"),
            Store(platform_name="shopee", store_name="Shopee Outlet MY", api_key="sh_out_key", api_secret="sh_out_secret", access_token="sh_out_token"),
            Store(platform_name="tiktok", store_name="TikTok Flagship ID", api_key="tt_flag_key", api_secret="tt_flag_secret", access_token="tt_flag_token"),
            Store(platform_name="tiktok", store_name="TikTok Live PH", api_key="tt_live_key", api_secret="tt_live_secret", access_token="tt_live_token"),
        ]
        db.add_all(stores)
        db.commit()

    # ---- Master SKUs ----
    if db.query(MasterSKU).count() == 0:
        skus = [
            MasterSKU(master_sku_code="SKU-TEE-BLK-M",  product_name="Essential Tee Black M",  real_stock=320, average_base_cost=4.20),
            MasterSKU(master_sku_code="SKU-TEE-WHT-L",  product_name="Essential Tee White L",  real_stock=180, average_base_cost=4.10),
            MasterSKU(master_sku_code="SKU-HOOD-NVY-M", product_name="Classic Hoodie Navy M",  real_stock=95,  average_base_cost=11.80),
            MasterSKU(master_sku_code="SKU-CAP-CAM-U",  product_name="Camo Cap Unisex",         real_stock=240, average_base_cost=2.90),
            MasterSKU(master_sku_code="SKU-SOCK-BLK-P3",product_name="Crew Socks Black 3-Pack",real_stock=520, average_base_cost=1.70),
            MasterSKU(master_sku_code="SKU-BAG-CVS-M",  product_name="Canvas Tote Bag M",      real_stock=140, average_base_cost=3.60),
            MasterSKU(master_sku_code="SKU-WATCH-STL-U",product_name="Steel Minimalist Watch", real_stock=42,  average_base_cost=18.20),
            MasterSKU(master_sku_code="SKU-EARBUD-BT5", product_name="Wireless Earbuds BT5",   real_stock=76,  average_base_cost=9.40),
        ]
        db.add_all(skus)
        db.commit()

    # ---- Mappings: each store gets a marketplace SKU for every master SKU ----
    if db.query(SKUMapping).count() == 0:
        stores = db.query(Store).all()
        skus = db.query(MasterSKU).all()
        for store in stores:
            prefix = "SHP" if store.platform_name == "shopee" else "TT"
            for sku in skus:
                mp_code = f"{prefix}-{store.id}-{sku.master_sku_code.split('-', 1)[1]}"
                db.add(SKUMapping(store_id=store.id, master_sku_id=sku.id, marketplace_sku_code=mp_code))
        db.commit()

    # ---- Dummy orders across last 14 days ----
    if db.query(Order).count() == 0:
        stores = db.query(Store).all()
        skus = db.query(MasterSKU).all()
        statuses = ["pending", "packed", "shipped", "delivered", "cancelled"]
        random.seed(42)
        now = datetime.now(timezone.utc)
        for _ in range(60):
            store = random.choice(stores)
            picked = random.sample(skus, k=random.randint(1, 3))
            items, revenue, cogs = [], 0.0, 0.0
            for s in picked:
                qty = random.randint(1, 4)
                unit_price = round(s.average_base_cost * random.uniform(2.2, 3.6), 2)
                items.append({"master_sku_code": s.master_sku_code, "quantity": qty, "unit_price": unit_price})
                revenue += unit_price * qty
                cogs += s.average_base_cost * qty
            order_date = now - timedelta(days=random.randint(0, 13), hours=random.randint(0, 23))
            db.add(Order(
                store_id=store.id,
                marketplace_order_id=f"{store.platform_name.upper()}-{store.id}-{random.randint(100000, 999999)}",
                status=random.choice(statuses),
                total_revenue=round(revenue, 2),
                total_cogs=round(cogs, 2),
                order_date=order_date,
                items_json=json.dumps(items),
            ))
        db.commit()

    # ---- Sample inbound log ----
    if db.query(InboundLog).count() == 0:
        first_sku = db.query(MasterSKU).first()
        if first_sku:
            db.add(InboundLog(
                master_sku_id=first_sku.id,
                quantity=100,
                base_cost=4.00,
                shipping_cost=50.0,
                final_cogs=4.50,
            ))
            db.commit()


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    run()
    print("Seeded successfully.")
