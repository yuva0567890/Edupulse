import pytest
from nlp.absa import segment_feedback
from nlp.pipeline import FeedbackError
from nlp.recommendations import recommend
from nlp.sentiment import lexicon_sentiment

CASES = [
    ("English", "The WiFi is very bad and the internet is not working at all.", "Negative"),
    ("English", "Teaching is very good and explanations are clear.", "Positive"),
    ("Tamil", "வைஃபை மிகவும் மோசமாக உள்ளது", "Negative"),
    ("Tamil", "ஆசிரியர்களின் விளக்கம் மிகவும் நன்றாக உள்ளது", "Positive"),
    ("Hindi", "कंप्यूटर लैब बहुत खराब है", "Negative"),
    ("Hindi", "पाठ्यक्रम बहुत बढ़िया है", "Positive"),
    ("Tanglish", "wifi romba mosam", "Negative"),
    ("Tanglish", "teaching romba nalla iruku", "Positive"),
]


@pytest.mark.parametrize("lang,text,expected", CASES)
def test_overall_sentiment(pipeline, lang, text, expected):
    r = pipeline.analyze(text)
    assert r["sentiment"]["label"] == expected
    assert 0.0 < r["sentiment"]["confidence"] <= 1.0


def test_mixed_feedback_aspects(pipeline):
    r = pipeline.analyze("Teacher explanation super but WiFi romba slow.")
    got = {a["aspect"]: a["sentiment"] for a in r["aspects"]}
    assert got["Wi-Fi"] == "Negative" and got["Teaching"] == "Positive"
    assert r["sentiment"]["label"] == "Negative"


def test_tamil_and_hindi_multi_aspect(pipeline):
    r = pipeline.analyze("ஆசிரியர் நன்றாக கற்பிக்கிறார் ஆனால் லேப் வசதிகள் குறைவாக உள்ளது.")
    got = {a["aspect"]: a["sentiment"] for a in r["aspects"]}
    assert got["Teaching"] == "Positive" and got["Lab/Infrastructure"] == "Negative"
    r = pipeline.analyze("शिक्षक बहुत अच्छा पढ़ाते हैं लेकिन लैब की सुविधा अच्छी नहीं है।")
    got = {a["aspect"]: a["sentiment"] for a in r["aspects"]}
    assert got["Teaching"] == "Positive" and got["Lab/Infrastructure"] == "Negative"


def test_segmentation_keeps_shared_predicate():
    segs = segment_feedback("The teaching and lab facilities are good")
    assert len(segs) == 1 and len(segs[0]["aspects"]) == 2


def test_all_four_aspects_detected():
    segs = segment_feedback("Teaching is good. The lab is poor. Syllabus is outdated. WiFi is slow.")
    found = {a for s in segs for a, _ in s["aspects"]}
    assert found == {"Teaching", "Lab/Infrastructure", "Course Content", "Wi-Fi"}


def test_explainability_terms_present(pipeline):
    r = pipeline.analyze("WiFi is very slow and poor")
    terms = [t["term"] for t in r["explanation"]["terms"]]
    assert terms and any(t in ("slow", "poor", "very slow", "wifi") or "slow" in t or "poor" in t for t in terms)
    assert set(r["explanation"]["text"]) == {"en", "ta", "hi"}


def test_recommendations_all_languages():
    for aspect in ("Teaching", "Lab/Infrastructure", "Course Content", "Wi-Fi"):
        rec = recommend(aspect, "Negative", "HIGH", 4)
        assert rec["en"] and rec["ta"] and rec["hi"] and rec["escalate"]
    assert not recommend("Wi-Fi", "Negative", "LOW", 1)["escalate"]
    assert "network" in recommend("Wi-Fi", "Negative")["en"].lower()


def test_lexicon_fallback_negation():
    assert lexicon_sentiment(["not", "good"])[0] == "Negative"
    assert lexicon_sentiment(["very", "good"])[0] == "Positive"
    assert lexicon_sentiment([])[0] == "Neutral"


def test_fallback_without_model(tmp_path):
    from nlp.pipeline import EduPulsePipeline
    p = EduPulsePipeline(str(tmp_path), data_path=str(tmp_path / "missing.csv"))
    assert p.mode == "Fallback / Demo"
    assert p.analyze("The wifi is terrible")["sentiment"]["label"] == "Negative"


@pytest.mark.parametrize("bad", ["", "   ", "a", None, "1234", "😀"])
def test_invalid_input_raises_cleanly(pipeline, bad):
    with pytest.raises(FeedbackError):
        pipeline.analyze(bad)


def test_unusual_unicode_does_not_crash(pipeline):
    pipeline.analyze("wifi \u200b\u0000 slow 🙁 \u202e bad")
    pipeline.analyze("x" * 4000 + " wifi slow")
