"""
init_db.py

Purpose:
This file initializes the PostgreSQL database schema for The Pirate Cove.
It creates all required database tables if they do not already exist.

Run this file manually when:
- Setting up the project for the first time
- Deploying to a new environment
- Ensuring the database schema is properly initialized
"""

# The Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Updated by Day Ekoi - Iteration 5 - 4/20/26 - added contact_info, preview_image_1-4, categories columns to storefronts; added ALTER TABLE migrations

# Updated by Anthony Jackson - Iteration 4 (beta) - 11/11/26
#   - Works against BOTH AWS RDS and a local / Docker Postgres. Connection settings now come from
#     backend/config/db.py (the same place the app uses), so DB_PORT, DB_SSLMODE, DB_SSLROOTCERT
#     and DATABASE_URL are all respected. (Ethan's 11/9 port/SSL fix is kept, just moved there.)
#   - On a local or Docker database (DB_HOST=localhost or db) it creates the database itself if it
#     doesn't exist yet, so "docker compose up" and a fresh install both work. Never on RDS.
#   - Every change runs in ONE transaction: if anything fails, nothing is half-applied.
#   - A lock stops two gunicorn workers from setting up the schema at the same moment.
#   - Safe to run any number of times (CREATE ... IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
#   - Added orders.payment_method / payment_status and lookup indexes for checkout.

import os
import sys

import psycopg2
from psycopg2 import sql

sys.path.append(os.path.abspath(os.path.dirname(__file__)))   # so "config" imports when run directly

from config.db import connect, database_name, current_host, is_local_host


def ensure_database_exists():
    """Create the app database if it is missing. Only on a local or Docker Postgres."""
    try:
        connect().close()
        return True
    except psycopg2.OperationalError as e:
        if "does not exist" not in str(e) or not is_local_host():
            raise
    # The server is up but the database isn't there yet: create it from the 'postgres' database.
    dbname = database_name()
    admin = connect(dbname="postgres")
    admin.autocommit = True   # CREATE DATABASE can't run inside a transaction
    try:
        with admin.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
        print(f"Created database '{dbname}' on {current_host()}.")
    finally:
        admin.close()
    return True


