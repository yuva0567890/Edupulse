"""Aspect-Based Sentiment Analysis (ABSA).

Four main aspects (from the EduPulse design): Teaching, Lab/Infrastructure,
Course Content, Wi-Fi.

Approach
  1. Split the feedback into clauses at hard connectors (but / ஆனால் / लेकिन /
     aana / lekin ...) and punctuation. Soft connectors (and / aur / ,) split only
     when both sides look like complete opinions (each has an aspect keyword and a
     polarity word) - so "teaching and lab are good" stays one clause.
  2. Detect aspects per clause with a multilingual keyword lexicon applied to the
     normalised "concept" tokens (rule-based NLP). A trained TF-IDF aspect
     classifier is used as a fallback when no keyword matches.
  3. The caller scores each clause's sentiment with the sentiment engine.
"""
from . import multilingual_utils as mu
from .preprocessing import tokenize, preprocess, normalize_token, concept_pairs

# The four original EduPulse aspects (kept) + additional aspects for the Hostel / Others categories.
ASPECTS = ["Teaching", "Lab/Infrastructure", "Course Content", "Wi-Fi"]
EXTRA_ASPECTS = ["Exams", "Assignments", "Academic Support",
                 "Food", "Room", "Cleanliness", "Water", "Electricity", "Security", "Maintenance", "Hostel Facilities",
                 "Transport", "Library", "Sports", "Events", "Administration", "Campus Facilities"]
ALL_ASPECTS = ASPECTS + EXTRA_ASPECTS
GENERAL = "General"
# Generic aspects are dropped when a more specific aspect appears in the same clause
GENERIC_ASPECTS = {"Hostel Facilities", "Campus Facilities"}
WEAK_KEYWORDS = {"Lab/Infrastructure": {"facility", "facilities", "infrastructure"}}

ASPECT_KEYWORDS = {
    "Teaching": {"teaching", "teach", "teaches", "teacher", "teachers", "faculty", "faculties", "lecturer",
                 "lecturers", "professor", "professors", "explanation", "explain", "explains", "explained",
                 "lecture", "lectures", "mentor", "mentors", "staff", "pace", "instructor", "instructors",
                 "sir", "madam", "tutor", "classes", "mentoring"},
    "Lab/Infrastructure": {"lab", "labs", "laboratory", "laboratories", "computer", "computers", "equipment",
                           "equipments", "classroom", "classrooms", "infrastructure", "facility", "facilities",
                           "projector", "projectors", "furniture", "bench", "benches", "building",
                           "fan", "fans", "seating", "machines", "systems", "hardware"},
    "Course Content": {"syllabus", "content", "course", "courses", "subject", "subjects", "material",
                       "materials", "curriculum", "portion", "portions", "lesson", "lessons", "topics",
                       "topic", "textbook", "textbooks", "books", "difficulty", "practical", "practicals", "notes"},
    "Wi-Fi": {"wifi", "internet", "network", "connectivity", "bandwidth", "router", "routers", "connection",
              "signal", "broadband", "hotspot", "disconnect", "disconnects", "disconnecting", "online",
              "speed", "lan"},
    "Exams": {"exam", "exams", "examination", "test", "tests", "marks", "results", "evaluation", "valuation",
              "timetable", "invigilation", "question", "paper", "papers"},
    "Assignments": {"assignment", "assignments", "homework", "deadline", "deadlines", "submission",
                    "submissions", "project", "projects", "record", "workload"},
    "Academic Support": {"doubt", "doubts", "remedial", "counselling", "counseling", "tutorial", "tutorials",
                         "guidance", "support"},
    "Food": {"food", "mess", "meal", "meals", "breakfast", "lunch", "dinner", "taste", "menu", "snacks", "curry",
             "rice", "chapati", "dosa", "idli"},
    "Room": {"room", "rooms", "bed", "beds", "cot", "mattress", "roommate", "roommates", "cupboard", "ventilation"},
    "Cleanliness": {"cleanliness", "hygiene", "sanitation", "washroom", "washrooms", "bathroom", "bathrooms",
                    "toilet", "toilets", "restroom", "restrooms", "garbage", "dust", "cockroach", "cockroaches",
                    "mosquito", "mosquitoes", "dirty", "unclean", "filthy", "clean", "unhygienic"},
    "Water": {"water", "tap", "taps", "geyser", "shower", "drinking"},
    "Electricity": {"electricity", "power", "voltage", "light", "lights", "generator", "inverter", "switch",
                    "socket", "sockets", "blackout"},
    "Security": {"security", "guard", "guards", "safety", "cctv", "theft", "curfew", "warden", "wardens",
                 "unsafe", "safe"},
    "Maintenance": {"maintenance", "repair", "repairs", "plumbing", "leak", "leakage", "leaking"},
    "Hostel Facilities": {"hostel", "hostels", "dorm", "dormitory", "hostellers", "block"},
    "Transport": {"bus", "buses", "transport", "transportation", "route", "routes", "driver", "shuttle", "van",
                  "vehicle", "commute"},
    "Library": {"library", "librarian", "journals", "reading"},
    "Sports": {"sports", "sport", "ground", "playground", "gym", "cricket", "football", "volleyball",
               "basketball", "court", "badminton"},
    "Events": {"event", "events", "fest", "fests", "festival", "cultural", "symposium", "workshop", "workshops",
               "seminar", "seminars", "club", "clubs", "competition", "competitions", "hackathon"},
    "Administration": {"administration", "office", "management", "principal", "fees", "fee", "scholarship",
                       "certificate", "certificates", "clerk", "bureaucracy", "placement", "placements", "admin"},
    "Campus Facilities": {"campus", "parking", "canteen", "cafeteria", "atm", "gate", "road", "roads", "garden",
                          "college"},
}
_KW_TO_ASPECT = {}


