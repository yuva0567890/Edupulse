"""Database-backed authentication: sign up, login (username or email), logout, protected routes."""
import sqlite3

import pytest

import security
from tests.conftest import ADMIN, make_app, signup


def login(c, ident, pw, **kw):
    return c.post("/admin/login", data={"identifier": ident, "password": pw}, **kw)


def test_signup_page_and_login_page_render(client):
    html = client.get("/admin/signup").get_data(as_text=True)
    for word in ("EduPulse", "Create Admin Account", "Username", "Email", "Password", "Confirm Password", "Sign Up", "Login"):
        assert word in html
    html = client.get("/admin/login").get_data(as_text=True)
    for word in ("EduPulse", "Welcome Back", "Email or Username", "Password", "Login", "Sign Up", "Don't have an account?"):
        assert word in html


def test_exact_spec_flow_signup_then_login_then_dashboard(client):
    r = signup(client)                                   # testadmin / testadmin@example.com / Test@12345
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/login")
    page = client.get("/admin/login").get_data(as_text=True)
    assert "Account created successfully. Please login." in page
    r = login(client, "testadmin@example.com", "Test@12345")
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/dashboard")
    dash = client.get("/admin/dashboard")
    assert dash.status_code == 200 and "Login successful" in dash.get_data(as_text=True)
    assert "EduPulse Admin" in dash.get_data(as_text=True)


def test_login_with_username_and_with_email_any_case(client):
    signup(client)
    for ident in ("testadmin", "TESTADMIN", "testadmin@example.com", "TestAdmin@Example.com", "  testadmin  "):
        c = client.application.test_client()
        r = login(c, ident, ADMIN["password"])
        assert r.status_code == 302, ident


def test_wrong_password_and_unknown_user(client):
    signup(client)
    for ident, pw in (("testadmin", "wrong-pass"), ("testadmin@example.com", ""), ("nobody", "Test@12345"),
                      ("nobody@example.com", "Test@12345"), ("", "")):
        r = login(client, ident, pw)
        assert r.status_code == 401 and "Invalid username/email or password." in r.get_data(as_text=True), ident
    assert client.get("/admin/dashboard").status_code == 302


def test_no_hardcoded_admin_exists(client):
    """admin / admin123 must NOT work on a fresh installation: authentication is database-only."""
    from database import db
    with client.application.app_context():
        assert db.count_users() == 0
    for ident, pw in (("admin", "admin123"), ("admin", "admin"), ("admin@example.com", "admin123")):
        assert login(client, ident, pw).status_code == 401


def test_signup_validation(client):
    cases = [
        ({"username": ""}, "username"), ({"username": "a b"}, "username"), ({"username": "ab"}, "username"),
        ({"email": ""}, "email"), ({"email": "not-an-email"}, "email"), ({"email": "a@b"}, "email"),
        ({"password": "", "confirm": ""}, "password"), ({"password": "short1", "confirm": "short1"}, "password"),
        ({"confirm": "Different@123"}, "confirm"), ({"confirm": ""}, "confirm"),
    ]
    for over, field in cases:
        r = signup(client, **over)
        assert r.status_code == 400, over
        assert field in r.get_data(as_text=True).lower() and 'class="err"' in r.get_data(as_text=True)
    from database import db
    with client.application.app_context():
        assert db.count_users() == 0


def test_duplicate_username_and_email_rejected(client):
    assert signup(client).status_code == 302
    r = signup(client, email="other@example.com")
    assert r.status_code == 400 and "already taken" in r.get_data(as_text=True)
    r = signup(client, username="someoneelse")
    assert r.status_code == 400 and "already exists" in r.get_data(as_text=True)
    r = signup(client, username="TESTADMIN", email="x@example.com")                # case-insensitive username
    assert r.status_code == 400
    r = signup(client, username="third", email="TESTADMIN@EXAMPLE.COM")            # case-insensitive email
    assert r.status_code == 400
    from database import db
    with client.application.app_context():
        assert db.count_users() == 1


def test_password_is_stored_hashed_and_fields(client):
    signup(client)
    from database import db
    with client.application.app_context():
        u = db.get_user_by_username("testadmin")
        assert u.email == "testadmin@example.com" and u.role == "admin" and u.is_active and u.created_at
        assert "Test@12345" not in u.password_hash and u.password_hash.split(":")[0] in ("scrypt", "pbkdf2")
        assert security.verify(u.password_hash, "Test@12345") and not security.verify(u.password_hash, "test@12345")
    assert "Test@12345" not in client.get("/admin/login").get_data(as_text=True)


def test_logout_clears_session_and_redirects_to_login(admin_client):
    assert admin_client.get("/admin/dashboard").status_code == 200
    r = admin_client.post("/admin/logout")
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/login")
    r = admin_client.get("/admin/dashboard")
    assert r.status_code == 302 and "/admin/login" in r.headers["Location"]
    assert admin_client.get("/api/feedback").status_code == 401
    r = admin_client.get("/admin/logout")                                      # GET works too
    assert r.status_code == 302


def test_protected_routes_redirect_to_login(client):
    for p in ("/admin/dashboard", "/admin/feedback", "/admin/feedback/1", "/admin/issues", "/admin/analytics",
              "/admin/model-performance", "/admin/settings", "/admin/feedback/export.csv"):
        r = client.get(p)
        assert r.status_code == 302 and "/admin/login" in r.headers["Location"], p
    for p in ("/api/feedback", "/api/issues", "/api/dashboard/stats", "/api/dashboard/trending", "/api/dashboard/critical",
              "/api/dashboard/similar", "/api/dashboard/summary", "/api/dashboard/recent"):
        assert client.get(p).status_code == 401, p
    assert client.post("/admin/feedback/1/update", data={"status": "Closed"}).status_code == 302


