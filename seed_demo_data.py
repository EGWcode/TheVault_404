# seed_demo_data.py
# Added by Anthony Jackson
# Updated by Anthony Jackson - Iteration 4 (11/11/26): SAFE TO RUN MORE THAN ONCE
#
# Fills a LOCAL (or Docker) database with demo users, storefronts, listings (with sizes and
# pictures), wishlist saves, ratings and one finished order, so every page has something to
# show in the beta demo.
#
#   py seed_demo_data.py            (Windows)
#   python3 seed_demo_data.py       (macOS)
#
# The install script runs this right after backend/init_db.py.
#
# Running it twice never makes duplicates. Every item is looked up by a natural key first
# (username, storefront owner, listing title, size, ...) and only added if it is missing.
# If a run is interrupted, the next run fills in whatever is still missing.
#
# Safety: it refuses to run unless the database is on your own computer or in our Docker
# container, so it can never put demo data into the team's shared AWS RDS database.
#
# Want more demo content? Add rows to the DEMO_* lists below. (Nicco + Anthony)

import os
import sys

sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), "backend"))

from config.db import connect, current_host, is_local_host   # noqa: E402
from init_db import create_vault_tables                       # noqa: E402
from utils.auth_utils import hash_password                    # noqa: E402

# Meets the password rule (upper, lower, number, symbol, 8+ characters)
DEMO_PASSWORD = "DemoPass123!"

# ---------------------------------------------------------------- demo content
DEMO_USERS = [
    # username,       first,     last,       class year
    ("demo_seller1", "Jordan", "Reed", "Junior"),
    ("demo_seller2", "Maya", "Brooks", "Senior"),
    ("demo_seller3", "Chris", "Allen", "Sophomore"),
    ("demo_buyer", "Taylor", "Green", "Freshman"),
]

DEMO_STOREFRONTS = [
    # owner,          brand name,         bio,                                   categories,            logo
    ("demo_seller1", "Von Dutch Vault", "Streetwear and vintage pieces.", "Streetwear, Vintage", "/static/images/vondutchlogo.png"),
    ("demo_seller2", "Essentials Co", "Everyday basics.", "Basics, Vintage", "/static/images/essentialslogo.png"),
    ("demo_seller3", "Onyx Athletics", "Athletic wear and sneakers.", "Athletic, Sneakers", "/static/images/onyxlogo.jpeg"),
]

DEMO_LISTINGS = [
    # owner,          title,               price,  sizes {size: qty},               picture
    ("demo_seller1", "Vintage Hoodie", 45.00, {"S": 2, "M": 3, "L": 1}, "/static/images/vondutch1.png"),
    ("demo_seller1", "Graphic Tee", 25.00, {"M": 4, "L": 4}, "/static/images/vondutch2.png"),
    ("demo_seller1", "Trucker Hat", 20.00, {"One Size": 6}, "/static/images/vondutch3.png"),
    ("demo_seller2", "Cargo Pants", 55.50, {"30": 2, "32": 2, "34": 1}, "/static/images/essentials1.png"),
    ("demo_seller2", "Plain White Tee", 15.00, {"S": 5, "M": 5, "L": 5}, "/static/images/essentials2.png"),
    ("demo_seller3", "Training Hoodie", 50.00, {"M": 2, "L": 2}, "/static/images/onyxhoodie.png"),
    ("demo_seller3", "Track Jacket", 65.00, {"L": 1}, "/static/images/nikejacket.png"),
]

DEMO_WISHLIST = [
    # who saved it,  listing title   ("Hot!" ranks by number of saves)
    ("demo_buyer", "Cargo Pants"),
    ("demo_seller1", "Cargo Pants"),
    ("demo_seller3", "Cargo Pants"),
    ("demo_buyer", "Vintage Hoodie"),
    ("demo_seller2", "Vintage Hoodie"),
    ("demo_buyer", "Track Jacket"),
]

