# The Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Updated by Day Ekoi - 4/22/26 - API-only blueprint

from flask import Blueprint, request, jsonify, session, redirect
import os
from dotenv import load_dotenv
import stripe
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

from services.checkout_service import (
    complete_transaction_from_session,
    get_order_summary_service,
    get_user_orders_service,
)

checkout_bp = Blueprint("checkout", __name__)
#Removed /checkout/complete so orders cant be created without a stripe payment - Tykeara Hammond 10/20/2026
@checkout_bp.route("/checkout/create-session", methods=["POST"])
def create_checkout_session(): # Starts a Stripe test-mode payment - Tykeara Hammond 10/18/2026
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    session_cart = session.get("cart", [])
    if not session_cart:
        return jsonify({"error": "Cart is empty"}), 400

    buyer = request.get_json() or {}
    required = ["first_name", "last_name", "email", "contact", "meeting_location"]
    for field in required:
        if not (buyer.get(field) or "").strip():
            return jsonify({"error": "All fields are required."}), 400
    session["pending_buyer"] = buyer

    line_items = []
    for item in session_cart:
        price = float(item.get("price", 0)) 
        line_items.append({
            "price_data": {
                "currency": "usd",
                "product_data": {"name": item.get("name", "Item")},
                "unit_amount": int(round(price * 100)),
            },
            "quantity": int(item.get("quantity", 1)),
        })

    try:
        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            success_url=request.host_url + "api/checkout/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.host_url + "checkout",
            metadata={"user_id": str(user_id)},
        )
        return jsonify({"url": checkout_session.url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


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
        checkout_session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return redirect("/checkout")

    # Only continue if Stripe says it's paid AND it belongs to this user
    if checkout_session.payment_status != "paid" or checkout_session.metadata.to_dict().get("user_id") != str(user_id):
        return redirect("/checkout")

    try:
        result = complete_transaction_from_session(user_id, session.get("cart", []), session.get("pending_buyer", {}))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    session["cart"] = []
    session.pop("pending_buyer", None)
    session["last_paid_session"] = session_id
    session["last_confirmation"] = result["confirmation_number"]
    session.modified = True
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
        return jsonify({"error": str(e)}), 400


@checkout_bp.route("/orders/my", methods=["GET"])
def get_my_orders():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    try:
        orders = get_user_orders_service(user_id)
        return jsonify({"orders": orders}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
