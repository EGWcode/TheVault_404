# The Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Created for Wishlist feature by Elali McNair 3/3/26
# Finished by Nicco Hill 11/12/2026: edge cases for deleted / sold-out listings and duplicates.

"""
services/wishlist_service.py

Purpose:
This service layer handles business logic for wishlist operations.
It coordinates between controllers and models, adding validation and processing.
"""

from models.wishlist_model import (
    add_to_wishlist,
    get_wishlist_by_user_id,
    remove_from_wishlist,
    is_in_wishlist,
    get_wishlist_item_by_id
)
from models.listing_model import get_listing_by_id


class WishlistService:
    def add_item_to_wishlist(self, user_id, listing_id):
        """
        Adds a listing to user's wishlist.
        Returns (success, message, error_code). error_code is one of
        None, "not_found", "duplicate", "error" so the controller can pick
        the right HTTP status.

        Edge cases (Nicco Hill 11/12/2026):
        - Deleted listings are treated as not found.
        - Sold-out / inactive listings CAN be wishlisted, so buyers can watch
          for a restock. GET /api/wishlist marks them "available": false.
        - Adding the same listing twice returns "Item already in wishlist".
        """
        listing = get_listing_by_id(listing_id)
        if not listing or listing["status"] == "DELETED":
            return False, "Listing not found", "not_found"

        try:
            result = add_to_wishlist(user_id, listing_id)
        except Exception as e:
            print(f"[wishlist] add failed for user {user_id}, listing {listing_id}: {e}")
            return False, "Failed to add item to wishlist", "error"

        if result:
            return True, "Item added to wishlist", None
        return False, "Item already in wishlist", "duplicate"

    def get_user_wishlist(self, user_id):
        """
        Retrieves the user's wishlist with listing details.
        Returns list of wishlist items.
        """
        try:
            wishlist = get_wishlist_by_user_id(user_id)
            return True, wishlist
        except Exception as e:
            print(f"[wishlist] {e}")
            return False, "Failed to retrieve wishlist"

    def remove_item_from_wishlist(self, user_id, listing_id):
        """
        Removes a listing from user's wishlist.
        Returns success status and message.
        """
        try:
            removed = remove_from_wishlist(user_id, listing_id)
            if removed:
                return True, "Item removed from wishlist"
            else:
                return False, "Item not found in wishlist"
        except Exception as e:
            print(f"[wishlist] {e}")
            return False, "Failed to remove item from wishlist"

    def check_item_in_wishlist(self, user_id, listing_id):
        """
        Checks if a specific listing is in user's wishlist.
        Returns boolean status.
        """
        try:
            in_wishlist = is_in_wishlist(user_id, listing_id)
            return True, in_wishlist
        except Exception as e:
            print(f"[wishlist] {e}")
            return False, "Failed to check wishlist status"

    def get_wishlist_item_details(self, wishlist_id):
        """
        Retrieves detailed information about a specific wishlist item.
        Returns wishlist item details or error.
        """
        try:
            item = get_wishlist_item_by_id(wishlist_id)
            if item:
                return True, item
            else:
                return False, "Wishlist item not found"
        except Exception as e:
            print(f"[wishlist] {e}")
            return False, "Failed to retrieve wishlist item details"