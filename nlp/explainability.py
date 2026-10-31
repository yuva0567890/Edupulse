"""TF-IDF explainability.

For a linear TF-IDF model the contribution of a term to the predicted class is
    contribution = tfidf_weight(term in this text) x coefficient(term, predicted class)
We list the terms with the largest positive contribution, show the student's original word
next to the normalised one (e.g. "slow (धीमा)"), and phrase the result in plain language in
English, Tamil and Hindi so an administrator can understand *why* a label was given.
"""
from . import multilingual_utils as mu
from .recommendations import SENT_I18N

_STOP2 = {"is", "are", "the", "a", "an", "of", "and", "was", "to", "in", "it", "but", "our", "this", "that", "ah",
          "iruku", "lekin", "aur", "ஆனால்", "மற்றும்", "लेकिन", "और", "है", "हैं", "की", "का", "के", "ஆக", "உள்ளது", "with"}
_SKIP = {"is", "are", "the", "a", "an", "of", "and", "was", "to", "in", "it", "ah", "ஆக", "है", "हैं", "की", "का",
         "के", "iruku", "இருக்கிறது", "but", "very", "இல்", "ni"}


def _surface_for(term, pairs):
    """Original student wording for a normalised term (exact phrase match first)."""
    for surf, concept in pairs:
        if concept == term:
            return surf.lower()
    surfaces, used = [], set()
    for w in term.split():
        for i, (surf, concept) in enumerate(pairs):
            if i not in used and w in concept.split():
                used.add(i)
                if surf.lower() not in surfaces:
                    surfaces.append(surf.lower())
                break
    return " ".join(surfaces)


def _lexicon_terms(prep, label):
    pol = {"Positive": mu.POSITIVE_WORDS, "Negative": mu.NEGATIVE_WORDS, "Neutral": mu.NEUTRAL_WORDS}[label]
    terms = []
    toks = prep["concept_tokens"]
    for i, t in enumerate(toks):
        if t in pol:
            neg = any(x in mu.NEGATORS for x in toks[max(0, i - 2):i])
            term = ("not " if neg else "") + t
            terms.append({"term": term, "surface": _surface_for(t, prep["pairs"]), "contribution": 1.0})
    for t in toks:  # explicit negations such as "not working"
        pass
    return terms


def explain_sentiment(engine, prep, label, top_k=5):
    """Return {'terms': [...], 'method': str}. Never raises."""
    terms = []
    method = "lexicon"
    try:
        if engine.bundle is not None and prep["model_text"]:
            pipe = engine.bundle["sentiment"]
            vec, clf = pipe.named_steps["tfidf"], pipe.named_steps["clf"]
            X = vec.transform([prep["model_text"]])
            names = vec.get_feature_names_out()
            ci = list(clf.classes_).index(label)
            coef = clf.coef_[ci]
            row = X.tocoo()
            raw = []
            for j, v in zip(row.col, row.data):
                c = float(v * coef[j])
                nm = names[j]
                words = nm.split()
                if c <= 0 or nm in _SKIP:
                    continue
                if len(words) > 1 and any(w in _STOP2 for w in words):
                    continue   # bigrams like "is very" / "clear and" are noise
                raw.append((nm, c))
            raw.sort(key=lambda x: -x[1])
            # prefer informative phrases: drop a unigram already contained in a listed bigram
            chosen = []
            for name, c in raw:
                if any((" " in o and name in o.split()) for o, _ in chosen):
                    continue
                chosen.append((name, c))
            total = sum(c for _, c in chosen) or 1.0
            terms = [{"term": n, "surface": _surface_for(n, prep["pairs"]), "contribution": round(c, 4),
                      "share": round(100 * c / total, 1)} for n, c in chosen[:top_k]]
            method = "tfidf-logreg"
    except Exception:
        terms = []
    if not terms:
        terms = _lexicon_terms(prep, label)[:top_k]
        n = len(terms) or 1
        for t in terms:
            t["share"] = round(100.0 / n, 1)
    for t in terms:
        s = t.get("surface", "")
        t["display"] = t["term"] if (not s or s == t["term"]) else f"{t['term']} ({s})"
    return {"terms": terms, "method": method}


def explanation_text(label, terms):
    shown = ", ".join(f"\"{t['display']}\"" for t in terms) if terms else "-"
    s = SENT_I18N
    if not terms:
        return {"en": f"Classified as {label}. No single dominant term was found (short or neutral wording).",
                "ta": f"{s[label]['ta']} என வகைப்படுத்தப்பட்டது. தெளிவான முக்கிய சொல் எதுவும் இல்லை.",
                "hi": f"{s[label]['hi']} के रूप में वर्गीकृत। कोई प्रमुख शब्द नहीं मिला।"}
    return {"en": f"Classified as {label} mainly because of these terms: {shown}.",
            "ta": f"{s[label]['ta']} என வகைப்படுத்தப்பட்டதற்கான முக்கிய சொற்கள்: {shown}.",
            "hi": f"{s[label]['hi']} के रूप में वर्गीकृत होने के मुख्य शब्द: {shown}।"}
