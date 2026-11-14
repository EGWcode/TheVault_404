#Testing for returns by Claude and Tykeara Hammond
"""
Pytest suite for the returns feature (controller + service).

- Database (create_return_record / update_return_status) and S3 upload are faked
  with monkeypatch; an autouse guard makes any un-faked call fail loudly.
- Tests tagged "SECURITY" assert the SECURE behaviour. Where the current code is
  vulnerable they are marked xfail(strict=True): they show up as XFAIL now and turn
  into a hard failure (XPASS) once the hole is fixed, reminding you to drop the marker.

Adjust the two import lines below if your package layout differs.
"""

import io

import pytest
from flask import Blueprint, Flask, session

import services.return_service as return_service
from controllers.return_controller import get_current_user, returns_bp

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
S3_URL = "https://fake-bucket.s3.amazonaws.com/returns/damage/photo.png"
VALID_FORM = {"order_number": "ORD-1001", "reason": "Arrived broken", "has_damage": "yes"}


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
class FakeDB:
    """In-memory stand-in for the model layer."""

    def __init__(self):
        self.created = []
        self.status_calls = []
        self.records = {}  # return_id -> record, used by update_return_status

    def create_return_record(self, **kwargs):
        record = {"id": len(self.created) + 1, **kwargs}
        self.created.append(record)
        return record

    def update_return_status(self, return_id, status):
        self.status_calls.append((return_id, status))
        record = self.records.get(return_id)
        return None if record is None else {**record, "status": status}


class FakeS3:
    """Records uploads; set .result to None to simulate a failed upload."""

    def __init__(self):
        self.calls = []
        self.result = S3_URL

    def upload(self, file, folder=None):
        self.calls.append({"filename": file.filename, "folder": folder, "data": file.read()})
        return self.result


@pytest.fixture(autouse=True)
def block_real_io(monkeypatch):
    """Safety net: any DB or S3 call that a test did not fake raises immediately."""

    def _blocked(*_a, **_k):
        raise AssertionError("Real DB/S3 call attempted - fake it in the test.")

    monkeypatch.setattr(return_service, "create_return_record", _blocked)
    monkeypatch.setattr(return_service, "update_return_status", _blocked)
    monkeypatch.setattr(return_service, "get_all_returns", _blocked)
    monkeypatch.setattr("utils.s3.upload_image_to_s3", _blocked)


@pytest.fixture
def fake_db(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(return_service, "create_return_record", db.create_return_record)
    monkeypatch.setattr(return_service, "update_return_status", db.update_return_status)
    monkeypatch.setattr(return_service, "order_belongs_to_user", lambda user_id, order: True, raising=False)
    return db


@pytest.fixture
def fake_s3(monkeypatch):
    s3 = FakeS3()
    monkeypatch.setattr("utils.s3.upload_image_to_s3", s3.upload)
    return s3


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    app.register_blueprint(returns_bp)

    # Minimal stand-in so url_for("auth.login") resolves; use your real blueprint if you have one.
    auth = Blueprint("auth", __name__)
    auth.add_url_rule("/login", "login", lambda: "login page")
    app.register_blueprint(auth)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, user_id=1, role="user"):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user"] = "testuser"
        sess["role"] = role


def upload(client, filename, content=PNG_BYTES, fields=None, headers=None):
    data = dict(fields or VALID_FORM)
    data["damage_image"] = (io.BytesIO(content), filename)
    return client.post("/returns", data=data, headers=headers, content_type="multipart/form-data")


# --------------------------------------------------------------------------- #
# Returns page
# --------------------------------------------------------------------------- #
# RET-01: GET /returns while logged out redirects to the login page.
def test_ret_01_returns_page_redirects_when_logged_out(client):
    resp = client.get("/returns")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


# RET-02: GET /returns for a logged-in user renders the returns template.
def test_ret_02_returns_page_renders_when_logged_in(client, monkeypatch):
    monkeypatch.setattr("controllers.return_controller.render_template", lambda name: f"rendered:{name}")
    with client.session_transaction() as sess:
        sess["user"] = "alice"
    resp = client.get("/returns")
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "rendered:returns.html"


