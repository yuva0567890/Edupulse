import re

PAGES = ["/", "/feedback", "/admin/login", "/healthz"]


def test_public_pages(client):
    for p in PAGES:
        assert client.get(p).status_code == 200, p
    assert client.get("/nope").status_code == 404


def test_css_js_served(client):
    for p in ("/static/css/style.css", "/static/js/app.js", "/static/js/dashboard.js"):
        assert client.get(p).status_code == 200


def test_ui_language_switch(client):
    client.get("/set-language/ta")
    assert "கருத்து அளிக்கவும்" in client.get("/").get_data(as_text=True)
    client.get("/set-language/hi")
    assert "फीडबैक दें" in client.get("/").get_data(as_text=True)
    client.get("/set-language/en")
    assert "Give Feedback" in client.get("/").get_data(as_text=True)


def test_submit_form_and_result_privacy(client, app):
    r = client.post("/feedback", data={"text": "Teaching romba nalla iruku but lab equipment illa.", "language": "Auto Detect"})
    assert r.status_code == 302
    url = r.headers["Location"]
    page = client.get(url)
    assert page.status_code == 200 and "Lab" in page.get_data(as_text=True)
    other = app.test_client()
    assert other.get(url).status_code == 404       # another visitor cannot read it


def test_form_validation(client):
    assert client.post("/feedback", data={"text": ""}).status_code == 400
    assert client.post("/feedback", data={"text": "ok fine", "rating": "x"}).status_code == 400
    assert client.post("/feedback", data={"text": "ok fine", "language": "Klingon"}).status_code == 400


def test_admin_requires_login(client):
    for p in ("/admin/dashboard", "/admin/feedback", "/admin/feedback/1", "/admin/model-performance", "/admin/settings",
              "/admin/feedback/export.csv", "/admin/issues", "/admin/analytics"):
        r = client.get(p)
        assert r.status_code == 302 and "/admin/login" in r.headers["Location"], p


def test_admin_pages_with_data(client, admin_client):
    client.post("/api/feedback", json={"text": "Teacher explanation अच्छा है but WiFi बहुत slow है.", "department": "CSE"})
    client.post("/api/feedback", json={"text": "ஆசிரியர் நன்றாக கற்பிக்கிறார்."})
    for p in ("/admin/dashboard", "/admin/feedback", "/admin/feedback/1", "/admin/model-performance", "/admin/settings",
              "/admin/issues", "/admin/analytics"):
        assert admin_client.get(p).status_code == 200, p
    html = admin_client.get("/admin/feedback?sentiment=Negative&sort=score&dir=desc&search=wifi").get_data(as_text=True)
    assert "WiFi" in html or "wifi" in html
    assert admin_client.get("/admin/feedback/999").status_code == 404


def test_csv_export(client, admin_client):
    client.post("/api/feedback", json={"text": "=cmd|' /C calc'!A0 wifi is slow"})
    r = admin_client.get("/admin/feedback/export.csv")
    body = r.get_data(as_text=True)
    assert r.status_code == 200 and r.mimetype == "text/csv" and "id,date,student" in body
    assert "'=cmd" in body                       # formula injection neutralised


def test_settings_update(admin_client, app):
    r = admin_client.post("/admin/settings", data={"action": "priority", "crit_Wi-Fi": "0.5", "frequency_cap": "8"})
    assert r.status_code == 302
    assert app.extensions["edupulse"]["pipeline"].priority_config.criticality["Wi-Fi"] == 0.5
    r = admin_client.post("/admin/settings", data={"action": "priority", "medium_min": "90", "high_min": "10"})
    assert app.extensions["edupulse"]["pipeline"].priority_config.medium_min != 90


def test_database_stores_rows(client, app):
    from database import db
    client.post("/api/feedback", json={"text": "Lab computers are poor and WiFi is slow"})
    with app.app_context():
        assert db.count_feedback() == 1
        assert len(db.feedback_detail(1)["rows"]) >= 2
