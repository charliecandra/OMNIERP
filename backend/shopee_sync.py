"""Background Shopee sync worker.

Uses the OAuth tokens saved via /api/oauth/shopee/callback. Skips any store
that has sync_enabled=False, no access_token, or missing credentials.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database import SessionLocal
from integrations import shopee as shopee_client
from models import Store

logger = logging.getLogger("erp.shopee_sync")
SYNC_INTERVAL_SECONDS = 300  # 5 minutes


async def _refresh_if_needed(db: Session, store: Store) -> None:
    if not store.token_expires_at or store.token_expires_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        return
    if not store.refresh_token:
        return
    try:
        fresh = await shopee_client.refresh_access_token(
            store.partner_id, store.partner_key, store.refresh_token, store.shop_id
        )
        store.access_token = fresh["access_token"]
        store.refresh_token = fresh["refresh_token"]
        store.token_expires_at = fresh["token_expires_at"]
        store.refresh_token_expires_at = fresh["refresh_token_expires_at"]
        db.commit()
    except Exception as exc:
        store.connection_status = "expired"
        store.last_sync_status = f"refresh failed: {exc}"[:250]
        db.commit()


async def _sync_cycle() -> None:
    db: Session = SessionLocal()
    try:
        stores = (
            db.query(Store)
            .filter(
                Store.sync_enabled.is_(True),
                Store.is_active.is_(True),
                Store.platform_name == "shopee",
            )
            .all()
        )
        for store in stores:
            if not (store.partner_id and store.partner_key and store.shop_id and store.access_token):
                store.last_sync_status = "missing credentials or not authorized"
                store.last_sync_at = datetime.now(timezone.utc)
                continue

            await _refresh_if_needed(db, store)
            try:
                data = await shopee_client.get_shop_info(
                    store.partner_id, store.partner_key, store.access_token, store.shop_id
                )
                store.connection_status = "active"
                store.last_sync_status = f"ok · shop_name={data.get('shop_name', '')[:80]}"
            except Exception as exc:
                store.connection_status = "error"
                store.last_sync_status = f"error: {exc}"[:250]
            store.last_sync_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


async def sync_loop() -> None:
    logger.info("Shopee sync worker started (interval=%ss)", SYNC_INTERVAL_SECONDS)
    while True:
        try:
            await _sync_cycle()
        except Exception as exc:  # pragma: no cover
            logger.exception("sync cycle failed: %s", exc)
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)


def start_background(app) -> None:
    @app.on_event("startup")
    async def _kick():
        asyncio.create_task(sync_loop())
