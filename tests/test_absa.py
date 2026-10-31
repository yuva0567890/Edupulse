def aspects(r):
    return {a["aspect"]: a["sentiment"] for a in r["aspects"]}


def test_english_two_aspects(pipeline):
    a = aspects(pipeline.analyze("Teaching is very good but the WiFi is very slow."))
    assert a["Teaching"] == "Positive" and a["Wi-Fi"] == "Negative"


def test_tamil_aspects(pipeline):
    a = aspects(pipeline.analyze("ஆசிரியர் நன்றாக கற்பிக்கிறார் ஆனால் லேப் வசதிகள் குறைவாக உள்ளது."))
    assert a["Teaching"] == "Positive" and a["Lab/Infrastructure"] == "Negative"


def test_hindi_aspects(pipeline):
    a = aspects(pipeline.analyze("शिक्षक बहुत अच्छा पढ़ाते हैं लेकिन लैब की सुविधा अच्छी नहीं है।"))
    assert a["Teaching"] == "Positive" and a["Lab/Infrastructure"] == "Negative"


def test_tanglish_aspects(pipeline):
    a = aspects(pipeline.analyze("Teaching romba nalla iruku but lab equipment illa."))
    assert a["Teaching"] == "Positive" and a["Lab/Infrastructure"] == "Negative"


def test_code_mixed_aspects(pipeline):
    a = aspects(pipeline.analyze("Teacher explanation अच्छा है but WiFi बहुत slow है."))
    assert a["Teaching"] == "Positive" and a["Wi-Fi"] == "Negative"


def test_shared_clause_aspects(pipeline):
    a = aspects(pipeline.analyze("The teaching and lab facilities are good"))
    assert set(a) == {"Teaching", "Lab/Infrastructure"} and set(a.values()) == {"Positive"}


def test_course_content(pipeline):
    assert aspects(pipeline.analyze("The syllabus is outdated and too difficult"))["Course Content"] == "Negative"


def test_no_aspect_is_general(pipeline):
    r = pipeline.analyze("Everything was bad")
    assert r["aspects"] and r["sentiment"]["label"] == "Negative"
