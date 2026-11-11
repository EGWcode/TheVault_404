# backend/db.py
# Updated by Anthony Jackson - Iteration 4 (11/11/26)
# The models import get_connection from here. It now uses the same settings as
# backend/config/db.py (RDS with SSL, local Postgres, Docker, or DATABASE_URL),
# so there is only one place to change connection settings.
# Unlike config.db.get_connection, this one raises an error instead of returning None.

from config.db import connect as get_connection  # noqa: F401