DEMO_RATINGS = [
    # rater,          storefront owner, stars
    ("demo_buyer", "demo_seller1", 5),
    ("demo_seller2", "demo_seller1", 4),
    ("demo_buyer", "demo_seller1", 5),
    ("demo_buyer", "demo_seller2", 3),
    ("demo_seller1", "demo_seller2", 4),
    ("demo_buyer", "demo_seller3", 4),
]

# One finished order so "My Orders" and the order confirmation page have something to show
DEMO_ORDER = {
    "buyer": "demo_buyer",
    "confirmation_number": "DEMO-000001",
    "meeting_location": "Student Center",
    "items": [("Graphic Tee", "M", 1), ("Plain White Tee", "L", 2)],
}


# ---------------------------------------------------------------- helpers
class Counter:
    def __init__(self):
        self.added = {}

    def add(self, what, n=1):
        self.added[what] = self.added.get(what, 0) + n

    def report(self):
        if not self.added:
            return "Demo data is already complete. Nothing was added."
        parts = [f"{n} {what}" for what, n in self.added.items()]
        return "Added: " + ", ".join(parts) + "."


def get_or_create_user(cur, counter, username, first, last, class_year, pw_hash):
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """INSERT INTO users (username, password, email, role, first_name, last_name, class_year)
           VALUES (%s, %s, %s, 'user', %s, %s, %s)
           ON CONFLICT DO NOTHING
           RETURNING id""",
        (username, pw_hash, f"{username}@my.hamptonu.edu", first, last, class_year),
    )
    row = cur.fetchone()
    if row is None:   # the email was already used by someone else; look the user up again
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"Could not create demo user {username} (email already taken?)")
        return row[0]
    counter.add("users")
    return row[0]


def get_or_create_storefront(cur, counter, owner_id, brand, bio, categories, logo):
    # owner_id is UNIQUE (one storefront per user), so it is the natural key
    cur.execute(
        """INSERT INTO storefronts (owner_id, brand_name, bio, categories, logo_url, is_active)
           VALUES (%s, %s, %s, %s, %s, TRUE)
           ON CONFLICT (owner_id) DO NOTHING
           RETURNING id""",
        (owner_id, brand, bio, categories, logo),
    )
    row = cur.fetchone()
    if row:
        counter.add("storefronts")
        return row[0]
    cur.execute("SELECT id FROM storefronts WHERE owner_id = %s", (owner_id,))
    return cur.fetchone()[0]


def get_or_create_listing(cur, counter, storefront_id, title, price, sizes, picture):
    cur.execute(
        "SELECT id FROM listings WHERE storefront_id = %s AND title = %s AND status <> 'DELETED' ORDER BY id LIMIT 1",
        (storefront_id, title),
    )
    row = cur.fetchone()
    if row:
        listing_id = row[0]
    else:
        cur.execute(
            """INSERT INTO listings (storefront_id, title, description, price, fulfillment_type,
                                     quantity_on_hand, sizes_available, status)
               VALUES (%s, %s, 'Demo listing for the Pirate Cove beta.', %s, 'IN_STOCK', %s, %s, 'ACTIVE')
               RETURNING id""",
            (storefront_id, title, price, sum(sizes.values()), ", ".join(sizes)),
        )
        listing_id = cur.fetchone()[0]
        counter.add("listings")

    for size, qty in sizes.items():
        cur.execute(
            """INSERT INTO listing_sizes (listing_id, size, quantity) VALUES (%s, %s, %s)
               ON CONFLICT (listing_id, size) DO NOTHING""",
            (listing_id, size, qty),
        )
        if cur.rowcount:
            counter.add("listing sizes")

    cur.execute("SELECT 1 FROM listing_images WHERE listing_id = %s LIMIT 1", (listing_id,))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO listing_images (listing_id, image_url, is_primary) VALUES (%s, %s, TRUE)",
            (listing_id, picture),
        )
        counter.add("pictures")
    return listing_id


