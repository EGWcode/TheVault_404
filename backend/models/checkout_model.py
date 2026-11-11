# The Vault Campus Marketplace
# CSC 405 Sp 26'
# Updated by Day Ekoi - 4/22/26 - rewrote to match orders/order_items schema
# Updated by Anthony Jackson - Iteration 4 (11/11/26):
#   - Added place_order(): the whole checkout now happens in ONE database transaction.
#     Before, the order, each item, the stock change, the cart clear and the wishlist clear
#     were separate connections, so a failure halfway left a half-made order or wrong stock.
#   - Prices and item names now come from the listings table, not from the browser.
#     (The add-to-cart form sends the price in a hidden field, which a buyer could edit.)
#   - Listing and size rows are locked (SELECT ... FOR UPDATE) while the order is placed,
#     so two buyers can't both buy the last item.
#   - Order reads now include payment_method / payment_status.

from db import get_connection


class CheckoutError(Exception):
    """A problem the buyer can fix (sold out, bad input...). The message is safe to show them.
    status is the HTTP code the API should return."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


_ORDER_COLUMNS = """id, user_id, confirmation_number, buyer_first_name, buyer_last_name,
                    buyer_email, buyer_contact, buyer_meeting_location, total_amount, order_status,
                    created_at, payment_method, payment_status"""


def _order_row_to_dict(row):
    return {
        "id": row[0],
        "user_id": row[1],
        "confirmation_number": row[2],
        "buyer_first_name": row[3],
        "buyer_last_name": row[4],
        "buyer_email": row[5],
        "buyer_contact": row[6],
        "buyer_meeting_location": row[7],
        "total_amount": float(row[8]),
        "order_status": row[9],
        "created_at": row[10].isoformat() if row[10] else None,
        "payment_method": row[11],
        "payment_status": row[12],
    }


def _lock_and_price_line(cur, user_id, listing_id, size, quantity):
    """Check one cart line against the database and return (title, unit_price, size_row_exists).
    Raises CheckoutError if it can't be bought."""
    cur.execute("""
        SELECT l.title, l.price, l.status, l.quantity_on_hand, COALESCE(l.is_made_to_order, FALSE),
               s.owner_id, COALESCE(s.is_active, TRUE)
        FROM listings l
        JOIN storefronts s ON s.id = l.storefront_id
        WHERE l.id = %s
        FOR UPDATE OF l;
    """, (listing_id,))
    row = cur.fetchone()
    if not row:
        raise CheckoutError("An item in your bag is no longer available. Please remove it and try again.", 409)
    title, price, status, qty_on_hand, made_to_order, owner_id, store_active = row

    if status in ("DELETED", "INACTIVE") or not store_active:
        raise CheckoutError(f'"{title}" is no longer available. Please remove it from your bag.', 409)
    if owner_id == user_id:
        raise CheckoutError(f'"{title}" is from your own storefront. You can\'t buy your own item.', 400)

    size_row_exists = False
    if not made_to_order:
        if status == "SOLD_OUT":
            raise CheckoutError(f'"{title}" is sold out.', 409)
        if size:
            cur.execute(
                "SELECT quantity FROM listing_sizes WHERE listing_id = %s AND size = %s FOR UPDATE;",
                (listing_id, size),
            )
            size_row = cur.fetchone()
            if size_row is not None:
                size_row_exists = True
                if int(size_row[0]) < quantity:
                    raise CheckoutError(
                        f'"{title}" only has {int(size_row[0])} left in size {size} (you asked for {quantity}).', 409)
            else:
                cur.execute("SELECT 1 FROM listing_sizes WHERE listing_id = %s LIMIT 1;", (listing_id,))
                if cur.fetchone():
                    raise CheckoutError(f'Size {size} of "{title}" is not available.', 409)
        if not size_row_exists and qty_on_hand is not None and int(qty_on_hand) < quantity:
            raise CheckoutError(
                f'"{title}" only has {int(qty_on_hand)} in stock (you asked for {quantity}).', 409)

    return title, float(price), size_row_exists, made_to_order


def _take_stock(cur, listing_id, size, quantity, size_row_exists, made_to_order):
    """Lower the stock after a sale and mark the listing SOLD_OUT when it hits zero."""
    if made_to_order:
        return
    if size_row_exists:
        cur.execute(
            "UPDATE listing_sizes SET quantity = quantity - %s WHERE listing_id = %s AND size = %s;",
            (quantity, listing_id, size),
        )
        cur.execute("SELECT COALESCE(SUM(quantity), 0) FROM listing_sizes WHERE listing_id = %s;", (listing_id,))
        remaining = int(cur.fetchone()[0])
        cur.execute("""
            UPDATE listings
            SET quantity_on_hand = %s,
                status = CASE WHEN %s = 0 THEN 'SOLD_OUT' ELSE status END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (remaining, remaining, listing_id))
    else:
        cur.execute("""
            UPDATE listings
            SET quantity_on_hand = GREATEST(0, quantity_on_hand - %s),
                status = CASE WHEN quantity_on_hand IS NOT NULL AND quantity_on_hand - %s <= 0
                              THEN 'SOLD_OUT' ELSE status END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (quantity, quantity, listing_id))


