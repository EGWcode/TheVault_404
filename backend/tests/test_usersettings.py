#This test file is created by Claude AI prompts that I, Jaylen Belle, used to create this file. 


"""
Tests for the account settings feature:
    models/usersettings.py
    services/usersettings.py
    controllers/usersettings.py
 
No real database is used. The model's get_connection() is replaced with a fake
connection, and the model functions the service calls are replaced with an
in-memory fake user.
 
Place this file in the backend folder (the one that holds db.py, models/,
services/, controllers/ and utils/) and run:  pytest test_usersettings.py -v
"""
 
import pytest
from flask import Flask
 
from models import usersettings as settings_model
from services import usersettings as settings_service
from controllers.usersettings import usersettings_bp
from utils.auth_utils import hash_password, verify_password
 
 
USER_ID = 1
OLD_PASSWORD = "OldPass123!"
NEW_PASSWORD = "NewPass456!"
 
FAKE_ACCOUNT = {
    "username": "jaylen",
    "email": "jaylen@example.com",
    "role": "buyer",
    "created_at": "2026-01-15",
    "listings_count": 2,
    "wishlist_count": 3,
    "orders_count": 4,
    "has_storefront": True,
}
 
 
# --------------------------------------------------------------------------
# Fake database objects used for the model tests
# --------------------------------------------------------------------------
 
class FakeCursor:
    def __init__(self, results=None, fail_on_execute=False):
        self.results = list(results or [])  # values returned by fetchone(), in order
        self.fail_on_execute = fail_on_execute
        self.executed = []                  # (sql, params) for every execute()
        self.closed = False
 
    def execute(self, sql, params=None):
        if self.fail_on_execute:
            raise RuntimeError("database error")
        self.executed.append((sql, params))
 
    def fetchone(self):
        return self.results.pop(0) if self.results else None
 
    def close(self):
        self.closed = True
 
 
class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False
 
    def cursor(self):
        return self._cursor
 
    def commit(self):
        self.committed = True
 
    def rollback(self):
        self.rolled_back = True
 
    def close(self):
        self.closed = True
 
 
def use_fake_db(monkeypatch, cursor):
    conn = FakeConnection(cursor)
    monkeypatch.setattr(settings_model, "get_connection", lambda: conn)
    return conn
 
 
# --------------------------------------------------------------------------
# Fake user store used for the service and route tests
# --------------------------------------------------------------------------
 
@pytest.fixture
def fake_user(monkeypatch):
    """Replace every model function with an in-memory user whose password is OLD_PASSWORD."""
    store = {"hash": hash_password(OLD_PASSWORD), "saved": []}
 
    def get_account(user_id):
        return dict(FAKE_ACCOUNT) if user_id == USER_ID else None
 
    def get_hash(user_id):
        return store["hash"] if user_id == USER_ID else None
 
    def set_hash(user_id, password_hash):
        store["hash"] = password_hash
        store["saved"].append((user_id, password_hash))
 
    monkeypatch.setattr(settings_model, "get_account", get_account)
    # Only the names the model actually defines are replaced. The service currently
    # calls get_password_hash / set_password_hash, which don't exist in the model,
    # so tests that reach that call fail with AttributeError until the names match.
    monkeypatch.setattr(settings_model, "get_user_password_hash", get_hash)
    monkeypatch.setattr(settings_model, "set_user_password_hash", set_hash)
    return store
 
 
def password_body(current=OLD_PASSWORD, new=NEW_PASSWORD, confirm=NEW_PASSWORD):
    return {"current_password": current, "new_password": new, "confirm_password": confirm}
 
 
# --------------------------------------------------------------------------
# Model tests (fake connection, no real database)
# --------------------------------------------------------------------------
 
