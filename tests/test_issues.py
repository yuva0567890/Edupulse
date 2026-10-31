"""Categories in the database, issue tracking, admin responses, filters, CSV, dashboard statistics, migration."""
import sqlite3
from datetime import timedelta

from database import db
from database.models import utcnow


def post(client, text, **extra):
    r = client.post("/api/feedback", json={"text": text, **extra})
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.get_json()["id"]


def test_negative_feedback_creates_issue(client, admin_client):
    fid = post(client, "Hostel food is not good", department="CSE")
    d = admin_client.get(f"/api/feedback/{fid}").get_json()
    year = utcnow().year
    assert d["category"] == "Hostel" and d["status"] == "Open" and d["issue_id"] == f"EDU-{year}-0001"
    assert d["rows"][0]["aspect"] == "Food" and d["history"][0]["new"] == "Open"


def test_positive_feedback_has_no_issue_until_created(client, admin_client):
    fid = post(client, "The teaching is excellent")
    d = admin_client.get(f"/api/feedback/{fid}").get_json()
    assert d["issue"] is None and d["status"] == ""
    r = admin_client.post(f"/admin/feedback/{fid}/update", data={"action": "create_issue"})
    assert r.status_code == 302
    assert admin_client.get(f"/api/feedback/{fid}").get_json()["issue"]["status"] == "Open"


def test_issue_ids_are_sequential_and_unique(client, admin_client):
    ids = [admin_client.get(f"/api/feedback/{post(client, 'WiFi is not working')}").get_json()["issue_id"] for _ in range(3)]
    assert [i.rsplit("-", 1)[1] for i in ids] == ["0001", "0002", "0003"] and len(set(ids)) == 3


def test_status_workflow_and_history(client, admin_client):
    fid = post(client, "The WiFi is not working in Block C")
    for status in ("In Progress", "Resolved", "Closed"):
        r = admin_client.post(f"/api/feedback/{fid}/status", json={"status": status, "note": f"moved to {status}"})
        assert r.status_code == 200 and r.get_json()["new"] == status
    d = admin_client.get(f"/api/feedback/{fid}").get_json()
    assert d["status"] == "Closed" and [h["new"] for h in d["history"]] == ["Open", "In Progress", "Resolved", "Closed"]
    assert admin_client.post(f"/api/feedback/{fid}/status", json={"status": "Bogus"}).status_code == 400
    assert admin_client.post("/api/feedback/9999/status", json={"status": "Open"}).status_code == 404


def test_status_update_through_form_and_issues_page(client, admin_client):
    fid = post(client, "The WiFi is not working")
    admin_client.post(f"/admin/feedback/{fid}/update", data={"status": "In Progress", "note": "checking"})
    assert admin_client.get(f"/api/feedback/{fid}").get_json()["status"] == "In Progress"
    admin_client.post(f"/admin/issues/{fid}/status", data={"status": "Resolved"})
    listing = admin_client.get("/api/issues?status=Resolved").get_json()
    assert listing["total"] == 1 and listing["counts"]["resolved"] == 1


def test_admin_response_saved_and_visible_to_student(client, admin_client):
    r = client.post("/feedback", data={"text": "Wifi is very slow", "category": "Auto Detect"})
    url, fid = r.headers["Location"], int(r.headers["Location"].rsplit("/", 1)[1])
    assert "No response yet" in client.get(url).get_data(as_text=True)
    admin_client.post(f"/admin/feedback/{fid}/update", data={"response": "Access points in Block B are being upgraded.", "status": "In Progress"})
    page = client.get(url).get_data(as_text=True)
    assert "Access points in Block B are being upgraded." in page and "In Progress" in page
    d = admin_client.get(f"/api/feedback/{fid}").get_json()
    assert d["admin_response"].startswith("Access points") and d["responses"][0]["admin"] == "testadmin"
    assert admin_client.post(f"/api/feedback/{fid}/response", json={"response": "  "}).status_code == 400
    assert admin_client.post(f"/api/feedback/{fid}/response", json={"response": "Done", "status": "Resolved"}).status_code == 200


def test_form_category_selection_and_validation(client, admin_client):
    r = client.post("/feedback", data={"text": "Hostel food is not good", "category": "Academics"})
    fid = int(r.headers["Location"].rsplit("/", 1)[1])
    d = admin_client.get(f"/api/feedback/{fid}").get_json()
    assert d["category"] == "Academics" and d["category_detected"] == "Hostel" and d["category_selected"] == "Academics"
    assert client.post("/feedback", data={"text": "ok fine", "category": "Nope"}).status_code == 400
    assert client.post("/api/analyze", json={"text": "hello world", "category": "Nope"}).status_code == 400


