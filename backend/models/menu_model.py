# menu_model.py
# Added by Anthony Jackson (back end)
# Database queries for the dropdown menu pages: New Drops, Hot!, and All Categories.
# Only reads data. Nothing here changes the database.

from db import get_connection


def _listing_rows_to_dicts(rows):
    listings = []
    for row in rows:
        listings.append({
            "id": row[0],
            "storefront_id": row[1],
            "title": row[2],
            "price": float(row[3]),
            "image_url": row[4],
            "brand_name": row[5],
            "wishlist_count": row[6],
        })
    return listings


def get_new_drops(limit=24):
    """Newest active listings from active storefronts."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT l.id, l.storefront_id, l.title, l.price, li.image_url, s.brand_name, 0
            FROM listings l
            JOIN storefronts s ON s.id = l.storefront_id
            LEFT JOIN listing_images li ON li.listing_id = l.id AND li.is_primary = TRUE
            WHERE l.status = 'ACTIVE' AND s.is_active = TRUE
            ORDER BY l.created_at DESC
            LIMIT %s;
        """, (limit,))
        return _listing_rows_to_dicts(cur.fetchall())
    finally:
        cur.close()
        conn.close()


def get_hot_listings(limit=24):
    """Active listings that the most people have saved to their wishlist."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT l.id, l.storefront_id, l.title, l.price, li.image_url, s.brand_name,
                   COALESCE(w.saves, 0)
            FROM listings l
            JOIN storefronts s ON s.id = l.storefront_id
            LEFT JOIN listing_images li ON li.listing_id = l.id AND li.is_primary = TRUE
            LEFT JOIN (
                SELECT listing_id, COUNT(*) AS saves FROM wishlist GROUP BY listing_id
            ) w ON w.listing_id = l.id
            WHERE l.status = 'ACTIVE' AND s.is_active = TRUE
            ORDER BY COALESCE(w.saves, 0) DESC, l.created_at DESC
            LIMIT %s;
        """, (limit,))
        return _listing_rows_to_dicts(cur.fetchall())
    finally:
        cur.close()
        conn.close()


def get_categories_with_storefronts():
    """
    Groups active storefronts by category.
    Returns a list like: [{"category": "Streetwear", "storefronts": [{"id": 1, "brand_name": "X"}]}]
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, brand_name, categories
            FROM storefronts
            WHERE is_active = TRUE
            ORDER BY brand_name;
        """)
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    groups = {}
    for store_id, brand_name, categories in rows:
        names = [c.strip() for c in str(categories or "").split(",") if c.strip()]
        for name in names:
            groups.setdefault(name, []).append({"id": store_id, "brand_name": brand_name})

    return [{"category": name, "storefronts": groups[name]} for name in sorted(groups, key=str.lower)]
