"""Language identification for Tamil, Hindi, English, Tanglish and code-mixed text.

1. Unicode script analysis (Tamil U+0B80-0BFF, Devanagari U+0900-097F, Latin).
2. For Latin-script text, a lexicon check for Romanized Tamil ("Tanglish") and
   Romanized Hindi ("Hinglish") marker words.
No external model is needed, so detection never fails offline.
"""
import re
from .multilingual_utils import TANGLISH_MARKERS, HINGLISH_MARKERS, ENGLISH_STOPWORDS

TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
LATIN_RE = re.compile(r"[A-Za-z]")
WORD_RE = re.compile(r"[A-Za-z']+")

LABELS = ["English", "Tamil", "Hindi", "Tanglish", "Hinglish",
          "Tamil + English", "Hindi + English", "Mixed", "Unknown"]


def script_counts(text: str) -> dict:
    return {"tamil": len(TAMIL_RE.findall(text)), "hindi": len(DEVANAGARI_RE.findall(text)),
            "latin": len(LATIN_RE.findall(text))}


def _res(lang, counts, conf, mixed):
    return {"language": lang, "scripts": counts, "confidence": round(float(conf), 2), "code_mixed": mixed}


def detect_language(text) -> dict:
    """Return {'language', 'scripts', 'confidence', 'code_mixed'}."""
    text = text if isinstance(text, str) else ""
    c = script_counts(text)
    total = sum(c.values())
    if total == 0:
        return _res("Unknown", c, 0.0, False)

    words = [w.lower() for w in WORD_RE.findall(text)]
    ta_rom = sum(1 for w in words if w in TANGLISH_MARKERS)
    hi_rom = sum(1 for w in words if w in HINGLISH_MARKERS)
    en = sum(1 for w in words if w in ENGLISH_STOPWORDS)
    ts, hs, ls = c["tamil"] / total, c["hindi"] / total, c["latin"] / total

    if c["tamil"] and c["hindi"]:
        return _res("Mixed", c, 0.6, True)
    if c["tamil"]:
        if ls >= 0.15 and words:
            return _res("Tamil + English", c, 0.8, True)
        return _res("Tamil", c, min(1.0, 0.7 + ts * 0.3), False)
    if c["hindi"]:
        if ls >= 0.15 and words:
            return _res("Hindi + English", c, 0.8, True)
        return _res("Hindi", c, min(1.0, 0.7 + hs * 0.3), False)

    n = max(len(words), 1)
    if ta_rom == 0 and hi_rom == 0:
        return _res("English", c, 0.9 if en else 0.7, False)
    if ta_rom >= hi_rom:
        return _res("Tanglish", c, min(0.95, 0.6 + ta_rom / n), True)
    return _res("Hinglish", c, min(0.95, 0.6 + hi_rom / n), True)


def primary_language(label: str) -> str:
    """Map a fine-grained label to Tamil / English / Hindi (for per-language metrics)."""
    if label in ("Tamil", "Tanglish", "Tamil + English"):
        return "Tamil"
    if label in ("Hindi", "Hinglish", "Hindi + English"):
        return "Hindi"
    if label == "English":
        return "English"
    return "Mixed"
