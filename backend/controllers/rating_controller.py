# The Vault Campus Marketplace
# Created by Anthony Jackson 10/21/26 for the storefront rating feature

"""
controllers/rating_controller.py

Purpose:
HTTP routes for storefront ratings. The logged in user always comes from the
Flask session (session['user_id']), never from the request.

API:
- POST /api/storefronts/<id>/ratings   rate a storefront  {stars: 1-5}
- GET  /api/storefronts/<id>/ratings   overall rating for one storefront
- GET  /api/ratings/summary            overall rating for every rated storefront
- GET  /api/ratings/top                top rated storefronts, best first
"""

from flask import Blueprint, request, jsonify, session
from services import rating_service

ratings_bp = Blueprint('ratings', __name__)


@ratings_bp.route('/api/storefronts/<int:storefront_id>/ratings', methods=['POST'])
def rate_storefront(storefront_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Please log in to rate a storefront."}), 401

    data = request.get_json(silent=True) or {}
    success, result = rating_service.submit_rating(user_id, storefront_id, data.get('stars'))
    if success:
        return jsonify(result), 201
    return jsonify({"error": result["error"]}), result["status"]


@ratings_bp.route('/api/storefronts/<int:storefront_id>/ratings', methods=['GET'])
def get_storefront_rating(storefront_id):
    try:
        return jsonify(rating_service.get_storefront_summary(storefront_id)), 200
    except Exception:
        return jsonify({"error": "Could not load the rating right now."}), 500


@ratings_bp.route('/api/ratings/summary', methods=['GET'])
def get_all_ratings():
    try:
        return jsonify(rating_service.get_all_summaries()), 200
    except Exception:
        return jsonify({"error": "Could not load ratings right now."}), 500


@ratings_bp.route('/api/ratings/top', methods=['GET'])
def get_top_rated():
    try:
        return jsonify(rating_service.get_top_rated()), 200
    except Exception:
        return jsonify({"error": "Could not load ratings right now."}), 500
