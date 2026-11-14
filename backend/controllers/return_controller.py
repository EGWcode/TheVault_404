"""
return_controller.py

Routes for the returns page and return request submission.
"""

from flask import Blueprint, jsonify, render_template, request, redirect, url_for, session

from services.return_service import create_return_service

returns_bp = Blueprint("returns_bp", __name__)


def get_current_user():

    # Require a valid authenticated Flask session.
    if not session.get("user"):
        return None

    user_id = session.get("user_id")

    if user_id is None:
        return None

    try:
        user_id = int(user_id)

        if user_id <= 0:
            return None

        return {
            "id": user_id,
            "role": session.get("role", "user")
        }

    except (ValueError, TypeError):
        return None


@returns_bp.get("/returns")
def returns_page():
    if "user" not in session:
        return redirect(url_for("auth.login"))
    return render_template("returns.html")


@returns_bp.post("/returns")
def submit_return():
    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Unauthorized."}), 401

    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    damage_image_url = None

    if "damage_image" in request.files and request.files["damage_image"].filename:
        from utils.s3 import upload_image_to_s3

        file = request.files["damage_image"]
        if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return jsonify({"error": "Damage image must be PNG, JPG, JPEG, GIF, or WebP."}), 400
 #Tykeara H: checked the file's real type by its first bytes.
        header = file.stream.read(12)
        file.stream.seek(0)
        is_image = (
            header.startswith(b"\x89PNG\r\n\x1a\n")
            or header.startswith(b"\xff\xd8\xff")
            or header.startswith(b"GIF8")
            or (header.startswith(b"RIFF") and header[8:12] == b"WEBP")
        )
        if not is_image:
            return jsonify({"error": "Damage image must be PNG, JPG, JPEG, GIF, or WebP."}), 400

        

        damage_image_url = upload_image_to_s3(file, folder="returns/damage")
        if not damage_image_url:
            return jsonify({"error": "Damage image upload failed."}), 500

    try:
        created = create_return_service(current_user, data, damage_image_url=damage_image_url)
        return jsonify(created), 201
    except ValueError as e:
        message = str(e)
        if "unauthorized" in message.lower():
            return jsonify({"error": message}), 401
        return jsonify({"error": message}), 400
    except Exception as e:
        print(e)
        return jsonify({"error": "Something went wrong. Please try again."}), 500
