# backend/tests/test_admin.py
# Created by David Jackson


import os
import sys
import time
import uuid

import pytest

# Add project root to Python path so app.py can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Add backend folder to Python path so db.py can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from db import get_connection


@pytest.fixture
def app():
    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def set_admin_session(client):
    with client.session_transaction() as session:
        session["user"] = "admin"
        session["role"] = "admin"
        session["last_activity"] = time.time()  # pass the idle-timeout check


def set_user_session(client):
    with client.session_transaction() as session:
        session["user"] = "student"
        session["role"] = "user"
        session["last_activity"] = time.time()  # pass the idle-timeout check


# Tests that logged-out users cannot access the admin dashboard
def test_admin_dashboard_blocks_logged_out_users(client):
    response = client.get("/admin")
    assert response.status_code == 401


# Tests that non-admin users cannot access the admin dashboard
def test_admin_dashboard_blocks_non_admin_users(client):
    set_user_session(client)
    response = client.get("/admin")
    assert response.status_code == 403


# Tests that admins can access the admin dashboard
def test_admin_dashboard_loads_for_admin(client):
    set_admin_session(client)
    response = client.get("/admin")
    assert response.status_code == 200
    assert b"Admin Dashboard" in response.data


# Tests that the users route returns JSON for admins
def test_admin_users_route_returns_json(client, monkeypatch):
    set_admin_session(client)

    monkeypatch.setattr(
        "controllers.admin_controller.fetch_users",
        lambda: [{"id": 1, "username": "admin", "email": "admin@test.com", "role": "admin"}],
    )

    response = client.get("/admin/users")
    assert response.status_code == 200
    assert response.get_json()[0]["username"] == "admin"


# Tests that the listings route returns JSON for admins
def test_admin_listings_route_returns_json(client, monkeypatch):
    set_admin_session(client)

    monkeypatch.setattr(
        "controllers.admin_controller.fetch_listings",
        lambda: [{"id": 1, "title": "Test Hoodie", "status": "active"}],
    )

    response = client.get("/admin/listings")
    assert response.status_code == 200
    assert response.get_json()[0]["title"] == "Test Hoodie"


# Tests that the storefronts route returns JSON for admins
def test_admin_storefronts_route_returns_json(client, monkeypatch):
    set_admin_session(client)

    monkeypatch.setattr(
        "controllers.admin_controller.fetch_storefronts",
        lambda: [{"id": 1, "brand_name": "Test Brand", "owner_id": 2}],
    )

    response = client.get("/admin/storefronts")
    assert response.status_code == 200
    assert response.get_json()[0]["brand_name"] == "Test Brand"


# Tests that the real database connection works
def test_real_database_connection():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT 1")
    result = cur.fetchone()

    cur.close()
    conn.close()

    assert result[0] == 1


def create_test_user():
    unique = uuid.uuid4().hex[:8]
    username = f"test_user_{unique}"
    email = f"{username}@example.com"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO users (username, password, email, role)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (username, "test_password", email, "user"),
    )

    user_id = cur.fetchone()[0]
    conn.commit()

    cur.close()
    conn.close()

    return user_id


def row_exists(table_name, row_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"SELECT 1 FROM {table_name} WHERE id = %s", (row_id,))
    result = cur.fetchone()

    cur.close()
    conn.close()

    return result is not None


