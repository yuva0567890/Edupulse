import pytest
from nlp.categories import CATEGORIES, category_of_aspect, detect_category, ASPECT_CATEGORY

CASES = [
    # (text, category, aspect, sentiment)
    ("Teacher explanation is very poor", "Academics", "Teaching", "Negative"),
    ("Hostel food is not good", "Hostel", "Food", "Negative"),
    ("College bus is always late", "Others", "Transport", "Negative"),
    ("The library is very good", "Others", "Library", "Positive"),
    ("The mess food is tasty", "Hostel", "Food", "Positive"),
    ("The syllabus is outdated and too difficult", "Academics", "Course Content", "Negative"),
    ("No water in hostel, very bad", "Hostel", "Water", "Negative"),
    ("விடுதி உணவு நன்றாக இல்லை", "Hostel", "Food", "Negative"),
    ("கல்லூரி பேருந்து எப்போதும் தாமதம்", "Others", "Transport", "Negative"),
    ("होस्टल का खाना अच्छा नहीं है", "Hostel", "Food", "Negative"),
    ("hostel saapadu nalla illa", "Hostel", "Food", "Negative"),
    ("शिक्षक अच्छा पढ़ाते हैं", "Academics", "Teaching", "Positive"),
]


@pytest.mark.parametrize("text,category,aspect,sentiment", CASES)
def test_category_aspect_sentiment(pipeline, text, category, aspect, sentiment):
    r = pipeline.analyze(text)
    assert r["category"]["final"] == category, r["category"]
    top = [a for a in r["aspects"] if a["aspect"] == aspect]
    assert top, [a["aspect"] for a in r["aspects"]]
    assert top[0]["sentiment"] == sentiment and top[0]["category"] == category


def test_hierarchy_fields_present(pipeline):
    r = pipeline.analyze("Hostel food is not good")
    a = r["aspects"][0]
    assert a["category"] == "Hostel" and a["aspect"] == "Food" and a["sentiment"] == "Negative"
    assert a["severity"] in ("Low", "Medium", "High", "Critical") and 0 <= a["priority"]["score"] <= 100


def test_wifi_category_depends_on_context(pipeline):
    assert pipeline.analyze("The campus wifi is very slow")["category"]["final"] == "Academics"
    assert pipeline.analyze("The hostel wifi is very slow")["category"]["final"] == "Hostel"
    assert category_of_aspect("Wi-Fi", True) == "Hostel" and category_of_aspect("Wi-Fi") == "Academics"


def test_four_original_aspects_kept_in_academics():
    for a in ("Teaching", "Lab/Infrastructure", "Course Content", "Wi-Fi"):
        assert a in ASPECT_CATEGORY


def test_mixed_feedback_takes_worst_aspect_category(pipeline):
    r = pipeline.analyze("The teaching is good but the hostel food is terrible")
    cats = {a["aspect"]: a["category"] for a in r["aspects"]}
    assert cats["Teaching"] == "Academics" and cats["Food"] == "Hostel"
    assert r["category"]["final"] == "Hostel"


def test_student_choice_is_kept_and_mismatch_flagged(pipeline):
    r = pipeline.analyze("Hostel food is not good", category_hint="Academics")
    assert r["category"]["final"] == "Academics" and r["category"]["detected"] == "Hostel" and r["category"]["mismatch"]
    r = pipeline.analyze("Hostel food is not good", category_hint="Auto Detect")
    assert r["category"]["final"] == "Hostel" and not r["category"]["mismatch"]


def test_unknown_text_defaults_to_others(pipeline):
    r = pipeline.analyze("Everything is okay I guess")
    assert r["category"]["final"] in CATEGORIES


def test_detect_category_empty():
    assert detect_category([])["category"] == "Others"


@pytest.mark.parametrize("text", [
    "ஆசிரியர் நன்றாக கற்பிக்கிறார் ஆனால் வைஃபை மிகவும் மெதுவாக உள்ளது",
    "The teaching is good but the Wi-Fi is very slow.",
    "शिक्षक अच्छा पढ़ाते हैं लेकिन वाईफाई बहुत धीमा है।",
    "Teacher explanation super but wifi romba slow ah iruku."])
def test_required_four_language_examples(pipeline, text):
    r = pipeline.analyze(text)
    got = {a["aspect"]: a["sentiment"] for a in r["aspects"]}
    assert got["Teaching"] == "Positive" and got["Wi-Fi"] == "Negative"
    assert r["category"]["final"] == "Academics" and r["sentiment"]["label"] == "Negative"
