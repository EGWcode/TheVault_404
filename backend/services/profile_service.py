# The Pirate Cove Campus Marketplace
# Created by Anthony Jackson 10/21/26 for the optional user profile

"""
services/profile_service.py

Purpose:
Rules for the optional profile info. Everything here is optional. A user can
add it from their Account page whenever they want, and clear any of it by
saving an empty box.

Rules:
- First and last name: up to 50 characters, letters, spaces, hyphens and apostrophes
- Phone: 10 digits (spaces, dashes and parentheses are fine, they get removed)
- Class year: Freshman, Sophomore, Junior, Senior or Graduate
- Hometown: up to 100 characters

Every function returns (success, result) like the other services. On a failure,
result is a dict with "error" (a message that's fine to show the user), the
"field" that has the problem, and an HTTP "status" for the controller to use.
"""

import re

from models import profile_model

CLASS_YEARS = ("Freshman", "Sophomore", "Junior", "Senior", "Graduate")


def _fail(message, field, status=400):
    return False, {"error": message, "field": field, "status": status}


class _Invalid(Exception):
    def __init__(self, message):
        self.message = message


def _clean_name(value, label):
    value = str(value).strip()
    if value == "":
        return None
    if len(value) > 50:
        raise _Invalid(f"{label} can be up to 50 characters.")
    if not all(ch.isalpha() or ch in " -'" for ch in value):
        raise _Invalid(f"{label} can only have letters, spaces, hyphens and apostrophes.")
    return value


def _clean_phone(value):
    digits = re.sub(r"[\s\-\(\)\.]", "", str(value))
    if digits == "":
        return None
    if digits.startswith("+1"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if not (digits.isdigit() and len(digits) == 10):
        raise _Invalid("Phone number must be 10 digits.")
    return digits


def _clean_class_year(value):
    value = str(value).strip()
    if value == "":
        return None
    for year in CLASS_YEARS:
        if value.lower() == year.lower():
            return year
    raise _Invalid("Pick Freshman, Sophomore, Junior, Senior or Graduate.")


def _clean_hometown(value):
    value = str(value).strip()
    if value == "":
        return None
    if len(value) > 100:
        raise _Invalid("Hometown can be up to 100 characters.")
    return value


_CLEANERS = {
    "first_name": lambda v: _clean_name(v, "First name"),
    "last_name": lambda v: _clean_name(v, "Last name"),
    "phone": _clean_phone,
    "class_year": _clean_class_year,
    "hometown": _clean_hometown,
}


def get_profile(user_id):
    profile = profile_model.get_profile(user_id)
    if profile is None:
        return _fail("We couldn't find your account.", None, 404)
    return True, profile


def update_profile(user_id, data):
    """Checks the values the user sent, saves them, and returns the updated profile."""
    if not isinstance(data, dict):
        return _fail("Nothing to save.", None)

    cleaned = {}
    for field, cleaner in _CLEANERS.items():
        if field not in data:
            continue
        value = data[field]
        if value is None:
            value = ""
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            return _fail("That doesn't look right.", field)
        try:
            cleaned[field] = cleaner(value)
        except _Invalid as problem:
            return _fail(problem.message, field)

    if not cleaned:
        return _fail("Nothing to save.", None)

    profile_model.update_profile(user_id, cleaned)
    return get_profile(user_id)
