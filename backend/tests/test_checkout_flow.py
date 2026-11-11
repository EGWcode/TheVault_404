# test_checkout_flow.py
# Created by Anthony Jackson - Iteration 4 (11/11/26) for the checkout feature.
#
# Part 1 (no database): buyer form rules, bag merging, and the Stripe test-mode-only rule.
# Part 2 (local/Docker database only): the full "pay in person" checkout through the API.
#   It makes its own temporary seller, buyer, storefront and listing, and deletes them after.
#   Skipped (not failed) if no local database is reachable. Never runs against AWS RDS.
# Test case IDs match the Test Specification (CO-01 ... CO-20).

import os
import sys
import time
import uuid

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.abspath(os.path.join(BACKEND, ".."))
for path in (BACKEND, ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

import pytest  # noqa: E402

from services import checkout_service  # noqa: E402
from services.checkout_service import CheckoutError  # noqa: E402
from utils import payments  # noqa: E402

GOOD_BUYER = {"first_name": "Test", "last_name": "Buyer", "email": "test.buyer@my.hamptonu.edu",
              "contact": "(757) 555-0100", "meeting_location": "Student Center"}


# ------------------------------------------------------------------ Part 1: no database

# CO-01
def test_buyer_form_is_cleaned():
    buyer = checkout_service.validate_buyer({**GOOD_BUYER, "first_name": "  Mary-Jane ", "contact": "1-757-555-0100"})
    assert buyer["first_name"] == "Mary-Jane"
    assert buyer["contact"] == "(757) 555-0100"


# CO-02
@pytest.mark.parametrize("field,value,words", [
    ("first_name", "", "required"),
    ("email", "not-an-email", "valid email"),
    ("contact", "555-0100", "10-digit"),
    ("first_name", "<script>", "letters"),
    ("meeting_location", "x" * 201, "too long"),
])
def test_bad_buyer_details_are_rejected(field, value, words):
    with pytest.raises(CheckoutError) as err:
        checkout_service.validate_buyer({**GOOD_BUYER, field: value})
    assert words in str(err.value)
    assert err.value.status == 400


# CO-03
def test_same_item_and_size_are_merged():
    lines = checkout_service.merge_cart_lines([
        {"id": 7, "size": "M", "quantity": 1},
        {"id": 7, "size": "M", "quantity": 2},
        {"id": 7, "size": "L", "quantity": 1},
    ])
    assert sorted(lines) == [(7, "L", 1), (7, "M", 3)]


# CO-04
@pytest.mark.parametrize("cart", [[], [{"id": None, "quantity": 1}], [{"id": 1, "quantity": 0}],
                                  [{"id": 1, "quantity": 21}]])
def test_bad_bags_are_rejected(cart):
    with pytest.raises(CheckoutError):
        checkout_service.merge_cart_lines(cart)


# CO-05
@pytest.mark.parametrize("key,mode", [
    ("", "off"), ("sk_test_abc", "test"), ("rk_test_abc", "test"),
    ("sk_live_abc", "live_refused"), ("rk_live_abc", "live_refused"), ("garbage", "off"),
])
def test_stripe_is_test_mode_only(monkeypatch, key, mode):
    monkeypatch.setenv("STRIPE_SECRET_KEY", key)
    assert payments.stripe_mode() == mode
    assert payments.stripe_enabled() == (mode == "test")
    if mode != "test":
        assert payments.stripe_api_key() is None      # a live key is never handed to Stripe


# ------------------------------------------------------------------ Part 2: database

def _local_db_or_skip():
    from config.db import connect, is_local_host, current_host
    if not is_local_host():
        pytest.skip(f"DB_HOST is '{current_host()}'. Checkout integration tests only run on a local/Docker database.")
    try:
        connect().close()
    except Exception as e:
        pytest.skip(f"No local database reachable: {e}")


@pytest.fixture(scope="module")
def world():
    """A seller with one listing (sizes M=2, L=1, price $30) and a buyer. Deleted afterwards."""
    _local_db_or_skip()
    from config.db import connect
    from app import app
    app.config["TESTING"] = True

    tag = uuid.uuid4().hex[:8]
    conn = connect()
    cur = conn.cursor()
    ids = {}
    for who in ("seller", "buyer", "other"):
        cur.execute("INSERT INTO users (username, password, email) VALUES (%s, 'x', %s) RETURNING id",
                    (f"cotest_{who}_{tag}", f"cotest_{who}_{tag}@my.hamptonu.edu"))
        ids[who] = cur.fetchone()[0]
    cur.execute("""INSERT INTO storefronts (owner_id, brand_name, is_active) VALUES (%s, %s, TRUE) RETURNING id""",
                (ids["seller"], f"Checkout Test Store {tag}"))
    ids["store"] = cur.fetchone()[0]
    conn.commit()
    cur.close()

    yield {"app": app, "conn": conn, "ids": ids, "tag": tag}

    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ANY(%s)", ([ids["seller"], ids["buyer"], ids["other"]],))
    conn.commit()
    cur.close()
    conn.close()


@pytest.fixture
def listing(world):
    """A fresh listing for each test so stock changes don't leak between tests."""
    conn = world["conn"]
    cur = conn.cursor()
    cur.execute("""INSERT INTO listings (storefront_id, title, price, fulfillment_type, quantity_on_hand, status)
                   VALUES (%s, %s, 30.00, 'IN_STOCK', 3, 'ACTIVE') RETURNING id""",
                (world["ids"]["store"], f"Test Hoodie {uuid.uuid4().hex[:6]}"))
    listing_id = cur.fetchone()[0]
    cur.executemany("INSERT INTO listing_sizes (listing_id, size, quantity) VALUES (%s, %s, %s)",
                    [(listing_id, "M", 2), (listing_id, "L", 1)])
    conn.commit()
    cur.close()
    return listing_id


def _client(world, who="buyer", cart=None):
    client = world["app"].test_client()
    with client.session_transaction() as sess:
        if who:
            sess["user_id"] = world["ids"][who]
            sess["user"] = f"cotest_{who}"
            sess["last_activity"] = time.time()   # a fresh login, so the 5-minute idle timeout doesn't fire
        sess["cart"] = cart or []
    return client


def _one(world, sql, params):
    cur = world["conn"].cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    world["conn"].commit()
    cur.close()
    return row


def _order_count(world):
    return _one(world, "SELECT COUNT(*) FROM orders WHERE user_id = %s", (world["ids"]["buyer"],))[0]


# CO-06: the main path, and the price comes from the database, not the browser
def test_in_person_checkout_uses_database_price(world, listing):
    cart = [{"id": listing, "name": "edited", "price": 0.01, "quantity": 2, "size": "M"}]
    res = _client(world, cart=cart).post("/api/checkout/complete", json=GOOD_BUYER)
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["total_amount"] == 60.00                  # 2 x $30, not 2 x $0.01
    assert body["payment_method"] == "IN_PERSON"
    assert body["confirmation_number"].startswith("COVE-")
    item = _one(world, "SELECT item_name, price_at_purchase FROM order_items oi JOIN orders o ON o.id = oi.order_id "
                       "WHERE o.confirmation_number = %s", (body["confirmation_number"],))
    assert item[0].startswith("Test Hoodie") and float(item[1]) == 30.00


# CO-07: stock goes down per size and the listing turns SOLD_OUT at zero
def test_stock_goes_down_and_sells_out(world, listing):
    res = _client(world, cart=[{"id": listing, "quantity": 2, "size": "M"}, {"id": listing, "quantity": 1, "size": "L"}]
                  ).post("/api/checkout/complete", json=GOOD_BUYER)
    assert res.status_code == 200, res.get_json()
    assert _one(world, "SELECT quantity FROM listing_sizes WHERE listing_id=%s AND size='M'", (listing,))[0] == 0
    status, qty = _one(world, "SELECT status, quantity_on_hand FROM listings WHERE id=%s", (listing,))
    assert (status, qty) == ("SOLD_OUT", 0)


# CO-08: asking for too many fails cleanly - no order, stock unchanged, bag kept
def test_not_enough_stock_changes_nothing(world, listing):
    before = _order_count(world)
    client = _client(world, cart=[{"id": listing, "quantity": 3, "size": "M"}])
    res = client.post("/api/checkout/complete", json=GOOD_BUYER)
    assert res.status_code == 409
    assert "only has 2 left" in res.get_json()["error"]
    assert _order_count(world) == before
    assert _one(world, "SELECT quantity FROM listing_sizes WHERE listing_id=%s AND size='M'", (listing,))[0] == 2
    with client.session_transaction() as sess:
        assert len(sess["cart"]) == 1


# CO-09: all or nothing - if anything fails halfway, the order is rolled back
def test_failure_halfway_rolls_everything_back(world, listing, monkeypatch):
    from models import checkout_model
    def boom(*args, **kwargs):
        raise RuntimeError("simulated crash after the order row was written")
    monkeypatch.setattr(checkout_model, "_take_stock", boom)
    before = _order_count(world)
    res = _client(world, cart=[{"id": listing, "quantity": 1, "size": "M"}]).post("/api/checkout/complete", json=GOOD_BUYER)
    assert res.status_code == 500
    assert "Nothing was charged" in res.get_json()["error"]
    assert "simulated" not in res.get_json()["error"]          # internal details aren't shown to buyers
    assert _order_count(world) == before


# CO-10
def test_cannot_buy_from_your_own_storefront(world, listing):
    res = _client(world, who="seller", cart=[{"id": listing, "quantity": 1, "size": "M"}]
                  ).post("/api/checkout/complete", json=GOOD_BUYER)
    assert res.status_code == 400
    assert "own storefront" in res.get_json()["error"]


# CO-11
def test_deleted_listing_cannot_be_bought(world, listing):
    _one(world, "UPDATE listings SET status='DELETED' WHERE id=%s RETURNING id", (listing,))
    res = _client(world, cart=[{"id": listing, "quantity": 1, "size": "M"}]).post("/api/checkout/complete", json=GOOD_BUYER)
    assert res.status_code == 409


# CO-12
def test_size_that_does_not_exist(world, listing):
    res = _client(world, cart=[{"id": listing, "quantity": 1, "size": "XXL"}]).post("/api/checkout/complete", json=GOOD_BUYER)
    assert res.status_code == 409
    assert "XXL" in res.get_json()["error"]


# CO-13
def test_bad_buyer_details_save_nothing(world, listing):
    before = _order_count(world)
    res = _client(world, cart=[{"id": listing, "quantity": 1, "size": "M"}]
                  ).post("/api/checkout/complete", json={**GOOD_BUYER, "email": "nope"})
    assert res.status_code == 400
    assert _order_count(world) == before


# CO-14
def test_must_be_logged_in(world):
    assert _client(world, who=None, cart=[{"id": 1, "quantity": 1}]).post(
        "/api/checkout/complete", json=GOOD_BUYER).status_code == 401


# CO-15
def test_empty_bag(world):
    assert _client(world, cart=[]).post("/api/checkout/complete", json=GOOD_BUYER).status_code == 400


# CO-16/17/18: the order confirmation page's API
def test_order_confirmation_only_for_the_buyer(world, listing):
    res = _client(world, cart=[{"id": listing, "quantity": 1, "size": "L"}]).post("/api/checkout/complete", json=GOOD_BUYER)
    conf = res.get_json()["confirmation_number"]

    mine = _client(world).get(f"/api/orders/by-confirmation/{conf}")
    assert mine.status_code == 200
    body = mine.get_json()
    assert body["order"]["payment_method"] == "IN_PERSON"
    assert body["order"]["buyer_meeting_location"] == "Student Center"
    assert body["order_items"][0]["selected_size"] == "L"

    assert _client(world, who="other").get(f"/api/orders/by-confirmation/{conf}").status_code == 404   # CO-17
    assert _client(world, who=None).get(f"/api/orders/by-confirmation/{conf}").status_code == 401      # CO-18


# CO-19: the order shows up in My Orders, and the bag is emptied
def test_order_in_my_orders_and_bag_cleared(world, listing):
    client = _client(world, cart=[{"id": listing, "quantity": 1, "size": "M"}])
    conf = client.post("/api/checkout/complete", json=GOOD_BUYER).get_json()["confirmation_number"]
    orders = client.get("/api/orders/my").get_json()["orders"]
    assert conf in [o["confirmation_number"] for o in orders]
    with client.session_transaction() as sess:
        assert sess["cart"] == []


# CO-20: with no Stripe key the page only offers "pay in person"
def test_checkout_options_without_stripe(world, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    body = _client(world).get("/api/checkout/options").get_json()
    assert body["in_person"] is True and body["stripe_test"] is False
