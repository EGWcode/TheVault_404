# The Vault Campus Marketplace
# Created by Anthony Jackson 10/21/26 for the storefront rating feature

"""
models/rating_model.py

Purpose:
Database work for storefront ratings (1 to 5 stars for a whole storefront).
Every rating is saved as its own row, so one user can rate the same storefront
more than once. The overall rating is the average of every row.
"""

from db import get_connection


def get_storefront_info(storefront_id):
    """Returns (owner_id, is_active) for a storefront, or None if it doesn't exist."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT owner_id, is_active FROM storefronts WHERE id = %s;", (storefront_id,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def add_rating(storefront_id, user_id, stars):
    """Saves one rating."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO storefront_ratings (storefront_id, user_id, stars) VALUES (%s, %s, %s);",
            (storefront_id, user_id, stars),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def get_summary(storefront_id):
    """Returns (average rounded to 1 decimal, number of ratings) for one storefront."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT COALESCE(ROUND(AVG(stars)::numeric, 1), 0), COUNT(*)
               FROM storefront_ratings WHERE storefront_id = %s;""",
            (storefront_id,),
        )
        avg, count = cur.fetchone()
        return float(avg), int(count)
    finally:
        cur.close()
        conn.close()


def get_all_summaries():
    """Returns {storefront_id: (average, count)} for every storefront that has ratings."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT storefront_id, ROUND(AVG(stars)::numeric, 1), COUNT(*)
               FROM storefront_ratings GROUP BY storefront_id;"""
        )
        return {row[0]: (float(row[1]), int(row[2])) for row in cur.fetchall()}
    finally:
        cur.close()
        conn.close()


def get_top_rated(limit=24):
    """Active storefronts that have ratings, best average first (more ratings break ties)."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT s.id, s.brand_name, ROUND(AVG(r.stars)::numeric, 1), COUNT(*)
               FROM storefront_ratings r
               JOIN storefronts s ON s.id = r.storefront_id
               WHERE s.is_active = TRUE
               GROUP BY s.id, s.brand_name
               ORDER BY AVG(r.stars) DESC, COUNT(*) DESC, s.brand_name
               LIMIT %s;""",
            (limit,),
        )
        return [(r[0], r[1], float(r[2]), int(r[3])) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
