# The Pirate Cove Campus Marketplace
# Created by Anthony Jackson 10/21/26 for the optional user profile

"""
controllers/profile_controller.py

Purpose:
HTTP routes for the optional profile info a user can add from their Account
page. The logged in user always comes from the Flask session
(session['user_id']), never from the request.

API:
- GET   /api/profile   the user's profile
- PATCH /api/profile   save any of: first_name, last_name, phone, class_year, hometown
"""

from flask import Blueprint, request, jsonify, session
from services import profile_service

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/api/profile', methods=['GET'])
def get_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Please log in to see your profile."}), 401

    success, result = profile_service.get_profile(user_id)
    if success:
        return jsonify(result), 200
    return jsonify({"error": result["error"]}), result["status"]


@profile_bp.route('/api/profile', methods=['PATCH'])
def update_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Please log in to save your profile."}), 401

    data = request.get_json(silent=True)
    success, result = profile_service.update_profile(user_id, data)
    if success:
        return jsonify(result), 200
    return jsonify({"error": result["error"], "field": result["field"]}), result["status"]
