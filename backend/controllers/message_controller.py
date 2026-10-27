# Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Created 10/20/26 for the buyer-seller messaging feature

"""
controllers/message_controller.py

Purpose:
Handles HTTP requests for buyer-seller messaging: the /messages page and the
JSON API it polls. The logged-in user always comes from the Flask session
(session['user_id'], set at login), never from the request.

API:
- POST /api/conversations                        start or reopen a thread  {storefront_id, listing_id?}
- GET  /api/conversations                        the user's inbox
- GET  /api/conversations/<id>                   one thread's details
- GET  /api/conversations/<id>/messages?after=N  messages newer than id N (marks them read)
- POST /api/conversations/<id>/messages          send a message  {body}
- GET  /api/messages/unread-count                unread total for the top-bar badge
"""

from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from services.message_service import MessageService

messages_bp = Blueprint('messages', __name__)
message_service = MessageService()


def _current_user_id():
    return session.get('user_id')


def _respond(success, result, ok_status=200, key=None):
    """
    Turns a service (success, result) pair into a JSON response.
    """
    if success:
        return jsonify({key: result} if key else result), ok_status
    return jsonify({"error": result["error"]}), result["status"]


def _parse_optional_int(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError
    return int(value)


# ________________________________________________________
# PAGE
# ________________________________________________________

@messages_bp.route('/messages')
def messages_page():
    if not _current_user_id():
        return redirect(url_for('auth.login'))
    return render_template('messages.html')


# ________________________________________________________
# API
# ________________________________________________________

@messages_bp.route('/api/conversations', methods=['POST'])
def start_conversation():
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "Please log in to send messages"}), 401

    data = request.get_json(silent=True) or {}
    try:
        storefront_id = _parse_optional_int(data.get('storefront_id'))
        listing_id = _parse_optional_int(data.get('listing_id'))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid storefront_id or listing_id"}), 400

    if storefront_id is None:
        return jsonify({"error": "Missing required field: storefront_id"}), 400

    try:
        success, result = message_service.start_conversation(user_id, storefront_id, listing_id)
        return _respond(success, result, ok_status=201)
    except Exception as e:
        print(f"[messages] start_conversation error: {e}")
        return jsonify({"error": "Could not start the conversation"}), 500


@messages_bp.route('/api/conversations', methods=['GET'])
def list_conversations():
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    try:
        success, result = message_service.list_conversations(user_id)
        return _respond(success, result, key="conversations")
    except Exception as e:
        print(f"[messages] list_conversations error: {e}")
        return jsonify({"error": "Could not load conversations"}), 500


@messages_bp.route('/api/conversations/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    try:
        success, result = message_service.get_conversation_details(conversation_id, user_id)
        return _respond(success, result, key="conversation")
    except Exception as e:
        print(f"[messages] get_conversation error: {e}")
        return jsonify({"error": "Could not load the conversation"}), 500


@messages_bp.route('/api/conversations/<int:conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    after_id = request.args.get('after', default=0, type=int)

    try:
        success, result = message_service.get_messages(conversation_id, user_id, after_id)
        return _respond(success, result, key="messages")
    except Exception as e:
        print(f"[messages] get_messages error: {e}")
        return jsonify({"error": "Could not load messages"}), 500


@messages_bp.route('/api/conversations/<int:conversation_id>/messages', methods=['POST'])
def send_message(conversation_id):
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    body = data.get('body')
    if not isinstance(body, str):
        return jsonify({"error": "Missing required field: body"}), 400

    try:
        success, result = message_service.send_message(conversation_id, user_id, body)
        return _respond(success, result, ok_status=201, key="message")
    except Exception as e:
        print(f"[messages] send_message error: {e}")
        return jsonify({"error": "Could not send the message"}), 500


@messages_bp.route('/api/messages/unread-count', methods=['GET'])
def unread_count():
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"unread": 0}), 200

    try:
        success, result = message_service.get_unread_count(user_id)
        return _respond(success, result, key="unread")
    except Exception as e:
        print(f"[messages] unread_count error: {e}")
        return jsonify({"unread": 0}), 200
