# Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Created 10/20/26 for the buyer-seller messaging feature

"""
models/message_model.py

Purpose:
This file handles all direct database operations related to messaging.

This file includes DB operations for:
- conversations (one thread per buyer + storefront + optional listing)
- messages (the messages inside a conversation)

The seller in a conversation is always the owner of the storefront.
Permission checks (who may read or post) live in services/message_service.py.
"""

from db import get_connection


def get_storefront_owner(storefront_id):
    """
    Returns the owner's user id for an active storefront, or None.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT owner_id FROM storefronts WHERE id = %s AND is_active = TRUE;",
            (storefront_id,)
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()
        conn.close()


def listing_belongs_to_storefront(listing_id, storefront_id):
    """
    Returns True if the listing exists, is not deleted, and belongs to the storefront.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1 FROM listings
            WHERE id = %s AND storefront_id = %s AND status <> 'DELETED';
            """,
            (listing_id, storefront_id)
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def get_or_create_conversation(buyer_id, storefront_id, listing_id=None):
    """
    Returns the id of the buyer's thread with this storefront (and listing),
    creating it first if it does not exist yet.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO conversations (buyer_id, storefront_id, listing_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (buyer_id, storefront_id, COALESCE(listing_id, 0)) DO NOTHING
            RETURNING id;
            """,
            (buyer_id, storefront_id, listing_id)
        )
        row = cur.fetchone()
        if row is None:
            cur.execute(
                """
                SELECT id FROM conversations
                WHERE buyer_id = %s AND storefront_id = %s
                  AND COALESCE(listing_id, 0) = COALESCE(%s, 0);
                """,
                (buyer_id, storefront_id, listing_id)
            )
            row = cur.fetchone()
        conn.commit()
        return row[0]
    finally:
        cur.close()
        conn.close()


def get_conversation(conversation_id):
    """
    Returns a conversation with its participants as a dictionary, or None.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT c.id, c.buyer_id, s.owner_id, c.storefront_id, c.listing_id,
                   s.brand_name, s.logo_url, u.username, l.title
            FROM conversations c
            JOIN storefronts s ON s.id = c.storefront_id
            JOIN users u ON u.id = c.buyer_id
            LEFT JOIN listings l ON l.id = c.listing_id
            WHERE c.id = %s;
            """,
            (conversation_id,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "buyer_id": row[1],
            "seller_id": row[2],
            "storefront_id": row[3],
            "listing_id": row[4],
            "brand_name": row[5],
            "logo_url": row[6],
            "buyer_username": row[7],
            "listing_title": row[8],
        }
    finally:
        cur.close()
        conn.close()


def get_user_conversations(user_id):
    """
    Returns every conversation the user is in (as buyer or as storefront owner),
    newest activity first, with the last message and the user's unread count.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT c.id, c.buyer_id, s.owner_id, c.storefront_id, c.listing_id,
                   s.brand_name, s.logo_url, u.username, l.title, c.last_message_at,
                   last_msg.body, last_msg.sender_id,
                   (SELECT COUNT(*) FROM messages m
                    WHERE m.conversation_id = c.id
                      AND m.sender_id <> %s
                      AND m.read_at IS NULL) AS unread
            FROM conversations c
            JOIN storefronts s ON s.id = c.storefront_id
            JOIN users u ON u.id = c.buyer_id
            LEFT JOIN listings l ON l.id = c.listing_id
            LEFT JOIN LATERAL (
                SELECT body, sender_id FROM messages m
                WHERE m.conversation_id = c.id
                ORDER BY m.id DESC LIMIT 1
            ) last_msg ON TRUE
            WHERE (c.buyer_id = %s OR s.owner_id = %s)
              AND last_msg.body IS NOT NULL
            ORDER BY c.last_message_at DESC;
            """,
            (user_id, user_id, user_id)
        )
        conversations = []
        for row in cur.fetchall():
            conversations.append({
                "id": row[0],
                "buyer_id": row[1],
                "seller_id": row[2],
                "storefront_id": row[3],
                "listing_id": row[4],
                "brand_name": row[5],
                "logo_url": row[6],
                "buyer_username": row[7],
                "listing_title": row[8],
                "last_message_at": row[9].isoformat() if row[9] else None,
                "last_message": row[10],
                "last_sender_id": row[11],
                "unread": row[12],
            })
        return conversations
    finally:
        cur.close()
        conn.close()


def get_messages(conversation_id, after_id=0, limit=200):
    """
    Returns messages in a conversation with an id greater than after_id, oldest first.
    Polling passes the last id it has, so only new messages come back.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, sender_id, body, created_at, read_at
            FROM messages
            WHERE conversation_id = %s AND id > %s
            ORDER BY id ASC
            LIMIT %s;
            """,
            (conversation_id, after_id, limit)
        )
        return [
            {
                "id": row[0],
                "sender_id": row[1],
                "body": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "read_at": row[4].isoformat() if row[4] else None,
            }
            for row in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def add_message(conversation_id, sender_id, body):
    """
    Inserts a message, bumps the conversation's last_message_at,
    and returns the new message as a dictionary.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO messages (conversation_id, sender_id, body)
            VALUES (%s, %s, %s)
            RETURNING id, sender_id, body, created_at, read_at;
            """,
            (conversation_id, sender_id, body)
        )
        row = cur.fetchone()
        cur.execute(
            "UPDATE conversations SET last_message_at = %s WHERE id = %s;",
            (row[3], conversation_id)
        )
        conn.commit()
        return {
            "id": row[0],
            "sender_id": row[1],
            "body": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
            "read_at": None,
        }
    finally:
        cur.close()
        conn.close()


def mark_conversation_read(conversation_id, reader_id):
    """
    Marks every message the other participant sent in this conversation as read.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE messages SET read_at = CURRENT_TIMESTAMP
            WHERE conversation_id = %s AND sender_id <> %s AND read_at IS NULL;
            """,
            (conversation_id, reader_id)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def count_unread_for_user(user_id):
    """
    Returns how many unread messages are waiting for the user across all conversations.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            JOIN storefronts s ON s.id = c.storefront_id
            WHERE (c.buyer_id = %s OR s.owner_id = %s)
              AND m.sender_id <> %s
              AND m.read_at IS NULL;
            """,
            (user_id, user_id, user_id)
        )
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


def count_recent_messages_by_sender(sender_id, seconds=60):
    """
    Returns how many messages the user sent in the last `seconds` seconds (for rate limiting).
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) FROM messages
            WHERE sender_id = %s
              AND created_at > CURRENT_TIMESTAMP - make_interval(secs => %s);
            """,
            (sender_id, seconds)
        )
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()
