# File created by David Jackson
# models/admin_model.py

"""
Database queries used by the admin dashboard.
"""

from db import get_connection
from models.listing_model import soft_delete_listing
from models.return_model import get_all_returns, update_return_status
from models.storefront_model import get_all_storefronts


def get_all_users():
    """
    Retrieves every user in the system.

    Returns:
        list: A list of user records from the database.
              Each record contains:
              - id
              - username
              - email
              - role
              - created_at
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, username, email, role, created_at
        FROM users
        ORDER BY created_at DESC
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "role": row[3],
            "created_at": row[4],
        }
        for row in rows
    ]


def get_user_role(user_id):
    """
    Returns the role ('user' or 'admin') for a user id, or None if there is no such user.
    Added by Ethan Williams 11/9/26 so the dashboard can refuse to delete admin accounts.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return (row[0] or "user") if row else None
    finally:
        cur.close()
        conn.close()


def delete_user(user_id):
    """
    Deletes a user. Returns True if a row was deleted, False if the id didn't exist.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM users
        WHERE id = %s
    """, (user_id,))
    deleted = cur.rowcount > 0

    conn.commit()
    cur.close()
    conn.close()
    return deleted


def get_all_listings():
    """
    Retrieves every listing in the marketplace.

    Returns:
        list: Listing records including:
              - id
              - storefront_id
              - title
              - price
              - quantity_on_hand
              - status
              - fulfillment_type
              - created_at
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, storefront_id, title, price, quantity_on_hand, status, fulfillment_type, created_at
        FROM listings
        ORDER BY created_at DESC
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id": row[0],
            "storefront_id": row[1],
            "title": row[2],
            "price": float(row[3]) if row[3] is not None else None,
            "quantity_on_hand": row[4],
            "status": row[5],
            "fulfillment_type": row[6],
            "created_at": row[7],
        }
        for row in rows
    ]


def delete_listing(listing_id):
    """
    Soft deletes a listing from the marketplace.

    Parameters:
        listing_id (int): Unique ID of the listing.
    """
    return soft_delete_listing(listing_id)


def get_admin_storefronts():
    """
    Retrieves all storefronts created by users.

    Returns:
        list: Storefront records including:
              - id
              - brand_name
              - owner_id
              - is_active
              - categories
    """
    rows = get_all_storefronts()

    return [
        {
            "id": row.get("id"),
            "brand_name": row.get("brand_name"),
            "owner_id": row.get("owner_id"),
            "is_active": row.get("is_active"),
            "categories": row.get("categories"),
            "item_count": row.get("item_count", 0),
        }
        for row in rows
    ]


def get_admin_returns():
    return get_all_returns(include_deleted=False)


def update_admin_return_status(return_id, status):
    return update_return_status(return_id, status)


# Added by David Jackson 4/23/2026
# Returns True/False (deleted or not found) - Ethan Williams 11/9/26
def delete_storefront(store_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM storefronts
        WHERE id = %s
    """, (store_id,))
    deleted = cur.rowcount > 0

    conn.commit()

    cur.close()
    conn.close()
    return deleted