def test_all_feedback_is_visible_and_filters_work(client, admin_client):
    post(client, "Teacher explanation is very poor", department="CSE", year="2")
    post(client, "Hostel food is not good", department="AI&DS", year="3")
    post(client, "College bus is always late", department="CSE", year="1")
    post(client, "ஆசிரியர் நன்றாக கற்பிக்கிறார்.", department="CSE")
    post(client, "Teacher explanation super but wifi romba slow ah iruku.")
    assert admin_client.get("/api/feedback?per_page=100").get_json()["total"] == 5

    def n(q):
        return admin_client.get("/api/feedback?" + q).get_json()["total"]
    assert n("category=Hostel") == 1 and n("category=Others") == 1 and n("category=Academics") == 3
    assert n("sentiment=Negative") == 4 and n("sentiment=Positive") == 1
    assert n("language=Tamil") == 1 and n("language=English") == 3 and n("language=Mixed") == 1
    assert n("aspect=Transport") == 1 and n("department=CSE") == 3 and n("year=2") == 1
    assert n("status=Open") == 4 and n("priority=LOW") >= 1
    assert n("search=bus") == 1 and n("search=zzzz") == 0
    assert n("category=Hostel&sentiment=Negative&department=AI%26DS") == 1
    assert n("date_from=2999-01-01") == 0 and n(f"date_from={utcnow().date().isoformat()}") == 5
    page = admin_client.get("/api/feedback?per_page=2&page=2&sort=id&dir=asc").get_json()
    assert [i["id"] for i in page["items"]] == [3, 4] and page["pages"] == 3
    html = admin_client.get("/admin/feedback?category=Hostel").get_data(as_text=True)
    assert "Hostel food is not good" in html and "College bus" not in html


def test_csv_export_contains_new_columns_and_respects_filters(client, admin_client):
    post(client, "Hostel food is not good", student_name="=EVIL()")
    post(client, "College bus is always late")
    r = admin_client.get("/admin/feedback/export.csv?category=Hostel")
    body = r.get_data(as_text=True)
    assert r.status_code == 200 and "category" in body.splitlines()[0] and "issue_id" in body.splitlines()[0]
    assert "Hostel food" in body and "College bus" not in body and "'=EVIL()" in body


def test_empty_database_stats_and_states(admin_client):
    s = admin_client.get("/api/dashboard/stats").get_json()
    assert s["total"] == 0 and s["categories"] == {"Academics": 0, "Hostel": 0, "Others": 0} and s["departments"] == []
    assert admin_client.get("/api/dashboard/trending?period=7").get_json()["status"] == "insufficient"
    assert admin_client.get("/api/dashboard/critical").get_json()["alerts"] == []
    assert admin_client.get("/api/dashboard/similar").get_json()["clusters"] == []
    assert admin_client.get("/api/dashboard/summary").get_json()["empty"] is True
    assert admin_client.get("/api/dashboard/recent").get_json()["items"] == []
    html = admin_client.get("/admin/dashboard").get_data(as_text=True)
    assert "No feedback available yet." in html


def test_dashboard_statistics_use_real_data(client, admin_client):
    post(client, "Teacher explanation is very poor", department="CSE")
    post(client, "Hostel food is not good", department="CSE")
    post(client, "Hostel food is tasty", department="AI&DS")
    post(client, "College bus is always late", department="AI&DS")
    s = admin_client.get("/api/dashboard/stats").get_json()
    assert s["total"] == 4 and s["categories"] == {"Academics": 1, "Hostel": 2, "Others": 1}
    assert s["negative_count"] == 3 and s["issues"]["open"] == 3 and s["issues"]["open_total"] == 3
    assert s["category_sentiment"]["Hostel"] == {"Positive": 1, "Neutral": 0, "Negative": 1}
    dept = {d["department"]: d for d in s["departments"]}
    assert dept["CSE"]["Academics"] == 1 and dept["CSE"]["Hostel"] == 1 and dept["AI&DS"]["Hostel"] == 1 and dept["AI&DS"]["Others"] == 1
    assert s["language_buckets"]["English"] == 4
    assert admin_client.get("/api/dashboard/stats?category=Hostel").get_json()["total"] == 2


def test_similar_complaints_recurring_issue_and_critical_alert(client, admin_client):
    for t in ("WiFi is very slow", "Wifi romba slow ah iruku", "Internet speed is poor", "WiFi बहुत slow है", "WiFi is slow in Block C"):
        post(client, t)
    post(client, "Hostel food is not good")
    sim = admin_client.get("/api/dashboard/similar").get_json()
    top = sim["clusters"][0]
    assert top["aspect"] == "Wi-Fi" and top["count"] == 5 and top["languages"]["Mixed"] == 2 and top["languages"]["English"] == 3
    assert admin_client.get("/api/dashboard/critical").get_json()["alerts"] == []        # not critical yet
    admin_client.post("/admin/settings", data={"action": "priority", "critical_min": "50", "high_min": "30", "medium_min": "10"})
    alerts = admin_client.get("/api/dashboard/critical").get_json()["alerts"]
    assert alerts and alerts[0]["aspect"] == "Wi-Fi" and alerts[0]["count"] == 5
    detail = admin_client.get("/admin/feedback/1").get_data(as_text=True)
    assert "similar complaint" in detail


