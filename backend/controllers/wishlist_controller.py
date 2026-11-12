# The Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Created for Wishlist feature by Elali McNair 3/3/26
# Finished by Nicco Hill 11/12/2026:
#   - The user now comes from the login session, not an X-User-Id header
#     (a header can be set to any id, so anyone could edit anyone's wishlist).
#   - Clear status codes for edge cases: 404 deleted/missing listing,
#     400 duplicate (storefront_view.js relies on this), 500 hides DB details.

"""
controllers/wishlist_controller.py

Purpose:
This controller handles HTTP requests related to wishlist operations.
It processes requests, calls service methods, and returns JSON responses.
"""

from flask import Blueprint, request, jsonify, session
from services.wishlist_service import WishlistService

wishlist_bp = Blueprint('wishlist', __name__, url_prefix="/api")
wishlist_service = WishlistService()

UNAUTHORIZED = ({"error": "Unauthorized: please log in."}, 401)


def get_current_user_id():
    """Returns the logged-in user's id (set at login), or None."""
    return session.get("user_id")


def _is_valid_id(value):
    # bool is a subclass of int in Python, so True/False would slip through isinstance(int)
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


@wishlist_bp.route('/wishlist', methods=['POST'])
def add_to_wishlist():
    """
    Adds an item to the logged-in user's wishlist.
    Expects JSON: {"listing_id": int}
    """
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify(UNAUTHORIZED[0]), UNAUTHORIZED[1]

    data = request.get_json(silent=True)
    if not data or 'listing_id' not in data:
        return jsonify({"error": "Missing required field: listing_id"}), 400

    listing_id = data['listing_id']
    if not _is_valid_id(listing_id):
        return jsonify({"error": "Invalid listing_id"}), 400

    success, message, error_code = wishlist_service.add_item_to_wishlist(user_id, listing_id)
    if success:
        return jsonify({"message": message}), 201

    status = {"not_found": 404, "duplicate": 400}.get(error_code, 500)
    return jsonify({"error": message}), status


@wishlist_bp.route('/wishlist', methods=['GET'])
def get_wishlist():
    """
    Retrieves the logged-in user's wishlist. Deleted listings are left out;
    sold-out / inactive ones are included with listing.available = false.
    """
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify(UNAUTHORIZED[0]), UNAUTHORIZED[1]

    success, result = wishlist_service.get_user_wishlist(user_id)
    if success:
        return jsonify({"wishlist": result}), 200
    return jsonify({"error": result}), 500


@wishlist_bp.route('/wishlist/<int:listing_id>', methods=['DELETE'])
def remove_from_wishlist(listing_id):
    """
    Removes an item from the logged-in user's wishlist.
    Works even if the listing was deleted, so old entries can always be cleared.
    """
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify(UNAUTHORIZED[0]), UNAUTHORIZED[1]

    success, result = wishlist_service.remove_item_from_wishlist(user_id, listing_id)
    if success:
        return jsonify({"message": result}), 200
    status = 404 if result == "Item not found in wishlist" else 500
    return jsonify({"error": result}), status


@wishlist_bp.route('/wishlist/<int:listing_id>/check', methods=['GET'])
def check_wishlist_status(listing_id):
    """
    Checks if a listing is in the logged-in user's wishlist.
    """
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify(UNAUTHORIZED[0]), UNAUTHORIZED[1]

    success, result = wishlist_service.check_item_in_wishlist(user_id, listing_id)
    if success:
        return jsonify({"in_wishlist": result}), 200
    return jsonify({"error": result}), 500


@wishlist_bp.route('/wishlist/items/<int:wishlist_id>', methods=['GET'])
def get_wishlist_item_details(wishlist_id):
    """
    Retrieves details of a specific wishlist item owned by the logged-in user.
    """
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify(UNAUTHORIZED[0]), UNAUTHORIZED[1]

    success, result = wishlist_service.get_wishlist_item_details(wishlist_id)
    if not success:
        status = 404 if result == "Wishlist item not found" else 500
        return jsonify({"error": result}), status

    # Don't reveal other users' wishlist entries
    if result['user_id'] != user_id:
        return jsonify({"error": "Access denied"}), 403
    return jsonify({"wishlist_item": result}), 200
