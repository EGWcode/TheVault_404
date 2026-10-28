"""Database queries for New Drops and Hot! public product discovery.

Browse page update by Noah Green, 10/17/2026.
Hot! ranks current active/sold-out listings by the quantity ordered through
The Pirate Cove checkout, rather than making up a popularity score.
"""

from db import get_connection


def get_public_discovery_listings(sort='new', limit=24):
    if sort not in ('new', 'hot'):
        raise ValueError('Unsupported sort')

    order_clause = (
        'ORDER BY COALESCE(sales.units_ordered, 0) DESC, l.created_at DESC, l.id DESC'
        if sort == 'hot' else
        'ORDER BY l.created_at DESC, l.id DESC'
    )
    sales_filter = 'AND COALESCE(sales.units_ordered, 0) > 0' if sort == 'hot' else ''

    # LATERAL chooses at most one image per listing, avoiding duplicate cards.
    # Listings must belong to an active storefront and be public-facing.
    query = f"""
        SELECT l.id, l.storefront_id, l.title, l.price, l.status, l.created_at,
               s.brand_name,
               COALESCE(img.image_url, s.preview_image_1, s.banner_url, s.logo_url) AS image_url,
               COALESCE(sales.units_ordered, 0) AS units_ordered
        FROM listings l
        INNER JOIN storefronts s ON s.id = l.storefront_id
        LEFT JOIN LATERAL (
            SELECT li.image_url
            FROM listing_images li
            WHERE li.listing_id = l.id
            ORDER BY li.is_primary DESC, li.id ASC
            LIMIT 1
        ) img ON TRUE
        LEFT JOIN (
            SELECT oi.listing_id, SUM(oi.quantity) AS units_ordered
            FROM order_items oi
            INNER JOIN orders o ON o.id = oi.order_id
            WHERE oi.listing_id IS NOT NULL
              AND COALESCE(o.order_status, '') <> 'CANCELLED'
            GROUP BY oi.listing_id
        ) sales ON sales.listing_id = l.id
        WHERE s.is_active = TRUE AND l.status IN ('ACTIVE', 'SOLD_OUT')
        {sales_filter}
        {order_clause}
        LIMIT %s;
    """

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(query, (limit,))
        rows = cur.fetchall()
        return [
            {
                'id': row[0],
                'storefront_id': row[1],
                'title': row[2],
                'price': float(row[3]),
                'status': row[4],
                'created_at': row[5].isoformat() if row[5] else None,
                'brand_name': row[6],
                'image_url': row[7],
                'units_ordered': int(row[8]),
            }
            for row in rows
        ]
    finally:
        if cur is not None:
            cur.close()
        conn.close()
