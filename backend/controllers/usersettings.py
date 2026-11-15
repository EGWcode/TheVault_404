






#Edited by Jaylen Belle
#This is the http routes for the setting tab on the account page





from flask import Blueprint, request, jsonify, session
from services import usersettings as settings_service

usersettings_bp = Blueprint('usersettings', __name__)


@usersettings_bp.route('/api/account/settings', methods=['GET'])
#Makes sure the user id always comes from the login session
def get_settings():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "log in to see you account settings"}), 401

    success, result = settings_service.get_settings(user_id)
    if success:
        return jsonify(result), 200
    return jsonify({"error": result["error"]}), result["status"]



@usersettings_bp.route('/api/account/password', methods=['POST'])
def change_password():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Log in to change your password"}), 401

    #returns none instead of crashing if body is invalid json
    data = request.get_json(silent=True)
    success, result = settings_service.change_password(user_id, data)
    if success:
        return jsonify(result), 200
    #Tells the page which field failed and to outline red.
    return jsonify({"error": result["error"], "field": result["field"]}), result["status"]



