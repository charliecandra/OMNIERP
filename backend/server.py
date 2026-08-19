"""FastAPI entrypoint for the Multi-Store E-commerce ERP."""
import csv
import io
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
from integrations import shopee as shopee_client  # noqa: E402
from integrations import tiktok as tiktok_client  # noqa: E402
from jose import JWTError, jwt as _jwt  # noqa: E402
from labels import generate_labels_pdf  # noqa: E402
from models import InboundLog, MasterSKU, Order, SKUMapping, Setting, Store, User  # noqa: E402
from notifier import send_low_stock_alert  # noqa: E402
from schemas import (  # noqa: E402
    AuthorizeStartResponse, DashboardMetrics, InboundLogOut, InboundStockRequest,
    LabelBatchRequest, LoginRequest, MasterSKUOut, OrderDetail, OrderOut,
    OrderTimelineEvent, OrderWebhookPayload, SettingsOut, SettingsUpdate,
    SKUThresholdUpdate, StoreOut, StoreUpdate, TestConnectionResponse, Token,
    UserOut,
)
from seed import run as run_seed  # noqa: E402
from shopee_sync import start_background as start_shopee_sync  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402
from datetime import timedelta  # noqa: E402
from urllib.parse import quote  # noqa: E402

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
    rows = db.query(Store).order_by(Store.id).all()
    return [_store_to_out(s) for s in rows]


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
    return _store_to_out(store)


def _store_to_out(s: Store) -> StoreOut:
    seeded_placeholder = s.access_token in {"sh_main_token", "sh_out_token", "tt_flag_token", "tt_live_token"}
    return StoreOut(
        id=s.id, platform_name=s.platform_name, store_name=s.store_name,
        is_active=s.is_active, sync_enabled=s.sync_enabled,
        partner_id=s.partner_id, shop_id=s.shop_id, shop_cipher=s.shop_cipher,
        last_sync_at=s.last_sync_at, last_sync_status=s.last_sync_status,
        connection_status=s.connection_status or "disconnected",
        last_verified_at=s.last_verified_at, token_expires_at=s.token_expires_at,
        is_authorized=bool(s.access_token) and not seeded_placeholder,
    )


# --------------------------------------------------------------------------- #
# OAuth 2.0 — Shopee & TikTok Shop
# --------------------------------------------------------------------------- #
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = os.environ.get("JWT_ALGORITHM", "HS256")


