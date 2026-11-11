# test_db_driver.py
# First version by Ryan Grimes 4/12/2026 (a script that printed the user count on RDS).
# Rewritten as real pytest integration tests by Anthony Jackson - Iteration 4 (11/11/26).
#
# Runs against the database in .env, but ONLY if it is a local or Docker database.
# (These tests create tables and demo rows, so they never run against the team's AWS RDS.)
# If no local database is reachable, they are skipped, not failed.
# Test case IDs match the Test Specification (DBI-01 ... DBI-06).

import os
import sys

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.abspath(os.path.join(BACKEND, ".."))
for path in (BACKEND, ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

import pytest  # noqa: E402

from config.db import connect, is_local_host, current_host  # noqa: E402
from init_db import create_vault_tables  # noqa: E402

EXPECTED_TABLES = {
    "users", "storefronts", "listings", "listing_images", "listing_sizes", "purchases",
    "wishlist", "returns", "cart_items", "orders", "order_items", "conversations",
    "messages", "storefront_ratings",
}

# Columns added by later iterations: if a migration is lost, these catch it
EXPECTED_COLUMNS = {
    "storefronts": {"contact_info", "preview_image_1", "preview_image_4", "categories", "is_active"},
    "listings": {"storefront_restore_status", "deleted_restore_status", "is_made_to_order"},
    "users": {"first_name", "last_name", "phone", "class_year", "hometown"},
    "orders": {"confirmation_number", "buyer_meeting_location", "payment_method", "payment_status"},
    "returns": {"damage_image_url", "is_deleted"},
}


def _local_db_or_skip():
    if not is_local_host():
        pytest.skip(f"DB_HOST is '{current_host()}'. Integration tests only run on a local/Docker database.")
    try:
        connect().close()
    except Exception as e:
        pytest.skip(f"No local database reachable: {e}")


@pytest.fixture(scope="module")
def db():
    _local_db_or_skip()
    assert create_vault_tables(verbose=False), "init_db failed - see SCHEMA ERROR above"
    conn = connect()
    # autocommit: every SELECT here finishes right away, so this connection never holds a lock
    # that init_db.py / the seed script (in their own connections) would have to wait for.
    conn.autocommit = True
    yield conn
    conn.close()


def _columns(cur, table):
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
                (table,))
    return {r[0] for r in cur.fetchall()}


# DBI-01
def test_connection_works(db):
    with db.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1


# DBI-02
def test_every_table_exists(db):
    with db.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = {r[0] for r in cur.fetchall()}
    assert EXPECTED_TABLES <= tables, f"missing: {EXPECTED_TABLES - tables}"


# DBI-03
def test_migration_columns_exist(db):
    with db.cursor() as cur:
        for table, cols in EXPECTED_COLUMNS.items():
            missing = cols - _columns(cur, table)
            assert not missing, f"{table} is missing {missing}"


# DBI-04
def test_init_db_can_run_again_without_errors_or_data_loss(db):
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM users")
        before = cur.fetchone()[0]
    assert create_vault_tables(verbose=False)
    assert create_vault_tables(verbose=False)
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM users")
        assert cur.fetchone()[0] == before
    db.rollback()


# DBI-05
def test_rating_stars_must_be_1_to_5(db):
    import psycopg2
    with db.cursor() as cur:
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("INSERT INTO storefront_ratings (storefront_id, user_id, stars) VALUES (1, 1, 6)")
    db.rollback()


# DBI-06
def test_seed_script_is_safe_to_run_twice(db):
    import seed_demo_data

    def counts():
        with db.cursor() as cur:
            out = {}
            for table in ("users", "storefronts", "listings", "listing_sizes", "listing_images",
                          "wishlist", "storefront_ratings", "orders", "order_items"):
                cur.execute(f"SELECT COUNT(*) FROM {table}")   # table names are fixed above
                out[table] = cur.fetchone()[0]
        db.rollback()
        return out

    assert seed_demo_data.main() == 0
    after_first = counts()
    assert seed_demo_data.main() == 0
    assert counts() == after_first, "the second run added duplicate rows"

    # If a demo row goes missing (an interrupted run, someone deleted it), the next run puts it back
    with db.cursor() as cur:
        cur.execute("""DELETE FROM wishlist WHERE user_id = (SELECT id FROM users WHERE username='demo_buyer')
                       AND listing_id = (SELECT id FROM listings WHERE title='Track Jacket' LIMIT 1)""")
    assert seed_demo_data.main() == 0
    assert counts() == after_first
