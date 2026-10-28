# Created by Ethan Williams 10/20/26
# Uses the database in .env and cleans up its test data.
import os
import sys
import time
import unittest
import uuid

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from app import create_app
from backend.config.db import get_connection
from services import message_service as message_service_module


class TestMessagingFeature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

        tag = uuid.uuid4().hex[:8]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password, email) VALUES (%s, 'x', %s) RETURNING id;",
            (f"msgtest_buyer_{tag}", f"msgtest_buyer_{tag}@my.hamptonu.edu"),
        )
        cls.buyer_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO users (username, password, email) VALUES (%s, 'x', %s) RETURNING id;",
            (f"msgtest_seller_{tag}", f"msgtest_seller_{tag}@my.hamptonu.edu"),
        )
        cls.seller_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO users (username, password, email) VALUES (%s, 'x', %s) RETURNING id;",
            (f"msgtest_other_{tag}", f"msgtest_other_{tag}@my.hamptonu.edu"),
        )
        cls.outsider_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO storefronts (owner_id, brand_name) VALUES (%s, %s) RETURNING id;",
            (cls.seller_id, f"Msg Test Brand {tag}"),
        )
        cls.storefront_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO listings (storefront_id, title, price, fulfillment_type, quantity_on_hand)
            VALUES (%s, 'Msg Test Hoodie', 40.00, 'IN_STOCK', 3) RETURNING id;
            """,
            (cls.storefront_id,),
        )
        cls.listing_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        # cascades to everything else
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM users WHERE id IN (%s, %s, %s);",
            (cls.buyer_id, cls.seller_id, cls.outsider_id),
        )
        conn.commit()
        cur.close()
        conn.close()

    def client_as(self, user_id):
        client = self.app.test_client()
        if user_id is not None:
            with client.session_transaction() as sess:
                sess["user_id"] = user_id
                sess["user"] = f"user{user_id}"
                sess["last_activity"] = time.time()  # pass the idle-timeout check
        return client

    def start_thread(self, client=None, listing_id="default"):
        client = client or self.client_as(self.buyer_id)
        payload = {"storefront_id": self.storefront_id}
        if listing_id == "default":
            payload["listing_id"] = self.listing_id
        elif listing_id is not None:
            payload["listing_id"] = listing_id
        return client.post("/api/conversations", json=payload)

    # starting conversations

    def test_requires_login(self):
        client = self.client_as(None)
        self.assertEqual(self.start_thread(client).status_code, 401)
        self.assertEqual(client.get("/api/conversations").status_code, 401)
        self.assertEqual(client.get("/messages").status_code, 302)

    def test_start_conversation_is_idempotent(self):
        first = self.start_thread()
        second = self.start_thread()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.get_json()["conversation_id"], second.get_json()["conversation_id"])

    def test_general_and_listing_threads_are_separate(self):
        general_a = self.start_thread(listing_id=None).get_json()["conversation_id"]
        general_b = self.start_thread(listing_id=None).get_json()["conversation_id"]
        about_item = self.start_thread().get_json()["conversation_id"]
        self.assertEqual(general_a, general_b)
        self.assertNotEqual(general_a, about_item)

    def test_seller_cannot_message_own_storefront(self):
        response = self.start_thread(self.client_as(self.seller_id))
        self.assertEqual(response.status_code, 400)

    def test_rejects_listing_from_another_storefront(self):
        self.assertEqual(self.start_thread(listing_id=999999999).status_code, 404)

    def test_rejects_unknown_storefront(self):
        client = self.client_as(self.buyer_id)
        response = client.post("/api/conversations", json={"storefront_id": 999999999})
        self.assertEqual(response.status_code, 404)

    # sending and reading

    def test_full_exchange_with_unread_counts(self):
        buyer = self.client_as(self.buyer_id)
        seller = self.client_as(self.seller_id)
        conversation_id = self.start_thread(buyer).get_json()["conversation_id"]

        sent = buyer.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"body": "  Is the hoodie still available in M?  "},
        )
        self.assertEqual(sent.status_code, 201)
        message = sent.get_json()["message"]
        self.assertEqual(message["body"], "Is the hoodie still available in M?")

        # seller sees it as unread
        self.assertGreaterEqual(seller.get("/api/messages/unread-count").get_json()["unread"], 1)
        inbox = seller.get("/api/conversations").get_json()["conversations"]
        thread = next(c for c in inbox if c["id"] == conversation_id)
        self.assertEqual(thread["role"], "seller")
        self.assertEqual(thread["listing_title"], "Msg Test Hoodie")
        self.assertTrue(thread["other_name"].startswith("msgtest_buyer_"))
        self.assertEqual(thread["unread"], 1)

        # opening marks it read
        messages = seller.get(f"/api/conversations/{conversation_id}/messages").get_json()["messages"]
        self.assertEqual([m["id"] for m in messages], [message["id"]])
        thread = next(c for c in seller.get("/api/conversations").get_json()["conversations"]
                      if c["id"] == conversation_id)
        self.assertEqual(thread["unread"], 0)

        # buyer only gets new messages
        reply = seller.post(f"/api/conversations/{conversation_id}/messages", json={"body": "Yes! 2 left."})
        self.assertEqual(reply.status_code, 201)
        newer = buyer.get(
            f"/api/conversations/{conversation_id}/messages?after={message['id']}"
        ).get_json()["messages"]
        self.assertEqual([m["body"] for m in newer], ["Yes! 2 left."])

        buyer_view = buyer.get(f"/api/conversations/{conversation_id}").get_json()["conversation"]
        self.assertEqual(buyer_view["role"], "buyer")
        self.assertTrue(buyer_view["other_name"].startswith("Msg Test Brand"))

    def test_outsider_cannot_read_or_post(self):
        conversation_id = self.start_thread().get_json()["conversation_id"]
        outsider = self.client_as(self.outsider_id)
        self.assertEqual(outsider.get(f"/api/conversations/{conversation_id}").status_code, 404)
        self.assertEqual(outsider.get(f"/api/conversations/{conversation_id}/messages").status_code, 404)
        response = outsider.post(f"/api/conversations/{conversation_id}/messages", json={"body": "hi"})
        self.assertEqual(response.status_code, 404)

    def test_rejects_empty_and_too_long_messages(self):
        buyer = self.client_as(self.buyer_id)
        conversation_id = self.start_thread(buyer).get_json()["conversation_id"]
        url = f"/api/conversations/{conversation_id}/messages"
        self.assertEqual(buyer.post(url, json={"body": "   "}).status_code, 400)
        self.assertEqual(buyer.post(url, json={}).status_code, 400)
        self.assertEqual(buyer.post(url, json={"body": "x" * 2001}).status_code, 400)

    def test_rate_limit(self):
        buyer = self.client_as(self.outsider_id)
        conversation_id = self.start_thread(buyer).get_json()["conversation_id"]
        url = f"/api/conversations/{conversation_id}/messages"
        original = message_service_module.RATE_LIMIT_PER_MINUTE
        message_service_module.RATE_LIMIT_PER_MINUTE = 2
        try:
            self.assertEqual(buyer.post(url, json={"body": "one"}).status_code, 201)
            self.assertEqual(buyer.post(url, json={"body": "two"}).status_code, 201)
            self.assertEqual(buyer.post(url, json={"body": "three"}).status_code, 429)
        finally:
            message_service_module.RATE_LIMIT_PER_MINUTE = original


if __name__ == "__main__":
    unittest.main()
