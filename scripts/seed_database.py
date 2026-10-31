"""Load the DEMO feedback (data/sample_feedback.csv) through the real NLP pipeline into the database.

The demo rows are synthetic, not real college data.
Usage:  python scripts/seed_database.py [--reset]
"""
import argparse
import csv
import os
import random
import sys
from datetime import timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def seed(app, path=None, reset=False):
    from database import db
    from database.models import utcnow
    from routes.common import get_pipeline, model_version
    path = path or app.config["SAMPLE_DATA"]
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found - run scripts/generate_dataset.py first")
    with app.app_context():
        if reset:
            db.delete_all_feedback()
        pipe = get_pipeline()
        cfg = pipe.priority_config
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        rows.sort(key=lambda r: -int(r["days_ago"]))      # oldest first so frequency builds up chronologically
        rnd = random.Random(1)
        now = utcnow()
        n = 0
        for r in rows:
            ts = now - timedelta(days=int(r["days_ago"]), hours=rnd.randint(0, 12), minutes=rnd.randint(0, 59))
            try:
                analysis = pipe.analyze(r["feedback_text"], r.get("language_hint"),
                                        freq_lookup=lambda a, ts=ts: db.frequency_count(a, ts, cfg.window_days))
            except Exception as e:
                print("skip:", e)
                continue
            form = {"text": r["feedback_text"], "student_name": r["student_name"], "student_id": r["student_id"],
                    "department": r["department"], "year": r["year"], "course": r["course"],
                    "language": r.get("language_hint") or "Auto Detect", "rating": r["rating"]}
            db.save_feedback(form, analysis, model_version(), timestamp=ts)
            n += 1
        return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete existing feedback first")
    a = ap.parse_args()
    from app import create_app
    count = seed(create_app(), reset=a.reset)
    print(f"Seeded {count} demo feedback rows.")
