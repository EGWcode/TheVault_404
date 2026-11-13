# seed_demo_data.py
# Added by Anthony Jackson
# Expanded by Nicco Hill and Anthony Jackson 11/12/2026 - realistic demo users,
# storefronts (with logos), listings (with photos, sizes and stock), wishlists and ratings.
#
# Fills a LOCAL test database with sample data so the demo has something real to show:
# the homepage, storefront pages, menu pages (New Drops, Hot!, All Categories, Top Rated),
# the wishlist (including a sold-out item) and the create-listing flow.
#
# Run it after the app has been started one time (that creates the tables):
#   py seed_demo_data.py
#
# Safe to run more than once: every user / storefront / listing / wishlist save / rating
# is looked up first and only added if it is missing. Older copies of the demo data
# (demo_seller1, demo_seller2, demo_buyer) are kept and filled in.
#
# Safety: it refuses to run unless the database is on your own computer or in our Docker
# container (DB_HOST=db), so it can never put sample data into the team's shared AWS database.
#
# Merged by Anthony Jackson 11/12/2026: also works with Docker, creates the tables first
# (so it runs on its own), and returns exit code 1 on failure so the installer can tell.

import json
import os
import sys

sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), "backend"))

from config.db import get_connection, current_host, is_local_host
from init_db import create_vault_tables
from utils.auth_utils import hash_password

DEMO_PASSWORD = "DemoPass123"
IMG = "/static/images/"

# ── Users ────────────────────────────────────────────────────────
# (username, role in the demo)
SELLERS = ["demo_seller1", "demo_seller2", "demo_seller3", "demo_seller4"]
BUYERS = ["demo_buyer", "demo_buyer2", "demo_buyer3", "demo_buyer4"]

# ── Storefronts ──────────────────────────────────────────────────
STOREFRONTS = [
    {
        "owner": "demo_seller1",
        "brand_name": "Von Dutch Vault",
        "bio": "Y2K and vintage Von Dutch pieces, hand-picked and steamed. Meetups at the Student Center.",
        "categories": "Streetwear, Vintage",
        "logo_url": IMG + "vondutchlogo.png",
        "contact_info": "DM me here or find me at the Student Center, weekdays 12-2.",
    },
    {
        "owner": "demo_seller2",
        "brand_name": "Essentials Co",
        "bio": "Clean everyday basics. Hoodies, sweats and tees that go with everything.",
        "categories": "Basics, Loungewear",
        "logo_url": IMG + "essentialslogo.png",
        "contact_info": "Pickups at the library steps after 3pm.",
    },
    {
        "owner": "demo_seller3",
        "brand_name": "Swoosh Swap",
        "bio": "Gently used and deadstock Nike athleisure. Every piece is checked and washed.",
        "categories": "Athletic, Streetwear",
        "logo_url": IMG + "nikelogo.png",
        "contact_info": "Meet at the gym lobby or the Student Center.",
    },
    {
        "owner": "demo_seller4",
        "brand_name": "Onyx Threads",
        "bio": "Student-run label. Heavyweight blanks, made to order in small batches.",
        "categories": "Streetwear, Made to Order",
        "logo_url": IMG + "onyxlogo.jpeg",
        "contact_info": "Orders ship to campus in 7-10 days. Message me with questions.",
    },
]