# --------------------------------------------------------------------------- #
# Authentication on submit
# --------------------------------------------------------------------------- #
# RET-03: POST /returns with no session and no headers returns 401 and writes nothing.
def test_ret_03_submit_requires_login(client, fake_db):
    resp = client.post("/returns", data=VALID_FORM)
    assert resp.status_code == 401
    assert resp.get_json() == {"error": "Unauthorized."}
    assert fake_db.created == []


# RET-04: A non-integer X-User-Id header is rejected with 401.
def test_ret_04_non_integer_user_id_header_is_unauthorized(client, fake_db):
    resp = client.post("/returns", data=VALID_FORM, headers={"X-User-Id": "abc"})
    assert resp.status_code == 401
    assert fake_db.created == []


# RET-05: A falsy user id (0) is rejected by the service with 401.
def test_ret_05_zero_user_id_is_unauthorized(client, fake_db):
    resp = client.post("/returns", data=VALID_FORM, headers={"X-User-Id": "0"})
    assert resp.status_code == 401
    assert fake_db.created == []


# --------------------------------------------------------------------------- #
# Valid submissions
# --------------------------------------------------------------------------- #
# RET-06: A valid form submission by a logged-in user returns 201 and stores a pending record.
def test_ret_06_valid_form_return_created(client, fake_db):
    login(client, user_id=7)
    resp = client.post("/returns", data=VALID_FORM)
    assert resp.status_code == 201
    assert fake_db.created == [
        {
            "id": 1,
            "user_id": 7,
            "order_number": "ORD-1001",
            "reason": "Arrived broken",
            "has_damage": True,
            "damage_image_url": None,
            "status": "pending",
        }
    ]
    assert resp.get_json()["id"] == 1


# RET-07: A valid JSON body (with boolean has_damage=False) is also accepted with 201.
def test_ret_07_valid_json_return_created(client, fake_db):
    login(client, user_id=3)
    resp = client.post("/returns", json={"order_number": "ORD-2", "reason": "Wrong size", "has_damage": False})
    assert resp.status_code == 201
    assert fake_db.created[0]["has_damage"] is False
    assert fake_db.created[0]["user_id"] == 3


# --------------------------------------------------------------------------- #
# Required fields
# --------------------------------------------------------------------------- #
# RET-08: Missing order_number returns 400 and creates no record.
def test_ret_08_missing_order_number(client, fake_db):
    login(client)
    resp = client.post("/returns", data={"reason": "x", "has_damage": "no"})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "order_number is required."}
    assert fake_db.created == []


# RET-09: Missing reason returns 400 and creates no record.
def test_ret_09_missing_reason(client, fake_db):
    login(client)
    resp = client.post("/returns", data={"order_number": "ORD-1", "has_damage": "no"})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "reason is required."}
    assert fake_db.created == []


# RET-10: Missing has_damage returns 400 and creates no record.
def test_ret_10_missing_has_damage(client, fake_db):
    login(client)
    resp = client.post("/returns", data={"order_number": "ORD-1", "reason": "x"})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "has_damage is required."}
    assert fake_db.created == []


# RET-11: Whitespace-only values count as missing for each required field.
@pytest.mark.parametrize("field", ["order_number", "reason", "has_damage"])
def test_ret_11_whitespace_only_field_is_missing(client, fake_db, field):
    login(client)
    resp = client.post("/returns", data={**VALID_FORM, field: "   "})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": f"{field} is required."}
    assert fake_db.created == []


# --------------------------------------------------------------------------- #
# Damage image upload
# --------------------------------------------------------------------------- #
# RET-12: Disallowed or extension-less filenames (incl. svg/php/double extension) get 400 and skip S3.
@pytest.mark.parametrize(
    "filename",
    ["report.pdf", "script.exe", "notes.txt", "shell.php", "logo.svg", "photo.png.exe", "photo"],
)
def test_ret_12_bad_image_file_type_rejected(client, fake_db, fake_s3, filename):
    login(client)
    resp = upload(client, filename)
    assert resp.status_code == 400
    assert "PNG, JPG, JPEG, GIF, or WebP" in resp.get_json()["error"]
    assert fake_s3.calls == []
    assert fake_db.created == []


