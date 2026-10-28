# The Vault Campus Marketplace
# Created by Anthony Jackson 10/21/26 for the storefront rating feature

"""
services/rating_service.py

Purpose:
Rules for storefront ratings. Controllers call these functions, and these
functions call models/rating_model.py for the database work.

Rules:
- A rating is a whole number from 1 to 5
- It's for a whole storefront (not a single item)
- A user can rate the same storefront as many times as they want
- You can't rate your own storefront
- The storefront has to exist and be active

Every function returns (success, result) like the other services. On a failure,
result is a dict with "error" (a message that's fine to show the user) and an
HTTP "status" for the controller to use.
"""

from models import rating_model


def _fail(message, status):
    return False, {"error": message, "status": status}


def rating_label(average, count):
    """Turns an average into a short label so higher rated storefronts stand out."""
    if count == 0:
        return "No ratings yet"
    if average >= 4.5:
        return "Top rated"
    if average >= 4.0:
        return "Highly rated"
    if average >= 3.0:
        return "Good"
    if average >= 2.0:
        return "Mixed"
    return "Low rated"


def rating_text(average, count):
    """Text to show next to the stars, like '4.3 stars (12 ratings)'."""
    if count == 0:
        return "No ratings yet"
    noun = "rating" if count == 1 else "ratings"
    return f"{average:.1f} stars ({count} {noun})"


def build_summary(average, count):
    return {
        "average": average,
        "count": count,
        "label": rating_label(average, count),
        "text": rating_text(average, count),
    }


def _clean_stars(value):
    """Returns the stars as an int from 1 to 5, or None if it isn't valid."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int) and 1 <= value <= 5:
        return value
    return None


def submit_rating(user_id, storefront_id, stars):
    """Saves a rating and returns the storefront's new overall summary."""
    clean = _clean_stars(stars)
    if clean is None:
        return _fail("Pick a rating from 1 to 5 stars.", 400)

    info = rating_model.get_storefront_info(storefront_id)
    if info is None or not info[1]:
        return _fail("That storefront could not be found.", 404)
    if info[0] == user_id:
        return _fail("You can't rate your own storefront.", 403)

    rating_model.add_rating(storefront_id, user_id, clean)
    average, count = rating_model.get_summary(storefront_id)
    return True, build_summary(average, count)


def get_storefront_summary(storefront_id):
    average, count = rating_model.get_summary(storefront_id)
    return build_summary(average, count)


def get_all_summaries():
    """{storefront_id: summary} for every storefront that has at least one rating."""
    return {sid: build_summary(avg, count) for sid, (avg, count) in rating_model.get_all_summaries().items()}


def get_top_rated(limit=24):
    stores = []
    for store_id, brand_name, average, count in rating_model.get_top_rated(limit):
        item = {"storefront_id": store_id, "brand_name": brand_name}
        item.update(build_summary(average, count))
        stores.append(item)
    return stores
