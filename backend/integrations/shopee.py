"""Shopee Open Platform OAuth 2.0 client.

Reference: https://open.shopee.com/developer-guide/20 (authorization)
           https://open.shopee.com/developer-guide/16 (signing rules)
"""
import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from typing import Any

import httpx


class ShopeeError(RuntimeError):
    pass


def _now_ts() -> int:
    return int(time.time())


def _sign(partner_key: str, base: str) -> str:
    return hmac.new(partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()


def public_signed_query(partner_id: str, partner_key: str, path: str) -> dict[str, Any]:
    ts = _now_ts()
    return {
        "partner_id": partner_id,
        "timestamp": ts,
        "sign": _sign(partner_key, f"{partner_id}{path}{ts}"),
    }


def shop_signed_query(
    partner_id: str, partner_key: str, path: str, access_token: str, shop_id: str
) -> dict[str, Any]:
    ts = _now_ts()
    base = f"{partner_id}{path}{ts}{access_token}{shop_id}"
    return {
        "partner_id": partner_id,
        "timestamp": ts,
        "access_token": access_token,
        "shop_id": shop_id,
        "sign": _sign(partner_key, base),
    }


def build_authorize_url(partner_id: str, partner_key: str, redirect_uri: str) -> str:
    """Build the Shopee /api/v2/shop/auth_partner URL that the browser navigates to."""
    host = os.environ.get("SHOPEE_HOST", "https://partner.shopeemobile.com")
    path = "/api/v2/shop/auth_partner"
    q = public_signed_query(partner_id, partner_key, path)
    q["redirect"] = redirect_uri
    return f"{host}{path}?{urlencode(q)}"


async def exchange_code(
    partner_id: str, partner_key: str, code: str, shop_id: str
) -> dict[str, Any]:
    """Trade the one-shot `code` for access_token + refresh_token."""
    host = os.environ.get("SHOPEE_HOST", "https://partner.shopeemobile.com")
    path = "/api/v2/auth/token/get"
    q = public_signed_query(partner_id, partner_key, path)
    body = {"code": code, "shop_id": int(shop_id), "partner_id": int(partner_id)}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"{host}{path}", params=q, json=body)
    data = _safe_json(r)
    if data.get("error"):
        raise ShopeeError(data.get("message") or data["error"])
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "token_expires_at": datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expire_in", 14400))),
        # Shopee refresh tokens are typically valid ~30 days
        "refresh_token_expires_at": datetime.now(timezone.utc) + timedelta(days=30),
    }


async def refresh_access_token(
    partner_id: str, partner_key: str, refresh_token: str, shop_id: str
) -> dict[str, Any]:
    host = os.environ.get("SHOPEE_HOST", "https://partner.shopeemobile.com")
    path = "/api/v2/auth/access_token/get"
    q = public_signed_query(partner_id, partner_key, path)
    body = {
        "refresh_token": refresh_token,
        "shop_id": int(shop_id),
        "partner_id": int(partner_id),
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"{host}{path}", params=q, json=body)
    data = _safe_json(r)
    if data.get("error"):
        raise ShopeeError(data.get("message") or data["error"])
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "token_expires_at": datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expire_in", 14400))),
        "refresh_token_expires_at": datetime.now(timezone.utc) + timedelta(days=30),
    }


async def get_shop_info(
    partner_id: str, partner_key: str, access_token: str, shop_id: str
) -> dict[str, Any]:
    host = os.environ.get("SHOPEE_HOST", "https://partner.shopeemobile.com")
    path = "/api/v2/shop/get_shop_info"
    q = shop_signed_query(partner_id, partner_key, path, access_token, shop_id)
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{host}{path}", params=q)
    data = _safe_json(r)
    if data.get("error"):
        raise ShopeeError(data.get("message") or data["error"])
    return data


def _safe_json(r: httpx.Response) -> dict[str, Any]:
    try:
        return r.json()
    except Exception:
        raise ShopeeError(f"HTTP {r.status_code}: {r.text[:200]}")
