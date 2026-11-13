# The Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Updated by Day Ekoi - 4/22/26 - API-only blueprint
# Stripe test-mode checkout by Tykeara Hammond 10/18/2026
# Updated by Anthony Jackson - Iteration 4 (11/11/26) - THE PAYMENT DECISION:
#   Pirate Cove is an in-person exchange marketplace. Two ways to check out:
#     1. POST /api/checkout/complete  -> "Pay in person at the meetup" (the default, always on).
#        Restored because, without it, nobody could finish a purchase unless a Stripe key was
#        set - and the installer leaves STRIPE_SECRET_KEY empty, so graders couldn't buy anything.
#     2. POST /api/checkout/create-session -> optional Stripe card checkout, TEST MODE ONLY.
#        Shown only when STRIPE_SECRET_KEY is a test key (sk_test_...). Live keys are refused.
#   GET /api/checkout/options tells checkout.js which buttons to show.
#   Both paths now price the bag from the database (the browser's price is ignored) and save
#   the whole order in one transaction. See backend/utils/payments.py.

from flask import Blueprint, request, jsonify, session, redirect
import stripe

from services.checkout_service import (
    CheckoutError,
    validate_buyer,
    quote_cart,
    complete_transaction_from_session,
    get_order_summary_service,
    get_user_orders_service,
)
from utils.payments import stripe_mode, stripe_enabled, stripe_api_key, payment_summary, STRIPE_TEST

checkout_bp = Blueprint("checkout", __name__)

GENERIC_ERROR = "Checkout failed. Nothing was charged and your bag was not changed. Please try again."


def _error(e):
    """Turn an exception into a JSON error. Only CheckoutError messages are shown to the buyer."""
    if isinstance(e, CheckoutError):
        return jsonify({"error": str(e)}), e.status
    print(f"[checkout] unexpected error: {e!r}")
    return jsonify({"error": GENERIC_ERROR}), 500


def _finish_order(result):
    session["cart"] = []
    session.pop("pending_buyer", None)
    session["last_confirmation"] = result["confirmation_number"]
    session.modified = True


@checkout_bp.route("/checkout/options", methods=["GET"])
def checkout_options():
    """Which payment choices the checkout page should show."""
    return jsonify({"in_person": True, "stripe_test": stripe_enabled(), "summary": payment_summary()}), 200


@checkout_bp.route("/checkout/complete", methods=["POST"])
def complete_checkout():
    """Pay in person at the meetup (default). Creates the order right away."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    session_cart = session.get("cart", [])
    if not session_cart:
        return jsonify({"error": "Cart is empty"}), 400

    try:
        result = complete_transaction_from_session(user_id, session_cart, request.get_json(silent=True) or {})
    except Exception as e:
        return _error(e)

    _finish_order(result)
    return jsonify({
        "success": True,
        "confirmation_number": result["confirmation_number"],
        "order_id": result["order"]["id"],
        "total_amount": result["total_amount"],
        "payment_method": result["order"]["payment_method"],
    }), 200


@checkout_bp.route("/checkout/create-session", methods=["POST"])
def create_checkout_session(): # Starts a Stripe test-mode payment - Tykeara Hammond 10/18/2026
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    session_cart = session.get("cart", [])
    if not session_cart:
        return jsonify({"error": "Cart is empty"}), 400

    if stripe_mode() == "live_refused":
        stripe_api_key()   # prints the warning
        return jsonify({"error": "Card checkout is turned off (live Stripe keys are not allowed). "
                                 "Choose Pay in Person instead."}), 503

    try:
        buyer = validate_buyer(request.get_json(silent=True) or {})
        # Database prices, not the browser's. This also checks stock (and deleted/paused listings)
        # BEFORE the buyer is sent to Stripe, so a card is never charged for an item that's gone
        # (same goal as Nicco Hill's 11/12/2026 check on main).
        quoted = quote_cart(user_id, session_cart)
    except Exception as e:
        return _error(e)
    session["pending_buyer"] = buyer

    line_items = [{
        "price_data": {
            "currency": "usd",
            "product_data": {"name": line["name"]},
            "unit_amount": int(round(line["price"] * 100)),
        },
        "quantity": line["quantity"],
    } for line in quoted]

    try:
        stripe.api_key = stripe_api_key()   # None unless it's a test key
        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            success_url=request.host_url + "api/checkout/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.host_url + "checkout",
            metadata={"user_id": str(user_id)},
        )
        return jsonify({"url": checkout_session.url}), 200
    except Exception as e:
        print(f"[checkout] Stripe error: {e!r}")
        if not stripe_enabled():
            return jsonify({"error": "Card checkout isn't set up on this copy. Choose Pay in Person instead."}), 503
        return jsonify({"error": "Stripe could not start the payment. Please try again."}), 502


@checkout_bp.route("/checkout/success", methods=["GET"])
def checkout_success(): # Confirms the Stripe payment, then creates the order - Tykeara Hammond 10/18/2026
    user_id = session.get("user_id")
    session_id = request.args.get("session_id")
    if not user_id or not session_id:
        return redirect("/checkout")

    # Refresh guard: reloading this page must not create the order twice
    if session.get("last_paid_session") == session_id:
        return redirect(f"/order-confirmation?conf={session.get('last_confirmation', '')}")

    try:
        stripe.api_key = stripe_api_key()
        checkout_session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return redirect("/checkout")

    # Only continue if Stripe says it's paid AND it belongs to this user
    if checkout_session.payment_status != "paid" or checkout_session.metadata.to_dict().get("user_id") != str(user_id):
        return redirect("/checkout")

    try:
        result = complete_transaction_from_session(
            user_id, session.get("cart", []), session.get("pending_buyer", {}), STRIPE_TEST, "PAID_TEST")
    except Exception as e:
        return _error(e)

    _finish_order(result)
    session["last_paid_session"] = session_id
    return redirect(f"/order-confirmation?conf={result['confirmation_number']}")


@checkout_bp.route("/orders/by-confirmation/<confirmation_number>", methods=["GET"])
def get_order_confirmation(confirmation_number):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    try:
        result = get_order_summary_service(confirmation_number, user_id)
        return jsonify(result), 200
    except Exception as e:
        return _error(e)


@checkout_bp.route("/orders/my", methods=["GET"])
def get_my_orders():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    try:
        orders = get_user_orders_service(user_id)
        return jsonify({"orders": orders}), 200
    except Exception as e:
        return _error(e)
