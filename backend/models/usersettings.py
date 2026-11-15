



#Edited by Jaylen Belle
#This is the database work for the settings tab on the account page for account information like username, email, role, account created, and password changing. 


from db import get_connection  #Opens a new connection to PostgreSQL


def get_account(user_id):
    """Gets the account information as a dictionary, or none if not found."""
    conn= get_connection()
    cur = conn.cursor()
    try:        #looks up the user info and keeps SQL injection safe
        cur.execute("SELECT username, email, role, created_at FROM users WHERE id = %s;", (user_id,),)
        row = cur.fetchone()
        if row is None:
            return None
        
        #A query that counts the user's listings, wishlist items, orders, and storefront ownership
        cur.execute("""SELECT (SELECT count(*) FROM listings l Join storefronts s ON l.storefront_id = s.id WHERE s.owner_id = %s AND l.status <> 'DELETED'), (SELECT COUNT (*) FROM wishlist WHERE user_id =%s), (SELECT COUNT (*) FROM orders WHERE user_id = %s), EXISTS (SELECT 1 FROM storefronts WHERE owner_id = %s);""", (user_id, user_id, user_id, user_id),)

        listings, wishlist, orders, has_storefront = cur.fetchone()

        #Return the user's account information as a dictionary to the page
        return {
            "username": row[0],
            "email": row[1],
            "role": row[2],
            "created_at": row[3],
            "listings_count": listings,
            "wishlist_count": wishlist,
            "orders_count": orders,
            "has_storefront": bool(has_storefront),
        }
    finally:
        cur.close()
        conn.close()



def get_user_password_hash(user_id):
    """Gets the stored password hash for the user, or None if the user is not found."""
    conn = get_connection()
    cur = conn.cursor()
    try: 
        cur.execute("SELECT password FROM users WHERE id = %s;", (user_id,))
        row = cur.fetchone()
        return row[0] if row is not None else None
    finally:
        cur.close()
        conn.close()



def set_user_password_hash(user_id, password_hash):
    """This saves a new password hash."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET password = %s WHERE id = %s;", (password_hash, user_id))
        conn.commit()   #makes the changes permanent
    except Exception:
        conn.rollback()   #rolls back the changes if an error occurs
        raise
    finally:
        cur.close()
        conn.close()







        




   

