"""Iteration 4 retest: verification of the 4 backend fixes from iteration_3.json.

Covers:
  * TikTok endpoint host/path corrections (no 'Invalid path', no raw Python errors)
  * POST /stores/{id}/test pre-signing validation (400s + clean error payloads)
  * OAuth callback state failures -> 303 redirect (not raw 400 JSON)
  * StoreOut.is_authorized (seeded placeholder tokens excluded)
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import jose.jwt as _jwt
import pytest
import requests
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")

FRONT = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONT.get("REACT_APP_BACKEND_URL")).rstrip("/")
BACK_ENV = dotenv_values("/app/backend/.env")
JWT_SECRET = BACK_ENV["JWT_SECRET"]
JWT_ALG = BACK_ENV.get("JWT_ALGORITHM", "HS256")
FRONTEND_STORES_URL = BACK_ENV["FRONTEND_STORES_URL"]

SHOPEE_STORE = 1
TIKTOK_STORE = 3
TEST_PARTNER_ID = "2010450"
TEST_PARTNER_KEY = "shpk636863744c5475546a5a42626e6169785769434a4a5a6b6a585947795778"

RAW_PY_MARKERS = [
    "NoneType", "object has no attribute", "unsupported operand",
    "Traceback", "TypeError", "AttributeError",
]


def _db():
    from database import SessionLocal
    return SessionLocal()


SEEDED_TOKENS = {1: "sh_main_token", 2: "sh_out_token", 3: "tt_flag_token", 4: "tt_live_token"}


def _reset_stores():
    from models import Store
    db = _db()
    for s in db.query(Store).all():
        if s.id in SEEDED_TOKENS:
            s.access_token = SEEDED_TOKENS[s.id]
        s.partner_id = None
        s.partner_key = None
        s.shop_id = None
        s.connection_status = "disconnected"
        s.last_verified_at = None
    db.commit()
    db.close()


@pytest.fixture(scope="session")
def auth():
    r = requests.post(f"{BASE_URL}/api/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session", autouse=True)
def cleanup_at_end():
    yield
    _reset_stores()


def _set(store_id, **fields):
    from models import Store
    db = _db()
    s = db.query(Store).filter(Store.id == store_id).first()
    for k, v in fields.items():
        setattr(s, k, v)
    db.commit()
    db.close()


def _get_store(store_id, auth):
    r = requests.get(f"{BASE_URL}/api/stores", headers=auth)
    assert r.status_code == 200, r.text
    return next(s for s in r.json() if s["id"] == store_id)


# --------------------------------------------------------------------------- #
# MINOR FIX: StoreOut.is_authorized
# --------------------------------------------------------------------------- #
class TestIsAuthorizedField:
    def test_all_seeded_stores_not_authorized(self, auth):
        r = requests.get(f"{BASE_URL}/api/stores", headers=auth)
        assert r.status_code == 200, r.text
        stores = r.json()
        assert len(stores) == 4, stores
        for s in stores:
            assert "is_authorized" in s, s
            assert s["is_authorized"] is False, f"store {s['id']} unexpectedly authorized"
            assert "access_token" not in s and "partner_key" not in s

    def test_is_authorized_true_for_real_token(self, auth):
        _set(SHOPEE_STORE, access_token="TEST_real_token_abc")
        try:
            assert _get_store(SHOPEE_STORE, auth)["is_authorized"] is True
        finally:
            _set(SHOPEE_STORE, access_token="sh_main_token")
        assert _get_store(SHOPEE_STORE, auth)["is_authorized"] is False


# --------------------------------------------------------------------------- #
# HIGH FIX #2: POST /stores/{id}/test validates before signing
# --------------------------------------------------------------------------- #
class TestTestConnectionValidation:
    def test_missing_partner_credentials_400(self, auth):
        _set(SHOPEE_STORE, partner_id=None, partner_key=None, access_token="TEST_tok")
        r = requests.post(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/test", headers=auth)
        assert r.status_code == 400, r.text
        assert "Partner credentials are not configured" in r.json()["detail"]

    def test_missing_access_token_400(self, auth):
        _set(SHOPEE_STORE, partner_id=TEST_PARTNER_ID, partner_key=TEST_PARTNER_KEY, access_token=None)
        r = requests.post(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/test", headers=auth)
        assert r.status_code == 400, r.text
        assert "not authorized yet" in r.json()["detail"]

    def test_shopee_missing_shop_id_400(self, auth):
        _set(SHOPEE_STORE, partner_id=TEST_PARTNER_ID, partner_key=TEST_PARTNER_KEY,
             access_token="TEST_tok", shop_id=None)
        r = requests.post(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/test", headers=auth)
        assert r.status_code == 400, r.text
        assert "shop_id is missing" in r.json()["detail"]

    def test_shopee_genuine_marketplace_error_clean(self, auth):
        _set(SHOPEE_STORE, partner_id=TEST_PARTNER_ID, partner_key=TEST_PARTNER_KEY,
             access_token="TEST_tok", shop_id="123456")
        r = requests.post(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/test", headers=auth)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["connection_status"] == "error"
        err = body["detail"].get("error", "")
        assert err, body
        for marker in RAW_PY_MARKERS:
            assert marker not in err, f"raw python error leaked: {err}"
        assert _get_store(SHOPEE_STORE, auth)["connection_status"] == "error"

    def test_tiktok_genuine_marketplace_error_clean_no_invalid_path(self, auth):
        _set(TIKTOK_STORE, partner_id="tt_app_key_dummy", partner_key="tt_app_secret_dummy",
             access_token="TEST_tt_tok")
        r = requests.post(f"{BASE_URL}/api/stores/{TIKTOK_STORE}/test", headers=auth)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is False
        err = body["detail"].get("error", "")
        assert err, body
        print(f"TikTok test-connection error detail: {err}")
        for marker in RAW_PY_MARKERS:
            assert marker not in err, f"raw python error leaked: {err}"
        assert "Invalid path" not in err, f"TikTok path still wrong: {err}"


# --------------------------------------------------------------------------- #
# MINOR FIX: invalid / expired / mismatched state -> 303 redirect
# --------------------------------------------------------------------------- #
class TestCallbackStateRedirects:
    def _assert_redirect(self, resp):
        assert resp.status_code == 303, f"{resp.status_code}: {resp.text[:300]}"
        loc = resp.headers["location"]
        assert loc.startswith(FRONTEND_STORES_URL), loc
        q = parse_qs(urlparse(loc).query)
        assert q.get("connect") == ["error"], loc
        assert q.get("msg", [""])[0], loc

    def test_shopee_invalid_state_redirects(self):
        r = requests.get(f"{BASE_URL}/api/oauth/shopee/callback",
                         params={"code": "dummy", "shop_id": "1", "state": "not-a-jwt"},
                         allow_redirects=False)
        self._assert_redirect(r)

    def test_shopee_platform_mismatch_redirects(self):
        state = _jwt.encode({"sid": TIKTOK_STORE, "p": "tiktok",
                             "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                            JWT_SECRET, algorithm=JWT_ALG)
        r = requests.get(f"{BASE_URL}/api/oauth/shopee/callback",
                         params={"code": "dummy", "shop_id": "1", "state": state},
                         allow_redirects=False)
        self._assert_redirect(r)

    def test_expired_state_redirects(self):
        state = _jwt.encode({"sid": SHOPEE_STORE, "p": "shopee",
                             "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
                            JWT_SECRET, algorithm=JWT_ALG)
        r = requests.get(f"{BASE_URL}/api/oauth/shopee/callback",
                         params={"code": "dummy", "shop_id": "1", "state": state},
                         allow_redirects=False)
        self._assert_redirect(r)

    def test_tiktok_invalid_state_redirects(self):
        r = requests.get(f"{BASE_URL}/api/oauth/tiktok/callback",
                         params={"code": "dummy", "state": "bogus"},
                         allow_redirects=False)
        self._assert_redirect(r)

    def test_tiktok_valid_state_dummy_code_redirects_error(self):
        _set(TIKTOK_STORE, partner_id="tt_app_key_dummy", partner_key="tt_app_secret_dummy")
        state = _jwt.encode({"sid": TIKTOK_STORE, "p": "tiktok",
                             "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                            JWT_SECRET, algorithm=JWT_ALG)
        r = requests.get(f"{BASE_URL}/api/oauth/tiktok/callback",
                         params={"code": "dummy_auth_code", "state": state},
                         allow_redirects=False)
        assert r.status_code == 303, r.text[:300]
        loc = r.headers["location"]
        q = parse_qs(urlparse(loc).query)
        assert q.get("connect") == ["error"], loc
        msg = q.get("msg", [""])[0]
        print(f"TikTok callback error msg: {msg}")
        for marker in RAW_PY_MARKERS:
            assert marker not in msg, f"raw python error leaked: {msg}"


# --------------------------------------------------------------------------- #
# HIGH FIX #1: TikTok client host/path defaults (direct unit level)
# --------------------------------------------------------------------------- #
class TestTikTokClientDirect:
    def test_exchange_code_hits_auth_host_and_raises_tiktokerror(self):
        from integrations import tiktok as tt

        async def go():
            with pytest.raises(tt.TikTokError) as ei:
                await tt.exchange_code("dummy_key", "dummy_secret", "dummy_code")
            return str(ei.value)

        msg = asyncio.get_event_loop().run_until_complete(go()) if False else asyncio.run(go())
        print(f"exchange_code error: {msg}")
        assert "Invalid path" not in msg
        for marker in RAW_PY_MARKERS:
            assert marker not in msg

    def test_refresh_token_raises_tiktokerror(self):
        from integrations import tiktok as tt

        async def go():
            with pytest.raises(tt.TikTokError) as ei:
                await tt.refresh_access_token("dummy_key", "dummy_secret", "dummy_refresh")
            return str(ei.value)

        msg = asyncio.run(go())
        print(f"refresh error: {msg}")
        assert "Invalid path" not in msg

    def test_hosts_and_paths_configured(self):
        assert BACK_ENV.get("TIKTOK_AUTH_API_BASE") == "https://auth.tiktok-shops.com"
        src = open("/app/backend/integrations/tiktok.py").read()
        assert '"/authorization/202309/shops"' in src
        assert '"/api/v2/token/get"' in src
        assert '"/api/v2/token/refresh"' in src

    def test_get_authorized_shops_null_guard(self):
        from integrations import tiktok as tt

        async def go():
            with pytest.raises(tt.TikTokError):
                await tt.get_authorized_shops("k", "s", None)
        asyncio.run(go())


# --------------------------------------------------------------------------- #
# REGRESSION: oauth/start + PATCH still fine
# --------------------------------------------------------------------------- #
class TestRegressionOAuthStart:
    def test_shopee_start_signed_url(self, auth):
        import hashlib, hmac
        _set(SHOPEE_STORE, partner_id=TEST_PARTNER_ID, partner_key=TEST_PARTNER_KEY)
        r = requests.get(f"{BASE_URL}/api/stores/{SHOPEE_STORE}/oauth/start", headers=auth)
        assert r.status_code == 200, r.text
        url = r.json()["authorize_url"]
        assert url.startswith("https://partner.shopeemobile.com/api/v2/shop/auth_partner"), url
        q = parse_qs(urlparse(url).query)
        ts = q["timestamp"][0]
        expected = hmac.new(TEST_PARTNER_KEY.encode(),
                            f"{TEST_PARTNER_ID}/api/v2/shop/auth_partner{ts}".encode(),
                            hashlib.sha256).hexdigest()
        assert q["sign"][0] == expected
        assert "state=" in q["redirect"][0] or "state" in q["redirect"][0]

    def test_tiktok_start_url(self, auth):
        _set(TIKTOK_STORE, partner_id="tt_app_key_dummy", partner_key="tt_app_secret_dummy")
        r = requests.get(f"{BASE_URL}/api/stores/{TIKTOK_STORE}/oauth/start", headers=auth)
        assert r.status_code == 200, r.text
        url = r.json()["authorize_url"]
        assert url.startswith("https://services.tiktokshop.com/open/authorize"), url
        q = parse_qs(urlparse(url).query)
        assert q["app_key"][0] == "tt_app_key_dummy"
        payload = _jwt.decode(q["state"][0], JWT_SECRET, algorithms=[JWT_ALG])
        assert payload["sid"] == TIKTOK_STORE and payload["p"] == "tiktok"

    def test_patch_accepts_documented_fields(self, auth):
        r = requests.patch(f"{BASE_URL}/api/stores/{SHOPEE_STORE}",
                           json={"partner_id": "TEST_pid", "partner_key": "TEST_pkey",
                                 "shop_id": "TEST_shop", "sync_enabled": False, "is_active": True},
                           headers=auth)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["partner_id"] == "TEST_pid"
        assert body["shop_id"] == "TEST_shop"
        assert "partner_key" not in body
        got = _get_store(SHOPEE_STORE, auth)
        assert got["partner_id"] == "TEST_pid" and got["shop_id"] == "TEST_shop"

    def test_unauthenticated_401(self):
        assert requests.post(f"{BASE_URL}/api/stores/1/test").status_code in (401, 403)
        assert requests.get(f"{BASE_URL}/api/stores/1/oauth/start").status_code in (401, 403)
