# Purchase flow tests - Nicco Hill 11/12/2026
#
# Covers POST/GET /api/purchases end to end against the real database:
#   - happy path: stock goes down, price comes from the DB, item leaves the wishlist,
#     purchase shows in history and only its owner can see it
#   - edge cases: sold out, not enough stock, deleted, paused, own listing,
#     per-size stock, made-to-order, bad input, login required
#   - two buyers racing for the last item: exactly one wins
#   - Stripe checkout refuses a deleted item BEFORE sending the buyer to pay
#
# Test users/listings are created per class (fixture_helpers.py) and deleted after.
# Run: python -m pytest backend/tests/test_purchase_flow.py -v

import os
import sys
import threading
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from app import create_app
from backend.config.db import get_connection
from backend.tests.fixture_helpers import DemoFixtures, log_in, log_out
import controllers.checkout_controller as checkout_controller


class TestPurchaseFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = get_connection()
        if conn is None:
            raise unittest.SkipTest("Database not available for purchase tests.")
        conn.close()

        cls.app = create_app()
        cls.app.config["TESTING"] = True

        cls.data = DemoFixtures()
        cls.seller = cls.data.create_user("seller")
        cls.buyer = cls.data.create_user("buyer")
        cls.other_buyer = cls.data.create_user("buyer2")
        cls.storefront_id = cls.data.create_storefront(cls.seller["id"])

    @classmethod
    def tearDownClass(cls):
        cls.data.cleanup()

    def setUp(self):
        self.client = self.app.test_client()
        log_in(self.client, self.buyer)

    def _buy(self, listing_id, quantity=1, size=None, client=None):
        body = {"listing_id": listing_id, "quantity": quantity}
        if size is not None:
            body["size"] = size
        return (client or self.client).post("/api/purchases", json=body)

    # PF-01 - Happy path. Buying 2 of a sized listing:
    #   * returns 201 with the price from the DATABASE (the client can't set it)
    #   * takes 2 off that size and off the listing total
    #   * removes the item from the buyer's wishlist
    #   * shows up in GET /api/purchases and GET /api/purchases/<id>
    #   * another user gets 403 on that purchase
    def test_successful_purchase_updates_stock_wishlist_and_history(self):
        listing_id = self.data.create_listing(self.storefront_id, title="Hoodie", price=45.00,
                                              sizes={"M": 3, "L": 2})
        self.assertEqual(
            self.client.post("/api/wishlist", json={"listing_id": listing_id}).status_code, 201
        )

        response = self.client.post(
            "/api/purchases",
            json={"listing_id": listing_id, "quantity": 2, "size": "M", "price": 0.01},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        purchase = response.get_json()["purchase"]
        self.assertEqual(purchase["purchase_price"], 45.00)  # ignored the client's 0.01
        self.assertEqual(purchase["quantity"], 2)
        self.assertEqual(purchase["size"], "M")

        status, total, sizes = self.data.listing_stock(listing_id)
        self.assertEqual(status, "ACTIVE")
        self.assertEqual(total, 3)
        self.assertEqual(sizes, {"M": 1, "L": 2})

        in_wishlist = self.client.get(f"/api/wishlist/{listing_id}/check").get_json()["in_wishlist"]
        self.assertFalse(in_wishlist)

        history = self.client.get("/api/purchases")
        self.assertEqual(history.status_code, 200)
        self.assertIn(purchase["id"], [p["id"] for p in history.get_json()["purchases"]])

        detail = self.client.get(f"/api/purchases/{purchase['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["purchase"]["listing_id"], listing_id)

        log_in(self.client, self.other_buyer)
        self.assertEqual(self.client.get(f"/api/purchases/{purchase['id']}").status_code, 403)

    # PF-02 - Buying the last item marks the listing SOLD_OUT, and the next
    # purchase is refused with 409 "sold out".
    def test_buying_last_item_marks_listing_sold_out(self):
        listing_id = self.data.create_listing(self.storefront_id, title="Last One", quantity=1)

        self.assertEqual(self._buy(listing_id).status_code, 201)
        status, total, _ = self.data.listing_stock(listing_id)
        self.assertEqual((status, total), ("SOLD_OUT", 0))

        log_in(self.client, self.other_buyer)
        second = self._buy(listing_id)
        self.assertEqual(second.status_code, 409, second.get_data(as_text=True))
        self.assertIn("sold out", second.get_json()["error"].lower())

    # PF-03 - Asking for more than is in stock is refused, and nothing changes.
    def test_not_enough_stock_is_rejected_without_changing_stock(self):
        listing_id = self.data.create_listing(self.storefront_id, title="Few Left", quantity=2)

        response = self._buy(listing_id, quantity=3)
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertIn("only 2 left", response.get_json()["error"].lower())
        self.assertEqual(self.data.listing_stock(listing_id)[:2], ("ACTIVE", 2))

    # PF-04 - Deleted listings can't be bought (404), and paused/inactive ones
    # can't either (409).
    def test_deleted_and_inactive_listings_cannot_be_bought(self):
        deleted_id = self.data.create_listing(self.storefront_id, title="Deleted", status="DELETED")
        inactive_id = self.data.create_listing(self.storefront_id, title="Paused", status="INACTIVE")

        self.assertEqual(self._buy(deleted_id).status_code, 404)
        self.assertEqual(self._buy(inactive_id).status_code, 409)
        self.assertEqual(self._buy(2_000_000_000).status_code, 404)

    # PF-05 - A listing whose storefront has been deactivated can't be bought.
    def test_listing_in_inactive_storefront_cannot_be_bought(self):
        paused_seller = self.data.create_user("paused")
        paused_store = self.data.create_storefront(paused_seller["id"], is_active=False)
        listing_id = self.data.create_listing(paused_store, title="Paused Store Item")

        self.assertEqual(self._buy(listing_id).status_code, 409)

    # PF-06 - Sellers can't buy their own listings.
    def test_seller_cannot_buy_own_listing(self):
        listing_id = self.data.create_listing(self.storefront_id, title="Own Item")
        log_in(self.client, self.seller)

        response = self._buy(listing_id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("your own", response.get_json()["error"].lower())

    # PF-07 - Listings with per-size stock need a valid size, and a sold-out
    # size is refused even if other sizes have stock.
    def test_size_rules_for_sized_listings(self):
        listing_id = self.data.create_listing(self.storefront_id, title="Sized", sizes={"S": 0, "M": 4})

        self.assertEqual(self._buy(listing_id).status_code, 400)               # no size
        self.assertEqual(self._buy(listing_id, size="XXL").status_code, 400)   # not offered
        self.assertEqual(self._buy(listing_id, size="S").status_code, 409)     # size sold out
        self.assertEqual(self._buy(listing_id, size="M").status_code, 201)
        self.assertEqual(self.data.listing_stock(listing_id)[2], {"S": 0, "M": 3})

    # PF-08 - Made-to-order listings can always be bought, and stock isn't touched.
    def test_made_to_order_skips_stock(self):
        listing_id = self.data.create_listing(self.storefront_id, title="MTO", quantity=0, made_to_order=True)

        self.assertEqual(self._buy(listing_id, quantity=5).status_code, 201)
        self.assertEqual(self.data.listing_stock(listing_id)[:2], ("ACTIVE", 0))

    # PF-09 - Bad input is rejected with 400 before touching the database.
    def test_invalid_input_returns_400(self):
        listing_id = self.data.create_listing(self.storefront_id, title="Input Checks")
        for quantity in [0, -1, "2", True, 1.5, 100]:
            with self.subTest(quantity=quantity):
                self.assertEqual(self._buy(listing_id, quantity=quantity).status_code, 400)
        self.assertEqual(self._buy("abc").status_code, 400)
        self.assertEqual(self._buy(listing_id, size="  ").status_code, 400)
        self.assertEqual(self.client.post("/api/purchases", json={}).status_code, 400)
        self.assertEqual(self.data.listing_stock(listing_id)[1], 5)

    # PF-10 - Every purchase endpoint requires login, and an X-User-Id header
    # is NOT accepted as a login.
    def test_requires_login(self):
        listing_id = self.data.create_listing(self.storefront_id, title="Login Check")
        log_out(self.client)

        self.assertEqual(self._buy(listing_id).status_code, 401)
        self.assertEqual(self.client.get("/api/purchases").status_code, 401)
        self.assertEqual(self.client.get("/api/purchases/1").status_code, 401)
        spoofed = self.client.post(
            "/api/purchases",
            json={"listing_id": listing_id, "quantity": 1},
            headers={"X-User-Id": str(self.buyer["id"])},
        )
        self.assertEqual(spoofed.status_code, 401)

    # PF-11 - Race condition: two buyers try to buy the LAST item at the same time.
    # The listing row is locked during the purchase, so exactly one succeeds and
    # stock never goes negative.
    def test_two_buyers_racing_for_last_item(self):
        listing_id = self.data.create_listing(self.storefront_id, title="Race", quantity=1)
        client_a, client_b = self.app.test_client(), self.app.test_client()
        log_in(client_a, self.buyer)
        log_in(client_b, self.other_buyer)

        results = []
        start = threading.Barrier(2)

        def attempt(client):
            start.wait()
            results.append(self._buy(listing_id, client=client).status_code)

        threads = [threading.Thread(target=attempt, args=(c,)) for c in (client_a, client_b)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sorted(results), [201, 409])
        self.assertEqual(self.data.listing_stock(listing_id)[:2], ("SOLD_OUT", 0))
        purchases = self.data.count("SELECT COUNT(*) FROM purchases WHERE listing_id = %s", (listing_id,))
        self.assertEqual(purchases, 1)

    # PF-12 - Stripe checkout: a cart holding a deleted listing is refused with 409
    # BEFORE a Stripe session is created, so the buyer is never charged for it.
    def test_checkout_rejects_deleted_item_before_stripe(self):
        listing_id = self.data.create_listing(self.storefront_id, title="Gone", status="DELETED")
        with self.client.session_transaction() as sess:
            sess["cart"] = [{"id": listing_id, "name": "Gone", "price": 20.0, "quantity": 1}]

        def stripe_must_not_be_called(**kwargs):
            raise AssertionError("Stripe session was created for an unavailable item")

        original = checkout_controller.stripe.checkout.Session.create
        original_key = checkout_controller.stripe.api_key
        checkout_controller.stripe.checkout.Session.create = stripe_must_not_be_called
        checkout_controller.stripe.api_key = "sk_test_fake"
        try:
            response = self.client.post("/api/checkout/create-session", json={
                "first_name": "Test", "last_name": "Buyer", "email": "t@my.hamptonu.edu",
                "contact": "5555555555", "meeting_location": "Student Center",
            })
        finally:
            checkout_controller.stripe.checkout.Session.create = original
            checkout_controller.stripe.api_key = original_key

        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertIn("no longer available", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