def quote_lines(user_id, lines):
    """Price the bag from the database without buying anything (used before sending the buyer
    to Stripe). Returns [{listing_id, name, price, quantity, size}] or raises CheckoutError."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        quoted = []
        for listing_id, size, quantity in lines:
            title, price, _, _ = _lock_and_price_line(cur, user_id, listing_id, size, quantity)
            quoted.append({"listing_id": listing_id, "name": title, "price": price,
                           "quantity": quantity, "size": size})
        return quoted
    finally:
        conn.rollback()   # read-only: release the row locks
        conn.close()


def place_order(user_id, confirmation_number, buyer, lines, payment_method="IN_PERSON",
                payment_status="PAY_AT_MEETUP"):
    """Create the order, its items, take the stock, and clear the bag and wishlist - all or nothing.

    buyer: dict with first_name, last_name, email, contact, meeting_location (already validated)
    lines: list of (listing_id, size, quantity), already merged so each listing+size appears once
    Returns {"order": {...}, "order_items": [...], "total_amount": float}
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Lock listings in a fixed order so two checkouts can't deadlock each other
        priced = []
        for listing_id, size, quantity in sorted(lines, key=lambda l: (l[0], l[1] or "")):
            title, price, size_row_exists, made_to_order = _lock_and_price_line(
                cur, user_id, listing_id, size, quantity)
            priced.append((listing_id, size, quantity, title, price, size_row_exists, made_to_order))

        total = round(sum(q * p for _, _, q, _, p, _, _ in priced), 2)

        cur.execute(f"""
            INSERT INTO orders (user_id, confirmation_number, buyer_first_name, buyer_last_name,
                                buyer_email, buyer_contact, buyer_meeting_location, total_amount,
                                order_status, payment_method, payment_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'SUBMITTED', %s, %s)
            RETURNING {_ORDER_COLUMNS};
        """, (user_id, confirmation_number, buyer["first_name"], buyer["last_name"], buyer["email"],
              buyer["contact"], buyer["meeting_location"], total, payment_method, payment_status))
        order = _order_row_to_dict(cur.fetchone())

        items = []
        for listing_id, size, quantity, title, price, size_row_exists, made_to_order in priced:
            cur.execute("""
                INSERT INTO order_items (order_id, listing_id, item_name, quantity, price_at_purchase, selected_size)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (order["id"], listing_id, title, quantity, price, size))
            items.append({
                "id": cur.fetchone()[0],
                "order_id": order["id"],
                "listing_id": listing_id,
                "item_name": title,
                "quantity": quantity,
                "price_at_purchase": price,
                "selected_size": size,
            })
            _take_stock(cur, listing_id, size, quantity, size_row_exists, made_to_order)

        cur.execute("DELETE FROM cart_items WHERE user_id = %s;", (user_id,))
        cur.execute("DELETE FROM wishlist WHERE user_id = %s AND listing_id = ANY(%s);",
                    (user_id, [p[0] for p in priced]))
        conn.commit()
        cur.close()
        return {"order": order, "order_items": items, "total_amount": total}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_order(user_id, confirmation_number, buyer_first_name, buyer_last_name,
                 buyer_email, buyer_contact, buyer_meeting_location, total_amount):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders (user_id, confirmation_number, buyer_first_name, buyer_last_name,
                            buyer_email, buyer_contact, buyer_meeting_location, total_amount, order_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'SUBMITTED')
        RETURNING id, user_id, confirmation_number, buyer_first_name, buyer_last_name,
                  buyer_email, buyer_contact, buyer_meeting_location, total_amount, order_status, created_at;
    """, (user_id, confirmation_number, buyer_first_name, buyer_last_name,
          buyer_email, buyer_contact, buyer_meeting_location, total_amount))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {
        "id": row[0],
        "user_id": row[1],
        "confirmation_number": row[2],
        "buyer_first_name": row[3],
        "buyer_last_name": row[4],
        "buyer_email": row[5],
        "buyer_contact": row[6],
        "buyer_meeting_location": row[7],
        "total_amount": float(row[8]),
        "order_status": row[9],
        "created_at": str(row[10]),
    }