def test_trending_with_real_history(client, admin_client, app, pipeline):
    now = utcnow()
    with app.app_context():
        for days, text in [(1, "WiFi is not working")] * 5 + [(2, "WiFi is slow")] * 2 + [(9, "WiFi is slow")] * 2 + [(10, "Teacher explanation is poor")] * 3 + [(11, "The teaching is good")] * 2:
            a = pipeline.analyze(text)
            db.save_feedback({"text": text}, a, "t", timestamp=now - timedelta(days=days))
    t = admin_client.get("/api/dashboard/trending?period=7").get_json()
    assert t["status"] == "ok"
    wifi = [x for x in t["items"] if x["aspect"] == "Wi-Fi"][0]
    assert wifi["recent"] == 7 and wifi["previous"] == 2 and wifi["change_pct"] == 250.0 and wifi["direction"] == "up"
    teach = [x for x in t["items"] if x["aspect"] == "Teaching"][0]
    assert teach["recent"] == 0 and teach["direction"] == "down" and teach["change_pct"] == -100.0
    assert admin_client.get("/api/dashboard/trending?period=90").get_json()["status"] == "insufficient"
    s = admin_client.get("/api/dashboard/summary?period=7").get_json()
    assert not s["empty"] and any("Wi-Fi" in b["en"] and "increased" in b["en"] for b in s["bullets"])


def test_summary_period_without_recent_data_is_empty(admin_client, app, pipeline):
    with app.app_context():
        a = pipeline.analyze("WiFi is slow")
        db.save_feedback({"text": "WiFi is slow"}, a, "t", timestamp=utcnow() - timedelta(days=40))
    assert admin_client.get("/api/dashboard/summary?period=7").get_json()["empty"] is True
    assert admin_client.get("/api/dashboard/summary?period=90").get_json()["empty"] is False


def test_new_admin_pages_render_with_data(client, admin_client):
    post(client, "Hostel food is not good", department="CSE")
    for p in ("/admin/dashboard", "/admin/analytics", "/admin/issues", "/admin/feedback", "/admin/feedback/1", "/admin/settings",
              "/admin/model-performance"):
        assert admin_client.get(p).status_code == 200, p
    for lang in ("ta", "hi"):
        admin_client.get(f"/set-language/{lang}")
        assert admin_client.get("/admin/dashboard").status_code == 200


def test_migration_adds_columns_and_backfills_old_database(tmp_path):
    """A database created by the previous EduPulse version keeps its data and gains the new columns."""
    from app import create_app
    path = tmp_path / "legacy.db"
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE feedback (id INTEGER PRIMARY KEY, timestamp DATETIME, student_name VARCHAR(120), student_id VARCHAR(60),
        department VARCHAR(120), year VARCHAR(20), course VARCHAR(160), language VARCHAR(40), language_hint VARCHAR(40),
        feedback_text TEXT, rating INTEGER);
    CREATE TABLE analysis_results (id INTEGER PRIMARY KEY, feedback_id INTEGER, sentiment VARCHAR(20), sentiment_confidence FLOAT,
        aspect VARCHAR(40), aspect_sentiment VARCHAR(20), aspect_confidence FLOAT, severity VARCHAR(20), priority VARCHAR(20),
        priority_score FLOAT, frequency INTEGER, explanation TEXT, recommendation TEXT, model_version VARCHAR(80), nlp_mode VARCHAR(60));
    INSERT INTO feedback VALUES (1,'2026-09-01 10:00:00','A','S1','CSE','2','DS','English','Auto Detect','The WiFi is very slow',3);
    INSERT INTO analysis_results VALUES (1,1,'Negative',0.9,'Wi-Fi','Negative',0.9,'High','MEDIUM',40.0,1,'{"clause": "The WiFi is very slow"}','{}','v','Fallback / Demo');
    """)
    con.commit()
    con.close()
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(path).replace("\\", "/"),
                      "AUTO_SEED": False})
    with app.app_context():
        d = db.feedback_detail(1)
        assert d["text"] == "The WiFi is very slow" and d["category"] == "Academics"
        assert d["issue_id"].startswith("EDU-2026-") and d["status"] == "Open"
    c = app.test_client()
    from tests.conftest import signup
    assert signup(c).status_code == 302
    c.post("/admin/login", data={"identifier": "testadmin", "password": "Test@12345"})
    assert c.get("/admin/feedback").status_code == 200 and c.get("/api/dashboard/stats").get_json()["total"] == 1


def test_seed_script_populates_demo_data(app):
    from scripts.seed_database import seed
    n = seed(app)
    assert n > 100
    with app.app_context():
        assert db.count_feedback() == n
        assert db.issue_counts()["total"] > 10
