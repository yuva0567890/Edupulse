"""Shared helpers for blueprints: CSRF, auth, rate limiting, validation, analyse-and-store."""
import hmac
import secrets
import time
from collections import defaultdict, deque
from functools import wraps

from flask import current_app, g, jsonify, redirect, request, session, url_for

from database import db

LANG_HINTS = ["Auto Detect", "English", "Tamil", "Hindi"]
CATEGORY_CHOICES = ["Auto Detect", "Academics", "Hostel", "Others"]
YEARS = ["1", "2", "3", "4", "5"]
MAX_TEXT = 5000


# ------------------------------------------------------------------ CSRF
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def check_csrf():
    """Validate token for HTML form posts. JSON posts are protected by the Content-Type check
    (a cross-site form cannot send application/json without a CORS pre-flight)."""
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    expected = session.get("_csrf", "")
    return bool(expected) and hmac.compare_digest(str(sent), expected)


# ------------------------------------------------------------------ auth
def current_user():
    """The logged-in User (loaded from the database once per request) or None.
    A session that points to a deleted / deactivated / non-admin account is cleared."""
    if "_cu" in g.__dict__:
        return g._cu
    user = None
    uid = session.get("user_id")
    if uid is not None:
        user = db.get_user_by_id(uid)
        if user is None or not user.is_active or user.role != "admin":
            session.pop("user_id", None)
            session.pop("admin", None)
            user = None
    g._cu = user
    return user


def is_admin():
    return current_user() is not None


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_admin():
            if request.path.startswith("/api/"):
                return jsonify({"error": "authentication required"}), 401
            return redirect(url_for("admin.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------- rate limiting
_hits = defaultdict(deque)


def rate_limited(key, limit, window=60):
    """True if `key` exceeded `limit` events in the last `window` seconds (in-memory, per process)."""
    if current_app.config.get("TESTING") and not current_app.config.get("RATE_LIMIT_IN_TESTS"):
        return False
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def client_ip():
    return (request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0]).strip()


# ------------------------------------------------------------ validation
def clean_form(data):
    """Validate a feedback submission (form or JSON). Returns (cleaned, errors)."""
    errors = {}
    g = lambda k: (data.get(k) if data.get(k) is not None else "")
    text = str(g("text") or g("feedback")).strip()
    if not text:
        errors["text"] = "empty"
    elif len(text) < 3:
        errors["text"] = "short"
    elif len(text) > MAX_TEXT:
        errors["text"] = "long"
    rating = g("rating")
    if rating not in ("", None):
        try:
            rating = int(rating)
            if not 1 <= rating <= 5:
                raise ValueError
        except (TypeError, ValueError):
            errors["rating"] = "invalid"
            rating = None
    else:
        rating = None
    lang = str(g("language") or "Auto Detect").strip()
    if lang not in LANG_HINTS:
        errors["language"] = "invalid"
        lang = "Auto Detect"
    category = str(g("category") or "Auto Detect").strip()
    if category not in CATEGORY_CHOICES:
        errors["category"] = "invalid"
        category = "Auto Detect"
    year = str(g("year")).strip()
    if year and year not in YEARS:
        errors["year"] = "invalid"
        year = ""
    cleaned = {"text": text, "language": lang, "rating": rating, "year": year, "category": category,
               "student_name": str(g("student_name")).strip()[:120], "student_id": str(g("student_id")).strip()[:60],
               "department": str(g("department")).strip()[:120], "course": str(g("course")).strip()[:160]}
    return cleaned, errors


def get_pipeline():
    return current_app.extensions["edupulse"]["pipeline"]


def model_version():
    info = get_pipeline().engine.info()
    return f"{info['mode']} | {info.get('trained_at') or 'n/a'}"


def analyze_only(cleaned):
    pipe = get_pipeline()
    cfg = pipe.priority_config
    now = db.utcnow()
    return pipe.analyze(cleaned["text"], cleaned["language"],
                        freq_lookup=lambda aspect: db.frequency_count(aspect, now, cfg.window_days),
                        category_hint=None if cleaned.get("category") in (None, "", "Auto Detect") else cleaned["category"])


def analyze_and_store(cleaned):
    analysis = analyze_only(cleaned)
    fid = db.save_feedback(cleaned, analysis, model_version())
    return fid, analysis
