# backend/tests/test_auth_pages.py
# Created by Nicco Hill 10/27/2026
# Unit tests for the log in, sign up and admin log in pages.
# Checks that errors show on the styled page (not a plain white page), the typed username
# stays filled in, and the moving waves + ship are on each page.
# The database and AuthService are faked, so these tests never touch real data.

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add project root (for app.py) and backend folder (for controllers) to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Skip the startup database migration so the tests don't need Postgres
with patch("init_db.create_vault_tables"):
    from app import create_app


@pytest.fixture
def client():
    with patch("init_db.create_vault_tables"):
        app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def fake_conn():
    conn = MagicMock()
    with patch("controllers.auth_controller.get_connection", return_value=conn):
        yield conn


@pytest.fixture
def fake_service():
    with patch("controllers.auth_controller.service") as service:
        yield service


# ---------- Log in ----------

def test_login_page_loads(client):
    res = client.get("/auth/login")
    assert res.status_code == 200
    assert b"LOG IN" in res.data
    assert b'name="username"' in res.data


def test_login_wrong_password_shows_error_on_page(client, fake_conn, fake_service):
    fake_service.validate_login.return_value = (False, None)

    res = client.post("/auth/login", data={"username": "demo_buyer", "password": "wrong"})

    assert res.status_code == 200
    assert b"That username and password don&#39;t match" in res.data
    assert b'class="flash flash-error"' in res.data
    assert b'value="demo_buyer"' in res.data     # username stays filled in
    assert b"Invalid Credentials" not in res.data  # old plain-text error is gone
    fake_conn.close.assert_called_once()


def test_login_database_down_shows_error_on_page(client, fake_service):
    with patch("controllers.auth_controller.get_connection", return_value=None):
        res = client.post("/auth/login", data={"username": "demo_buyer", "password": "x"})

    assert res.status_code == 200
    assert b"reach the database right now" in res.data
    assert b'value="demo_buyer"' in res.data
    fake_service.validate_login.assert_not_called()


def test_login_success_redirects_to_listings(client, fake_conn, fake_service):
    fake_service.validate_login.return_value = (True, "user")
    fake_service.get_user_cart.return_value = []
    fake_conn.cursor.return_value.fetchone.return_value = (3,)

    res = client.post("/auth/login", data={"username": "demo_buyer", "password": "DemoPass123"})

    assert res.status_code == 302
    assert res.headers["Location"].endswith("/auth/listings")
    with client.session_transaction() as sess:
        assert sess["user"] == "demo_buyer"
        assert sess["user_id"] == 3


def test_login_admin_role_redirects_to_dashboard(client, fake_conn, fake_service):
    fake_service.validate_login.return_value = (True, "admin")
    fake_service.get_user_cart.return_value = []
    fake_conn.cursor.return_value.fetchone.return_value = (1,)

    res = client.post("/auth/login", data={"username": "boss", "password": "pw"})

    assert res.status_code == 302
    assert "/admin" in res.headers["Location"]


def test_login_username_is_escaped(client, fake_conn, fake_service):
    fake_service.validate_login.return_value = (False, None)

    res = client.post("/auth/login", data={"username": '"><script>alert(1)</script>', "password": "x"})

    assert b"<script>alert(1)</script>" not in res.data
    assert b"&lt;script&gt;" in res.data


# ---------- Sign up ----------

def test_signup_error_keeps_username_and_email(client, fake_conn, fake_service):
    fake_service.register_user.return_value = (False, "Please use your Hampton email.")

    res = client.post("/auth/signup", data={
        "username": "newkid", "password": "Password123!", "email": "newkid@gmail.com",
    })

    assert res.status_code == 200
    assert b"Please use your Hampton email." in res.data
    assert b'value="newkid"' in res.data
    assert b'value="newkid@gmail.com"' in res.data


def test_signup_success_redirects_to_login(client, fake_conn, fake_service):
    fake_service.register_user.return_value = (True, "ok")

    res = client.post("/auth/signup", data={
        "username": "newkid", "password": "Password123!", "email": "newkid@my.hamptonu.edu",
    })

    assert res.status_code == 302
    assert res.headers["Location"].endswith("/auth/login")


# ---------- Admin log in ----------

def test_admin_login_wrong_password_shows_error_on_page(client):
    res = client.post("/auth/admin-login", data={"username": "admin", "password": "nope"})

    assert res.status_code == 200
    assert b"That admin username and password don&#39;t match" in res.data
    assert b'class="flash flash-error"' in res.data
    assert b'value="admin"' in res.data
    assert b"Invalid Admin Credentials" not in res.data


# ---------- Hampton redesign: waves and ship ----------

@pytest.mark.parametrize("path", ["/auth/login", "/auth/signup", "/auth/admin-login"])
def test_page_has_moving_waves_and_ship(client, path):
    res = client.get(path)

    assert res.status_code == 200
    for wave_id in (b'id="wave-far"', b'id="wave-mid"', b'id="wave-front"'):
        assert wave_id in res.data
    assert b'id="ship-sail"' in res.data
    assert b"prefers-reduced-motion: reduce" in res.data  # animation turns off for reduced motion
