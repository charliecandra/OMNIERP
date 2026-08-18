"""Batch thermal-label PDF generator (4x6 inch per label)."""
import io
import json
from datetime import datetime, timezone

from reportlab.lib.pagesizes import inch
from reportlab.lib.units import inch as UNIT
from reportlab.pdfgen import canvas


LABEL_W = 4 * UNIT
LABEL_H = 6 * UNIT


def generate_labels_pdf(orders_with_stores: list) -> bytes:
    """orders_with_stores: list of (Order, Store) SQLAlchemy tuples."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(LABEL_W, LABEL_H))

    for order, store in orders_with_stores:
        _draw_label(c, order, store)
        c.showPage()

    c.save()
    return buf.getvalue()


def _draw_label(c, order, store) -> None:
    margin = 0.25 * UNIT
    y = LABEL_H - margin

    # Header — platform + store
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y - 14, f"{store.platform_name.upper()} · {store.store_name}")
    y -= 24

    c.setStrokeColorRGB(0, 0, 0)
    c.line(margin, y, LABEL_W - margin, y)
    y -= 8

    # Order ID (mono-ish, prominent)
    c.setFont("Courier-Bold", 11)
    c.drawString(margin, y - 12, "ORDER ID")
    c.setFont("Courier-Bold", 16)
    c.drawString(margin, y - 30, order.marketplace_order_id[:26])
    y -= 44

    # Buyer
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "SHIP TO")
    y -= 12
    c.setFont("Helvetica", 11)
    c.drawString(margin, y, (order.buyer_name or "—")[:36])
    y -= 14

    c.setFont("Helvetica", 9)
    address = order.buyer_address or "Address not provided"
    for line in _wrap(address, 42):
        c.drawString(margin, y, line)
        y -= 11

    # Divider
    y -= 6
    c.line(margin, y, LABEL_W - margin, y)
    y -= 12

    # Items
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "ITEMS")
    y -= 12
    c.setFont("Courier", 9)
    try:
        items = json.loads(order.items_json or "[]")
    except Exception:
        items = []
    for it in items[:6]:
        line = f"{it.get('quantity', 0):>3} x {it.get('master_sku_code', '')[:22]}"
        c.drawString(margin, y, line)
        y -= 11

    # Barcode-esque tracking block
    y = margin + 0.9 * UNIT
    c.setFillColorRGB(0, 0, 0)
    c.rect(margin, y, LABEL_W - 2 * margin, 0.55 * UNIT, fill=True, stroke=False)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Courier-Bold", 12)
    c.drawCentredString(LABEL_W / 2, y + 0.32 * UNIT, order.tracking_number or "TRK-PENDING")
    c.setFillColorRGB(0, 0, 0)

    # Footer
    c.setFont("Helvetica-Oblique", 7)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    c.drawString(margin, margin, f"Printed {stamp} · Omni.ERP")


def _wrap(text: str, width: int):
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 <= width:
            line = f"{line} {w}".strip()
        else:
            if line:
                out.append(line)
            line = w
    if line:
        out.append(line)
    return out[:4]
