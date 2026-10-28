# Tests for Stripe test mode checkout - Tykeara Hammond 10/27/2026
# Stripe and the order service are faked, so no card is charged and no rows are written

import sys, os
# Path
sys.path.append(os.path.join(os.path.dirname(__file__), "..")) 

from types import SimpleNamespace
import pytest
from app import app
import controllers.checkout_controller as checkout_controller

CART = [{"listing_id": 1, "name": "STRIPE TEST ITEM", "price": 25.00, "quantity": 1}]
BUYER = {"first_name": "Test", "last_name": "Buyer", "email": "test@hamptonu.edu",
         "contact": "5555555555", "meeting_location": "Student Center"}

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def log_in_with_cart(client, user_id=1, cart=CART):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["cart"] = cart

def fake_stripe_session(payment_status, user_id):
    metadata = SimpleNamespace(to_dict=lambda: {"user_id": str(user_id)})
    return SimpleNamespace(payment_status=payment_status, metadata=metadata)

# SC-01
def test_create_session_requires_login(client):
    res = client.post("/api/checkout/create-session", json=BUYER)
    assert res.status_code == 401

# SC-02
def test_create_session_rejects_empty_cart(client):
    log_in_with_cart(client, cart=[])
    res = client.post("/api/checkout/create-session", json=BUYER)
    assert res.status_code == 400

# SC-03
def test_create_session_requires_buyer_fields(client):
    log_in_with_cart(client)
    res = client.post("/api/checkout/create-session", json={"first_name": "Test"})
    assert res.status_code == 400

# SC-04
def test_create_session_sends_price_in_cents(client, monkeypatch):
    captured = {}
    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.stripe.com/test")
    monkeypatch.setattr(checkout_controller.stripe.checkout.Session, "create", fake_create)
    log_in_with_cart(client)
    res = client.post("/api/checkout/create-session", json=BUYER)
    assert res.status_code == 200
    assert res.get_json()["url"] == "https://checkout.stripe.com/test"
    assert captured["line_items"][0]["price_data"]["unit_amount"] == 2500
    assert captured["metadata"]["user_id"] == "1"

# FP-02 (unpaid = no order)
def test_success_no_order_when_unpaid(client, monkeypatch):
    monkeypatch.setattr(checkout_controller.stripe.checkout.Session, "retrieve",
                        lambda session_id: fake_stripe_session("unpaid", 1))
    called = []
    monkeypatch.setattr(checkout_controller, "complete_transaction_from_session",
                        lambda *args: called.append(args))
    log_in_with_cart(client)
    res = client.get("/api/checkout/success?session_id=cs_test_123")
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/checkout")
    assert called == []

# SC-05
def test_success_rejects_other_users_payment(client, monkeypatch):
    monkeypatch.setattr(checkout_controller.stripe.checkout.Session, "retrieve",
                        lambda session_id: fake_stripe_session("paid", 999))
    called = []
    monkeypatch.setattr(checkout_controller, "complete_transaction_from_session",
                        lambda *args: called.append(args))
    log_in_with_cart(client, user_id=1)
    res = client.get("/api/checkout/success?session_id=cs_test_123")
    assert res.headers["Location"].endswith("/checkout")
    assert called == []

# SC-06
def test_success_creates_order_once(client, monkeypatch):
    monkeypatch.setattr(checkout_controller.stripe.checkout.Session, "retrieve",
                        lambda session_id: fake_stripe_session("paid", 1))
    called = []
    def fake_complete(user_id, cart, buyer):
        called.append(user_id)
        return {"confirmation_number": "VAULT-TEST-1"}
    monkeypatch.setattr(checkout_controller, "complete_transaction_from_session", fake_complete)
    log_in_with_cart(client)
    first = client.get("/api/checkout/success?session_id=cs_test_123")
    refresh = client.get("/api/checkout/success?session_id=cs_test_123")
    assert "VAULT-TEST-1" in first.headers["Location"]
    assert "VAULT-TEST-1" in refresh.headers["Location"]
    assert len(called) == 1

# SC-07
def test_old_free_checkout_route_is_gone(client):
    log_in_with_cart(client)
    res = client.post("/api/checkout/complete", json=BUYER)
    assert res.status_code in (404, 405)