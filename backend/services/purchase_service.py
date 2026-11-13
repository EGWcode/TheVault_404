# The Pirate Cove Campus Marketplace
# CSC 405 Sp 26'
# Created for Purchase History feature by Elali McNair 3/3/26
# Finished by Nicco Hill 11/12/2026: purchase edge cases (sold out, deleted, stock).

"""
services/purchase_service.py

Purpose:
This service layer handles business logic for purchase operations.
It coordinates between controllers and models, adding validation and processing.
"""

from models.purchase_model import (
    PurchaseError,
    create_purchase,
    get_purchases_by_user_id,
    get_purchase_by_id
)


class PurchaseService:
    def record_purchase(self, user_id, listing_id, quantity, size=None):
        """
        Records a new purchase for a user.
        Returns (success, purchase_or_message, error_code).

        All availability checks (deleted, inactive, sold out, stock, size,
        buying your own listing) happen inside create_purchase while the
        listing row is locked, so they can't go stale between check and write.
        - Nicco Hill 11/12/2026
        """
        try:
            purchase = create_purchase(user_id, listing_id, quantity, size)
            return True, purchase, None
        except PurchaseError as e:
            return False, str(e), e.code
        except Exception as e:
            print(f"[purchase] failed for user {user_id}, listing {listing_id}: {e}")
            return False, "Failed to record purchase", "error"

    def get_user_purchase_history(self, user_id):
        """
        Retrieves the complete purchase history for a user.
        Returns list of purchases with listing and storefront details.
        """
        try:
            purchases = get_purchases_by_user_id(user_id)
            return True, purchases
        except Exception as e:
            print(f"[purchase] {e}")
            return False, "Failed to retrieve purchase history"

    def get_purchase_details(self, purchase_id):
        """
        Retrieves detailed information about a specific purchase.
        Returns purchase details or error.
        """
        try:
            purchase = get_purchase_by_id(purchase_id)
            if purchase:
                return True, purchase
            else:
                return False, "Purchase not found"
        except Exception as e:
            print(f"[purchase] {e}")
            return False, "Failed to retrieve purchase details"