class TestModel:
    # Checks that get_account combines the user row and the count query into one dictionary,
    # passes the user_id to every placeholder, and closes the cursor and connection.
    def test_get_account_returns_dict(self, monkeypatch):
        cursor = FakeCursor(results=[
            ("jaylen", "jaylen@example.com", "buyer", "2026-01-15"),
            (2, 3, 4, 1),
        ])
        conn = use_fake_db(monkeypatch, cursor)
 
        account = settings_model.get_account(USER_ID)
 
        assert account == FAKE_ACCOUNT
        assert account["has_storefront"] is True
        assert cursor.executed[0][1] == (USER_ID,)
        assert cursor.executed[1][1] == (USER_ID, USER_ID, USER_ID, USER_ID)
        assert cursor.closed and conn.closed
 
    # Checks that get_account returns None for a user that doesn't exist
    # and stops before running the count query.
    def test_get_account_returns_none_when_user_missing(self, monkeypatch):
        cursor = FakeCursor(results=[None])
        conn = use_fake_db(monkeypatch, cursor)
 
        assert settings_model.get_account(999) is None
        assert len(cursor.executed) == 1  # stops before the count query
        assert cursor.closed and conn.closed
 
    # Checks that the stored password hash is returned when the user exists.
    def test_get_user_password_hash_found(self, monkeypatch):
        cursor = FakeCursor(results=[("stored-hash",)])
        conn = use_fake_db(monkeypatch, cursor)
 
        assert settings_model.get_user_password_hash(USER_ID) == "stored-hash"
        assert cursor.executed[0][1] == (USER_ID,)
        assert conn.closed
 
    # Checks that None is returned when the user doesn't exist.
    def test_get_user_password_hash_missing(self, monkeypatch):
        use_fake_db(monkeypatch, FakeCursor(results=[None]))
        assert settings_model.get_user_password_hash(999) is None
 
    # Checks that the UPDATE runs with the new hash and user_id, gets committed,
    # and that the cursor and connection are closed.
    def test_set_user_password_hash_commits(self, monkeypatch):
        cursor = FakeCursor()
        conn = use_fake_db(monkeypatch, cursor)
 
        settings_model.set_user_password_hash(USER_ID, "new-hash")
 
        sql, params = cursor.executed[0]
        assert "UPDATE users" in sql
        assert params == ("new-hash", USER_ID)
        assert conn.committed and not conn.rolled_back
        assert cursor.closed and conn.closed
 
    # Checks that a database error rolls back the change, is raised to the caller,
    # and still closes the cursor and connection.
    def test_set_user_password_hash_rolls_back_on_error(self, monkeypatch):
        cursor = FakeCursor(fail_on_execute=True)
        conn = use_fake_db(monkeypatch, cursor)
 
        with pytest.raises(RuntimeError):
            settings_model.set_user_password_hash(USER_ID, "new-hash")
 
        assert conn.rolled_back and not conn.committed
        assert cursor.closed and conn.closed
 
 
# --------------------------------------------------------------------------
# Service tests: get_settings
# --------------------------------------------------------------------------
 
class TestGetSettingsService:
    # Checks that get_settings returns success and the account dictionary for a real user.
    def test_returns_account(self, fake_user):
        success, result = settings_service.get_settings(USER_ID)
        assert success is True
        assert result == FAKE_ACCOUNT
 
    # Checks that get_settings returns a 404 failure for a user that doesn't exist.
    def test_unknown_user_is_404(self, fake_user):
        success, result = settings_service.get_settings(999)
        assert success is False
        assert result["status"] == 404
        assert result["field"] == "user_id"
 
 
# --------------------------------------------------------------------------
# Service tests: change_password
# --------------------------------------------------------------------------
 
