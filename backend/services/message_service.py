# The Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Created 10/20/26 for the buyer-seller messaging feature

"""
services/message_service.py

Purpose:
Business rules for buyer-seller messaging. Controllers call these methods,
and these methods call models/message_model.py for database work.

Rules enforced here:
- Only the buyer and the storefront owner of a conversation can read or post in it
- Sellers cannot start a conversation with their own storefront
- A listing attached to a conversation must belong to that storefront
- Messages are trimmed, cannot be empty, and are capped at MAX_MESSAGE_LENGTH
- Each user can send at most RATE_LIMIT_PER_MINUTE messages per minute

Every method returns (success, result) like the other services. On failure,
result is a dict with "error" and an HTTP "status" for the controller to use.
"""

from models import message_model

MAX_MESSAGE_LENGTH = 2000
RATE_LIMIT_PER_MINUTE = 20


def _fail(message, status):
    return False, {"error": message, "status": status}


class MessageService:

    def start_conversation(self, user_id, storefront_id, listing_id=None):
        """
        Finds or creates the user's thread with a storefront (optionally about one listing).
        """
        owner_id = message_model.get_storefront_owner(storefront_id)
        if owner_id is None:
            return _fail("Storefront not found", 404)

        if owner_id == user_id:
            return _fail("You can't message your own storefront", 400)

        if listing_id is not None and not message_model.listing_belongs_to_storefront(listing_id, storefront_id):
            return _fail("Listing not found in this storefront", 404)

        conversation_id = message_model.get_or_create_conversation(user_id, storefront_id, listing_id)
        return True, {"conversation_id": conversation_id}

    def _get_conversation_for_user(self, conversation_id, user_id):
        """
        Returns (conversation, None) if the user is a participant, otherwise (None, failure).
        Non-participants get a 404 so they can't tell which conversation ids exist.
        """
        conversation = message_model.get_conversation(conversation_id)
        if conversation is None or user_id not in (conversation["buyer_id"], conversation["seller_id"]):
            return None, _fail("Conversation not found", 404)
        return conversation, None

    def list_conversations(self, user_id):
        """
        Returns the user's inbox, each entry labeled from the user's point of view.
        """
        conversations = message_model.get_user_conversations(user_id)
        for conversation in conversations:
            _add_viewer_fields(conversation, user_id)
        return True, conversations

    def get_conversation_details(self, conversation_id, user_id):
        conversation, failure = self._get_conversation_for_user(conversation_id, user_id)
        if failure:
            return failure
        _add_viewer_fields(conversation, user_id)
        return True, conversation

    def get_messages(self, conversation_id, user_id, after_id=0):
        """
        Returns new messages since after_id and marks the other person's messages as read.
        """
        conversation, failure = self._get_conversation_for_user(conversation_id, user_id)
        if failure:
            return failure

        messages = message_model.get_messages(conversation_id, after_id)
        message_model.mark_conversation_read(conversation_id, user_id)
        return True, messages

    def send_message(self, conversation_id, user_id, body):
        conversation, failure = self._get_conversation_for_user(conversation_id, user_id)
        if failure:
            return failure

        body = (body or "").strip()
        if not body:
            return _fail("Message can't be empty", 400)
        if len(body) > MAX_MESSAGE_LENGTH:
            return _fail(f"Message is too long (max {MAX_MESSAGE_LENGTH} characters)", 400)

        if message_model.count_recent_messages_by_sender(user_id) >= RATE_LIMIT_PER_MINUTE:
            return _fail("You're sending messages too quickly. Please wait a moment.", 429)

        message = message_model.add_message(conversation_id, user_id, body)
        return True, message

    def get_unread_count(self, user_id):
        return True, message_model.count_unread_for_user(user_id)


def _add_viewer_fields(conversation, user_id):
    """
    Adds fields that depend on who is looking:
    - role: "buyer" or "seller"
    - other_name: the storefront name for buyers, the buyer's username for sellers
    """
    is_seller = conversation["seller_id"] == user_id
    conversation["role"] = "seller" if is_seller else "buyer"
    conversation["other_name"] = conversation["buyer_username"] if is_seller else conversation["brand_name"]