def test_logged_in_user_can_open_every_admin_page(admin_client):
    for p in ("/admin/dashboard", "/admin/feedback", "/admin/issues", "/admin/analytics", "/admin/model-performance",
              "/admin/settings"):
        assert admin_client.get(p).status_code == 200, p
    assert admin_client.get("/admin/login").status_code == 302              # already logged in


def test_next_redirect_and_open_redirect_blocked(client):
    signup(client)
    r = login(client, "testadmin", ADMIN["password"], query_string={"next": "/admin/issues"})
    assert r.headers["Location"].endswith("/admin/issues")
    c = client.application.test_client()
    r = login(c, "testadmin", ADMIN["password"], query_string={"next": "https://evil.example/x"})
    assert r.headers["Location"].endswith("/admin/dashboard")


def test_accounts_persist_across_restart(tmp_path):
    a1 = make_app(tmp_path)
    signup(a1.test_client())
    a2 = make_app(tmp_path)                                  # new process, same database file
    assert login(a2.test_client(), "testadmin@example.com", "Test@12345").status_code == 302


def test_deactivated_or_deleted_account_session_is_rejected(admin_client, app):
    from database import db
    with app.app_context():
        u = db.get_user_by_username("testadmin")
        u.is_active = False
        db.get_session().commit()
    assert admin_client.get("/admin/dashboard").status_code == 302
    c = app.test_client()
    assert login(c, "testadmin", ADMIN["password"]).status_code == 401


def test_change_password_in_settings(admin_client, app):
    r = admin_client.post("/admin/settings", data={"action": "password", "current_password": "wrong",
                                                   "new_password": "Brand@New123", "new_password2": "Brand@New123"})
    assert login(app.test_client(), "testadmin", "Brand@New123").status_code == 401
    admin_client.post("/admin/settings", data={"action": "password", "current_password": "Test@12345",
                                               "new_password": "Brand@New123", "new_password2": "Brand@New123"})
    assert login(app.test_client(), "testadmin", "Brand@New123").status_code == 302
    assert login(app.test_client(), "testadmin", "Test@12345").status_code == 401


def test_second_admin_can_sign_up_and_both_work(client):
    signup(client)
    assert signup(client, username="second", email="second@example.com", password="Second@1234", confirm="Second@1234").status_code == 302
    assert login(client.application.test_client(), "second@example.com", "Second@1234").status_code == 302
    assert login(client.application.test_client(), "testadmin", "Test@12345").status_code == 302


def test_signup_policy_flags(tmp_path):
    closed = make_app(tmp_path, ALLOW_SIGNUP="false")
    c = closed.test_client()
    assert signup(c).status_code == 302                       # the very first account is always allowed
    assert signup(c, username="late", email="late@example.com").status_code == 403
    assert "Sign up is closed" in c.get("/admin/signup").get_data(as_text=True)
    prod = make_app(tmp_path / "p" if (tmp_path / "p").mkdir() or True else tmp_path, IS_PRODUCTION=True)
    pc = prod.test_client()
    assert pc.get("/admin/signup").status_code == 200
    assert signup(pc).status_code == 302
    assert pc.get("/admin/signup").status_code == 403         # production: closed after the first account


def test_invitation_code(tmp_path):
    app = make_app(tmp_path, ADMIN_SIGNUP_CODE="letmein")
    c = app.test_client()
    assert signup(c).status_code == 302                       # first account needs no code
    r = signup(c, username="second", email="second@example.com")
    assert r.status_code == 400 and "Invalid invitation code" in r.get_data(as_text=True)
    assert signup(c, username="second", email="second@example.com", signup_code="letmein").status_code == 302


def test_legacy_admin_table_is_migrated(tmp_path):
    from werkzeug.security import generate_password_hash
    path = tmp_path / "legacy.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE admin_users (id INTEGER PRIMARY KEY, username VARCHAR(80), password_hash VARCHAR(255), created_at DATETIME)")
    con.execute("INSERT INTO admin_users VALUES (1, 'olduser', ?, '2026-01-01 00:00:00')", (generate_password_hash("Old@Pass123"),))
    con.commit(); con.close()
    app = make_app(tmp_path, SQLALCHEMY_DATABASE_URI="sqlite:///" + str(path).replace("\\", "/"))
    c = app.test_client()
    assert login(c, "olduser", "Old@Pass123").status_code == 302
    assert login(app.test_client(), "olduser@edupulse.local", "Old@Pass123").status_code == 302


def test_new_feedback_visible_after_logout_and_login(client, admin_client):
    r = client.post("/api/feedback", json={"text": "Hostel food is not good", "department": "CSE"})
    assert r.status_code == 201
    fid = r.get_json()["id"]
    assert fid in [i["id"] for i in admin_client.get("/api/feedback").get_json()["items"]]
    admin_client.post("/admin/logout")
    again = admin_client.application.test_client()
    assert login(again, "testadmin", "Test@12345").status_code == 302
    assert fid in [i["id"] for i in again.get("/api/feedback").get_json()["items"]]
    assert "Hostel food is not good" in again.get("/admin/feedback").get_data(as_text=True)


def test_security_helpers():
    assert security.validate_signup("testadmin", "testadmin@example.com", "Test@12345", "Test@12345") == {}
    assert security.verify("", "x") is False and security.verify("garbage", "x") is False
    h1, h2 = security.hash_password("same"), security.hash_password("same")
    assert h1 != h2 and security.verify(h1, "same") and security.verify(h2, "same")      # salted
