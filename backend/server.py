"""FastAPI entrypoint for the Multi-Store E-commerce ERP."""
import json
import logging
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from auth import create_access_token, get_current_user, verify_password  # noqa: E402
from database import SessionLocal, get_db  # noqa: E402
from labels import generate_labels_pdf  # noqa: E402
from models import InboundLog, MasterSKU, Order, SKUMapping, Setting, Store, User  # noqa: E402
from notifier import send_low_stock_alert  # noqa: E402
from schemas import (  # noqa: E402
    DashboardMetrics, InboundLogOut, InboundStockRequest, LabelBatchRequest,
    LoginRequest, MasterSKUOut, OrderDetail, OrderOut, OrderTimelineEvent,
    OrderWebhookPayload, SettingsOut, SettingsUpdate, SKUThresholdUpdate,
    StoreOut, StoreUpdate, Token, UserOut,
)
from seed import run as run_seed  # noqa: E402
from shopee_sync import start_background as start_shopee_sync  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("erp")

app = FastAPI(title="Multi-Store E-commerce ERP", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")


@app.on_event("startup")
def _startup() -> None:
    try:
        run_seed()
        logger.info("Database initialised and seeded.")
    except Exception as exc:  # pragma: no cover
        logger.exception("Seed failed: %s", exc)


start_shopee_sync(app)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@api.get("/")
def health():
    return {"status": "ok", "service": "erp-backend"}


@api.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return Token(access_token=create_access_token(user.username), username=user.username)


@api.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current


# --------------------------------------------------------------------------- #
# Stores
# --------------------------------------------------------------------------- #
@api.get("/stores", response_model=list[StoreOut])
def list_stores(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Store).order_by(Store.id).all()


@api.patch("/stores/{store_id}", response_model=StoreOut)
def update_store(
    store_id: int,
    payload: StoreUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(store, field, value)
    db.commit()
    db.refresh(store)
    return store


# --------------------------------------------------------------------------- #
# Settings (Slack webhook)
# --------------------------------------------------------------------------- #
def _get_settings_row(db: Session) -> Setting:
    row = db.query(Setting).filter(Setting.id == 1).first()
    if not row:
        row = Setting(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@api.get("/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    row = _get_settings_row(db)
    return SettingsOut(slack_webhook_url=row.slack_webhook_url)


@api.put("/settings", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    row = _get_settings_row(db)
    if payload.slack_webhook_url is not None:
        row.slack_webhook_url = payload.slack_webhook_url or None
    db.commit()
    db.refresh(row)
    return SettingsOut(slack_webhook_url=row.slack_webhook_url)


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@api.get("/dashboard/metrics", response_model=DashboardMetrics)
def dashboard_metrics(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    totals = db.query(
        func.coalesce(func.sum(Order.total_revenue), 0.0),
        func.coalesce(func.sum(Order.total_cogs), 0.0),
        func.count(Order.id),
    ).filter(Order.status != "cancelled").one()

    per_store_rows = (
        db.query(
            Store.id, Store.store_name, Store.platform_name,
            func.coalesce(func.sum(Order.total_revenue), 0.0).label("gmv"),
            func.coalesce(func.sum(Order.total_cogs), 0.0).label("cogs"),
            func.count(Order.id).label("orders"),
        )
        .outerjoin(Order, (Order.store_id == Store.id) & (Order.status != "cancelled"))
        .group_by(Store.id)
        .order_by(Store.id)
        .all()
    )
    per_store = [
        {
            "store_id": r.id,
            "store_name": r.store_name,
            "platform_name": r.platform_name,
            "gmv": round(float(r.gmv), 2),
            "cogs": round(float(r.cogs), 2),
            "profit": round(float(r.gmv) - float(r.cogs), 2),
            "orders": int(r.orders),
        }
        for r in per_store_rows
    ]
    gmv, cogs, orders = totals
    return DashboardMetrics(
        total_gmv=round(float(gmv), 2),
        total_orders=int(orders),
        total_cogs=round(float(cogs), 2),
        net_profit=round(float(gmv) - float(cogs), 2),
        per_store=per_store,
    )


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
@api.get("/orders", response_model=list[OrderOut])
def list_orders(
    platform: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Order, Store).join(Store, Store.id == Order.store_id)
    if platform:
        q = q.filter(Store.platform_name == platform)
    if status:
        q = q.filter(Order.status == status)
    q = q.order_by(Order.order_date.desc())
    result = []
    for order, store in q.all():
        result.append(OrderOut(
            id=order.id, store_id=order.store_id, store_name=store.store_name,
            platform_name=store.platform_name, marketplace_order_id=order.marketplace_order_id,
            status=order.status, total_revenue=order.total_revenue, total_cogs=order.total_cogs,
            order_date=order.order_date,
        ))
    return result


@api.get("/orders/{order_id}", response_model=OrderDetail)
def get_order(order_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    row = db.query(Order, Store).join(Store, Store.id == Order.store_id).filter(Order.id == order_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    order, store = row
    try:
        items = json.loads(order.items_json or "[]")
    except Exception:
        items = []
    timeline_raw = []
    try:
        timeline_raw = json.loads(order.timeline_json or "[]")
    except Exception:
        pass
    timeline = [OrderTimelineEvent(**e) for e in timeline_raw]
    return OrderDetail(
        id=order.id, store_id=order.store_id, store_name=store.store_name,
        platform_name=store.platform_name, marketplace_order_id=order.marketplace_order_id,
        status=order.status, total_revenue=order.total_revenue, total_cogs=order.total_cogs,
        order_date=order.order_date, buyer_name=order.buyer_name, buyer_address=order.buyer_address,
        tracking_number=order.tracking_number, items=items, timeline=timeline,
    )


@api.post("/orders/labels/pdf")
def batch_labels_pdf(
    payload: LabelBatchRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not payload.order_ids:
        raise HTTPException(status_code=400, detail="No order ids provided")
    rows = (
        db.query(Order, Store)
        .join(Store, Store.id == Order.store_id)
        .filter(Order.id.in_(payload.order_ids))
        .order_by(Order.id)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No matching orders")
    pdf = generate_labels_pdf(rows)
    filename = f"labels_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------------- #
@api.get("/inventory", response_model=list[MasterSKUOut])
def list_inventory(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(MasterSKU).order_by(MasterSKU.master_sku_code).all()


@api.patch("/inventory/{sku_id}/threshold", response_model=MasterSKUOut)
def update_threshold(
    sku_id: int, payload: SKUThresholdUpdate,
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
):
    sku = db.query(MasterSKU).filter(MasterSKU.id == sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    sku.reorder_threshold = payload.reorder_threshold
    db.commit()
    db.refresh(sku)
    return sku


@api.post("/inventory/inbound", response_model=InboundLogOut)
def add_inbound(
    payload: InboundStockRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    sku = db.query(MasterSKU).filter(MasterSKU.id == payload.master_sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="Master SKU not found")

    final_cogs = round(payload.base_cost + (payload.shipping_cost / payload.quantity), 4)
    old_qty = sku.real_stock
    old_avg = sku.average_base_cost
    new_qty = old_qty + payload.quantity
    new_avg = ((old_qty * old_avg) + (payload.quantity * final_cogs)) / new_qty if new_qty else final_cogs

    sku.real_stock = new_qty
    sku.average_base_cost = round(new_avg, 4)

    log = InboundLog(
        master_sku_id=sku.id, quantity=payload.quantity, base_cost=payload.base_cost,
        shipping_cost=payload.shipping_cost, final_cogs=final_cogs,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


# --------------------------------------------------------------------------- #
# Order webhook — deducts stock + Slack alert on low stock
# --------------------------------------------------------------------------- #
@api.post("/webhooks/orders")
def webhook_orders(payload: OrderWebhookPayload, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.id == payload.store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    total_revenue = 0.0
    total_cogs = 0.0
    items_out = []
    affected_skus: list[MasterSKU] = []

    for item in payload.items:
        mapping = (
            db.query(SKUMapping)
            .filter(
                SKUMapping.store_id == payload.store_id,
                SKUMapping.marketplace_sku_code == item.marketplace_sku_code,
            )
            .first()
        )
        if not mapping:
            raise HTTPException(status_code=400, detail=f"No mapping for marketplace SKU {item.marketplace_sku_code}")
        sku = mapping.master_sku
        prev = sku.real_stock
        sku.real_stock = prev - item.quantity
        # Alert if crossed threshold on this write
        if prev > sku.reorder_threshold and sku.real_stock <= sku.reorder_threshold:
            affected_skus.append(sku)
        total_revenue += item.unit_price * item.quantity
        total_cogs += sku.average_base_cost * item.quantity
        items_out.append({
            "master_sku_code": sku.master_sku_code,
            "product_name": sku.product_name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
        })

    now = datetime.now(timezone.utc)
    tracking = None if payload.status == "cancelled" else f"TRK{random.randint(10**11, 10**12 - 1)}"
    order = Order(
        store_id=payload.store_id,
        marketplace_order_id=payload.marketplace_order_id,
        status=payload.status,
        total_revenue=round(total_revenue, 2),
        total_cogs=round(total_cogs, 2),
        order_date=now,
        items_json=json.dumps(items_out),
        buyer_name=payload.buyer_name,
        buyer_address=payload.buyer_address,
        tracking_number=tracking,
        timeline_json=json.dumps([{"at": now.isoformat(), "status": payload.status, "note": "created via webhook"}]),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # Fire alerts (best-effort)
    alerts_sent = 0
    for sku in affected_skus:
        if send_low_stock_alert(db, sku):
            alerts_sent += 1

    return {
        "ok": True,
        "order_id": order.id,
        "marketplace_order_id": order.marketplace_order_id,
        "low_stock_alerts_sent": alerts_sent,
    }


app.include_router(api)