class TestChangePasswordService:
    # Checks that a valid change succeeds and that the new password is saved
    # as a hash (not plain text) that matches the new password and not the old one.
    def test_success_saves_new_password_as_hash(self, fake_user):
        success, result = settings_service.change_password(USER_ID, password_body())
 
        assert success is True
        assert "message" in result
        assert len(fake_user["saved"]) == 1
        saved_user, saved_hash = fake_user["saved"][0]
        assert saved_user == USER_ID
        assert saved_hash != NEW_PASSWORD                   # not stored as plain text
        assert verify_password(saved_hash, NEW_PASSWORD)    # but it is the new password
        assert not verify_password(saved_hash, OLD_PASSWORD)
 
    # Checks that a wrong current password is rejected with a 403
    # on the current_password field and nothing is saved.
    def test_wrong_current_password(self, fake_user):
        success, result = settings_service.change_password(
            USER_ID, password_body(current="WrongPass999!"))
 
        assert success is False
        assert result["status"] == 403
        assert result["field"] == "current_password"
        assert fake_user["saved"] == []
 
    @pytest.mark.parametrize("weak", ["short1!", "alllowercase1!", "ALLUPPERCASE1!",
                                      "NoNumbers!!", "NoSpecial123"])
    # Runs once for each weak password (too short, no uppercase, no lowercase,
    # no number, no special character). Each should be rejected with the password rules
    # on the new_password field, and nothing should be saved.
    def test_weak_new_password(self, fake_user, weak):
        success, result = settings_service.change_password(
            USER_ID, password_body(new=weak, confirm=weak))
 
        assert success is False
        assert result["status"] == 400
        assert result["field"] == "new_password"
        assert result["error"] == settings_service.PASSWORD_RULES
        assert fake_user["saved"] == []
 
    # Checks that reusing the current password as the new password is rejected
    # on the new_password field and nothing is saved.
    def test_new_password_same_as_old(self, fake_user):
        success, result = settings_service.change_password(
            USER_ID, password_body(new=OLD_PASSWORD, confirm=OLD_PASSWORD))
 
        assert success is False
        assert result["status"] == 400
        assert result["field"] == "new_password"
        assert "different" in result["error"]
        assert fake_user["saved"] == []
 
    # Checks that a confirm box that doesn't match the new password is rejected
    # on the confirm_password field and nothing is saved.
    def test_confirm_does_not_match(self, fake_user):
        success, result = settings_service.change_password(
            USER_ID, password_body(confirm="Different789!"))
 
        assert success is False
        assert result["status"] == 400
        assert result["field"] == "confirm_password"
        assert fake_user["saved"] == []
 
    # Runs once for each of the three boxes, with it blank ("") and missing (None).
    # Each should be rejected with "Fill in all password fields" naming that box,
    # and nothing should be saved.
    @pytest.mark.parametrize("field", ["current_password", "new_password", "confirm_password"])
    @pytest.mark.parametrize("empty_value", ["", None])
    def test_empty_box(self, fake_user, field, empty_value):
        body = password_body()
        body[field] = empty_value
 
        success, result = settings_service.change_password(USER_ID, body)
 
        assert success is False
        assert result["status"] == 400
        assert result["field"] == field
        assert result["error"] == "Fill in all password fields"
        assert fake_user["saved"] == []
 
    # Checks that changing the password for a user that doesn't exist returns a 404.
    def test_unknown_user_is_404(self, fake_user):
        success, result = settings_service.change_password(999, password_body())
        assert success is False
        assert result["status"] == 404
 
 
# --------------------------------------------------------------------------
# Route tests (Flask test client)
# --------------------------------------------------------------------------
 
@pytest.fixture
def client():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    app.register_blueprint(usersettings_bp)
    with app.test_client() as test_client:
        yield test_client
 
 
def log_in(client, user_id=USER_ID):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
 
 
class TestSettingsRoute:
    # Checks that viewing settings without a user_id in the session returns a 401.
    def test_logged_out_returns_401(self, client, fake_user):
        response = client.get("/api/account/settings")
        assert response.status_code == 401
        assert "error" in response.get_json()
 
    # Checks that a logged-in user gets a 200 and their account information.
    def test_logged_in_returns_account(self, client, fake_user):
        log_in(client)
        response = client.get("/api/account/settings")
        assert response.status_code == 200
        assert response.get_json() == FAKE_ACCOUNT
 
 
class TestPasswordRoute:
    # Checks that changing the password without a user_id in the session returns a 401
    # and nothing is saved.
    def test_logged_out_returns_401(self, client, fake_user):
        response = client.post("/api/account/password", json=password_body())
        assert response.status_code == 401
        assert "error" in response.get_json()
        assert fake_user["saved"] == []
 
    # Checks that a logged-in user with a valid request gets a 200
    # and the stored hash now matches the new password.
    def test_logged_in_changes_password(self, client, fake_user):
        log_in(client)
        response = client.post("/api/account/password", json=password_body())
 
        assert response.status_code == 200
        assert "message" in response.get_json()
        assert verify_password(fake_user["hash"], NEW_PASSWORD)
 
    # Checks that a failed change returns the service's status code (403 here)
    # and the field name, so the front end knows which box to highlight.
    def test_logged_in_error_includes_field(self, client, fake_user):
        log_in(client)
        response = client.post("/api/account/password",
                               json=password_body(current="WrongPass999!"))
 
        assert response.status_code == 403
        assert response.get_json()["field"] == "current_password"
 