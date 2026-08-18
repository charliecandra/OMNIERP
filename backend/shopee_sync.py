"""Background Shopee sync worker.

The full HMAC-signed Shopee Open API flow is scaffolded here but the worker
skips any store whose `sync_enabled` is False or which is missing partner_id /
partner_key / shop_id. A store operator pastes those keys via
`PATCH /api/stores/{id}` and toggles `sync_enabled=true` to go live.
"""
import asyncio
import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Store

logger = logging.getLogger("erp.shopee_sync")

SHOPEE_HOST = "https://partner.shopeemobile.com"
SYNC_INTERVAL_SECONDS = 300  # 5 minutes


def _sign(partner_id: str, path: str, timestamp: int, partner_key: str) -> str:
    base = f"{partner_id}{path}{timestamp}"
    return hmac.new(partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()


async def _pull_orders_for_store(store: Store) -> tuple[bool, str]:
    """Placeholder for the Shopee /order/get_order_list call.

    Returns (ok, message). Real integration should:
      1. Refresh access_token if expired (Shopee returns 14-day tokens).
      2. Call /api/v2/order/get_order_list with `time_range_field=create_time`.
      3. For each order call /api/v2/order/get_order_detail and upsert Order rows.
      4. Deduct stock via existing internal webhook logic.
    """
    path = "/api/v2/order/get_order_list"
    ts = int(time.time())
    sign = _sign(store.partner_id or "", path, ts, store.partner_key or "")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{SHOPEE_HOST}{path}",
                params={
                    "partner_id": store.partner_id,
                    "shop_id": store.shop_id,
                    "timestamp": ts,
                    "sign": sign,
                    "access_token": store.access_token,
                    "time_range_field": "create_time",
                    "time_from": ts - 3600,
                    "time_to": ts,
                    "page_size": 50,
                },
            )
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}"
        return True, "ok"
    except httpx.RequestError as exc:
        return False, f"network: {exc.__class__.__name__}"


def _sync_cycle_sync() -> None:
    """One pass over all active, sync-enabled stores (synchronous wrapper)."""
    db: Session = SessionLocal()
    try:
        stores = (
            db.query(Store)
            .filter(Store.sync_enabled.is_(True), Store.is_active.is_(True))
            .all()
        )
        for store in stores:
            if not (store.partner_id and store.partner_key and store.shop_id):
                store.last_sync_status = "missing credentials"
                store.last_sync_at = datetime.now(timezone.utc)
                continue
            ok, msg = asyncio.run(_pull_orders_for_store(store))
            store.last_sync_at = datetime.now(timezone.utc)
            store.last_sync_status = msg if ok else f"error: {msg}"
        db.commit()
    finally:
        db.close()


async def sync_loop() -> None:
    logger.info("Shopee sync worker started (interval=%ss)", SYNC_INTERVAL_SECONDS)
    while True:
        try:
            _sync_cycle_sync()
        except Exception as exc:  # pragma: no cover
            logger.exception("sync cycle failed: %s", exc)
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)


def start_background(app) -> None:
    """Attach the loop to FastAPI startup."""
    @app.on_event("startup")
    async def _kick():
        asyncio.create_task(sync_loop())