def cleanup_user(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()

    cur.close()
    conn.close()


# Tests that admin delete user route actually removes a user from the database
def test_admin_delete_user_in_real_database(client):
    set_admin_session(client)

    user_id = create_test_user()

    try:
        assert row_exists("users", user_id) is True

        response = client.delete(f"/admin/users/{user_id}")
        assert response.status_code == 200

        assert row_exists("users", user_id) is False

    finally:
        cleanup_user(user_id)


# Tests that logout clears the session and redirects to login
def test_logout_clears_admin_session(client):
    set_admin_session(client)

    response = client.get("/auth/logout", follow_redirects=False)

    assert response.status_code in (301, 302)
    assert "/auth/login" in response.headers["Location"]

# ---------------------------------------------------------------------------
# Added by Ethan Williams 11/9/26 - admin login against real admin accounts,
# delete safety rules, and return status validation (no database needed).
# ---------------------------------------------------------------------------

class _FakeCursor:
    def __init__(self, row=(7,)):
        self.row = row

    def execute(self, *args, **kwargs):
        pass

    def fetchone(self):
        return self.row

    def close(self):
        pass


class _FakeConn:
    closed = False

    def cursor(self):
        return _FakeCursor()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def patch_admin_login(monkeypatch, valid, role, attempts_left=2):
    import controllers.auth_controller as auth

    monkeypatch.setattr(auth, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(auth, "initialize_login_security", lambda conn: None)
    monkeypatch.setattr(auth, "get_remaining_lock", lambda conn, user: 0)
    monkeypatch.setattr(auth, "reset_login_attempts", lambda conn, user: None)
    monkeypatch.setattr(auth, "record_failed_login", lambda conn, user: attempts_left)
    monkeypatch.setattr(auth.service, "validate_login", lambda user, pw, conn: (valid, role))


# The old hardcoded admin/admin123 login must no longer work
def test_old_hardcoded_admin_password_rejected(client, monkeypatch):
    patch_admin_login(monkeypatch, valid=False, role=None)
    response = client.post("/auth/admin-login", data={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    assert b"don&#39;t match" in response.data or b"don't match" in response.data
    with client.session_transaction() as session:
        assert session.get("role") != "admin"


# A correct password on a normal account does not open the admin dashboard
def test_admin_login_rejects_non_admin_account(client, monkeypatch):
    patch_admin_login(monkeypatch, valid=True, role="user")
    response = client.post("/auth/admin-login", data={"username": "student", "password": "Good#Pass1"})
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert "user" not in session


# A real admin account logs in and lands on the dashboard
def test_admin_login_accepts_admin_account(client, monkeypatch):
    patch_admin_login(monkeypatch, valid=True, role="admin")
    response = client.post("/auth/admin-login", data={"username": "boss", "password": "Good#Pass1"})
    assert response.status_code in (301, 302)
    assert response.headers["Location"].endswith("/admin")
    with client.session_transaction() as session:
        assert session["role"] == "admin"
        assert session["user_id"] == 7


# Three wrong tries lock the admin login
def test_admin_login_lockout(client, monkeypatch):
    patch_admin_login(monkeypatch, valid=False, role=None, attempts_left=0)
    response = client.post("/auth/admin-login", data={"username": "boss", "password": "nope"})
    assert response.status_code == 429


# An admin can't delete their own account
def test_admin_cannot_delete_self(client, monkeypatch):
    set_admin_session(client)
    with client.session_transaction() as session:
        session["user_id"] = 5
    monkeypatch.setattr("services.admin_service.delete_user", lambda user_id: pytest.fail("should not delete"))
    response = client.delete("/admin/users/5")
    assert response.status_code == 403


# Admin accounts can't be deleted from the dashboard
def test_admin_cannot_delete_other_admin(client, monkeypatch):
    set_admin_session(client)
    monkeypatch.setattr("services.admin_service.get_user_role", lambda user_id: "admin")
    monkeypatch.setattr("services.admin_service.delete_user", lambda user_id: pytest.fail("should not delete"))
    response = client.delete("/admin/users/9")
    assert response.status_code == 403


# Deleting things that don't exist returns 404 instead of a fake success
def test_admin_delete_missing_rows_returns_404(client, monkeypatch):
    set_admin_session(client)
    monkeypatch.setattr("services.admin_service.get_user_role", lambda user_id: None)
    monkeypatch.setattr("services.admin_service.delete_listing", lambda listing_id: None)
    monkeypatch.setattr("services.admin_service.delete_storefront", lambda store_id: False)

    assert client.delete("/admin/users/999999").status_code == 404
    assert client.delete("/admin/listings/999999").status_code == 404
    assert client.delete("/admin/storefronts/999999").status_code == 404


# Return status must be one of pending / reviewed / resolved
def test_admin_return_status_validation(client, monkeypatch):
    set_admin_session(client)
    monkeypatch.setattr(
        "services.admin_service.update_admin_return_status",
        lambda return_id, status: {"id": return_id, "status": status},
    )

    bad = client.patch("/admin/returns/1", json={"status": "<script>"})
    assert bad.status_code == 400

    good = client.patch("/admin/returns/1", json={"status": "Resolved"})
    assert good.status_code == 200
    assert good.get_json()["status"] == "resolved"


# A database failure comes back as a JSON 500, not a crash page
def test_admin_route_database_error_returns_json(client, monkeypatch):
    set_admin_session(client)

    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr("controllers.admin_controller.fetch_users", broken)
    response = client.get("/admin/users")
    assert response.status_code == 500
    assert "error" in response.get_json()
