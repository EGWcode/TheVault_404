# controllers/admin_controller.py
# File created by David Jackson

"""
Admin Controller

The controller layer defines API endpoints used by the frontend.

Responsibilities:
• Receive HTTP requests
• Call service functions
• Return JSON responses

Example Request Flow:
Frontend → Controller → Service → Model → Database
"""

from flask import Blueprint, jsonify, request, session, abort, render_template  # Updated 4/21/2026

# Import service functions
from services.admin_service import (
    fetch_users,
    remove_user,
    fetch_listings,
    remove_listing,
    fetch_storefronts,
    remove_storefront,
    fetch_returns,
    update_return_status_service
)

def _run_admin_action(action, *args, **kwargs):
    """
    Runs a service call and turns its errors into JSON responses.
    Added by Ethan Williams 11/9/26 (see the error list in services/admin_service.py).
    """
    try:
        return jsonify(action(*args, **kwargs))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        print(f"[admin] {action.__name__} error: {e}")
        return jsonify({"error": "Something went wrong. Please try again."}), 500


# Create Flask Blueprint for admin routes
# All routes will start with /admin
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def require_admin():
    """
    Authorization helper function.

    This function ensures that the current user
    is logged in and has administrator privileges.

    Behavior:
    • If the user is not logged in → return HTTP 401
    • If the user is logged in but NOT an admin → return HTTP 403

    This prevents normal users from accessing admin-only routes.
    """

    # Check if the user is logged in - updated by David Jackson 3/23/2026
    if "user" not in session:
        abort(401)  # Unauthorized (user not logged in)

    # Check if the user has the admin role
    if session.get("role") != "admin":
        abort(403)  # Forbidden (not an admin)


@admin_bp.route("", methods=["GET"])
def admin_dashboard():
    require_admin()
    return render_template("admin_dashboard.html")


@admin_bp.route("/dashboard", methods=["GET"])
def admin_dashboard_page():
    """
    GET /admin/dashboard

    Renders the admin dashboard page.
    """

    # Ensure only admins can access the dashboard
    require_admin()

    return render_template("admin_dashboard.html")


@admin_bp.route("/users", methods=["GET"])
def get_users():
    """
    GET /admin/users

    Retrieves all users from the system.

    Returns:
        JSON list of users
    """

    # Ensure only admins can access this endpoint
    require_admin()

    return _run_admin_action(fetch_users)


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user_route(user_id):
    """
    DELETE /admin/users/<user_id>

    Removes a specific user from the system.

    URL Parameter:
        user_id: ID of the user to delete
    """

    # Ensure only admins can perform user deletion
    require_admin()

    return _run_admin_action(remove_user, user_id, acting_user_id=session.get("user_id"))


@admin_bp.route("/listings", methods=["GET"])
def get_listings():
    """
    GET /admin/listings

    Returns all listings currently in the marketplace.
    """

    # Ensure only admins can view marketplace listings through admin tools
    require_admin()

    return _run_admin_action(fetch_listings)


@admin_bp.route("/listings/<int:listing_id>", methods=["DELETE"])
def delete_listing_route(listing_id):
    """
    DELETE /admin/listings/<listing_id>

    Removes a listing from the marketplace.

    Used when:
    • Listings violate rules
    • Listings are fraudulent
    """

    # Ensure only admins can delete listings
    require_admin()

    return _run_admin_action(remove_listing, listing_id)


@admin_bp.route("/storefronts", methods=["GET"])
def get_storefronts():
    """
    GET /admin/storefronts

    Retrieves all storefronts created by users.

    This helps admins monitor marketplace activity.
    """

    # Ensure only admins can access storefront monitoring tools
    require_admin()

    return _run_admin_action(fetch_storefronts)


@admin_bp.route("/storefronts/<int:store_id>", methods=["DELETE"])
def delete_storefront_route(store_id):
    require_admin()

    return _run_admin_action(remove_storefront, store_id)


@admin_bp.route("/returns", methods=["GET"])
def get_returns():
    require_admin()
    return _run_admin_action(fetch_returns)


@admin_bp.route("/returns/<int:return_id>", methods=["PATCH"])
def update_return_route(return_id):
    require_admin()

    data = request.get_json(silent=True) or {}
    return _run_admin_action(update_return_status_service, return_id, data.get("status"))