def create_vault_tables(verbose=True):
    """Create or update every table. Returns True on success, False on failure."""
    conn = None
    try:
        ensure_database_exists()
        conn = connect()

        cur = conn.cursor()

        # Only one process sets up the schema at a time (released at commit/rollback).
        cur.execute("SELECT pg_advisory_xact_lock(405405);")

        # ________________________________________________________
        # USERS TABLE
        # ________________________________________________________
        create_users_table = """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                role VARCHAR(10) DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        cur.execute(create_users_table)
# Update made by Sidney Cerami 10/15/2026- Table for forgot passwords and usernames
        create_password_reset_table = """
            CREATE TABLE IF NOT EXISTS password_resets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                reset_token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_reset_user
                    FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );
        """
        cur.execute(create_password_reset_table)
        # ________________________________________________________
        # STOREFRONTS TABLE (One storefront per user)
        # Added by Day Ekoi 2/26/26
        # Updated by Day Ekoi 4/20/26 - added contact_info, preview_image_1-4 columns
        # ________________________________________________________
        create_storefronts_table = """
            CREATE TABLE IF NOT EXISTS storefronts (
                id SERIAL PRIMARY KEY,
                owner_id INTEGER NOT NULL UNIQUE,
                brand_name VARCHAR(80) NOT NULL,
                bio TEXT,
                logo_url TEXT,
                banner_url TEXT,
                contact_info TEXT,
                preview_image_1 TEXT,
                preview_image_2 TEXT,
                preview_image_3 TEXT,
                preview_image_4 TEXT,
                categories TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_storefront_owner
                    FOREIGN KEY(owner_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );
        """
        cur.execute(create_storefronts_table)

        # Migrations for existing databases - Added by Day Ekoi 4/20/26
        cur.execute("ALTER TABLE storefronts ADD COLUMN IF NOT EXISTS contact_info TEXT;")
        cur.execute("ALTER TABLE storefronts ADD COLUMN IF NOT EXISTS preview_image_1 TEXT;")
        cur.execute("ALTER TABLE storefronts ADD COLUMN IF NOT EXISTS preview_image_2 TEXT;")
        cur.execute("ALTER TABLE storefronts ADD COLUMN IF NOT EXISTS preview_image_3 TEXT;")
        cur.execute("ALTER TABLE storefronts ADD COLUMN IF NOT EXISTS preview_image_4 TEXT;")
        cur.execute("ALTER TABLE storefronts ADD COLUMN IF NOT EXISTS categories TEXT;")
        # Backfill is_active so existing rows are never NULL (NULL was treated as deactivated)
        cur.execute("ALTER TABLE storefronts ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;")
        cur.execute("UPDATE storefronts SET is_active = TRUE WHERE is_active IS NULL;")

        # ________________________________________________________
        # LISTINGS TABLE (Each listing belongs to a storefront)
        # Added by Day Ekoi 2/26/26
        # ________________________________________________________
        create_listings_table = """
            CREATE TABLE IF NOT EXISTS listings (
                id SERIAL PRIMARY KEY,
                storefront_id INTEGER NOT NULL,

                title VARCHAR(120) NOT NULL,
                description TEXT,
                price NUMERIC(10,2) NOT NULL CHECK (price >= 0),

                fulfillment_type VARCHAR(20) NOT NULL
                    CHECK (fulfillment_type IN ('IN_STOCK', 'PREORDER')),

                quantity_on_hand INTEGER CHECK (quantity_on_hand >= 0),

                sizes_available TEXT,

                status VARCHAR(20) DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'INACTIVE', 'SOLD_OUT', 'DELETED')),

                storefront_restore_status VARCHAR(20),
                deleted_restore_status VARCHAR(20),

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_listing_storefront
                    FOREIGN KEY(storefront_id)
                    REFERENCES storefronts(id)
                    ON DELETE CASCADE
            );
        """
        cur.execute(create_listings_table)
        cur.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS storefront_restore_status VARCHAR(20);")
        cur.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS deleted_restore_status VARCHAR(20);")
        cur.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS is_made_to_order BOOLEAN DEFAULT FALSE;")
        cur.execute("UPDATE listings SET is_made_to_order = FALSE WHERE is_made_to_order IS NULL;")

        # ________________________________________________________
        # LISTING IMAGES TABLE (Multiple images per listing)
        # Added by Day Ekoi 2/26/26
        # ________________________________________________________
        create_listing_images_table = """
            CREATE TABLE IF NOT EXISTS listing_images (
                id SERIAL PRIMARY KEY,
                listing_id INTEGER NOT NULL,
                image_url TEXT NOT NULL,
                is_primary BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_image_listing
                    FOREIGN KEY(listing_id)
                    REFERENCES listings(id)
                    ON DELETE CASCADE
            );
        """
        cur.execute(create_listing_images_table)

        # ________________________________________________________
        # LISTING SIZES TABLE (Inventory per size)
        # Added by Day Ekoi 2/26/26
        # ________________________________________________________
        create_listing_sizes_table = """
            CREATE TABLE IF NOT EXISTS listing_sizes (
                id SERIAL PRIMARY KEY,
                listing_id INTEGER NOT NULL,
                size VARCHAR(20) NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity >= 0),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_size_listing
                    FOREIGN KEY(listing_id)
                    REFERENCES listings(id)
                    ON DELETE CASCADE,

                CONSTRAINT unique_listing_size
                    UNIQUE (listing_id, size)
            );
        """
        cur.execute(create_listing_sizes_table)

        # ________________________________________________________
        # PURCHASES TABLE (Purchase history for users)
        # Added by Elali McNair 3/3/26
        # The frontend protion of this code is not finished or implemented yet. Therfore, this code is not oporational or properly implemented yet.
        # ________________________________________________________
        create_purchases_table = """
            CREATE TABLE IF NOT EXISTS purchases (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                listing_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                purchase_price NUMERIC(10,2) NOT NULL CHECK (purchase_price >= 0),
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_purchase_user
                    FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_purchase_listing
                    FOREIGN KEY(listing_id)
                    REFERENCES listings(id)
                    ON DELETE CASCADE
            );
        """
        cur.execute(create_purchases_table)

        # ________________________________________________________
        # WISHLIST TABLE (User wishlists)
        # Added by Elali McNair 3/3/26
        # The frontend protion of this code is not finished or implemented yet. Therfore, this code is not oporational or properly implemented yet.
        # ________________________________________________________
        create_wishlist_table = """
            CREATE TABLE IF NOT EXISTS wishlist (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                listing_id INTEGER NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_wishlist_user
                    FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_wishlist_listing
                    FOREIGN KEY(listing_id)
                    REFERENCES listings(id)
                    ON DELETE CASCADE,

                CONSTRAINT unique_user_listing_wishlist
                    UNIQUE (user_id, listing_id)
            );
        """
        cur.execute(create_wishlist_table)

        # ________________________________________________________
        # RETURNS TABLE
        # Tracks return requests without hard deletion.
        # ________________________________________________________
        create_returns_table = """
            CREATE TABLE IF NOT EXISTS returns (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                order_number VARCHAR(120) NOT NULL,
                reason TEXT NOT NULL,
                has_damage BOOLEAN NOT NULL,
                damage_image_url TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'reviewed', 'resolved')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted BOOLEAN DEFAULT FALSE,

                CONSTRAINT fk_return_user
                    FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );
        """
        cur.execute(create_returns_table)

        cur.execute("ALTER TABLE returns ADD COLUMN IF NOT EXISTS damage_image_url TEXT;")
        cur.execute("ALTER TABLE returns ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
        cur.execute("ALTER TABLE returns ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;")

        # ________________________________________________________
        # CART ITEMS TABLE (Persistent Bag)
        # Added by Ryan Grimes 4/12/26
        # ________________________________________________________
        create_cart_items_table = """
            CREATE TABLE IF NOT EXISTS cart_items (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                item_id INTEGER,
                item_name VARCHAR(255) NOT NULL,
                price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
                quantity INTEGER NOT NULL DEFAULT 1,
                size VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_cart_user
                    FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );
        """
        cur.execute(create_cart_items_table)

        # ________________________________________________________
        # ORDERS TABLE (Checkout orders)
        # Added by Day Ekoi 4/22/26
        # ________________________________________________________
        create_orders_table = """
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                confirmation_number VARCHAR(50) UNIQUE NOT NULL,
                buyer_first_name VARCHAR(100) NOT NULL,
                buyer_last_name VARCHAR(100) NOT NULL,
                buyer_email VARCHAR(255) NOT NULL,
                buyer_contact VARCHAR(100) NOT NULL,
                buyer_meeting_location TEXT NOT NULL,
                total_amount NUMERIC(10,2) NOT NULL,
                order_status VARCHAR(20) DEFAULT 'SUBMITTED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_order_user
                    FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );
        """
        cur.execute(create_orders_table)

        # ________________________________________________________
        # ORDER ITEMS TABLE (Items per order)
        # Added by Day Ekoi 4/22/26
        # ________________________________________________________
        create_order_items_table = """
            CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL,
                listing_id INTEGER,
                item_name VARCHAR(255) NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                price_at_purchase NUMERIC(10,2) NOT NULL,
                selected_size VARCHAR(50),

                CONSTRAINT fk_order_item_order
                    FOREIGN KEY(order_id)
                    REFERENCES orders(id)
                    ON DELETE CASCADE
            );
        """
        cur.execute(create_order_items_table)

        # CONVERSATIONS TABLE - added by Ethan Williams 10/20/26
        # listing_id is NULL for general questions
        create_conversations_table = """
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                buyer_id INTEGER NOT NULL,
                storefront_id INTEGER NOT NULL,
                listing_id INTEGER,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                last_message_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_conversation_buyer
                    FOREIGN KEY(buyer_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_conversation_storefront
                    FOREIGN KEY(storefront_id)
                    REFERENCES storefronts(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_conversation_listing
                    FOREIGN KEY(listing_id)
                    REFERENCES listings(id)
                    ON DELETE SET NULL
            );
        """
        cur.execute(create_conversations_table)
        # one thread per buyer + storefront + listing
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_thread
            ON conversations (buyer_id, storefront_id, COALESCE(listing_id, 0));
        """)

        # MESSAGES TABLE - added by Ethan Williams 10/20/26
        # read_at is NULL until read
        create_messages_table = """
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                conversation_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                body TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMPTZ,

                CONSTRAINT fk_message_conversation
                    FOREIGN KEY(conversation_id)
                    REFERENCES conversations(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_message_sender
                    FOREIGN KEY(sender_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );
        """
        cur.execute(create_messages_table)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id, id);")

        # ________________________________________________________
        # PROFILE COLUMNS (added to the users table)
        # Added by Anthony Jackson 10/21/26
        # These are optional. Users add them from the Account page, not at signup/login.
        # ADD COLUMN IF NOT EXISTS keeps existing users and their data safe.
        # ________________________________________________________
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(50);")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(50);")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS class_year VARCHAR(12);")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS hometown VARCHAR(100);")

        # ________________________________________________________
        # STOREFRONT RATINGS TABLE (1 to 5 stars for a whole storefront)
        # Added by Anthony Jackson 10/21/26
        # Every rating is its own row, so a user can rate the same storefront
        # more than once. The overall rating is the average of all rows.
        # ________________________________________________________
        create_storefront_ratings_table = """
            CREATE TABLE IF NOT EXISTS storefront_ratings (
                id SERIAL PRIMARY KEY,
                storefront_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                stars SMALLINT NOT NULL CHECK (stars BETWEEN 1 AND 5),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_rating_storefront
                    FOREIGN KEY(storefront_id)
                    REFERENCES storefronts(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_rating_user
                    FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );
        """
        cur.execute(create_storefront_ratings_table)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ratings_storefront ON storefront_ratings (storefront_id);")

        # ________________________________________________________
        # CHECKOUT ADDITIONS
        # Added by Anthony Jackson 11/11/26 - Iteration 4
        # Pirate Cove is an in-person exchange marketplace: by default the buyer pays the seller
        # at the meetup (IN_PERSON / PAY_AT_MEETUP). Orders paid with the optional Stripe
        # TEST-mode checkout are saved as STRIPE_TEST / PAID_TEST. See backend/utils/payments.py.
        # ________________________________________________________
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20) DEFAULT 'IN_PERSON';")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) DEFAULT 'PAY_AT_MEETUP';")
        cur.execute("UPDATE orders SET payment_method = 'IN_PERSON' WHERE payment_method IS NULL;")
        cur.execute("UPDATE orders SET payment_status = 'PAY_AT_MEETUP' WHERE payment_status IS NULL;")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders (user_id, created_at DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items (order_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cart_items_user ON cart_items (user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_listings_storefront ON listings (storefront_id);")

        conn.commit()
        cur.close()

        if verbose:
            print("DATABASE INITIALIZED: users, storefronts, listings, listing_images, listing_sizes, purchases, "
                  "wishlist, returns, cart_items, orders, order_items, conversations, messages, and "
                  "storefront_ratings tables are ready.")
        return True

    except Exception as e:
        if conn is not None:
            conn.rollback()   # nothing is half-applied
        print(f"SCHEMA ERROR: {e}")
        return False

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(0 if create_vault_tables() else 1)
