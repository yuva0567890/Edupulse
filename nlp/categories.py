"""Feedback categories: Academics / Hostel / Others, and the Category -> Aspect hierarchy.

    Category (Academics | Hostel | Others)
        -> Aspect (Teaching, Food, Transport, ...)
            -> Sentiment -> Severity -> Priority

The detector is rule based and configurable:
  * ASPECT_CATEGORY maps every aspect to a category (edit below, or override in data/category_rules.json),
  * the aspect keyword lexicon lives in nlp/absa.py (multilingual: English, Tamil, Hindi, Tanglish),
  * the "Wi-Fi" aspect belongs to Hostel when the clause (or a feedback that has no academic aspect)
    talks about the hostel, otherwise to Academics (campus Wi-Fi).
"""
import json
import os

from . import absa

CATEGORIES = ["Academics", "Hostel", "Others"]
CATEGORY_CHOICES = ["Auto Detect"] + CATEGORIES

ASPECT_CATEGORY = {
    # Academics
    "Teaching": "Academics", "Lab/Infrastructure": "Academics", "Course Content": "Academics",
    "Exams": "Academics", "Assignments": "Academics", "Academic Support": "Academics", "Wi-Fi": "Academics",
    # Hostel
    "Food": "Hostel", "Room": "Hostel", "Cleanliness": "Hostel", "Water": "Hostel", "Electricity": "Hostel",
    "Security": "Hostel", "Maintenance": "Hostel", "Hostel Facilities": "Hostel",
    # Others
    "Transport": "Others", "Library": "Others", "Sports": "Others", "Events": "Others",
    "Administration": "Others", "Campus Facilities": "Others", "General": "Others",
}
ASPECT_FAMILY = {  # which aspects belong to which category (for UI grouping)
    c: [a for a, cat in ASPECT_CATEGORY.items() if cat == c and a != "General"] for c in CATEGORIES}

HOSTEL_CONTEXT = {"hostel", "hostels", "dorm", "dormitory", "hostellers", "mess", "warden", "wardens",
                  "roommate", "roommates"}
ACADEMIC_ASPECTS = {a for a, c in ASPECT_CATEGORY.items() if c == "Academics" and a != "Wi-Fi"}

CATEGORY_I18N = {
    "Academics": {"en": "Academics", "ta": "கல்வி", "hi": "शैक्षणिक"},
    "Hostel": {"en": "Hostel", "ta": "விடுதி", "hi": "हॉस्टल"},
    "Others": {"en": "Others", "ta": "பிற", "hi": "अन्य"},
    "Auto Detect": {"en": "Auto Detect", "ta": "தானாக கண்டறி", "hi": "स्वतः पहचानें"},
}


def category_of_aspect(aspect, hostel_context=False):
    if aspect == "Wi-Fi":
        return "Hostel" if hostel_context else "Academics"
    return ASPECT_CATEGORY.get(aspect, "Others")


def has_hostel_context(concept_tokens):
    return any(t in HOSTEL_CONTEXT for t in concept_tokens)


def categorize_aspects(segments_aspects, whole_concepts):
    """segments_aspects: list of (aspect, clause_concept_tokens). Returns {aspect: category}."""
    names = {a for a, _ in segments_aspects}
    text_hostel = has_hostel_context(whole_concepts)
    no_academics = not (names & ACADEMIC_ASPECTS)
    out = {}
    for aspect, toks in segments_aspects:
        ctx = has_hostel_context(toks) or (text_hostel and no_academics)
        out[aspect] = category_of_aspect(aspect, ctx)
    return out


def detect_category(aspect_rows):
    """Choose the feedback-level category from analysed aspect rows.

    aspect_rows: list of dicts with 'category', 'sentiment', 'priority_score'. Preference:
    the category of the highest-priority NEGATIVE aspect; otherwise the most mentioned category.
    Returns {'category', 'confidence', 'method', 'scores'}.
    """
    if not aspect_rows:
        return {"category": "Others", "confidence": 0.0, "method": "default", "scores": {c: 0 for c in CATEGORIES}}
    scores = {c: 0.0 for c in CATEGORIES}
    for r in aspect_rows:
        w = 1.0 + (r.get("priority_score", 0) / 100.0 if r.get("sentiment") == "Negative" else 0.0)
        scores[r["category"]] += w
    negatives = [r for r in aspect_rows if r.get("sentiment") == "Negative"]
    if negatives:
        top = max(negatives, key=lambda r: r.get("priority_score", 0))
        cat, method = top["category"], "top-negative-aspect"
    else:
        cat, method = max(scores, key=scores.get), "most-mentioned"
    total = sum(scores.values()) or 1.0
    explicit = [r for r in aspect_rows if r["aspect"] != "General"]
    return {"category": cat, "confidence": round(scores[cat] / total, 3) if explicit else 0.0,
            "method": method if explicit else "default", "scores": {k: round(v, 3) for k, v in scores.items()}}


def load_overrides(path):
    """Optional data/category_rules.json:
       {"aspect_category": {"Transport": "Others"}, "aspect_keywords": {"Transport": ["metro"]},
        "hostel_context": ["pg"]}"""
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return False
    for a, c in (cfg.get("aspect_category") or {}).items():
        if c in CATEGORIES:
            ASPECT_CATEGORY[a] = c
    for a, words in (cfg.get("aspect_keywords") or {}).items():
        absa.add_keywords(a, words)
    HOSTEL_CONTEXT.update(w.lower() for w in cfg.get("hostel_context", []))
    return True
