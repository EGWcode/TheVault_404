# seed_demo_data.py
# Added by Anthony Jackson
# Fills a LOCAL test database with sample users, storefronts, listings and wishlist saves
# so the menu pages (New Drops, Hot!, All Categories) have something to show.
#
# Run it ONCE after the app has been started one time (that creates the tables):
#   py seed_demo_data.py
#
# Safety: it refuses to run unless DB_HOST is your own computer, so it can never
# put sample data into the team's shared AWS database.

import os
import sys

sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), "backend"))

from config.db import get_connection
from utils.auth_utils import hash_password

DEMO_PASSWORD = "DemoPass123"


def main():
    host = (os.getenv("DB_HOST") or "").strip().lower()
    if host not in ("localhost", "127.0.0.1", "::1"):
        print(f"Stopping. DB_HOST is '{host}', not your own computer.")
        print("This script only runs on a local test database.")
        return

    conn = get_connection()
    if conn is None:
        print("Could not connect to the database. Check your .env file.")
        return

    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE username = 'demo_seller1'")
        if cur.fetchone():
            print("Demo data is already there. Nothing to do.")
            return

        pw = hash_password(DEMO_PASSWORD)
        user_ids = []
        for name in ("demo_seller1", "demo_seller2", "demo_buyer"):
            cur.execute(
                "INSERT INTO users (username, password, email, role) VALUES (%s, %s, %s, 'user') RETURNING id",
                (name, pw, f"{name}@my.hamptonu.edu"),
            )
            user_ids.append(cur.fetchone()[0])

        stores = [
            (user_ids[0], "Von Dutch Vault", "Streetwear and vintage pieces.", "Streetwear, Vintage"),
            (user_ids[1], "Essentials Co", "Everyday basics.", "Basics, Vintage"),
        ]
        store_ids = []
        for owner, brand, bio, cats in stores:
            cur.execute(
                "INSERT INTO storefronts (owner_id, brand_name, bio, categories, is_active) VALUES (%s, %s, %s, %s, TRUE) RETURNING id",
                (owner, brand, bio, cats),
            )
            store_ids.append(cur.fetchone()[0])

        listings = [
            (store_ids[0], "Vintage Hoodie", 45.00),
            (store_ids[0], "Graphic Tee", 25.00),
            (store_ids[1], "Cargo Pants", 55.50),
            (store_ids[1], "Plain White Tee", 15.00),
        ]
        listing_ids = []
        for sid, title, price in listings:
            cur.execute(
                """INSERT INTO listings (storefront_id, title, description, price, fulfillment_type, quantity_on_hand, status)
                   VALUES (%s, %s, 'Sample listing', %s, 'IN_STOCK', 5, 'ACTIVE') RETURNING id""",
                (sid, title, price),
            )
            listing_ids.append(cur.fetchone()[0])

        # Wishlist saves so "Hot!" has an order: Cargo Pants 2 saves, Vintage Hoodie 1 save
        cur.execute("INSERT INTO wishlist (user_id, listing_id) VALUES (%s, %s), (%s, %s), (%s, %s)",
                    (user_ids[2], listing_ids[2], user_ids[0], listing_ids[2], user_ids[2], listing_ids[0]))

        conn.commit()
        print("Done. Sample data added.")
        print(f"You can log in as demo_seller1, demo_seller2 or demo_buyer with password {DEMO_PASSWORD}")
    except Exception as e:
        conn.rollback()
        print(f"Something went wrong: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
