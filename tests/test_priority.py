from nlp.priority import PriorityConfig, compute_priority, detect_severity, level_for


def test_severity_rules():
    assert detect_severity(["very", "good"], "Positive") == "Low"
    assert detect_severity(["not", "working"], "Negative") == "Critical"
    assert detect_severity(["very", "bad"], "Negative") == "High"
    assert detect_severity(["not", "good"], "Negative") == "Medium"


def test_formula_and_normalisation():
    cfg = PriorityConfig()
    r = compute_priority("Critical", 5, "Teaching", cfg)      # 100 * 1 * 1 * 1.0
    assert r["score"] == 100.0 and r["level"] == "CRITICAL"
    low = compute_priority("Low", 0, "Wi-Fi", cfg)
    assert 0 <= low["score"] < 25 and low["level"] == "LOW"


def test_frequency_increases_score():
    a = compute_priority("High", 1, "Wi-Fi")["score"]
    b = compute_priority("High", 4, "Wi-Fi")["score"]
    assert b > a


def test_criticality_configurable():
    cfg = PriorityConfig.from_dict({"criticality": {"Wi-Fi": 0.2}})
    assert compute_priority("High", 5, "Wi-Fi", cfg)["score"] < compute_priority("High", 5, "Teaching", cfg)["score"]


def test_score_within_bounds_and_explained():
    r = compute_priority("Critical", 10_000, "Teaching")
    assert r["score"] <= 100 and all(r["why"][k] for k in ("en", "ta", "hi"))


def test_levels():
    cfg = PriorityConfig()
    assert [level_for(s, cfg) for s in (10, 30, 60, 90)] == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