def seed(cur):
    counter = Counter()
    pw_hash = hash_password(DEMO_PASSWORD)

    users = {}
    for username, first, last, class_year in DEMO_USERS:
        users[username] = get_or_create_user(cur, counter, username, first, last, class_year, pw_hash)

    stores = {}
    for owner, brand, bio, cats, logo in DEMO_STOREFRONTS:
        stores[owner] = get_or_create_storefront(cur, counter, users[owner], brand, bio, cats, logo)

    listings = {}
    prices = {}
    for owner, title, price, sizes, picture in DEMO_LISTINGS:
        listings[title] = get_or_create_listing(cur, counter, stores[owner], title, price, sizes, picture)
        prices[title] = price

    for who, title in DEMO_WISHLIST:
        cur.execute(
            "INSERT INTO wishlist (user_id, listing_id) VALUES (%s, %s) ON CONFLICT (user_id, listing_id) DO NOTHING",
            (users[who], listings[title]),
        )
        if cur.rowcount:
            counter.add("wishlist saves")

    # Ratings have no natural key (a user may rate a store more than once), so only add the
    # demo ratings for a storefront if no demo user has rated it yet.
    demo_ids = list(users.values())
    for owner in {o for _, o, _ in DEMO_RATINGS}:
        cur.execute(
            "SELECT COUNT(*) FROM storefront_ratings WHERE storefront_id = %s AND user_id = ANY(%s)",
            (stores[owner], demo_ids),
        )
        if cur.fetchone()[0]:
            continue
        for rater, rated_owner, stars in DEMO_RATINGS:
            if rated_owner == owner:
                cur.execute(
                    "INSERT INTO storefront_ratings (storefront_id, user_id, stars) VALUES (%s, %s, %s)",
                    (stores[owner], users[rater], stars),
                )
                counter.add("ratings")

    # The demo order is keyed by its confirmation number (UNIQUE)
    order = DEMO_ORDER
    lines = [(title, size, qty, prices[title]) for title, size, qty in order["items"]]
    total = round(sum(qty * price for _, _, qty, price in lines), 2)
    cur.execute(
        """INSERT INTO orders (user_id, confirmation_number, buyer_first_name, buyer_last_name,
                               buyer_email, buyer_contact, buyer_meeting_location, total_amount,
                               order_status, payment_method, payment_status)
           VALUES (%s, %s, 'Taylor', 'Green', %s, '757-555-0100', %s, %s,
                   'SUBMITTED', 'IN_PERSON', 'PAY_AT_MEETUP')
           ON CONFLICT (confirmation_number) DO NOTHING
           RETURNING id""",
        (users[order["buyer"]], order["confirmation_number"], f"{order['buyer']}@my.hamptonu.edu",
         order["meeting_location"], total),
    )
    row = cur.fetchone()
    if row:
        for title, size, qty, price in lines:
            cur.execute(
                """INSERT INTO order_items (order_id, listing_id, item_name, quantity, price_at_purchase, selected_size)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (row[0], listings[title], title, qty, price, size),
            )
        counter.add("orders")

    return counter


def main():
    host = current_host()
    if not is_local_host(host):
        print(f"Stopping. The database host is '{host}', which is not your own computer or Docker.")
        print("Demo data is only ever added to a local test database, never to AWS RDS.")
        return 1

    # Make sure every table exists first, so this script also works on its own.
    if not create_vault_tables(verbose=False):
        print("Could not set up the database tables. Is Postgres running? Check your .env file.")
        return 1

    try:
        conn = connect()
    except Exception as e:
        print(f"Could not connect to the database: {e}")
        return 1

    try:
        with conn:                      # one transaction: all of it or none of it
            with conn.cursor() as cur:
                counter = seed(cur)
        print(counter.report())
        print("Demo logins: demo_buyer, demo_seller1, demo_seller2, demo_seller3")
        print(f"Password for all of them: {DEMO_PASSWORD}")
        return 0
    except Exception as e:
        print(f"Something went wrong, so nothing was saved: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
