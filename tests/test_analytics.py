from datetime import datetime, timedelta

from nlp.analytics import (build_summary, canonical_issue_text, cluster_complaints, critical_alerts,
                           language_bucket, similar_feedback_ids, trending_issues)
from nlp.priority import PriorityConfig

NOW = datetime(2026, 10, 7, 12, 0)


def row(fid, days, aspect="Wi-Fi", clause="WiFi is very slow", lang="English", sev="High", cat="Academics", sent="Negative"):
    return {"feedback_id": fid, "timestamp": NOW - timedelta(days=days), "language": lang, "category": cat,
            "aspect": aspect, "sentiment": sent, "severity": sev, "priority": "HIGH", "score": 60.0,
            "clause": clause, "department": "CSE", "term": ""}


def test_same_issue_in_four_languages_has_one_canonical_form():
    forms = {canonical_issue_text(t) for t in ["WiFi is very slow", "Wifi romba slow ah iruku",
                                                "Internet speed is poor", "WiFi बहुत slow है"]}
    assert forms == {"wifi slow"}


def test_clustering_groups_similar_and_separates_different():
    rows = [row(1, 1, clause="WiFi is very slow"), row(2, 1, clause="Wifi romba slow ah iruku", lang="Tanglish"),
            row(3, 2, clause="Internet speed is poor"), row(4, 2, clause="WiFi बहुत slow है", lang="Hindi + English"),
            row(5, 2, clause="The wifi is not working at all", sev="Critical"),
            row(6, 3, aspect="Food", clause="Hostel food is tasteless", cat="Hostel")]
    cl = cluster_complaints(rows, PriorityConfig())
    slow = [c for c in cl if c["aspect"] == "Wi-Fi" and c["count"] >= 4]
    assert len(slow) == 1 and slow[0]["languages"]["Mixed"] == 2 and slow[0]["languages"]["English"] == 2
    assert any(c["aspect"] == "Food" and c["count"] == 1 for c in cl)
    assert similar_feedback_ids(cl, 1)[0]["others"] == sorted({2, 3, 4})


def test_threshold_is_configurable():
    rows = [row(1, 1, clause="wifi slow lab"), row(2, 1, clause="wifi crashes often")]
    assert len(cluster_complaints(rows, PriorityConfig(similarity_threshold=0.9))) == 2
    assert len(cluster_complaints(rows, PriorityConfig(similarity_threshold=0.05))) == 1


def test_positive_rows_are_not_clustered():
    assert cluster_complaints([row(1, 1, sent="Positive")], PriorityConfig()) == []


def test_critical_alerts_use_configured_threshold():
    rows = [row(i, 1, clause="WiFi is not working", sev="Critical") for i in range(1, 7)]
    cfg = PriorityConfig()
    cl = cluster_complaints(rows, cfg)
    assert cl[0]["score"] == 85.0 and len(critical_alerts(cl, cfg)) == 1
    assert critical_alerts(cl, PriorityConfig(critical_min=95)) == []
    assert critical_alerts(cluster_complaints([row(1, 1)], cfg), cfg) == []     # a single complaint is not critical


def test_trend_insufficient_data_is_reported_not_faked():
    rows = [row(1, 1)]
    t = trending_issues(rows, [r["timestamp"] for r in rows], 7, NOW)
    assert t["status"] == "insufficient" and "Not enough historical data" in t["message"] and t["items"] == []
    assert trending_issues([], [], 30, NOW)["status"] == "insufficient"


def test_trend_percentages():
    rows = [row(i, 1) for i in range(1, 7)] + [row(10 + i, 9) for i in range(1, 4)]          # 6 recent vs 3 previous
    rows += [row(30 + i, 2, aspect="Teaching", clause="teaching is poor") for i in range(2)]
    rows += [row(40 + i, 10, aspect="Teaching", clause="teaching is poor") for i in range(4)]  # 2 recent vs 4 previous
    t = trending_issues(rows, [r["timestamp"] for r in rows], 7, NOW)
    by = {x["aspect"]: x for x in t["items"]}
    assert t["status"] == "ok" and by["Wi-Fi"]["change_pct"] == 100.0 and by["Wi-Fi"]["direction"] == "up"
    assert by["Teaching"]["change_pct"] == -50.0 and by["Teaching"]["direction"] == "down"


def test_trend_new_issue_has_no_percentage():
    rows = [row(i, 1) for i in range(1, 4)] + [row(10 + i, 9, aspect="Food", clause="food poor", cat="Hostel", sent="Positive") for i in range(3)]
    t = trending_issues(rows, [r["timestamp"] for r in rows], 7, NOW)
    wifi = [x for x in t["items"] if x["aspect"] == "Wi-Fi"]
    assert wifi and wifi[0]["direction"] == "new" and wifi[0]["change_pct"] is None


def test_summary_is_generated_from_data_only():
    items = [{"id": i, "_dt": NOW - timedelta(days=1), "sentiment": "Negative", "category": "Hostel", "language": "Tanglish"} for i in range(1, 4)]
    rows = [row(i, 1, aspect="Food", clause="hostel food poor", cat="Hostel") for i in range(1, 4)]
    cl = cluster_complaints(rows, PriorityConfig())
    s = build_summary(items, rows, cl, None, {"open": 3, "in_progress": 0, "critical": 0}, 7, NOW)
    text = " ".join(b["en"] for b in s["bullets"])
    assert "3 feedback" in text and "Hostel received the most complaints (3)" in text and "Tanglish" in text
    assert all(set(b) == {"en", "ta", "hi"} for b in s["bullets"])


def test_summary_empty_state():
    s = build_summary([], [], [], None, {}, 7, NOW)
    assert s["empty"] and not s["bullets"] and "No feedback" in s["message"]


def test_language_buckets():
    assert [language_bucket(x) for x in ("English", "Tamil", "Hindi", "Tanglish", "Hinglish", "Tamil + English", "Mixed")] == \
        ["English", "Tamil", "Hindi", "Mixed", "Mixed", "Mixed", "Mixed"]
