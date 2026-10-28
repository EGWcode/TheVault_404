# The Vault Campus Marketplace
# Created by Anthony Jackson 10/21/26 for the optional user profile

"""
models/profile_model.py

Purpose:
Database work for the optional profile info on the users table:
first name, last name, phone, class year, and hometown.
"""

from db import get_connection

# Only these columns can ever be changed through the profile
PROFILE_FIELDS = ("first_name", "last_name", "phone", "class_year", "hometown")


def get_profile(user_id):
    """Returns the user's profile as a dict, or None if the user doesn't exist."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT username, email, first_name, last_name, phone, class_year, hometown
               FROM users WHERE id = %s;""",
            (user_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "username": row[0],
            "email": row[1],
            "first_name": row[2] or "",
            "last_name": row[3] or "",
            "phone": row[4] or "",
            "class_year": row[5] or "",
            "hometown": row[6] or "",
        }
    finally:
        cur.close()
        conn.close()


def update_profile(user_id, values):
    """
    Saves the given profile values. 'values' maps a column name to its new value
    (None clears it). Column names are checked against PROFILE_FIELDS first.
    """
    columns = [c for c in values if c in PROFILE_FIELDS]
    if not columns:
        return
    assignments = ", ".join(f"{c} = %s" for c in columns)
    params = [values[c] for c in columns] + [user_id]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"UPDATE users SET {assignments} WHERE id = %s;", params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
