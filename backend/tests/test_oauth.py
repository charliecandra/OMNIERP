"""Iteration 3: OAuth 2.0 (Shopee + TikTok) backend tests."""
import hashlib
import hmac
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")

FRONT = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONT.get("REACT_APP_BACKEND_URL")).rstrip("/")
BACK_ENV = dotenv_values("/app/backend/.env")
JWT_SECRET = BACK_ENV["JWT_SECRET"]
JWT_ALG = BACK_ENV.get("JWT_ALGORITHM", "HS256")

SHOPEE_STORE = 1   # shopee
TIKTOK_STORE = 3   # tiktok

TEST_PARTNER_ID = "2010450"
TEST_PARTNER_KEY = "shpk636863744c5475546a5a42626e6169785769434a4a5a6b6a585947795778"


@pytest.fixture(scope="session")
def auth():
    r = requests.post(f"{BASE_URL}/api/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def seeded_creds(auth):
    """Set partner creds on store 1 (shopee) and 3 (tiktok); reset to null afterwards."""
    for sid in (SHOPEE_STORE, TIKTOK_STORE):
        r = requests.patch(
            f"{BASE_URL}/api/stores/{sid}",
            json={"partner_id": TEST_PARTNER_ID, "partner_key": TEST_PARTNER_KEY},
            headers=auth,
        )
        assert r.status_code == 200, r.text
    yield {"partner_id": TEST_PARTNER_ID, "partner_key": TEST_PARTNER_KEY}
    # cleanup: restore pristine store state
    from database import SessionLocal
    from models import Store
    db = SessionLocal()
    for sid in (SHOPEE_STORE, TIKTOK_STORE):
        s = db.query(Store).filter(Store.id == sid).first()
        s.partner_id = None
        s.partner_key = None
        s.shop_id = None
        s.connection_status = "disconnected"
        s.last_verified_at = None
    db.commit()
    db.close()


def _make_state(store_id, platform, exp_minutes=15):
    from jose import jwt as _jwt
    return _jwt.encode(
        {"sid": store_id, "p": platform,
         "exp": datetime.now(timezone.utc) + timedelta(minutes=exp_minutes)},
        JWT_SECRET, algorithm=JWT_ALG,
    )


# --------------------------- oauth/start (Shopee) --------------------------- #
class TestShopeeOAuthStart:
    def test_start_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/oauth/start")
        assert r.status_code == 401, r.text

    def test_start_missing_creds_400(self, auth):
        # ensure creds cleared first
        from database import SessionLocal
        from models import Store
        db = SessionLocal()
        s = db.query(Store).filter(Store.id == SHOPEE_STORE).first()
        prev = (s.partner_id, s.partner_key)
        s.partner_id, s.partner_key = None, None
        db.commit()
        try:
            r = requests.get(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/oauth/start", headers=auth)
            assert r.status_code == 400, r.text
            assert "Partner" in r.json()["detail"]
        finally:
            s.partner_id, s.partner_key = prev
            db.commit()
            db.close()

    def test_start_returns_signed_url(self, auth, seeded_creds):
        r = requests.get(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/oauth/start", headers=auth)
        assert r.status_code == 200, r.text
        url = r.json()["authorize_url"]
        assert url.startswith("https://partner.shopeemobile.com/api/v2/shop/auth_partner")
        q = parse_qs(urlparse(url).query)
        assert q["partner_id"][0] == seeded_creds["partner_id"]
        ts = q["timestamp"][0]
        assert ts.isdigit()
        sign = q["sign"][0]
        assert re.fullmatch(r"[0-9a-f]{64}", sign), sign
        expected = hmac.new(
            seeded_creds["partner_key"].encode(),
            f"{seeded_creds['partner_id']}/api/v2/shop/auth_partner{ts}".encode(),
            hashlib.sha256,
        ).hexdigest()
        assert sign == expected
        assert "redirect" in q
        redirect = q["redirect"][0]
        assert "/api/oauth/shopee/callback" in redirect
        # state must be embedded in redirect and be a valid JWT for this store
        rq = parse_qs(urlparse(redirect).query)
        from jose import jwt as _jwt
        payload = _jwt.decode(rq["state"][0], JWT_SECRET, algorithms=[JWT_ALG])
        assert payload["sid"] == SHOPEE_STORE and payload["p"] == "shopee"

    def test_start_404_unknown_store(self, auth):
        r = requests.get(f"{BASE_URL}/api/stores/9999/oauth/start", headers=auth)
        assert r.status_code == 404


# --------------------------- oauth/start (TikTok) --------------------------- #
class TestTikTokOAuthStart:
    def test_start_returns_authorize_url(self, auth, seeded_creds):
        r = requests.get(f"{BASE_URL}/api/stores/{TIKTOK_STORE}/oauth/start", headers=auth)
        assert r.status_code == 200, r.text
        url = r.json()["authorize_url"]
        assert url.startswith("https://services.tiktokshop.com/open/authorize")
        q = parse_qs(urlparse(url).query)
        assert q["app_key"][0] == seeded_creds["partner_id"]
        from jose import jwt as _jwt
        payload = _jwt.decode(q["state"][0], JWT_SECRET, algorithms=[JWT_ALG])
        assert payload["sid"] == TIKTOK_STORE and payload["p"] == "tiktok"
        assert "exp" in payload

    def test_start_missing_creds_400(self, auth):
        from database import SessionLocal
        from models import Store
        db = SessionLocal()
        s = db.query(Store).filter(Store.id == TIKTOK_STORE).first()
        prev = (s.partner_id, s.partner_key)
        s.partner_id, s.partner_key = None, None
        db.commit()
        try:
            r = requests.get(f"{BASE_URL}/api/stores/{TIKTOK_STORE}/oauth/start", headers=auth)
            assert r.status_code == 400, r.text
            assert "App Key" in r.json()["detail"]
        finally:
            s.partner_id, s.partner_key = prev
            db.commit()
            db.close()


# --------------------------- callbacks --------------------------- #
class TestShopeeCallback:
    def test_missing_params_redirects_error(self):
        r = requests.get(f"{BASE_URL}/api/oauth/shopee/callback", allow_redirects=False)
        assert r.status_code == 303, r.text
        loc = r.headers["location"]
        assert "connect=error" in loc and "Missing" in loc

    def test_error_param_redirects_error(self):
        r = requests.get(f"{BASE_URL}/api/oauth/shopee/callback",
                         params={"error": "user_denied"}, allow_redirects=False)
        assert r.status_code == 303
        assert "connect=error" in r.headers["location"]
        assert "user_denied" in r.headers["location"]

    def test_bad_state_400(self):
        r = requests.get(f"{BASE_URL}/api/oauth/shopee/callback",
                         params={"code": "abc", "shop_id": "123", "state": "not-a-jwt"},
                         allow_redirects=False)
        assert r.status_code in (303, 400), r.text
        if r.status_code == 303:
            assert "connect=error" in r.headers["location"]
        else:
            assert "Invalid state" in r.json()["detail"]

    def test_platform_mismatch_rejected(self):
        state = _make_state(SHOPEE_STORE, "tiktok")
        r = requests.get(f"{BASE_URL}/api/oauth/shopee/callback",
                         params={"code": "abc", "shop_id": "123", "state": state},
                         allow_redirects=False)
        assert r.status_code in (303, 400), r.text
        if r.status_code == 400:
            assert "mismatch" in r.json()["detail"].lower()

    def test_expired_state_rejected(self):
        state = _make_state(SHOPEE_STORE, "shopee", exp_minutes=-10)
        r = requests.get(f"{BASE_URL}/api/oauth/shopee/callback",
                         params={"code": "abc", "shop_id": "123", "state": state},
                         allow_redirects=False)
        assert r.status_code in (303, 400), r.text

    def test_valid_state_dummy_code_redirects_error(self, auth, seeded_creds):
        state = _make_state(SHOPEE_STORE, "shopee")
        r = requests.get(f"{BASE_URL}/api/oauth/shopee/callback",
                         params={"code": "dummycode", "shop_id": "99999", "state": state},
                         allow_redirects=False, timeout=60)
        assert r.status_code == 303, r.text
        loc = r.headers["location"]
        assert "connect=error" in loc, loc
        assert "msg=" in loc and len(loc.split("msg=")[1]) > 0, loc
        # connection_status persisted as error
        s = requests.get(f"{BASE_URL}/api/stores", headers=auth).json()
        row = [x for x in s if x["id"] == SHOPEE_STORE][0]
        assert row["connection_status"] == "error", row


class TestTikTokCallback:
    def test_missing_params_redirects_error(self):
        r = requests.get(f"{BASE_URL}/api/oauth/tiktok/callback", allow_redirects=False)
        assert r.status_code == 303
        assert "connect=error" in r.headers["location"]

    def test_platform_mismatch_rejected(self):
        state = _make_state(TIKTOK_STORE, "shopee")
        r = requests.get(f"{BASE_URL}/api/oauth/tiktok/callback",
                         params={"code": "abc", "state": state}, allow_redirects=False)
        assert r.status_code in (303, 400)
        if r.status_code == 400:
            assert "mismatch" in r.json()["detail"].lower()

    def test_valid_state_dummy_code_redirects_error(self, auth, seeded_creds):
        state = _make_state(TIKTOK_STORE, "tiktok")
        r = requests.get(f"{BASE_URL}/api/oauth/tiktok/callback",
                         params={"code": "dummycode", "state": state},
                         allow_redirects=False, timeout=60)
        assert r.status_code == 303, r.text
        assert "connect=error" in r.headers["location"], r.headers["location"]
        row = [x for x in requests.get(f"{BASE_URL}/api/stores", headers=auth).json()
               if x["id"] == TIKTOK_STORE][0]
        assert row["connection_status"] == "error"


# --------------------------- test connection --------------------------- #
class TestTestConnection:
    def test_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/test")
        assert r.status_code == 401

    def test_404_unknown_store(self, auth):
        r = requests.post(f"{BASE_URL}/api/stores/9999/test", headers=auth)
        assert r.status_code == 404

    def test_no_access_token_400(self, auth):
        from database import SessionLocal
        from models import Store
        db = SessionLocal()
        s = db.query(Store).filter(Store.id == SHOPEE_STORE).first()
        prev = s.access_token
        s.access_token = None
        db.commit()
        try:
            r = requests.post(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/test", headers=auth)
            assert r.status_code == 400, r.text
            assert "not authorized" in r.json()["detail"].lower()
        finally:
            s.access_token = prev
            db.commit()
            db.close()

    def test_shopee_real_call_returns_error_state(self, auth, seeded_creds):
        r = requests.post(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/test", headers=auth, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["platform"] == "shopee"
        assert body["connection_status"] == "error"
        assert body["detail"].get("error"), body
        # persisted
        row = [x for x in requests.get(f"{BASE_URL}/api/stores", headers=auth).json()
               if x["id"] == SHOPEE_STORE][0]
        assert row["connection_status"] == "error"

    def test_tiktok_real_call_returns_error_state(self, auth, seeded_creds):
        r = requests.post(f"{BASE_URL}/api/stores/{TIKTOK_STORE}/test", headers=auth, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["platform"] == "tiktok"
        assert body["connection_status"] in ("error", "active")
        if not body["ok"]:
            assert body["detail"].get("error")


# --------------------------- auto refresh no-op --------------------------- #
class TestAutoRefresh:
    def test_expired_token_without_refresh_token_no_crash(self, auth, seeded_creds):
        from database import SessionLocal
        from models import Store
        db = SessionLocal()
        s = db.query(Store).filter(Store.id == SHOPEE_STORE).first()
        prev = (s.token_expires_at, s.refresh_token)
        s.token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.refresh_token = None
        db.commit()
        try:
            r = requests.post(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/test", headers=auth, timeout=60)
            assert r.status_code == 200, r.text
            assert r.json()["ok"] is False
        finally:
            s.token_expires_at, s.refresh_token = prev
            db.commit()
            db.close()


# --------------------------- StoreOut / PATCH --------------------------- #
class TestStorePatchAndSchema:
    def test_store_out_fields(self, auth):
        r = requests.get(f"{BASE_URL}/api/stores", headers=auth)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) >= 1
        for row in rows:
            for k in ("id", "platform_name", "store_name", "is_active", "sync_enabled",
                      "partner_id", "shop_id", "shop_cipher", "connection_status",
                      "last_verified_at", "token_expires_at"):
                assert k in row, (k, row)
            assert "partner_key" not in row
            assert "access_token" not in row
            assert "_id" not in row

    def test_patch_accepts_new_fields(self, auth):
        payload = {"partner_id": "TEST_PID", "partner_key": "TEST_PKEY",
                   "shop_id": "TEST_SHOP", "sync_enabled": False, "is_active": True}
        r = requests.patch(f"{BASE_URL}/api/stores/2", json=payload, headers=auth)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["partner_id"] == "TEST_PID"
        assert d["shop_id"] == "TEST_SHOP"
        assert d["sync_enabled"] is False
        # verify persisted
        row = [x for x in requests.get(f"{BASE_URL}/api/stores", headers=auth).json()
               if x["id"] == 2][0]
        assert row["partner_id"] == "TEST_PID" and row["shop_id"] == "TEST_SHOP"
        # cleanup
        from database import SessionLocal
        from models import Store
        db = SessionLocal()
        s = db.query(Store).filter(Store.id == 2).first()
        s.partner_id = None
        s.partner_key = None
        s.shop_id = None
        db.commit()
        db.close()

    def test_patch_requires_auth(self):
        r = requests.patch(f"{BASE_URL}/api/stores/2", json={"sync_enabled": True})
        assert r.status_code == 401
