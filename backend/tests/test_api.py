"""backend/tests/test_api.py - smoke tests against an isolated temp SQLite DB.

Run from repo root: .venv/bin/pytest backend/tests -v
"""

import os
import tempfile

TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "rto_dashboard_test.db")
if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)
# must be set BEFORE any backend.app import, since db.py builds the engine at import time
os.environ["RTO_DASHBOARD_DB_URL"] = f"sqlite:///{TEST_DB_PATH}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.db import Base, SessionLocal, engine  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.models import Order, OrderStatus, Tenant  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def seed_minimal():
    db = SessionLocal()
    tenant = Tenant(name="Test Tenant", slug="test-tenant")
    db.add(tenant)
    db.flush()
    order = Order(
        order_id="TEST-ORD-000001", tenant_id=tenant.id, customer_ref="c1", product_ref="p1",
        order_date="2021-10-15", model_risk_score=0.9, reasons_json='["high risk"]',
        customer_no_history=0, product_no_history=0, customer_return_rate=0.8,
        product_return_rate=0.6, avg_discount_value=10.0, avg_gbp_price=20.0,
        country_bucket="Country_A", product_brand_bucket="Brand_A", product_type_bucket="productType_A",
        raw_features_json="{}", is_returned_ground_truth=1,
    )
    db.add(order)
    db.add(OrderStatus(order_id=order.order_id, current_score=0.9, status="pending"))
    db.commit()
    db.close()
    yield


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200


def test_list_orders():
    r = client.get("/api/orders")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["order_id"] == "TEST-ORD-000001"


def test_order_detail_omits_ground_truth():
    r = client.get("/api/orders/TEST-ORD-000001")
    assert r.status_code == 200
    assert "is_returned_ground_truth" not in r.json()


def test_unknown_order_404():
    r = client.get("/api/orders/NOPE-000000")
    assert r.status_code == 404


def test_override_writes_both_tables():
    r = client.post(
        "/api/orders/TEST-ORD-000001/override",
        json={"new_score": 0.1, "reason": "test override", "actor_name": "tester"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["current_score"] == 0.1
    assert body["status"] == "overridden"

    hist = client.get("/api/orders/TEST-ORD-000001/history")
    assert hist.status_code == 200
    events = hist.json()
    assert any(e["event_type"] == "override" and e["new_score"] == 0.1 for e in events)


def test_role_gate_403_then_201():
    denied = client.post(
        "/api/rules?tenant=test-tenant",
        json={"name": "r1", "score_threshold": 0.9, "action_type": "call_customer"},
        headers={"X-Role": "ops_analyst"},
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/api/rules?tenant=test-tenant",
        json={"name": "r1", "score_threshold": 0.9, "action_type": "call_customer"},
        headers={"X-Role": "ops_manager"},
    )
    assert allowed.status_code == 201


def test_unknown_role_403():
    r = client.get("/api/orders", headers={"X-Role": "not_a_role"})
    assert r.status_code == 403
