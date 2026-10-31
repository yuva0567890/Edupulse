"""Browser-like flow with CSRF protection ENFORCED (as in production): the forms must carry valid tokens."""
import re

from tests.conftest import make_app


def token(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "form has no csrf token"
    return m.group(1)


def test_signup_login_logout_with_csrf_enforced(tmp_path):
    app = make_app(tmp_path, TESTING=False)           # production-like request handling
    c = app.test_client()
    t = token(c.get("/admin/signup").get_data(as_text=True))
    # a POST without the token is rejected
    assert c.post("/admin/signup", data={"username": "testadmin", "email": "testadmin@example.com",
                                          "password": "Test@12345", "confirm": "Test@12345"}).status_code == 400
    r = c.post("/admin/signup", data={"csrf_token": t, "username": "testadmin", "email": "testadmin@example.com",
                                      "password": "Test@12345", "confirm": "Test@12345"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/login")
    page = c.get("/admin/login").get_data(as_text=True)
    assert "Account created successfully. Please login." in page
    t = token(page)
    r = c.post("/admin/login", data={"csrf_token": t, "identifier": "testadmin@example.com", "password": "Test@12345"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/dashboard")
    dash = c.get("/admin/dashboard")
    assert dash.status_code == 200
    t = token(dash.get_data(as_text=True))           # logout form on the page
    r = c.post("/admin/logout", data={"csrf_token": t})
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/login")
    assert c.get("/admin/dashboard").status_code == 302


def test_student_feedback_form_then_admin_sees_it(tmp_path):
    app = make_app(tmp_path, TESTING=False)
    student, admin = app.test_client(), app.test_client()
    t = token(student.get("/feedback").get_data(as_text=True))
    r = student.post("/feedback", data={"csrf_token": t, "text": "Teacher explanation super but wifi romba slow ah iruku.",
                                        "department": "CSE", "year": "2", "category": "Auto Detect", "language": "Auto Detect"})
    assert r.status_code == 302 and "/result/" in r.headers["Location"]
    assert student.get(r.headers["Location"]).status_code == 200
    t = token(admin.get("/admin/signup").get_data(as_text=True))
    admin.post("/admin/signup", data={"csrf_token": t, "username": "boss", "email": "boss@example.com",
                                      "password": "Boss@12345", "confirm": "Boss@12345"})
    t = token(admin.get("/admin/login").get_data(as_text=True))
    assert admin.post("/admin/login", data={"csrf_token": t, "identifier": "boss", "password": "Boss@12345"}).status_code == 302
    html = admin.get("/admin/feedback").get_data(as_text=True)
    assert "wifi romba slow" in html and "Academics" in html
    assert "wifi romba slow" in admin.get("/admin/feedback/1").get_data(as_text=True)


def test_login_without_csrf_token_is_rejected_not_logged_in(tmp_path):
    app = make_app(tmp_path, TESTING=False)
    c = app.test_client()
    t = token(c.get("/admin/signup").get_data(as_text=True))
    c.post("/admin/signup", data={"csrf_token": t, "username": "boss", "email": "boss@example.com",
                                  "password": "Boss@12345", "confirm": "Boss@12345"})
    c2 = app.test_client()
    r = c2.post("/admin/login", data={"identifier": "boss", "password": "Boss@12345"})
    assert r.status_code == 400 and c2.get("/admin/dashboard").status_code == 302
