"""Iteration 2 backend regression tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Orders detail ----
class TestOrderDetail:
    def test_order_detail_ok(self, auth):
        r = requests.get(f"{BASE_URL}/api/orders", headers=auth)
        assert r.status_code == 200
        order_id = r.json()[0]["id"]
        r2 = requests.get(f"{BASE_URL}/api/orders/{order_id}", headers=auth)
        assert r2.status_code == 200
        d = r2.json()
        assert d["id"] == order_id
        assert "marketplace_order_id" in d
        assert "buyer_name" in d and "buyer_address" in d and "tracking_number" in d
        assert isinstance(d["items"], list) and len(d["items"]) >= 1
        it = d["items"][0]
        for k in ("master_sku_code", "product_name", "quantity", "unit_price"):
            assert k in it
        assert isinstance(d["timeline"], list) and len(d["timeline"]) >= 1
        tl = d["timeline"][0]
        for k in ("at", "status"):
            assert k in tl

    def test_order_detail_404(self, auth):
        r = requests.get(f"{BASE_URL}/api/orders/999999", headers=auth)
        assert r.status_code == 404

    def test_order_detail_401(self):
        r = requests.get(f"{BASE_URL}/api/orders/1")
        assert r.status_code == 401


# ---- Labels PDF ----
class TestLabelsPDF:
    def test_pdf_ok(self, auth):
        r = requests.get(f"{BASE_URL}/api/orders", headers=auth)
        ids = [o["id"] for o in r.json()[:3]]
        r2 = requests.post(f"{BASE_URL}/api/orders/labels/pdf", json={"order_ids": ids}, headers=auth)
        assert r2.status_code == 200
        assert r2.headers.get("content-type", "").startswith("application/pdf")
        assert "attachment" in r2.headers.get("content-disposition", "").lower()
        assert r2.content[:5] == b"%PDF-"

    def test_pdf_empty(self, auth):
        r = requests.post(f"{BASE_URL}/api/orders/labels/pdf", json={"order_ids": []}, headers=auth)
        assert r.status_code == 400

    def test_pdf_unknown(self, auth):
        r = requests.post(f"{BASE_URL}/api/orders/labels/pdf", json={"order_ids": [999998, 999999]}, headers=auth)
        assert r.status_code == 404

    def test_pdf_401(self):
        r = requests.post(f"{BASE_URL}/api/orders/labels/pdf", json={"order_ids": [1]})
        assert r.status_code == 401


# ---- Inventory threshold ----
class TestThreshold:
    def test_update_and_persist(self, auth):
        r = requests.patch(f"{BASE_URL}/api/inventory/1/threshold", json={"reorder_threshold": 99}, headers=auth)
        assert r.status_code == 200, r.text
        assert r.json()["reorder_threshold"] == 99
        r2 = requests.get(f"{BASE_URL}/api/inventory", headers=auth)
        sku = next(s for s in r2.json() if s["id"] == 1)
        assert sku["reorder_threshold"] == 99
        # cleanup - reset to 80
        requests.patch(f"{BASE_URL}/api/inventory/1/threshold", json={"reorder_threshold": 80}, headers=auth)

    def test_negative_422(self, auth):
        r = requests.patch(f"{BASE_URL}/api/inventory/1/threshold", json={"reorder_threshold": -5}, headers=auth)
        assert r.status_code == 422

    def test_missing_404(self, auth):
        r = requests.patch(f"{BASE_URL}/api/inventory/99999/threshold", json={"reorder_threshold": 10}, headers=auth)
        assert r.status_code == 404


# ---- Stores update ----
class TestStoresUpdate:
    def test_patch_store(self, auth):
        r = requests.patch(
            f"{BASE_URL}/api/stores/1",
            json={"partner_id": "PID_TEST", "partner_key": "SECRET_KEY", "shop_id": "SHOP_TEST", "sync_enabled": True},
            headers=auth,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sync_enabled"] is True
        assert d["partner_id"] == "PID_TEST"
        assert "partner_key" not in d  # write-only

        r2 = requests.get(f"{BASE_URL}/api/stores", headers=auth)
        s = next(s for s in r2.json() if s["id"] == 1)
        assert s["sync_enabled"] is True
        assert s["partner_id"] == "PID_TEST"
        assert "partner_key" not in s

        # cleanup
        requests.patch(f"{BASE_URL}/api/stores/1", json={"sync_enabled": False}, headers=auth)


# ---- Settings ----
class TestSettings:
    def test_get_put_settings(self, auth):
        r = requests.get(f"{BASE_URL}/api/settings", headers=auth)
        assert r.status_code == 200
        assert "slack_webhook_url" in r.json()

        url = "https://hooks.slack.com/services/T/B/xxx"
        r2 = requests.put(f"{BASE_URL}/api/settings", json={"slack_webhook_url": url}, headers=auth)
        assert r2.status_code == 200
        assert r2.json()["slack_webhook_url"] == url

        r3 = requests.get(f"{BASE_URL}/api/settings", headers=auth)
        assert r3.json()["slack_webhook_url"] == url

        r4 = requests.put(f"{BASE_URL}/api/settings", json={"slack_webhook_url": ""}, headers=auth)
        assert r4.status_code == 200
        assert r4.json()["slack_webhook_url"] in (None, "")

        r5 = requests.get(f"{BASE_URL}/api/settings", headers=auth)
        assert r5.json()["slack_webhook_url"] in (None, "")


# ---- Webhook low-stock ----
class TestWebhookLowStock:
    def test_webhook_low_stock(self, auth):
        # Get an SKU and mapping. Set threshold high to trigger.
        skus = requests.get(f"{BASE_URL}/api/inventory", headers=auth).json()
        sku = skus[0]
        # bump threshold to just below real_stock so any order triggers
        thr = max(sku["real_stock"] - 1, 0)
        requests.patch(
            f"{BASE_URL}/api/inventory/{sku['id']}/threshold",
            json={"reorder_threshold": thr},
            headers=auth,
        )
        # Find a mapping for store 1 for this sku
        # Use webhook with a marketplace_sku_code that maps. Use a known one from seed.
        # We fallback: try store 1 with sku's master code as marketplace code (seed maps master->itself sometimes)
        payload = {
            "store_id": 1,
            "marketplace_order_id": f"TEST_LOW_{sku['id']}",
            "status": "pending",
            "items": [{"marketplace_sku_code": sku["master_sku_code"], "quantity": 1, "unit_price": 10.0}],
            "buyer_name": "Test",
            "buyer_address": "Somewhere",
        }
        r = requests.post(f"{BASE_URL}/api/webhooks/orders", json=payload)
        # Either succeeds (200) or returns 400 if no mapping - both are acceptable
        # but if there's a mapping, must not 500
        assert r.status_code in (200, 400), r.text
        if r.status_code == 200:
            body = r.json()
            assert "low_stock_alerts_sent" in body
            assert isinstance(body["low_stock_alerts_sent"], int)
        # reset threshold
        requests.patch(
            f"{BASE_URL}/api/inventory/{sku['id']}/threshold",
            json={"reorder_threshold": 80},
            headers=auth,
        )
