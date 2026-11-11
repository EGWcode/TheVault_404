"""
Admin service helpers for dashboard data and moderation actions.

Errors (Ethan Williams 11/9/26) - the controller turns these into HTTP codes:
- ValueError      -> 400 (bad input)
- PermissionError -> 403 (action not allowed, e.g. deleting an admin account)
- LookupError     -> 404 (the row doesn't exist)
"""

from models.admin_model import (
    get_all_users,
    get_user_role,
    delete_user,
    get_all_listings,
    delete_listing,
    get_admin_storefronts,
    delete_storefront,
    get_admin_returns,
    update_admin_return_status,
)

RETURN_STATUSES = ("pending", "reviewed", "resolved")


def fetch_users():
    return get_all_users()


def remove_user(user_id, acting_user_id=None):
    if not user_id:
        raise ValueError("User ID required")

    if acting_user_id is not None and user_id == acting_user_id:
        raise PermissionError("You can't delete your own admin account")

    role = get_user_role(user_id)
    if role is None:
        raise LookupError("User not found")
    if role.lower() == "admin":
        # Admin accounts are managed with backend/create_admin.py, not from the dashboard
        raise PermissionError("Admin accounts can't be deleted from the dashboard")

    if not delete_user(user_id):
        raise LookupError("User not found")
    return {"message": "User deleted successfully"}


def fetch_listings():
    return get_all_listings()


def remove_listing(listing_id):
    if not listing_id:
        raise ValueError("Listing ID required")
    if delete_listing(listing_id) is None:
        raise LookupError("Listing not found")
    return {"message": "Listing soft-deleted successfully"}


def fetch_storefronts():
    return get_admin_storefronts()


def remove_storefront(store_id):
    """
    Deletes a storefront (its listings go with it through ON DELETE CASCADE).
    """
    if not store_id:
        raise ValueError("Storefront ID required")
    if not delete_storefront(store_id):
        raise LookupError("Storefront not found")
    return {"message": "Storefront removed successfully"}


def fetch_returns():
    return get_admin_returns()


def update_return_status_service(return_id, status):
    if not return_id:
        raise ValueError("Return ID required")
    status = (status or "").strip().lower()
    if status not in RETURN_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(RETURN_STATUSES)}")
    updated = update_admin_return_status(return_id, status)
    if updated is None:
        raise LookupError("Return not found")
    return updated