def _oauth_state(store_id: int, platform: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    return _jwt.encode({"sid": store_id, "p": platform, "exp": exp}, JWT_SECRET, algorithm=JWT_ALG)


def _verify_state(state: str, expected_platform: str) -> int:
    try:
        payload = _jwt.decode(state, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        return -1
    if payload.get("p") != expected_platform:
        return -2
    return int(payload["sid"])


def _frontend_redirect(status: str, message: str = "") -> RedirectResponse:
    base = os.environ.get("FRONTEND_STORES_URL", "/stores")
    return RedirectResponse(f"{base}?connect={status}&msg={quote(message)}", status_code=303)


@api.get("/stores/{store_id}/oauth/start", response_model=AuthorizeStartResponse)
def oauth_start(
    store_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    state = _oauth_state(store_id, store.platform_name)

    if store.platform_name == "shopee":
        if not (store.partner_id and store.partner_key):
            raise HTTPException(status_code=400, detail="Partner ID and Partner Key are required")
        redirect_base = os.environ.get("SHOPEE_REDIRECT_URI") or f"{os.environ.get('APP_URL','')}/api/oauth/shopee/callback"
        # Encode our state into the redirect URL so Shopee sends it back
        redirect_with_state = f"{redirect_base}?state={quote(state)}"
        url = shopee_client.build_authorize_url(store.partner_id, store.partner_key, redirect_with_state)
        return AuthorizeStartResponse(authorize_url=url)

    if store.platform_name == "tiktok":
        if not (store.partner_id and store.partner_key):
            raise HTTPException(status_code=400, detail="App Key and App Secret are required")
        url = tiktok_client.build_authorize_url(store.partner_id, state)
        return AuthorizeStartResponse(authorize_url=url)

    raise HTTPException(status_code=400, detail=f"Unsupported platform: {store.platform_name}")


@api.get("/oauth/shopee/callback")
async def shopee_callback(
    code: Optional[str] = None,
    shop_id: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if error:
        return _frontend_redirect("error", error)
    if not (code and shop_id and state):
        return _frontend_redirect("error", "Missing code/shop_id/state")

    store_id = _verify_state(state, "shopee")
    if store_id < 0:
        return _frontend_redirect("error", "Invalid or platform-mismatched state")
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        return _frontend_redirect("error", "Store not found")

    try:
        tokens = await shopee_client.exchange_code(
            store.partner_id, store.partner_key, code, shop_id
        )
    except Exception as exc:
        store.connection_status = "error"
        db.commit()
        return _frontend_redirect("error", str(exc)[:200])

    store.shop_id = str(shop_id)
    store.access_token = tokens["access_token"]
    store.refresh_token = tokens["refresh_token"]
    store.token_expires_at = tokens["token_expires_at"]
    store.refresh_token_expires_at = tokens["refresh_token_expires_at"]
    store.connection_status = "active"
    store.last_verified_at = datetime.now(timezone.utc)
    db.commit()
    return _frontend_redirect("success", store.store_name)


@api.get("/oauth/tiktok/callback")
async def tiktok_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if error:
        return _frontend_redirect("error", error)
    if not (code and state):
        return _frontend_redirect("error", "Missing code or state")

    store_id = _verify_state(state, "tiktok")
    if store_id < 0:
        return _frontend_redirect("error", "Invalid or platform-mismatched state")
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        return _frontend_redirect("error", "Store not found")

    try:
        tokens = await tiktok_client.exchange_code(store.partner_id, store.partner_key, code)
    except Exception as exc:
        store.connection_status = "error"
        db.commit()
        return _frontend_redirect("error", str(exc)[:200])

    if tokens.get("shop_id"):
        store.shop_id = tokens["shop_id"]
    if tokens.get("shop_cipher"):
        store.shop_cipher = tokens["shop_cipher"]
    store.access_token = tokens["access_token"]
    store.refresh_token = tokens["refresh_token"]
    store.token_expires_at = tokens["token_expires_at"]
    store.refresh_token_expires_at = tokens["refresh_token_expires_at"]
    store.connection_status = "active"
    store.last_verified_at = datetime.now(timezone.utc)
    db.commit()
    return _frontend_redirect("success", store.store_name)


async def _ensure_fresh_token(db: Session, store: Store) -> None:
    """Refresh 5 minutes early. No-op if no tokens yet."""
    if not store.access_token or not store.token_expires_at:
        return
    now = datetime.now(timezone.utc)
    if store.token_expires_at > now + timedelta(minutes=5):
        return
    if not store.refresh_token:
        return
    try:
        if store.platform_name == "shopee":
            fresh = await shopee_client.refresh_access_token(
                store.partner_id, store.partner_key, store.refresh_token, store.shop_id
            )
        else:
            fresh = await tiktok_client.refresh_access_token(
                store.partner_id, store.partner_key, store.refresh_token
            )
        store.access_token = fresh["access_token"]
        if fresh.get("refresh_token"):
            store.refresh_token = fresh["refresh_token"]
        store.token_expires_at = fresh["token_expires_at"]
        if fresh.get("refresh_token_expires_at"):
            store.refresh_token_expires_at = fresh["refresh_token_expires_at"]
        db.commit()
    except Exception as exc:
        store.connection_status = "expired"
        store.last_sync_status = f"refresh failed: {exc}"
        db.commit()


@api.post("/stores/{store_id}/test", response_model=TestConnectionResponse)
async def test_store_connection(
    store_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    if not (store.partner_id and store.partner_key):
        raise HTTPException(status_code=400, detail="Partner credentials are not configured for this store")
    if not store.access_token:
        raise HTTPException(status_code=400, detail="Store is not authorized yet — click Connect / Authorize first")
    if store.platform_name == "shopee" and not store.shop_id:
        raise HTTPException(status_code=400, detail="Shopee shop_id is missing — complete the OAuth handshake to link a shop")

    await _ensure_fresh_token(db, store)

    try:
        if store.platform_name == "shopee":
            data = await shopee_client.get_shop_info(
                store.partner_id, store.partner_key, store.access_token, store.shop_id
            )
        else:
            data = await tiktok_client.get_authorized_shops(
                store.partner_id, store.partner_key, store.access_token
            )
    except (shopee_client.ShopeeError, tiktok_client.TikTokError) as exc:
        store.connection_status = "error"
        db.commit()
        return TestConnectionResponse(
            ok=False, platform=store.platform_name, connection_status="error",
            detail={"error": str(exc)[:300]},
        )
    except Exception as exc:
        logger.exception("Test connection unexpected error")
        store.connection_status = "error"
        db.commit()
        return TestConnectionResponse(
            ok=False, platform=store.platform_name, connection_status="error",
            detail={"error": f"Unexpected: {exc.__class__.__name__}"},
        )

    store.connection_status = "active"
    store.last_verified_at = datetime.now(timezone.utc)
    db.commit()
    return TestConnectionResponse(
        ok=True, platform=store.platform_name, connection_status="active", detail=data,
    )


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


@api.get("/orders/export.csv")
def export_orders_csv(
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
    rows = q.order_by(Order.order_date.desc()).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "order_id", "marketplace_order_id", "platform", "store", "status",
        "revenue", "cogs", "profit", "order_date_utc",
        "buyer_name", "buyer_address", "tracking_number",
    ])
    for order, store in rows:
        w.writerow([
            order.id, order.marketplace_order_id, store.platform_name, store.store_name,
            order.status, f"{order.total_revenue:.2f}", f"{order.total_cogs:.2f}",
            f"{(order.total_revenue - order.total_cogs):.2f}",
            order.order_date.isoformat() if order.order_date else "",
            order.buyer_name or "", (order.buyer_address or "").replace("\n", " "),
            order.tracking_number or "",
        ])
    filename = f"orders_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api.get("/inventory/export.csv")
def export_inventory_csv(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    skus = db.query(MasterSKU).order_by(MasterSKU.master_sku_code).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "sku_id", "master_sku_code", "product_name", "real_stock",
        "reorder_threshold", "average_base_cost", "inventory_value", "status",
    ])
    for s in skus:
        if s.real_stock < 0:
            state = "oversold"
        elif s.real_stock <= s.reorder_threshold:
            state = "reorder"
        else:
            state = "healthy"
        w.writerow([
            s.id, s.master_sku_code, s.product_name, s.real_stock,
            s.reorder_threshold, f"{s.average_base_cost:.4f}",
            f"{(s.real_stock * s.average_base_cost):.2f}", state,
        ])
    filename = f"inventory_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
