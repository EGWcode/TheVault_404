# Created by Anthony Jackson 10/21/26 for the optional user profile
# The first part tests the rules with no database. The second part runs against the
# database in .env. It creates its own temporary user and deletes it afterwards.
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
from services import profile_service


class TestProfileRules(unittest.TestCase):
    """No database needed."""

    def test_names(self):
        clean = profile_service._clean_name
        self.assertEqual(clean("  Anthony ", "First name"), "Anthony")
        self.assertEqual(clean("Mary-Jane O'Neil", "Last name"), "Mary-Jane O'Neil")
        self.assertIsNone(clean("   ", "First name"))
        with self.assertRaises(profile_service._Invalid):
            clean("Anthony2", "First name")
        with self.assertRaises(profile_service._Invalid):
            clean("A" * 51, "First name")

    def test_phone(self):
        clean = profile_service._clean_phone
        self.assertEqual(clean("(757) 555-1234"), "7575551234")
        self.assertEqual(clean("757.555.1234"), "7575551234")
        self.assertEqual(clean("+1 757 555 1234"), "7575551234")
        self.assertEqual(clean("17575551234"), "7575551234")
        self.assertIsNone(clean(""))
        for bad in ("12345", "abcdefghij", "75755512345678"):
            with self.assertRaises(profile_service._Invalid):
                clean(bad)

    def test_class_year(self):
        clean = profile_service._clean_class_year
        self.assertEqual(clean("senior"), "Senior")
        self.assertEqual(clean("GRADUATE"), "Graduate")
        self.assertIsNone(clean(""))
        with self.assertRaises(profile_service._Invalid):
            clean("Fifth year")

    def test_hometown(self):
        clean = profile_service._clean_hometown
        self.assertEqual(clean(" Norfolk, VA "), "Norfolk, VA")
        self.assertIsNone(clean(""))
        with self.assertRaises(profile_service._Invalid):
            clean("x" * 101)


class TestProfileRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

        tag = uuid.uuid4().hex[:8]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password, email) VALUES (%s, 'x', %s) RETURNING id;",
            (f"proftest_{tag}", f"proftest_{tag}@my.hamptonu.edu"),
        )
        cls.user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = %s;", (cls.user_id,))
        conn.commit()
        cur.close()
        conn.close()

    def _client(self, logged_in=True):
        client = self.app.test_client()
        if logged_in:
            with client.session_transaction() as session:
                session["user_id"] = self.user_id
        return client

    def test_1_must_be_logged_in(self):
        client = self._client(logged_in=False)
        self.assertEqual(client.get("/api/profile").status_code, 401)
        self.assertEqual(client.patch("/api/profile", json={"phone": "7575551234"}).status_code, 401)

    def test_2_new_user_starts_with_a_blank_profile(self):
        body = self._client().get("/api/profile").get_json()
        for field in ("first_name", "last_name", "phone", "class_year", "hometown"):
            self.assertEqual(body[field], "")

    def test_3_saves_and_reads_back(self):
        client = self._client()
        response = client.patch("/api/profile", json={
            "first_name": "Anthony", "last_name": "Jackson", "phone": "(757) 555-1234",
            "class_year": "senior", "hometown": "Norfolk, VA",
        })
        self.assertEqual(response.status_code, 200)
        saved = client.get("/api/profile").get_json()
        self.assertEqual(saved["first_name"], "Anthony")
        self.assertEqual(saved["phone"], "7575551234")
        self.assertEqual(saved["class_year"], "Senior")
        self.assertEqual(saved["hometown"], "Norfolk, VA")

    def test_4_clear_error_messages_name_the_field(self):
        client = self._client()
        cases = [
            ({"phone": "123"}, "phone", "10 digits"),
            ({"class_year": "Fifth year"}, "class_year", "Freshman"),
            ({"first_name": "Anthony2"}, "first_name", "letters"),
            ({"hometown": "x" * 101}, "hometown", "100"),
        ]
        for payload, field, words in cases:
            response = client.patch("/api/profile", json=payload)
            self.assertEqual(response.status_code, 400, payload)
            body = response.get_json()
            self.assertEqual(body["field"], field)
            self.assertIn(words, body["error"])

    def test_5_a_bad_value_saves_nothing(self):
        client = self._client()
        client.patch("/api/profile", json={"first_name": "Keep"})
        client.patch("/api/profile", json={"first_name": "Changed", "phone": "bad"})
        self.assertEqual(client.get("/api/profile").get_json()["first_name"], "Keep")

    def test_6_empty_box_clears_a_field(self):
        client = self._client()
        client.patch("/api/profile", json={"hometown": "Richmond"})
        client.patch("/api/profile", json={"hometown": ""})
        self.assertEqual(client.get("/api/profile").get_json()["hometown"], "")

    def test_7_cannot_change_role_or_other_columns(self):
        client = self._client()
        response = client.patch("/api/profile", json={"role": "admin", "email": "evil@x.com"})
        self.assertEqual(response.status_code, 400)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE id = %s;", (self.user_id,))
        self.assertNotEqual(cur.fetchone()[0], "admin")
        cur.close()
        conn.close()

    def test_8_nothing_to_save(self):
        response = self._client().patch("/api/profile", json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Nothing to save", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