# ── Listings ─────────────────────────────────────────────────────
# sizes: {size: quantity}. Status is worked out from stock (0 total -> SOLD_OUT)
# unless "status" is given. made_to_order listings ignore stock.
LISTINGS = [
    # Von Dutch Vault
    {"store": "Von Dutch Vault", "title": "Vintage Hoodie", "price": 45.00,
     "description": "Faded black pullover, early-2000s fit. Small mark on the cuff (see photos).",
     "images": ["vondutch1.png", "vondutch2.png"], "sizes": {"M": 2, "L": 3}},
    {"store": "Von Dutch Vault", "title": "Graphic Tee", "price": 25.00,
     "description": "Classic logo tee, soft washed cotton.",
     "images": ["vondutch3.png"], "sizes": {"S": 1, "M": 2, "L": 2}},
    {"store": "Von Dutch Vault", "title": "Von Dutch Trucker Hat", "price": 30.00,
     "description": "Mesh-back trucker in great condition. Adjustable snap.",
     "images": ["vondutch4.png"], "sizes": {"One Size": 4}},
    # Essentials Co
    {"store": "Essentials Co", "title": "Cargo Pants", "price": 55.50,
     "description": "Relaxed cargo sweats with side pockets. Worn twice.",
     "images": ["essentials2.png"], "sizes": {"M": 2, "L": 2, "XL": 1}},
    {"store": "Essentials Co", "title": "Plain White Tee", "price": 15.00,
     "description": "Heavy cotton tee. New, never worn.",
     "images": ["essentials3.png"], "sizes": {"S": 3, "M": 4, "L": 3}},
    {"store": "Essentials Co", "title": "Essentials Pullover Hoodie", "price": 70.00,
     "description": "Oversized fleece hoodie in oatmeal. Rubber logo on the chest.",
     "images": ["essentials1.png", "essentials4.png"], "sizes": {"M": 1, "L": 1}},
    # Swoosh Swap
    {"store": "Swoosh Swap", "title": "Nike Tech Fleece Hoodie", "price": 65.00,
     "description": "Full-zip Tech Fleece in grey. Barely worn.",
     "images": ["nikehoodie1.png", "nikehoodie2.png"], "sizes": {"S": 1, "M": 2, "L": 1}},
    {"store": "Swoosh Swap", "title": "Nike Windrunner Jacket", "price": 50.00,
     "description": "Lightweight windbreaker, packs into its own pocket.",
     "images": ["nikejacket.png"], "sizes": {"M": 1, "L": 1, "XL": 1}},
    # Sold out on purpose, so the demo can show a sold-out item sitting on a wishlist
    {"store": "Swoosh Swap", "title": "Nike Club Sweatpants", "price": 35.00,
     "description": "Fleece joggers. Sold out, restocking soon!",
     "images": ["nikepants1.png"], "sizes": {"M": 0, "L": 0}},
    # Onyx Threads
    {"store": "Onyx Threads", "title": "Onyx Heavyweight Hoodie", "price": 60.00,
     "description": "400gsm cotton hoodie, made to order in your size. Ships in 7-10 days.",
     "images": ["onyxhoodie.png"], "sizes": {"S": 0, "M": 0, "L": 0, "XL": 0}, "made_to_order": True},
]

# ── Wishlist saves (buyer -> listing titles) ─────────────────────
# More saves = higher on the Hot! page. Cargo Pants and the Tech Fleece lead.
WISHLISTS = {
    "demo_buyer":  ["Cargo Pants", "Vintage Hoodie", "Nike Tech Fleece Hoodie", "Nike Club Sweatpants"],
    "demo_buyer2": ["Cargo Pants", "Nike Tech Fleece Hoodie", "Onyx Heavyweight Hoodie"],
    "demo_buyer3": ["Nike Tech Fleece Hoodie", "Essentials Pullover Hoodie", "Von Dutch Trucker Hat"],
    "demo_buyer4": ["Cargo Pants", "Graphic Tee"],
    "demo_seller1": ["Cargo Pants"],
}

# ── Ratings (storefront -> [(rater, stars)]) ─────────────────────
RATINGS = {
    "Von Dutch Vault": [("demo_buyer", 5), ("demo_seller2", 4), ("demo_buyer2", 5)],
    "Essentials Co": [("demo_buyer", 3), ("demo_seller1", 4), ("demo_buyer3", 4)],
    "Swoosh Swap": [("demo_buyer", 5), ("demo_buyer2", 5), ("demo_buyer4", 4)],
    "Onyx Threads": [("demo_buyer2", 4), ("demo_buyer3", 5)],
}


def get_or_create_user(cur, username, password_hash):
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    if row:
        return row[0], False
    cur.execute(
        "INSERT INTO users (username, password, email, role) VALUES (%s, %s, %s, 'user') RETURNING id",
        (username, password_hash, f"{username}@my.hamptonu.edu"),
    )
    return cur.fetchone()[0], True


def get_or_create_storefront(cur, owner_id, store):
    # owner_id is UNIQUE on storefronts: one storefront per user
    cur.execute("SELECT id FROM storefronts WHERE owner_id = %s", (owner_id,))
    row = cur.fetchone()
    if row:
        # Fill in details older seeds left blank, without overwriting anything a person changed
        cur.execute(
            """UPDATE storefronts
               SET logo_url = COALESCE(logo_url, %s),
                   contact_info = COALESCE(contact_info, %s),
                   bio = CASE WHEN bio IS NULL OR bio IN ('Streetwear and vintage pieces.', 'Everyday basics.')
                              THEN %s ELSE bio END
               WHERE id = %s""",
            (store["logo_url"], store["contact_info"], store["bio"], row[0]),
        )
        return row[0], False
    cur.execute(
        """INSERT INTO storefronts (owner_id, brand_name, bio, categories, logo_url, contact_info, is_active)
           VALUES (%s, %s, %s, %s, %s, %s, TRUE) RETURNING id""",
        (owner_id, store["brand_name"], store["bio"], store["categories"], store["logo_url"], store["contact_info"]),
    )
    return cur.fetchone()[0], True


