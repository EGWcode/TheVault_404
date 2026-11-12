# The Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Created for Purchase History feature by Elali McNair 3/3/26
# Finished by Nicco Hill 11/12/2026: atomic stock handling and edge cases in create_purchase.

"""
models/purchase_model.py

Purpose:
This file handles all direct database operations related to purchases.

This file includes DB operations for:
- purchases (user purchase history)

It will:
- Insert new purchase records
- Retrieve purchase data for a user
- Return results as dictionaries
"""

from db import get_connection


class PurchaseError(Exception):
    """Raised when a purchase can't go through. code is used for the HTTP status."""
    def __init__(self, message, code="invalid"):
        super().__init__(message)
        self.code = code  # "not_found" | "unavailable" | "sold_out" | "insufficient_stock" | "invalid"


def create_purchase(user_id, listing_id, quantity, size=None):
    """
    Records a purchase and takes the items out of inventory in ONE transaction.
    Returns the created purchase as a dictionary, or raises PurchaseError.

    Updated by Nicco Hill 11/12/2026:
    - The listing row is locked (SELECT ... FOR UPDATE) so two buyers can't both
      buy the last item at the same time.
    - Price comes from the database, never from the client.
    - Deleted -> not_found; inactive / storefront paused -> unavailable;
      sold out or not enough stock -> sold_out / insufficient_stock.
    - Made-to-order and preorder listings skip the stock check.
    - Listings with per-size stock (listing_sizes) need a size; that size is
      decremented and the listing total is re-synced.
    - When stock hits 0 the listing is marked SOLD_OUT.
    - The item is removed from the buyer's wishlist (same as checkout does).
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT l.id, l.status, l.price, l.quantity_on_hand, l.is_made_to_order,
                   l.fulfillment_type, s.is_active, s.owner_id
            FROM listings l
            JOIN storefronts s ON s.id = l.storefront_id
            WHERE l.id = %s
            FOR UPDATE OF l;
        """, (listing_id,))
        row = cur.fetchone()
        if row is None or row[1] == "DELETED":
            raise PurchaseError("Listing not found", "not_found")

        _, status, price, qty_on_hand, made_to_order, fulfillment_type, store_active, owner_id = row
        if owner_id == user_id:
            raise PurchaseError("You can't buy your own listing", "invalid")
        if status == "SOLD_OUT":
            raise PurchaseError("This item is sold out", "sold_out")
        if status != "ACTIVE" or store_active is False:
            raise PurchaseError("Listing is not available for purchase", "unavailable")

        tracks_stock = not made_to_order and fulfillment_type == "IN_STOCK" and qty_on_hand is not None
        if tracks_stock:
            cur.execute("SELECT size, quantity FROM listing_sizes WHERE listing_id = %s FOR UPDATE;", (listing_id,))
            size_rows = dict(cur.fetchall())

            if size_rows:
                if not size:
                    raise PurchaseError("Please choose a size", "invalid")
                if size not in size_rows:
                    raise PurchaseError(f"Size '{size}' is not offered for this listing", "invalid")
                if size_rows[size] < quantity:
                    if size_rows[size] == 0:
                        raise PurchaseError(f"Size {size} is sold out", "sold_out")
                    raise PurchaseError(f"Only {size_rows[size]} left in size {size}", "insufficient_stock")
                cur.execute(
                    "UPDATE listing_sizes SET quantity = quantity - %s WHERE listing_id = %s AND size = %s;",
                    (quantity, listing_id, size),
                )
                new_total = sum(size_rows.values()) - quantity
            else:
                if qty_on_hand < quantity:
                    if qty_on_hand == 0:
                        raise PurchaseError("This item is sold out", "sold_out")
                    raise PurchaseError(f"Only {qty_on_hand} left in stock", "insufficient_stock")
                new_total = qty_on_hand - quantity

            cur.execute("""
                UPDATE listings
                SET quantity_on_hand = %s,
                    status = CASE WHEN %s = 0 THEN 'SOLD_OUT' ELSE status END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (new_total, new_total, listing_id))

        cur.execute("""
            INSERT INTO purchases (user_id, listing_id, quantity, purchase_price)
            VALUES (%s, %s, %s, %s)
            RETURNING id, user_id, listing_id, quantity, purchase_price, purchase_date;
        """, (user_id, listing_id, quantity, price))
        row = cur.fetchone()

        cur.execute("DELETE FROM wishlist WHERE user_id = %s AND listing_id = %s;", (user_id, listing_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return {
        "id": row[0],
        "user_id": row[1],
        "listing_id": row[2],
        "quantity": row[3],
        "purchase_price": float(row[4]),
        "purchase_date": row[5],
        "size": size,
    }


def get_purchases_by_user_id(user_id):
    """
    Retrieves all purchases for a specific user.
    Returns a list of purchase dictionaries.
    """
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT p.id, p.user_id, p.listing_id, p.quantity, p.purchase_price, p.purchase_date,
               l.title, l.description, l.price as current_price, l.fulfillment_type,
               s.brand_name, s.logo_url
        FROM purchases p
        JOIN listings l ON p.listing_id = l.id
        JOIN storefronts s ON l.storefront_id = s.id
        WHERE p.user_id = %s
        ORDER BY p.purchase_date DESC;
    """

    cur.execute(query, (user_id,))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    purchases = []
    for row in rows:
        purchases.append({
            "id": row[0],
            "user_id": row[1],
            "listing_id": row[2],
            "quantity": row[3],
            "purchase_price": float(row[4]),
            "purchase_date": row[5],
            "listing": {
                "title": row[6],
                "description": row[7],
                "current_price": float(row[8]),
                "fulfillment_type": row[9],
            },
            "storefront": {
                "brand_name": row[10],
                "logo_url": row[11],
            }
        })

    return purchases


def get_purchase_by_id(purchase_id):
    """
    Retrieves a specific purchase by its ID.
    Returns None if not found.
    """
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT p.id, p.user_id, p.listing_id, p.quantity, p.purchase_price, p.purchase_date,
               l.title, l.description, l.price as current_price, l.fulfillment_type,
               s.brand_name, s.logo_url
        FROM purchases p
        JOIN listings l ON p.listing_id = l.id
        JOIN storefronts s ON l.storefront_id = s.id
        WHERE p.id = %s;
    """

    cur.execute(query, (purchase_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    if row:
        return {
            "id": row[0],
            "user_id": row[1],
            "listing_id": row[2],
            "quantity": row[3],
            "purchase_price": float(row[4]),
            "purchase_date": row[5],
            "listing": {
                "title": row[6],
                "description": row[7],
                "current_price": float(row[8]),
                "fulfillment_type": row[9],
            },
            "storefront": {
                "brand_name": row[10],
                "logo_url": row[11],
            }
        }
    return None