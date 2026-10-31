from datetime import timedelta
from database import db
from database.models import utcnow


def test_save_and_read_back(app, pipeline):
    with app.app_context():
        form = {"text": "WiFi is very slow", "department": "CS", "year": "2", "language": "Auto Detect", "rating": "2"}
        a = pipeline.analyze(form["text"], "Auto Detect")
        fid = db.save_feedback(form, a, "test")
        d = db.feedback_detail(fid)
        assert d["text"] == form["text"] and d["rows"][0]["aspect"] == "Wi-Fi" and d["rating"] == 2
        assert db.count_feedback() == 1
        assert db.feedback_detail(999) is None


def test_frequency_window(app, pipeline):
    with app.app_context():
        old = utcnow() - timedelta(days=60)
        form = {"text": "WiFi is not working", "language": "Auto Detect"}
        db.save_feedback(form, pipeline.analyze(form["text"]), "t", timestamp=old)
        db.save_feedback(form, pipeline.analyze(form["text"]), "t")
        assert db.frequency_count("Wi-Fi", utcnow(), 30) == 1
        assert db.frequency_count("Wi-Fi", utcnow(), 90) == 2
        assert db.frequency_count("Teaching", utcnow(), 90) == 0


def test_settings_roundtrip(app):
    with app.app_context():
        db.set_setting("k", {"a": 1})
        assert db.get_setting("k") == {"a": 1} and db.get_setting("missing", 5) == 5