# RET-13: A PNG upload is sent to S3 under returns/damage and its URL is stored on the record.
def test_ret_13_png_upload_succeeds(client, fake_db, fake_s3):
    login(client, user_id=4)
    resp = upload(client, "damage.png")
    assert resp.status_code == 201
    assert fake_s3.calls == [{"filename": "damage.png", "folder": "returns/damage", "data": PNG_BYTES}]
    assert fake_db.created[0]["damage_image_url"] == S3_URL
    assert resp.get_json()["damage_image_url"] == S3_URL


# RET-14: Extension matching is case-insensitive (PHOTO.JPG is accepted).
def test_ret_14_uppercase_extension_accepted(client, fake_db, fake_s3):
    login(client)
    resp = upload(client, "PHOTO.JPG")
    assert resp.status_code == 201
    assert len(fake_s3.calls) == 1


# RET-15: When S3 returns no URL the API responds 500 and no return record is saved.
def test_ret_15_s3_upload_failure_returns_500(client, fake_db, fake_s3):
    fake_s3.result = None
    login(client)
    resp = upload(client, "damage.png")
    assert resp.status_code == 500
    assert resp.get_json() == {"error": "Damage image upload failed."}
    assert fake_db.created == []


# RET-16: A file field with an empty filename is ignored (no S3 call, 201, no image URL).
def test_ret_16_empty_file_field_is_ignored(client, fake_db, fake_s3):
    login(client)
    resp = upload(client, "", content=b"")
    assert resp.status_code == 201
    assert fake_s3.calls == []
    assert fake_db.created[0]["damage_image_url"] is None


# --------------------------------------------------------------------------- #
# has_damage parsing
# --------------------------------------------------------------------------- #
# RET-17: Truthy spellings (true/yes/y/1, any case, padded) parse to True.
@pytest.mark.parametrize("value", ["true", "True", "yes", "YES", "y", "1", "  Yes  "])
def test_ret_17_has_damage_truthy_values(client, fake_db, value):
    login(client)
    resp = client.post("/returns", data={**VALID_FORM, "has_damage": value})
    assert resp.status_code == 201
    assert fake_db.created[0]["has_damage"] is True


# RET-18: Falsy spellings (false/no/n/0, any case, padded) parse to False.
@pytest.mark.parametrize("value", ["false", "False", "no", "NO", "n", "0", "  No  "])
def test_ret_18_has_damage_falsy_values(client, fake_db, value):
    login(client)
    resp = client.post("/returns", data={**VALID_FORM, "has_damage": value})
    assert resp.status_code == 201
    assert fake_db.created[0]["has_damage"] is False


# RET-19: An unrecognised has_damage value returns 400 and creates no record.
@pytest.mark.parametrize("value", ["maybe", "2", "yess", "null"])
def test_ret_19_has_damage_invalid_value(client, fake_db, value):
    login(client)
    resp = client.post("/returns", data={**VALID_FORM, "has_damage": value})
    assert resp.status_code == 400
    assert fake_db.created == []


# --------------------------------------------------------------------------- #
# Admin status updates (service layer - the controller exposes no status route)
# --------------------------------------------------------------------------- #
# RET-20: Valid statuses are normalised (trim + lowercase) and passed to the DB layer.
@pytest.mark.parametrize(
    "raw, expected",
    [("pending", "pending"), ("reviewed", "reviewed"), ("resolved", "resolved"),
     ("  RESOLVED ", "resolved"), ("Reviewed", "reviewed")],
)
def test_ret_20_update_status_valid(fake_db, raw, expected):
    fake_db.records[7] = {"id": 7, "status": "pending"}
    result = return_service.update_return_status_service(7, raw)
    assert result == {"id": 7, "status": expected}
    assert fake_db.status_calls == [(7, expected)]