def _rebuild_index():
    _KW_TO_ASPECT.clear()
    for _a, _kws in ASPECT_KEYWORDS.items():
        for _k in _kws:
            _KW_TO_ASPECT.setdefault(_k, []).append(_a)


_rebuild_index()


def add_keywords(aspect, words):
    """Extend (or create) an aspect keyword list at runtime (used by data/category_rules.json)."""
    ASPECT_KEYWORDS.setdefault(aspect, set()).update(w.lower() for w in words)
    if aspect not in ALL_ASPECTS:
        ALL_ASPECTS.append(aspect)
    _rebuild_index()


POLARITY = mu.POSITIVE_WORDS | mu.NEGATIVE_WORDS | mu.NEUTRAL_WORDS


def _segment_tokens(tokens):
    """Split a punctuation-keeping token list into clause token lists."""
    # pass 1: hard splits
    chunks, cur = [], []
    for t in tokens:
        nt = normalize_token(t) if t.isascii() else t
        if t in mu.HARD_PUNCT or nt in mu.HARD_CONNECTORS:
            if cur:
                chunks.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        chunks.append(cur)

    # pass 2: soft splits
    out = []
    for ch in chunks:
        out.extend(_soft_split(ch))
    return out


def _has_aspect(concepts):
    return any(c in _KW_TO_ASPECT for c in concepts)


def _has_polarity(concepts):
    return any(c in POLARITY for c in concepts)


def _concepts(toks):
    return [w for _, c in concept_pairs([x for x in toks if x not in mu.SOFT_PUNCT]) for w in c.split()]


def _soft_split(chunk):
    pieces, cur = [], []
    for t in chunk:
        if t in mu.SOFT_CONNECTORS or t in mu.SOFT_PUNCT:
            pieces.append((cur, t))
            cur = []
        else:
            cur.append(t)
    pieces.append((cur, None))
    # greedily merge pieces unless both neighbours look like full opinions
    result, acc = [], []
    for i, (toks, _sep) in enumerate(pieces):
        if not toks:
            continue
        if not acc:
            acc = list(toks)
            continue
        left, right = _concepts(acc), _concepts(toks)
        if _has_aspect(left) and _has_polarity(left) and _has_aspect(right) and _has_polarity(right):
            result.append(acc)
            acc = list(toks)
        else:
            acc.extend(toks)
    if acc:
        result.append(acc)
    return result


def detect_aspects_in_text(concept_tokens, surface_tokens=()):
    """Return ordered list of (aspect, [matched keywords]) found in tokens."""
    hits = {}
    order = []
    for tok in list(concept_tokens) + [s.lower() for s in surface_tokens]:
        for a in _KW_TO_ASPECT.get(tok, []):
            hits.setdefault(a, [])
            if tok not in hits[a]:
                hits[a].append(tok)
            if a not in order:
                order.append(a)
    found = [(a, hits[a]) for a in order]
    # aspects matched only through weak words ("facilities") yield to any other aspect in the clause
    strong = [x for x in found if not (x[0] in WEAK_KEYWORDS and set(x[1]) <= WEAK_KEYWORDS[x[0]])]
    found = strong if strong else found
    specific = [x for x in found if x[0] not in GENERIC_ASPECTS]
    return specific if specific else found


def segment_feedback(text):
    """Return list of clause dicts: {text, aspects:[(aspect, keywords)], concept_tokens}."""
    p = preprocess(text)
    toks = tokenize(p["cleaned"], keep_punct=True)
    clauses = _segment_tokens(toks)
    segs = []
    for ch in clauses:
        surface = " ".join(ch)
        cp = preprocess(surface)
        found = detect_aspects_in_text(cp["concept_tokens"], cp["tokens"])
        segs.append({"text": surface, "prep": cp, "aspects": found})

    # Clauses with no aspect keyword inherit the previous clause's aspect (e.g. "... but very slow")
    merged = []
    for s in segs:
        if not s["aspects"] and merged:
            prev = merged[-1]
            prev["text"] += " " + s["text"]
            prev["prep"] = preprocess(prev["text"])
            continue
        merged.append(s)
    # leading aspect-less clause followed by an aspect clause: attach forward
    if len(merged) > 1 and not merged[0]["aspects"]:
        nxt = merged[1]
        nxt["text"] = merged[0]["text"] + " " + nxt["text"]
        nxt["prep"] = preprocess(nxt["text"])
        merged = merged[1:]
    return merged
