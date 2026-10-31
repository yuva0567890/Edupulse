"""Text preprocessing, tokenization and Tanglish / code-mixed normalisation.

Pipeline for one text:
    raw -> clean (Unicode NFC, control chars, emoji, contractions)
        -> tokenize (script-aware: Tamil / Devanagari / Latin / digits)
        -> normalise spelling variants (romba/rombha, bahut/bohot, ...)
        -> map every token (or phrase) to a shared English "concept" token
        -> model_text (space separated concept tokens used by TF-IDF models)

The (surface, concept) pairs are kept so explanations can show the student's
original word next to its normalised meaning.
"""
import re
import unicodedata
from . import multilingual_utils as mu

MAX_CHARS = 5000

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WIFI_RE = re.compile(r"wi[\s\-_]?fi|வை[\s\-]?ஃ?பை|वाई[\s\-]?फाई", re.IGNORECASE)
_TOKEN_RE = re.compile(
    r"[\u0B80-\u0BFF]+"                      # Tamil
    r"|[\u0900-\u0963\u0966-\u097F]+(?:-[\u0900-\u0963\u0966-\u097F]+)?"  # Devanagari (danda excluded)
    r"|[A-Za-z]+(?:'[A-Za-z]+)?"             # Latin
    r"|\d+"                                  # digits
    r"|[,;.!?\u0964\n&]"                     # punctuation we keep for clause splitting
)
_REPEAT_RE = re.compile(r"(.)\1{2,}")


def _nfc_dict(d):
    return {unicodedata.normalize("NFC", k): v for k, v in d.items()}


_NATIVE = _nfc_dict(mu.NATIVE_TO_ENGLISH)
_ROMAN = {k.lower(): v for k, v in mu.ROMAN_TO_ENGLISH.items()}
_PHRASES = {tuple(unicodedata.normalize("NFC", p) for p in k): v for k, v in mu.PHRASES.items()}
_MAX_PHRASE = max(len(k) for k in _PHRASES)


def clean_text(text) -> str:
    """Safe, idempotent cleaning. Never raises for odd input."""
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""
    text = text[:MAX_CHARS]
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_ZERO_WIDTH)
    text = _CONTROL_RE.sub(" ", text)
    for emo, word in mu.EMOJI_MAP.items():
        text = text.replace(emo, word)
    text = _WIFI_RE.sub("wifi", text)
    text = re.sub(r"(?i)\b(\w+)n['’]t\b", r"\1 not", text)   # isn't -> is not
    text = text.replace("’", "'")
    text = re.sub(r"[ \t\r\f\v]+", " ", text).strip()
    return text


def tokenize(text: str, keep_punct: bool = False):
    """Script-aware tokenizer. Latin tokens are lowercased."""
    toks = []
    for m in _TOKEN_RE.findall(text or ""):
        if len(m) == 1 and m in ",;.!?\u0964\n&":
            if keep_punct:
                toks.append(m)
            continue
        toks.append(m.lower() if m.isascii() else m)
    return toks


def normalize_token(tok: str) -> str:
    """Collapse elongations (sooo -> soo) and map Romanized spelling variants."""
    if tok.isascii():
        tok = _REPEAT_RE.sub(r"\1\1", tok.lower())
        tok = mu.ENGLISH_CONTRACTIONS.get(tok, tok)
        tok = mu.ROMAN_SPELLING_VARIANTS.get(tok, tok)
    return tok


def _strip_tamil_suffix(tok: str):
    for suf in sorted(mu.TAMIL_SUFFIXES, key=len, reverse=True):
        if tok.endswith(suf) and len(tok) - len(suf) >= 2:
            stem = tok[: -len(suf)]
            if stem in _NATIVE:
                return _NATIVE[stem]
    return None


def to_concept(tok: str) -> str:
    if tok in _NATIVE:
        return _NATIVE[tok]
    if tok in _ROMAN:
        return _ROMAN[tok]
    if re.match(r"[\u0B80-\u0BFF]", tok):
        s = _strip_tamil_suffix(tok)
        if s is not None:
            return s
    return tok


def concept_pairs(tokens):
    """Return list of (surface, concept) pairs, applying phrase rules first."""
    norm = [normalize_token(t) for t in tokens]
    pairs, i = [], 0
    while i < len(norm):
        matched = False
        for n in range(min(_MAX_PHRASE, len(norm) - i), 0, -1):
            key = tuple(norm[i:i + n])
            if key in _PHRASES and (n > 1 or key[0] in ("puriyala",)):
                pairs.append((" ".join(tokens[i:i + n]), _PHRASES[key]))
                i += n
                matched = True
                break
        if matched:
            continue
        pairs.append((tokens[i], to_concept(norm[i])))
        i += 1
    return pairs


def preprocess(text) -> dict:
    """Full preprocessing. Always returns a dict (empty fields for empty input)."""
    cleaned = clean_text(text)
    tokens = tokenize(cleaned)
    pairs = concept_pairs(tokens)
    concept_tokens = [w for _, c in pairs for w in c.split() if w]
    return {
        "original": text if isinstance(text, str) else (cleaned or ""),
        "cleaned": cleaned,
        "tokens": tokens,
        "pairs": pairs,
        "concept_tokens": concept_tokens,
        "model_text": " ".join(concept_tokens),
    }
