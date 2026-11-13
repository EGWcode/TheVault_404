# Shared test data helpers - Nicco Hill 11/12/2026
#
# Creates throwaway users / storefronts / listings for a test class and deletes
# them afterwards, so tests never depend on (or change) whatever data is already
# in the database. Every name gets a random suffix so parallel runs don't collide.
#
# Deleting a user cascades to their storefront, listings, sizes, images,
# wishlist rows and purchases (see ON DELETE CASCADE in init_db.py).

import json
import time
import uuid

from backend.config.db import get_connection


class DemoFixtures:
    def __init__(self):
        self.suffix = uuid.uuid4().hex[:8]
        self.user_ids = []

    def _run(self, query, params=(), fetch=True):
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(query, params)
            row = cur.fetchone() if fetch else None
            conn.commit()
            return row
        finally:
            cur.close()
            conn.close()

    def create_user(self, name):
        username = f"t_{name}_{self.suffix}"[:50]
        row = self._run(
            "INSERT INTO users (username, password, email, role) VALUES (%s, 'x', %s, 'user') RETURNING id",
            (username, f"{username}@my.hamptonu.edu"),
        )
        self.user_ids.append(row[0])
        return {"id": row[0], "username": username}

    def create_storefront(self, owner_id, is_active=True):
        row = self._run(
            "INSERT INTO storefronts (owner_id, brand_name, is_active) VALUES (%s, %s, %s) RETURNING id",
            (owner_id, f"Test Store {self.suffix}", is_active),
        )
        return row[0]

    def create_listing(self, storefront_id, title="Test Item", price=20.00, quantity=5,
                       status="ACTIVE", sizes=None, made_to_order=False):
        """sizes: optional {size: qty}. When given, quantity is the sum of the sizes."""
        if sizes:
            quantity = sum(sizes.values())
        row = self._run(
            """INSERT INTO listings (storefront_id, title, price, fulfillment_type, quantity_on_hand,
                                     sizes_available, status, is_made_to_order)
               VALUES (%s, %s, %s, 'IN_STOCK', %s, %s, %s, %s) RETURNING id""",
            (storefront_id, f"{title} {self.suffix}", price, quantity,
             json.dumps(list(sizes)) if sizes else None, status, made_to_order),
        )
        listing_id = row[0]
        for size, qty in (sizes or {}).items():
            self._run(
                "INSERT INTO listing_sizes (listing_id, size, quantity) VALUES (%s, %s, %s)",
                (listing_id, size, qty), fetch=False,
            )
        return listing_id

    def set_listing_status(self, listing_id, status):
        self._run("UPDATE listings SET status = %s WHERE id = %s", (status, listing_id), fetch=False)

    def listing_stock(self, listing_id):
        """Returns (status, quantity_on_hand, {size: qty})."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT status, quantity_on_hand FROM listings WHERE id = %s", (listing_id,))
            status, qty = cur.fetchone()
            cur.execute("SELECT size, quantity FROM listing_sizes WHERE listing_id = %s", (listing_id,))
            return status, qty, dict(cur.fetchall())
        finally:
            cur.close()
            conn.close()

    def count(self, query, params=()):
        return self._run(query, params)[0]

    def cleanup(self):
        if self.user_ids:
            self._run("DELETE FROM users WHERE id = ANY(%s)", (self.user_ids,), fetch=False)
            self.user_ids = []


def log_in(client, user):
    """Logs the Flask test client in the same way auth_controller.login does."""
    with client.session_transaction() as sess:
        sess.clear()
        sess["user"] = user["username"]
        sess["user_id"] = user["id"]
        sess["role"] = "user"
        sess["last_activity"] = time.time()


def log_out(client):
    with client.session_transaction() as sess:
        sess.clear()
