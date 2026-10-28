# menu_controller.py
# Added by Anthony Jackson (back end)
# Makes the dropdown menu buttons work: New Drops, Hot!, All Categories, Top Rated, About.
# (The Sitemap page is Jaylen Belle's, it lives in app.py)
# menu_api_bp gives the data (JSON). menu_pages_bp opens the pages.

from flask import Blueprint, jsonify, render_template
from models.menu_model import get_new_drops, get_hot_listings, get_categories_with_storefronts

menu_api_bp = Blueprint("menu_api_bp", __name__, url_prefix="/api/menu")
menu_pages_bp = Blueprint("menu_pages_bp", __name__)


# ---------- Data (JSON) ----------

@menu_api_bp.get("/new-drops")
def new_drops_route():
    try:
        return jsonify(get_new_drops()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@menu_api_bp.get("/hot")
def hot_route():
    try:
        return jsonify(get_hot_listings()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@menu_api_bp.get("/categories")
def categories_route():
    try:
        return jsonify(get_categories_with_storefronts()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Pages ----------

@menu_pages_bp.route("/new-drops")
def new_drops_page():
    return render_template("menu_page.html", page="new-drops")


@menu_pages_bp.route("/hot")
def hot_page():
    return render_template("menu_page.html", page="hot")


@menu_pages_bp.route("/categories")
def categories_page():
    return render_template("menu_page.html", page="categories")


@menu_pages_bp.route("/about")
def about_page():
    return render_template("menu_page.html", page="about")


@menu_pages_bp.route("/top-rated")
def top_rated_page():
    return render_template("menu_page.html", page="top-rated")
