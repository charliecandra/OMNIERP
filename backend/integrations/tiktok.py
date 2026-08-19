"""TikTok Shop Open API OAuth 2.0 client.

Auth host (token exchange & refresh):  https://auth.tiktok-shops.com
API host (authenticated shop APIs):    https://open-api.tiktokglobalshop.com
Authorize (browser):                   https://services.tiktokshop.com/open/authorize
Reference: https://partner.tiktokshop.com/docv2/page/authorization-overview-202407
           https://partner.tiktokshop.com/docv2/page/sign-your-api-request
"""
import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from typing import Any

import httpx


class TikTokError(RuntimeError):
    pass


def build_authorize_url(app_key: str, state: str) -> str:
    base = os.environ.get("TIKTOK_AUTH_BASE", "https://services.tiktokshop.com/open/authorize")
    return f"{base}?{urlencode({'app_key': app_key, 'state': state})}"


def _sign_request(app_secret: str, path: str, params: dict[str, Any], body: bytes) -> str:
    """HMAC-SHA256(app_secret, app_secret + path + sorted_query_concat + body + app_secret)."""
    pairs = [(str(k), str(v)) for k, v in params.items()
             if k not in ("sign", "access_token") and v is not None]
    pairs.sort(key=lambda x: x[0])
    query_concat = "".join(k + v for k, v in pairs)
    message = (app_secret + path + query_concat).encode() + body + app_secret.encode()
    return hmac.new(app_secret.encode(), message, hashlib.sha256).hexdigest()


async def exchange_code(app_key: str, app_secret: str, auth_code: str) -> dict[str, Any]:
    if not (app_key and app_secret and auth_code):
        raise TikTokError("Missing app_key/app_secret/auth_code")
    base = os.environ.get("TIKTOK_AUTH_API_BASE", "https://auth.tiktok-shops.com")
    path = "/api/v2/token/get"
    params = {
        "app_key": app_key,
        "app_secret": app_secret,
        "auth_code": auth_code,
        "grant_type": "authorized_code",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{base}{path}", params=params)
    payload = _safe_json(r)
    data = payload.get("data") or payload
    if not data.get("access_token"):
        raise TikTokError(payload.get("message") or data.get("message") or "TikTok token exchange failed")
    return _parse_token_payload(data)


async def refresh_access_token(app_key: str, app_secret: str, refresh_token: str) -> dict[str, Any]:
    if not (app_key and app_secret and refresh_token):
        raise TikTokError("Missing app_key/app_secret/refresh_token")
    base = os.environ.get("TIKTOK_AUTH_API_BASE", "https://auth.tiktok-shops.com")
    path = "/api/v2/token/refresh"
    params = {
        "app_key": app_key,
        "app_secret": app_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{base}{path}", params=params)
    payload = _safe_json(r)
    data = payload.get("data") or payload
    if not data.get("access_token"):
        raise TikTokError(payload.get("message") or data.get("message") or "TikTok refresh failed")
    return _parse_token_payload(data)


async def get_authorized_shops(
    app_key: str, app_secret: str, access_token: str
) -> dict[str, Any]:
    if not (app_key and app_secret and access_token):
        raise TikTokError("Missing app_key/app_secret/access_token")
    base = os.environ.get("TIKTOK_API_BASE", "https://open-api.tiktokglobalshop.com")
    path = "/authorization/202309/shops"
    params = {"app_key": app_key, "timestamp": int(time.time())}
    params["sign"] = _sign_request(app_secret, path, params, b"")
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{base}{path}",
            params=params,
            headers={"x-tts-access-token": access_token, "Content-Type": "application/json"},
        )
    data = _safe_json(r)
    code = data.get("code")
    if code is None or code != 0:
        raise TikTokError(data.get("message") or f"HTTP {r.status_code}")
    return data


def _parse_token_payload(data: dict[str, Any]) -> dict[str, Any]:
    ciphers = data.get("shop_cipher") or data.get("shop_ciphers") or []
    ids = data.get("shop_id") or data.get("shop_ids") or []
    if isinstance(ciphers, str):
        ciphers = [ciphers]
    if isinstance(ids, str):
        ids = [ids]
    now = datetime.now(timezone.utc)
    access_ttl = int(data.get("access_token_expire_in") or data.get("expires_in") or 7 * 86400)
    refresh_ttl = int(data.get("refresh_token_expire_in") or data.get("refresh_expires_in") or 365 * 86400)
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token") or "",
        "token_expires_at": now + timedelta(seconds=access_ttl),
        "refresh_token_expires_at": now + timedelta(seconds=refresh_ttl),
        "shop_cipher": ciphers[0] if ciphers else None,
        "shop_id": str(ids[0]) if ids else None,
    }


def _safe_json(r: httpx.Response) -> dict[str, Any]:
    try:
        return r.json()
    except Exception:
        raise TikTokError(f"HTTP {r.status_code}: {r.text[:200]}")
