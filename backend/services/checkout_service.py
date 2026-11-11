# The Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Updated by Day Ekoi - 4/22/26
# Updated by Anthony Jackson - Iteration 4 (11/11/26):
#   - Checkout is now ONE database transaction (models.checkout_model.place_order).
#     Before, a failure halfway could leave an order with missing items or the wrong stock.
#   - Prices and names come from the listings table, never from the cart in the browser.
#   - Buyer details are checked properly (email format, 10-digit phone, length limits).
#   - Duplicate bag lines for the same item and size are merged before stock is checked.
#   - Errors the buyer can fix are CheckoutError (safe message + HTTP status). Anything else is
#     logged and shown as a general error, so database details never reach the browser.
#   - payment_method / payment_status are saved on every order (in person vs. Stripe test).

import re
import secrets
import string
from datetime import datetime

import psycopg2

from models.checkout_model import (
    CheckoutError,
    place_order,
    quote_lines,
    get_order_by_confirmation,
    get_order_items_by_order_id,
    get_orders_by_user_id,
)
from utils.payments import IN_PERSON

__all__ = [
    "CheckoutError",
    "validate_buyer",
    "merge_cart_lines",
    "quote_cart",
    "complete_transaction_from_session",
    "get_order_summary_service",
    "get_user_orders_service",
]

MAX_QTY_PER_LINE = 20
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'\-]*$")


def _generate_confirmation_number():
    date_str = datetime.now().strftime("%y%m%d")
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"COVE-{date_str}-{suffix}"


def validate_buyer(details):
    """Clean the buyer form. Returns a dict, or raises CheckoutError naming the problem."""
    details = details or {}

    def text(key):
        value = details.get(key)
        return value.strip() if isinstance(value, str) else ""

    buyer = {k: text(k) for k in ("first_name", "last_name", "email", "contact", "meeting_location")}

    if not all(buyer.values()):
        raise CheckoutError("All fields are required to complete your transaction.")
    for key, label in (("first_name", "First name"), ("last_name", "Last name")):
        if len(buyer[key]) > 100 or not _NAME_RE.match(buyer[key]):
            raise CheckoutError(f"{label} can only use letters, spaces, hyphens and apostrophes (100 max).")
    if len(buyer["email"]) > 255 or not _EMAIL_RE.match(buyer["email"]):
        raise CheckoutError("Please enter a valid email address.")
    digits = re.sub(r"\D", "", buyer["contact"])
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise CheckoutError("Contact number must be a 10-digit phone number.")
    buyer["contact"] = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if len(buyer["meeting_location"]) > 200:
        raise CheckoutError("Meeting location is too long (200 characters max).")
    return buyer


def merge_cart_lines(session_cart):
    """Turn the session cart into [(listing_id, size, quantity)], one line per item + size."""
    if not session_cart:
        raise CheckoutError("Your bag is empty.")
    merged = {}
    for item in session_cart:
        raw_id = item.get("id", item.get("listing_id"))
        try:
            listing_id = int(raw_id)
            quantity = int(item.get("quantity", 1))
        except (TypeError, ValueError):
            raise CheckoutError("An item in your bag is no longer available. Please remove it and try again.", 409)
        if quantity < 1:
            raise CheckoutError("Quantity must be at least 1.")
        size = (item.get("size") or "").strip() or None
        key = (listing_id, size)
        merged[key] = merged.get(key, 0) + quantity
    lines = []
    for (listing_id, size), quantity in merged.items():
        if quantity > MAX_QTY_PER_LINE:
            raise CheckoutError(f"You can buy at most {MAX_QTY_PER_LINE} of one item per order.")
        lines.append((listing_id, size, quantity))
    return lines


def quote_cart(user_id, session_cart):
    """Database prices for the bag (used for Stripe line items). Raises CheckoutError."""
    return quote_lines(user_id, merge_cart_lines(session_cart))


def complete_transaction_from_session(user_id, session_cart, buyer_details,
                                      payment_method=IN_PERSON, payment_status="PAY_AT_MEETUP"):
    """
    Completes checkout using the session cart and the buyer form - all or nothing.

    buyer_details keys: first_name, last_name, email, contact, meeting_location
    session_cart items: { id, name, price, quantity, size }  (name and price are ignored;
                        the database values are used)
    """
    buyer = validate_buyer(buyer_details)
    lines = merge_cart_lines(session_cart)

    for _ in range(3):   # a new confirmation number if one ever collides
        try:
            result = place_order(user_id, _generate_confirmation_number(), buyer, lines,
                                 payment_method=payment_method, payment_status=payment_status)
            break
        except psycopg2.errors.UniqueViolation as e:
            if "confirmation_number" not in str(e):
                raise
    else:
        raise CheckoutError("Could not create a confirmation number. Please try again.", 500)

    return {
        "confirmation_number": result["order"]["confirmation_number"],
        "order": result["order"],
        "order_items": result["order_items"],
        "total_amount": result["total_amount"],
    }


def get_order_summary_service(confirmation_number, user_id):
    """Returns order + items for the confirmation page. Only the buyer can see it.
    Someone else's order looks the same as a missing one (404), so numbers can't be probed."""
    order = get_order_by_confirmation(confirmation_number)
    if not order or order["user_id"] != user_id:
        raise CheckoutError("Order not found.", 404)
    items = get_order_items_by_order_id(order["id"])
    return {"order": order, "order_items": items}


def get_user_orders_service(user_id):
    """Returns all orders for the given user, newest first."""
    return get_orders_by_user_id(user_id)
