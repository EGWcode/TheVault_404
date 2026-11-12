# Create Listing feature tests (POST /api/listings/create)
# Original tests by Elali McNair 4/19/26 (create from form, image required, login required).
# Updated by Nicco Hill 11/12/2026:
#   - Tests create their own seller + storefront (fixture_helpers.py) instead of
#     borrowing the first storefront in the database, and delete it afterwards.
#   - Uploaded test images are deleted from static/uploads after each test.
#   - Fixed CL-02: the server's message is now "At least one listing image is required."
#   - Added form validation tests (CL-04 to CL-08) for the checks that now run
#     BEFORE any image is uploaded, and checked nothing is saved when they fail.
#
# Note: the listing API still identifies the user by X-User-Id header, so these
# tests send it. See the listing_controller.py get_current_user() TODO.
#
# Run: python -m pytest backend/tests/test_create_listing_feature.py -v

import io
import os
import sys
import unittest
import uuid

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from app import create_app
from backend.config.db import get_connection
from backend.tests.fixture_helpers import DemoFixtures

UPLOAD_DIR = os.path.join(PROJECT_ROOT, "static", "uploads", "listings")


class TestCreateListingFeature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = get_connection()
        if conn is None:
            raise unittest.SkipTest("Database not available for create listing tests.")
        conn.close()

        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        cls.data = DemoFixtures()
        cls.seller = cls.data.create_user("lister")
        cls.user_id = cls.seller["id"]
        cls.storefront_id = cls.data.create_storefront(cls.user_id)

    @classmethod
    def tearDownClass(cls):
        cls.data.cleanup()  # cascades to the storefront and every listing it created

    def setUp(self):
        self.uploads_before = self._list_uploads()

    def tearDown(self):
        # Remove any image files this test uploaded locally
        for filename in self._list_uploads() - self.uploads_before:
            os.remove(os.path.join(UPLOAD_DIR, filename))

    @staticmethod
    def _list_uploads():
        return set(os.listdir(UPLOAD_DIR)) if os.path.isdir(UPLOAD_DIR) else set()

    def _auth_headers(self):
        return {"X-User-Id": str(self.user_id)}

    def _listing_count(self):
        return self.data.count("SELECT COUNT(*) FROM listings WHERE storefront_id = %s", (self.storefront_id,))

    def _post_form(self, **overrides):
        """Posts a valid create-listing form; pass a field=None to leave it out."""
        form = {
            "title": f"TEST_CREATE_LISTING_{uuid.uuid4().hex[:8]}",
            "quantity_on_hand": "5",
            "price": "39.99",
            "fulfillment_type": "IN_STOCK",
            "status": "ACTIVE",
            "sizes_available": '["M", "L"]',
            "size_quantities": '{"M": 2, "L": 3}',
            "listing_images": (io.BytesIO(b"fake image bytes"), "test_listing.png"),
        }
        form.update(overrides)
        form = {k: v for k, v in form.items() if v is not None}
        return self.client.post(
            "/api/listings/create",
            data=form,
            headers=self._auth_headers(),
            content_type="multipart/form-data",
        )

    # CL-01 (Elali McNair, extended by Nicco Hill) - A valid form creates an ACTIVE
    # listing in the seller's storefront, with per-size stock and the total
    # quantity worked out from the sizes (2 + 3 = 5).
    def test_create_listing_from_form_success(self):
        unique_title = f"TEST_CREATE_LISTING_{uuid.uuid4().hex[:8]}"
        response = self._post_form(title=unique_title)

        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual(payload["title"], unique_title)
        self.assertEqual(payload["storefront_id"], self.storefront_id)
        self.assertEqual(payload["status"], "ACTIVE")
        self.assertEqual(payload["fulfillment_type"], "IN_STOCK")
        self.assertEqual(payload["quantity_on_hand"], 5)

        status, total, sizes = self.data.listing_stock(payload["id"])
        self.assertEqual(sizes, {"M": 2, "L": 3})

        verify_response = self.client.get(f"/api/storefronts/{self.storefront_id}/listings")
        self.assertEqual(verify_response.status_code, 200)
        matched = next((item for item in verify_response.get_json() if item["id"] == payload["id"]), None)
        self.assertIsNotNone(matched)
        self.assertEqual(matched["title"], unique_title)

    # CL-02 (Elali McNair, message updated by Nicco Hill) - At least one image is required.
    def test_create_listing_requires_image_file(self):
        response = self._post_form(listing_images=None)

        self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
        self.assertIn("At least one listing image is required", response.get_data(as_text=True))

    # CL-03 (Elali McNair) - Creating a listing without logging in is refused.
    def test_create_listing_requires_authentication(self):
        response = self.client.post(
            f"/api/storefronts/{self.storefront_id}/listings",
            json={
                "title": "Unauthorized Listing",
                "price": 20,
                "fulfillment_type": "IN_STOCK",
                "quantity_on_hand": 2,
            },
        )

        self.assertEqual(response.status_code, 401, response.get_data(as_text=True))
        self.assertIn("Unauthorized", response.get_data(as_text=True))

    # CL-04 (Nicco Hill) - Bad prices are rejected: missing, not a number,
    # negative, more than 2 decimals, too big for NUMERIC(10,2), and "nan".
    def test_invalid_price_is_rejected(self):
        cases = {
            "": "price is required",
            "abc": "price must be a number",
            "-5": "cannot be negative",
            "19.999": "2 decimal places",
            "100000000": "cannot be more than",
            "nan": "price must be a number",
        }
        for price, expected in cases.items():
            with self.subTest(price=price):
                response = self._post_form(price=price)
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
                self.assertIn(expected, response.get_json()["error"])

    # CL-05 (Nicco Hill) - Title is required and limited to 120 characters
    # (the size of the listings.title column).
    def test_title_rules(self):
        self.assertIn("title is required", self._post_form(title="   ").get_json()["error"])

        too_long = self._post_form(title="x" * 121)
        self.assertEqual(too_long.status_code, 400)
        self.assertIn("120 characters", too_long.get_json()["error"])

        exactly_max = self._post_form(title="y" * 120)
        self.assertEqual(exactly_max.status_code, 201, exactly_max.get_data(as_text=True))

    # CL-06 (Nicco Hill) - Size and quantity rules: sizes must be from the form's
    # list, can't repeat, quantities must be whole numbers 0 or more, and a
    # quantity can't be given for a size that wasn't selected.
    def test_size_and_quantity_rules(self):
        cases = [
            ({"sizes_available": "[]"}, "At least one size"),
            ({"sizes_available": '["M", "HUGE"]'}, "Sizes must be from"),
            ({"sizes_available": '["M", "M"]', "size_quantities": '{"M": 1}'}, "only be listed once"),
            ({"size_quantities": '{"M": -1, "L": 3}'}, "cannot be negative"),
            ({"size_quantities": '{"M": 1.5, "L": 3}'}, "whole number"),
            ({"size_quantities": '{"M": "two", "L": 3}'}, "whole number"),
            ({"size_quantities": '{"M": 1, "XL": 3}'}, "wasn't selected"),
            ({"sizes_available": "not json"}, "Invalid sizes_available"),
        ]
        for overrides, expected in cases:
            with self.subTest(**overrides):
                response = self._post_form(**overrides)
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
                self.assertIn(expected, response.get_json()["error"])

    # CL-07 (Nicco Hill) - Only ACTIVE/INACTIVE status and image files are accepted.
    def test_status_and_image_type_rules(self):
        self.assertIn("status must be", self._post_form(status="SOLD_OUT").get_json()["error"])
        bad_image = self._post_form(listing_images=(io.BytesIO(b"MZ"), "virus.exe"))
        self.assertEqual(bad_image.status_code, 400)
        self.assertIn("Image must be", bad_image.get_json()["error"])

    # CL-08 (Nicco Hill) - When validation fails, nothing is saved: no listing row
    # and no uploaded image file. (Before, images were uploaded first, so a bad
    # price left an orphaned file in S3.)
    def test_failed_validation_saves_nothing(self):
        listings_before = self._listing_count()

        response = self._post_form(price="-1")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._listing_count(), listings_before)
        self.assertEqual(self._list_uploads(), self.uploads_before)

    # CL-09 (Nicco Hill) - A listing with 0 total stock is created as SOLD_OUT,
    # but a made-to-order listing with 0 stock stays ACTIVE.
    def test_zero_stock_and_made_to_order(self):
        zero = self._post_form(size_quantities='{"M": 0, "L": 0}')
        self.assertEqual(zero.status_code, 201, zero.get_data(as_text=True))
        self.assertEqual(zero.get_json()["status"], "SOLD_OUT")

        mto = self._post_form(size_quantities='{"M": 0, "L": 0}', is_made_to_order="true")
        self.assertEqual(mto.status_code, 201, mto.get_data(as_text=True))
        self.assertEqual(mto.get_json()["status"], "ACTIVE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
