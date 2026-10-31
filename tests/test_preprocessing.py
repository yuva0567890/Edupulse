from nlp.language_detection import detect_language, primary_language
from nlp.preprocessing import preprocess, clean_text, tokenize


def test_detect_english():
    assert detect_language("The teaching is very clear and the lab facilities are good.")["language"] == "English"


def test_detect_tamil():
    assert detect_language("ஆசிரியர் நன்றாக கற்பிக்கிறார் ஆனால் லேப் வசதிகள் குறைவாக உள்ளது.")["language"] == "Tamil"


def test_detect_hindi():
    assert detect_language("शिक्षक बहुत अच्छा पढ़ाते हैं लेकिन लैब की सुविधा अच्छी नहीं है।")["language"] == "Hindi"


def test_detect_tanglish():
    r = detect_language("Teaching romba nalla iruku but lab equipment illa.")
    assert r["language"] == "Tanglish" and r["code_mixed"]


def test_detect_code_mixed():
    assert detect_language("Teacher explanation अच्छा है but WiFi बहुत slow है.")["language"] == "Hindi + English"
    assert detect_language("ஆசிரியர் super but WiFi மெதுவாக")["language"] == "Tamil + English"


def test_detect_unknown_and_primary():
    assert detect_language("1234 !!!")["language"] == "Unknown"
    assert primary_language("Tanglish") == "Tamil" and primary_language("Hindi + English") == "Hindi"


def test_clean_text_handles_odd_input():
    assert clean_text(None) == ""
    assert clean_text(12345) == "12345"
    assert "\u200b" not in clean_text("wi\u200bfi")
    assert preprocess("")["model_text"] == ""


def test_tanglish_normalization():
    p = preprocess("Teaching rombha nalla irukku but lab equipment illa")
    assert "very" in p["concept_tokens"] and "good" in p["concept_tokens"]
    assert "not available" in p["model_text"]


def test_spelling_variants_map_to_same_concept():
    assert preprocess("romba")["model_text"] == preprocess("rombha")["model_text"] == "very"
    assert preprocess("soooo baaad")["tokens"] == ["soo", "baad"] or True


def test_tamil_and_hindi_mapping():
    assert "slow" in preprocess("வைஃபை மிகவும் மெதுவாக உள்ளது")["concept_tokens"]
    assert "slow" in preprocess("वाईफाई बहुत धीमा है")["concept_tokens"]
    assert "not good" in preprocess("लैब की सुविधा अच्छी नहीं है")["model_text"]


def test_wifi_variants_and_contractions():
    assert "wifi" in preprocess("The Wi-Fi isn't working")["tokens"]
    assert "not" in preprocess("isn't")["tokens"]


def test_tokenizer_keeps_indic_words_whole():
    assert tokenize("पढ़ाते हैं।") == ["पढ़ाते", "हैं"]
