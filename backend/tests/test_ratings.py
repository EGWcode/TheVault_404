# Created by Anthony Jackson 10/21/26 for the storefront rating feature
# The first part tests the rules with no database. The second part runs against the
# database in .env. It creates its own temporary users and storefront, and deletes
# them (and their ratings) afterwards.
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
from services import rating_service


class TestRatingRules(unittest.TestCase):
    """No database needed."""

    def test_label_tiers(self):
        self.assertEqual(rating_service.rating_label(0, 0), "No ratings yet")
        self.assertEqual(rating_service.rating_label(5.0, 3), "Top rated")
        self.assertEqual(rating_service.rating_label(4.5, 2), "Top rated")
        self.assertEqual(rating_service.rating_label(4.4, 2), "Highly rated")
        self.assertEqual(rating_service.rating_label(3.5, 2), "Good")
        self.assertEqual(rating_service.rating_label(2.5, 2), "Mixed")
        self.assertEqual(rating_service.rating_label(1.5, 2), "Low rated")

    def test_text_uses_singular_and_plural(self):
        self.assertEqual(rating_service.rating_text(0, 0), "No ratings yet")
        self.assertEqual(rating_service.rating_text(5.0, 1), "5.0 stars (1 rating)")
        self.assertEqual(rating_service.rating_text(4.3, 12), "4.3 stars (12 ratings)")

    def test_stars_must_be_a_whole_number_from_1_to_5(self):
        clean = rating_service._clean_stars
        for good in (1, 2, 3, 4, 5, "3", 4.0):
            self.assertIsNotNone(clean(good), good)
        for bad in (0, 6, -1, 4.5, "x", "", None, True, [], {}):
            self.assertIsNone(clean(bad), bad)


class TestRatingRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

        tag = uuid.uuid4().hex[:8]
        conn = get_connection()
        cur = conn.cursor()
        ids = []
        for who in ("rater", "owner"):
            cur.execute(
                "INSERT INTO users (username, password, email) VALUES (%s, 'x', %s) RETURNING id;",
                (f"ratetest_{who}_{tag}", f"ratetest_{who}_{tag}@my.hamptonu.edu"),
            )
            ids.append(cur.fetchone()[0])
        cls.rater_id, cls.owner_id = ids
        cur.execute(
            "INSERT INTO storefronts (owner_id, brand_name, bio, categories, is_active) "
            "VALUES (%s, %s, 'test', 'Test', TRUE) RETURNING id;",
            (cls.owner_id, f"Rating Test Store {tag}"),
        )
        cls.storefront_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM storefronts WHERE id = %s;", (cls.storefront_id,))
        cur.execute("DELETE FROM users WHERE id IN (%s, %s);", (cls.rater_id, cls.owner_id))
        conn.commit()
        cur.close()
        conn.close()

    def _client(self, user_id=None):
        client = self.app.test_client()
        if user_id:
            with client.session_transaction() as session:
                session["user_id"] = user_id
        return client

    def _rate(self, client, stars, storefront_id=None):
        return client.post(
            f"/api/storefronts/{storefront_id or self.storefront_id}/ratings", json={"stars": stars}
        )

    def test_1_must_be_logged_in(self):
        response = self._rate(self._client(), 5)
        self.assertEqual(response.status_code, 401)
        self.assertIn("log in", response.get_json()["error"].lower())

    def test_2_bad_star_values_are_rejected_with_a_clear_message(self):
        client = self._client(self.rater_id)
        for bad in (0, 6, 4.5, "five", None):
            response = self._rate(client, bad)
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn("1 to 5", response.get_json()["error"])

    def test_3_cannot_rate_your_own_storefront(self):
        response = self._rate(self._client(self.owner_id), 5)
        self.assertEqual(response.status_code, 403)
        self.assertIn("own storefront", response.get_json()["error"])

    def test_4_unknown_storefront(self):
        response = self._rate(self._client(self.rater_id), 5, storefront_id=99999999)
        self.assertEqual(response.status_code, 404)

    def test_5_same_user_can_rate_again_and_average_updates(self):
        client = self._client(self.rater_id)
        first = self._rate(client, 5)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.get_json()["count"], 1)
        self.assertEqual(first.get_json()["average"], 5.0)

        second = self._rate(client, 4)
        self.assertEqual(second.status_code, 201)
        body = second.get_json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["average"], 4.5)
        self.assertEqual(body["label"], "Top rated")
        self.assertEqual(body["text"], "4.5 stars (2 ratings)")

    def test_6_summary_routes_show_the_rating(self):
        client = self._client(self.rater_id)
        self._rate(client, 4)

        one = client.get(f"/api/storefronts/{self.storefront_id}/ratings")
        self.assertEqual(one.status_code, 200)
        self.assertGreaterEqual(one.get_json()["count"], 1)

        everyone = client.get("/api/ratings/summary").get_json()
        self.assertIn(str(self.storefront_id), everyone)

        top = client.get("/api/ratings/top").get_json()
        self.assertIn(self.storefront_id, [item["storefront_id"] for item in top])

    def test_7_top_rated_is_sorted_best_first(self):
        top = self._client().get("/api/ratings/top").get_json()
        averages = [item["average"] for item in top]
        self.assertEqual(averages, sorted(averages, reverse=True))

    def test_8_unrated_storefront_says_no_ratings_yet(self):
        # One storefront per user is allowed, so this test uses its own temporary user
        tag = uuid.uuid4().hex[:8]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password, email) VALUES (%s, 'x', %s) RETURNING id;",
            (f"ratetest_empty_{tag}", f"ratetest_empty_{tag}@my.hamptonu.edu"),
        )
        empty_owner = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO storefronts (owner_id, brand_name, bio, categories, is_active) "
            "VALUES (%s, %s, 'test', 'Test', TRUE) RETURNING id;",
            (empty_owner, f"Unrated Store {tag}"),
        )
        empty_id = cur.fetchone()[0]
        conn.commit()
        try:
            body = self._client().get(f"/api/storefronts/{empty_id}/ratings").get_json()
            self.assertEqual(body["count"], 0)
            self.assertEqual(body["label"], "No ratings yet")
        finally:
            cur.execute("DELETE FROM storefronts WHERE id = %s;", (empty_id,))
            cur.execute("DELETE FROM users WHERE id = %s;", (empty_owner,))
            conn.commit()
            cur.close()
            conn.close()


if __name__ == "__main__":
    unittest.main()
