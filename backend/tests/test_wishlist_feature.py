# Wishlist feature tests
# Original tests by Elali McNair 4/19/26 (add/get/check/remove, duplicate add).
# Updated by Nicco Hill 11/12/2026:
#   - Tests log in through the session (the API no longer trusts an X-User-Id header).
#   - Tests create their own users/listings (fixture_helpers.py) instead of using
#     the first rows in the database, and delete them afterwards.
#   - Added edge cases: deleted listings, sold-out listings, missing listings,
#     bad input, login required, and other users' wishlist items.
#
# Run: python -m pytest backend/tests/test_wishlist_feature.py -v
# Needs the database from .env (local Postgres). Skips if it can't connect.

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from app import create_app
from backend.config.db import get_connection
from backend.tests.fixture_helpers import DemoFixtures, log_in, log_out


class TestWishlistFeature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = get_connection()
        if conn is None:
            raise unittest.SkipTest("Database not available for wishlist tests.")
        conn.close()

        cls.app = create_app()
        cls.app.config["TESTING"] = True

        # One seller with a storefront, and two buyers
        cls.data = DemoFixtures()
        cls.seller = cls.data.create_user("seller")
        cls.buyer = cls.data.create_user("buyer")
        cls.other_buyer = cls.data.create_user("buyer2")
        cls.storefront_id = cls.data.create_storefront(cls.seller["id"])

    @classmethod
    def tearDownClass(cls):
        cls.data.cleanup()

    def setUp(self):
        # Fresh client + fresh active listing for every test so tests can't affect each other
        self.client = self.app.test_client()
        self.listing_id = self.data.create_listing(self.storefront_id, title="Wishlist Item")
        log_in(self.client, self.buyer)

    def _add(self, listing_id):
        return self.client.post("/api/wishlist", json={"listing_id": listing_id})

    def _wishlist(self):
        response = self.client.get("/api/wishlist")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["wishlist"]

    def _find(self, listing_id):
        return next((item for item in self._wishlist() if item["listing_id"] == listing_id), None)

    # WL-01 (Elali McNair) - Full happy path: add, check, list (with listing +
    # storefront details), remove, then check again.
    def test_add_get_check_and_remove_wishlist_item(self):
        add_response = self._add(self.listing_id)
        self.assertEqual(add_response.status_code, 201, add_response.get_data(as_text=True))

        check_response = self.client.get(f"/api/wishlist/{self.listing_id}/check")
        self.assertEqual(check_response.status_code, 200)
        self.assertTrue(check_response.get_json()["in_wishlist"])

        matched_item = self._find(self.listing_id)
        self.assertIsNotNone(matched_item)
        self.assertIn("title", matched_item["listing"])
        self.assertEqual(matched_item["listing"]["price"], 20.0)
        self.assertTrue(matched_item["listing"]["available"])
        self.assertIn("brand_name", matched_item["storefront"])

        remove_response = self.client.delete(f"/api/wishlist/{self.listing_id}")
        self.assertEqual(remove_response.status_code, 200, remove_response.get_data(as_text=True))

        final_check = self.client.get(f"/api/wishlist/{self.listing_id}/check")
        self.assertFalse(final_check.get_json()["in_wishlist"])

    # WL-02 (Elali McNair, extended by Nicco Hill) - Adding the same listing twice
    # returns 400 "already in wishlist" (storefront_view.js depends on this exact
    # response) and leaves exactly one row in the database.
    def test_duplicate_add_returns_error(self):
        self.assertEqual(self._add(self.listing_id).status_code, 201)

        second_response = self._add(self.listing_id)
        self.assertEqual(second_response.status_code, 400, second_response.get_data(as_text=True))
        self.assertIn("already in wishlist", second_response.get_data(as_text=True).lower())

        rows = self.data.count(
            "SELECT COUNT(*) FROM wishlist WHERE user_id = %s AND listing_id = %s",
            (self.buyer["id"], self.listing_id),
        )
        self.assertEqual(rows, 1)

    # WL-03 (Nicco Hill) - A deleted listing can't be added to a wishlist.
    def test_cannot_add_deleted_listing(self):
        self.data.set_listing_status(self.listing_id, "DELETED")

        response = self._add(self.listing_id)
        self.assertEqual(response.status_code, 404, response.get_data(as_text=True))
        self.assertIn("not found", response.get_json()["error"].lower())

    # WL-04 (Nicco Hill) - If a seller deletes a listing that is already on someone's
    # wishlist, it disappears from the wishlist and /check says false, but the
    # buyer can still remove the old entry.
    def test_listing_deleted_after_being_wishlisted(self):
        self.assertEqual(self._add(self.listing_id).status_code, 201)
        self.data.set_listing_status(self.listing_id, "DELETED")

        self.assertIsNone(self._find(self.listing_id))
        check = self.client.get(f"/api/wishlist/{self.listing_id}/check")
        self.assertFalse(check.get_json()["in_wishlist"])

        remove_response = self.client.delete(f"/api/wishlist/{self.listing_id}")
        self.assertEqual(remove_response.status_code, 200, remove_response.get_data(as_text=True))

    # WL-05 (Nicco Hill) - Sold-out items CAN be wishlisted (so buyers can wait for a
    # restock) but come back marked available = false so the UI won't sell them.
    def test_sold_out_listing_can_be_wishlisted_but_is_unavailable(self):
        sold_out_id = self.data.create_listing(self.storefront_id, title="Sold Out", quantity=0, status="SOLD_OUT")

        response = self._add(sold_out_id)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))

        item = self._find(sold_out_id)
        self.assertIsNotNone(item)
        self.assertEqual(item["listing"]["status"], "SOLD_OUT")
        self.assertFalse(item["listing"]["available"])

    # WL-06 (Nicco Hill) - Made-to-order items with 0 stock are still available.
    def test_made_to_order_listing_is_available_with_zero_stock(self):
        mto_id = self.data.create_listing(self.storefront_id, title="Made To Order", quantity=0, made_to_order=True)
        self.assertEqual(self._add(mto_id).status_code, 201)
        self.assertTrue(self._find(mto_id)["listing"]["available"])

    # WL-07 (Nicco Hill) - A listing id that doesn't exist returns 404.
    def test_add_missing_listing_returns_404(self):
        response = self._add(2_000_000_000)
        self.assertEqual(response.status_code, 404, response.get_data(as_text=True))

    # WL-08 (Nicco Hill) - Bad listing_id values are rejected with 400.
    # True is checked on purpose: in Python, bool counts as an int.
    def test_invalid_listing_id_returns_400(self):
        for bad_value in ["5", True, -1, 0, None, 1.5]:
            with self.subTest(listing_id=bad_value):
                response = self._add(bad_value)
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True))

        missing_field = self.client.post("/api/wishlist", json={})
        self.assertEqual(missing_field.status_code, 400)

    # WL-09 (Nicco Hill) - Every wishlist endpoint requires a logged-in user.
    def test_all_endpoints_require_login(self):
        log_out(self.client)
        requests = [
            self.client.post("/api/wishlist", json={"listing_id": self.listing_id}),
            self.client.get("/api/wishlist"),
            self.client.delete(f"/api/wishlist/{self.listing_id}"),
            self.client.get(f"/api/wishlist/{self.listing_id}/check"),
            self.client.get("/api/wishlist/items/1"),
        ]
        for response in requests:
            self.assertEqual(response.status_code, 401, response.get_data(as_text=True))

    # WL-10 (Nicco Hill) - Security regression: an X-User-Id header must NOT log you
    # in. Before this fix, anyone could read or edit any user's wishlist with it.
    def test_x_user_id_header_is_not_trusted(self):
        log_out(self.client)
        response = self.client.post(
            "/api/wishlist",
            json={"listing_id": self.listing_id},
            headers={"X-User-Id": str(self.buyer["id"])},
        )
        self.assertEqual(response.status_code, 401)

    # WL-11 (Nicco Hill) - Users can't look at another user's wishlist item by id.
    def test_cannot_view_other_users_wishlist_item(self):
        self.assertEqual(self._add(self.listing_id).status_code, 201)
        wishlist_id = self._find(self.listing_id)["id"]

        own = self.client.get(f"/api/wishlist/items/{wishlist_id}")
        self.assertEqual(own.status_code, 200)

        log_in(self.client, self.other_buyer)
        other = self.client.get(f"/api/wishlist/items/{wishlist_id}")
        self.assertEqual(other.status_code, 403)

    # WL-12 (Nicco Hill) - Removing something that isn't on the wishlist returns 404.
    def test_remove_item_not_in_wishlist_returns_404(self):
        response = self.client.delete(f"/api/wishlist/{self.listing_id}")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