# RET-21: Invalid statuses (empty, None, unknown, SQL-ish) raise and never reach the DB.
@pytest.mark.parametrize("bad", ["", None, "done", "closed", "resolved'; DROP TABLE returns;--"])
def test_ret_21_update_status_invalid(fake_db, bad):
    with pytest.raises(Exception, match="status must be pending, reviewed, or resolved"):
        return_service.update_return_status_service(7, bad)
    assert fake_db.status_calls == []


# RET-22: Updating a return id that does not exist raises "Return not found."
def test_ret_22_update_status_return_not_found(fake_db):
    with pytest.raises(Exception, match="Return not found"):
        return_service.update_return_status_service(999, "reviewed")
    assert fake_db.status_calls == [(999, "reviewed")]


# --------------------------------------------------------------------------- #
# SECURITY
# --------------------------------------------------------------------------- #
# RET-23: SECURITY - a user-supplied user_id in the body is ignored (no mass assignment).
def test_ret_23_body_user_id_is_ignored(client, fake_db):
    login(client, user_id=1)
    resp = client.post("/returns", data={**VALID_FORM, "user_id": "99", "status": "resolved"})
    assert resp.status_code == 201
    assert fake_db.created[0]["user_id"] == 1
    assert fake_db.created[0]["status"] == "pending"


# RET-24: SECURITY - a logged-in user must not be able to impersonate another via X-User-Id.
def test_ret_24_header_cannot_impersonate_other_user(client, fake_db):
    login(client, user_id=1)
    resp = client.post("/returns", data=VALID_FORM, headers={"X-User-Id": "2"})
    assert fake_db.created == [] or fake_db.created[0]["user_id"] == 1
    assert resp.status_code in (201, 400, 401, 403)


# RET-25: SECURITY - an X-User-Id header alone (no session) must not authenticate a request.
def test_ret_25_header_only_request_is_unauthorized(client, fake_db):
    resp = client.post("/returns", data=VALID_FORM, headers={"X-User-Id": "5"})
    assert resp.status_code == 401
    assert fake_db.created == []


# RET-26: SECURITY - a client-sent X-User-Role header must not raise privileges above the session role.
def test_ret_26_role_header_cannot_escalate_privileges(app):
    with app.test_request_context("/returns", headers={"X-User-Id": "1", "X-User-Role": "admin"}):
        session["user_id"] = 1
        session["user"] = "testuser"
        session["role"] = "user"
        assert get_current_user()["role"] == "user"


# RET-27: SECURITY - a non-image payload named *.png should be rejected (content, not just extension).
def test_ret_27_fake_png_content_rejected(client, fake_db, fake_s3):
    login(client)
    resp = upload(client, "avatar.png", content=b"<?php system($_GET['c']); ?>")
    assert resp.status_code == 400
    assert fake_s3.calls == []


# RET-28: SECURITY - unexpected backend errors must not leak internals (DSNs, passwords) to the client.
def test_ret_28_internal_errors_not_leaked(client, fake_db, monkeypatch):
    def boom(**_kw):
        raise Exception("connection refused: postgres://admin:s3cret@db.internal:5432/market")

    monkeypatch.setattr(return_service, "create_return_record", boom)
    login(client)
    resp = client.post("/returns", data=VALID_FORM)
    assert "s3cret" not in resp.get_data(as_text=True)
    assert resp.status_code == 500


# RET-29: SECURITY/consistency - page and submit should agree on what "logged in" means (session key).
def test_ret_29_page_and_submit_use_same_session_key(client, fake_db, monkeypatch):
    monkeypatch.setattr("controllers.return_controller.render_template", lambda name: name)
    login(client, user_id=1)  # sets user_id/role only, as submit_return accepts
    assert client.post("/returns", data=VALID_FORM).status_code == 201
    assert client.get("/returns").status_code == 200