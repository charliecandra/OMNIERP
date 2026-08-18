"""Slack incoming-webhook notifier for stock alerts."""
import logging
import httpx
from sqlalchemy.orm import Session
from models import Setting, MasterSKU

logger = logging.getLogger("erp.notifier")


def _get_webhook(db: Session) -> str | None:
    row = db.query(Setting).filter(Setting.id == 1).first()
    return row.slack_webhook_url if row and row.slack_webhook_url else None


def send_low_stock_alert(db: Session, sku: MasterSKU) -> bool:
    """Best-effort Slack alert; never raises to the caller."""
    url = _get_webhook(db)
    if not url:
        return False
    payload = {
        "text": (
            f":warning: *Low stock alert*\n"
            f"*SKU:* `{sku.master_sku_code}` — {sku.product_name}\n"
            f"*Current stock:* `{sku.real_stock}`   *Threshold:* `{sku.reorder_threshold}`\n"
            f"Reorder soon to avoid oversell."
        )
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.post(url, json=payload)
            return 200 <= r.status_code < 300
    except Exception as exc:  # pragma: no cover
        logger.warning("Slack webhook failed: %s", exc)
        return False