def get_or_create_listing(cur, storefront_id, listing):
    cur.execute(
        "SELECT id FROM listings WHERE storefront_id = %s AND title = %s AND status != 'DELETED'",
        (storefront_id, listing["title"]),
    )
    row = cur.fetchone()
    made_to_order = listing.get("made_to_order", False)
    total = sum(listing["sizes"].values())
    status = listing.get("status") or ("SOLD_OUT" if total == 0 and not made_to_order else "ACTIVE")

    if row:
        listing_id, created = row[0], False
        # Older seeds used a placeholder description; replace only that
        cur.execute(
            "UPDATE listings SET description = %s WHERE id = %s AND description = 'Sample listing'",
            (listing["description"], listing_id),
        )
    else:
        cur.execute(
            """INSERT INTO listings (storefront_id, title, description, price, fulfillment_type,
                                     quantity_on_hand, sizes_available, status, is_made_to_order)
               VALUES (%s, %s, %s, %s, 'IN_STOCK', %s, %s, %s, %s) RETURNING id""",
            (storefront_id, listing["title"], listing["description"], listing["price"], total,
             json.dumps(list(listing["sizes"])), status, made_to_order),
        )
        listing_id, created = cur.fetchone()[0], True

    # Photos: add any that are missing; first photo is the primary one
    cur.execute("SELECT COUNT(*) FROM listing_images WHERE listing_id = %s", (listing_id,))
    if cur.fetchone()[0] == 0:
        for index, filename in enumerate(listing["images"]):
            cur.execute(
                "INSERT INTO listing_images (listing_id, image_url, is_primary) VALUES (%s, %s, %s)",
                (listing_id, IMG + filename, index == 0),
            )

    # Per-size stock: add any sizes that are missing, then sync the listing total
    cur.execute("SELECT COUNT(*) FROM listing_sizes WHERE listing_id = %s", (listing_id,))
    if cur.fetchone()[0] == 0:
        for size, qty in listing["sizes"].items():
            cur.execute(
                "INSERT INTO listing_sizes (listing_id, size, quantity) VALUES (%s, %s, %s)",
                (listing_id, size, qty),
            )
        cur.execute(
            "UPDATE listings SET quantity_on_hand = %s, sizes_available = %s WHERE id = %s",
            (total, json.dumps(list(listing["sizes"])), listing_id),
        )

    return listing_id, created


def main():
    host = current_host()
    if not is_local_host(host):
        print(f"Stopping. DB_HOST is '{host}', not your own computer or Docker.")
        print("This script only runs on a local test database.")
        return 1

    # Make sure every table exists first, so this also works before the app has ever started
    if not create_vault_tables(verbose=False):
        print("Could not set up the database tables. Is Postgres running? Check your .env file.")
        return 1

    conn = get_connection()
    if conn is None:
        print("Could not connect to the database. Check your .env file.")
        return 1

    counts = {"users": 0, "storefronts": 0, "listings": 0, "wishlist saves": 0, "ratings": 0}
    try:
        cur = conn.cursor()
        pw = hash_password(DEMO_PASSWORD)

        user_ids = {}
        for username in SELLERS + BUYERS:
            user_ids[username], created = get_or_create_user(cur, username, pw)
            counts["users"] += created

        store_ids = {}
        for store in STOREFRONTS:
            store_ids[store["brand_name"]], created = get_or_create_storefront(cur, user_ids[store["owner"]], store)
            counts["storefronts"] += created

        listing_ids = {}
        for listing in LISTINGS:
            listing_ids[listing["title"]], created = get_or_create_listing(cur, store_ids[listing["store"]], listing)
            counts["listings"] += created

        for username, titles in WISHLISTS.items():
            for title in titles:
                cur.execute(
                    """INSERT INTO wishlist (user_id, listing_id) VALUES (%s, %s)
                       ON CONFLICT (user_id, listing_id) DO NOTHING""",
                    (user_ids[username], listing_ids[title]),
                )
                counts["wishlist saves"] += cur.rowcount

        for brand, ratings in RATINGS.items():
            for rater, stars in ratings:
                cur.execute(
                    "SELECT 1 FROM storefront_ratings WHERE storefront_id = %s AND user_id = %s",
                    (store_ids[brand], user_ids[rater]),
                )
                if cur.fetchone():
                    continue
                cur.execute(
                    "INSERT INTO storefront_ratings (storefront_id, user_id, stars) VALUES (%s, %s, %s)",
                    (store_ids[brand], user_ids[rater], stars),
                )
                counts["ratings"] += 1

        conn.commit()
        added = ", ".join(f"{n} {label}" for label, n in counts.items())
        print(f"Done. Added {added}.")
        print(f"Log in as any of: {', '.join(SELLERS + BUYERS)}")
        print(f"Password for all demo accounts: {DEMO_PASSWORD}")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"Something went wrong, nothing was saved: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
