# The Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Created for Purchase History feature by Elali McNair 3/3/26
# Finished by Nicco Hill 11/12/2026:
#   - The user now comes from the login session, not an X-User-Id header.
#   - Status codes for edge cases: 404 deleted/missing listing,
#     409 sold out / not enough stock / listing paused, 400 bad input.

"""
controllers/purchase_controller.py

Purpose:
This controller handles HTTP requests related to purchase operations.
It processes requests, calls service methods, and returns JSON responses.
"""

from flask import Blueprint, request, jsonify, session
from services.purchase_service import PurchaseService

purchase_bp = Blueprint('purchase', __name__, url_prefix="/api")
purchase_service = PurchaseService()

UNAUTHORIZED = ({"error": "Unauthorized: please log in."}, 401)
MAX_QUANTITY_PER_PURCHASE = 99

ERROR_STATUS = {
    "not_found": 404,
    "unavailable": 409,
    "sold_out": 409,
    "insufficient_stock": 409,
    "invalid": 400,
}


def get_current_user_id():
    """Returns the logged-in user's id (set at login), or None."""
    return session.get("user_id")


def _is_positive_int(value):
    # bool is a subclass of int in Python, so True/False would slip through isinstance(int)
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


@purchase_bp.route('/purchases', methods=['POST'])
def record_purchase():
    """
    Records a new purchase for the logged-in user.
    Expects JSON: {"listing_id": int, "quantity": int, "size": str (optional)}
    "size" is required when the listing tracks stock per size.
    """
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify(UNAUTHORIZED[0]), UNAUTHORIZED[1]

    data = request.get_json(silent=True)
    if not data or 'listing_id' not in data or 'quantity' not in data:
        return jsonify({"error": "Missing required fields: listing_id, quantity"}), 400

    listing_id = data['listing_id']
    quantity = data['quantity']
    size = data.get('size')

    if not _is_positive_int(listing_id):
        return jsonify({"error": "Invalid listing_id"}), 400
    if not _is_positive_int(quantity) or quantity > MAX_QUANTITY_PER_PURCHASE:
        return jsonify({"error": f"quantity must be a whole number from 1 to {MAX_QUANTITY_PER_PURCHASE}"}), 400
    if size is not None and (not isinstance(size, str) or not size.strip()):
        return jsonify({"error": "Invalid size"}), 400

    success, result, error_code = purchase_service.record_purchase(
        user_id, listing_id, quantity, size.strip() if size else None
    )
    if success:
        return jsonify({"message": "Purchase recorded successfully", "purchase": result}), 201
    return jsonify({"error": result}), ERROR_STATUS.get(error_code, 500)


@purchase_bp.route('/purchases', methods=['GET'])
def get_purchase_history():
    """
    Retrieves the purchase history for the logged-in user.
    """
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify(UNAUTHORIZED[0]), UNAUTHORIZED[1]

    success, result = purchase_service.get_user_purchase_history(user_id)
    if success:
        return jsonify({"purchases": result}), 200
    return jsonify({"error": result}), 500


@purchase_bp.route('/purchases/<int:purchase_id>', methods=['GET'])
def get_purchase_details(purchase_id):
    """
    Retrieves details of a specific purchase owned by the logged-in user.
    """
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify(UNAUTHORIZED[0]), UNAUTHORIZED[1]

    success, result = purchase_service.get_purchase_details(purchase_id)
    if not success:
        status = 404 if result == "Purchase not found" else 500
        return jsonify({"error": result}), status

    if result['user_id'] != user_id:
        return jsonify({"error": "Access denied"}), 403
    return jsonify({"purchase": result}), 200