def create_order_item(order_id, listing_id, item_name, quantity, price_at_purchase, selected_size=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO order_items (order_id, listing_id, item_name, quantity, price_at_purchase, selected_size)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, order_id, listing_id, item_name, quantity, price_at_purchase, selected_size;
    """, (order_id, listing_id, item_name, quantity, price_at_purchase, selected_size))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {
        "id": row[0],
        "order_id": row[1],
        "listing_id": row[2],
        "item_name": row[3],
        "quantity": row[4],
        "price_at_purchase": float(row[5]),
        "selected_size": row[6],
    }


def get_order_by_confirmation(confirmation_number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT {_ORDER_COLUMNS}
        FROM orders
        WHERE confirmation_number = %s;
    """, (confirmation_number,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return _order_row_to_dict(row)


def get_order_items_by_order_id(order_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, order_id, listing_id, item_name, quantity, price_at_purchase, selected_size
        FROM order_items
        WHERE order_id = %s
        ORDER BY id ASC;
    """, (order_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id": r[0],
            "order_id": r[1],
            "listing_id": r[2],
            "item_name": r[3],
            "quantity": r[4],
            "price_at_purchase": float(r[5]),
            "selected_size": r[6],
        }
        for r in rows
    ]


def get_orders_by_user_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, confirmation_number, buyer_first_name, buyer_last_name,
               buyer_email, total_amount, order_status, created_at, payment_method, payment_status
        FROM orders
        WHERE user_id = %s
        ORDER BY created_at DESC;
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "confirmation_number": r[2],
            "buyer_first_name": r[3],
            "buyer_last_name": r[4],
            "buyer_email": r[5],
            "total_amount": float(r[6]),
            "order_status": r[7],
            "created_at": str(r[8]),
            "payment_method": r[9],
            "payment_status": r[10],
        }
        for r in rows
    ]


def remove_purchased_from_wishlist(user_id, listing_ids):
    """
    Removes wishlist entries for listings the user just purchased.
    Uses listing_id matching only — the wishlist has a UNIQUE(user_id, listing_id)
    constraint so there is at most one entry per listing per user.
    """
    if not listing_ids:
        return {"deleted_count": 0}
    # Filter out None values
    valid_ids = [int(lid) for lid in listing_ids if lid is not None]
    if not valid_ids:
        return {"deleted_count": 0}
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM wishlist WHERE user_id = %s AND listing_id = ANY(%s);",
        (user_id, valid_ids)
    )
    deleted_count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return {"deleted_count": deleted_count}


def clear_cart_for_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE user_id = %s;", (user_id,))
    deleted_count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return {"deleted_count": deleted_count}


def check_listing_availability(listing_id, quantity_requested):
    """Raises if the listing is sold out or has insufficient stock. Skips made-to-order items."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT title, status, quantity_on_hand, is_made_to_order FROM listings WHERE id = %s",
        (listing_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise Exception(f"Item (ID {listing_id}) is no longer available.")
    title, status, qty_on_hand, is_made_to_order = row
    if is_made_to_order:
        return
    if status == "SOLD_OUT":
        raise Exception(f'"{title}" is sold out.')
    if qty_on_hand is not None and int(qty_on_hand) < quantity_requested:
        raise Exception(
            f'"{title}" only has {qty_on_hand} in stock (you requested {quantity_requested}).'
        )


def update_listing_size_inventory(listing_id, size, purchased_qty):
    """Decrements per-size inventory and syncs listing quantity_on_hand after purchase."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT quantity FROM listing_sizes WHERE listing_id = %s AND size = %s",
        (listing_id, size)
    )
    size_row = cur.fetchone()
    if size_row is None or int(size_row[0]) < purchased_qty:
        cur.close()
        conn.close()
        available = int(size_row[0]) if size_row else 0
        raise Exception(
            f"Insufficient stock for listing {listing_id} size '{size}': "
            f"requested {purchased_qty}, available {available}."
        )
    cur.execute("""
        UPDATE listing_sizes
        SET quantity = GREATEST(0, quantity - %s)
        WHERE listing_id = %s AND size = %s;
    """, (purchased_qty, listing_id, size))
    cur.execute("""
        SELECT COALESCE(SUM(quantity), 0) FROM listing_sizes WHERE listing_id = %s;
    """, (listing_id,))
    total_qty = int(cur.fetchone()[0])
    new_status = "SOLD_OUT" if total_qty == 0 else None
    cur.execute("""
        UPDATE listings
        SET quantity_on_hand = %s,
            status = COALESCE(%s, CASE WHEN status = 'SOLD_OUT' AND %s > 0 THEN 'ACTIVE' ELSE status END),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s AND (is_made_to_order = FALSE OR is_made_to_order IS NULL);
    """, (total_qty, new_status, total_qty, listing_id))
    conn.commit()
    cur.close()
    conn.close()
