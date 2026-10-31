"""Database access layer (SQLAlchemy 2.x ORM) + aggregation helpers for the dashboard.

Safe schema evolution: ``init_db`` creates missing tables and adds any missing columns to
existing tables (ALTER TABLE ... ADD COLUMN), then back-fills categories / issues for rows saved by
an older version. Existing data is never dropped.
"""
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import scoped_session, selectinload, sessionmaker

from .models import (AdminResponse, AdminUser, AnalysisResult, Base, Feedback, Issue, IssueHistory, ModelRun,
                     Setting, User, utcnow)

log = logging.getLogger("edupulse.db")
_engine = None
_Session = None

LEVEL_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
SEV_RANK = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
ASPECTS = ["Teaching", "Lab/Infrastructure", "Course Content", "Wi-Fi"]
STATUSES = ["Open", "In Progress", "Resolved", "Closed"]
CATEGORIES = ["Academics", "Hostel", "Others"]
LANG_BUCKETS = ["Tamil", "English", "Hindi", "Mixed"]

_NEW_COLUMNS = {
    "feedback": [("category", "VARCHAR(40) DEFAULT 'Others'"), ("category_selected", "VARCHAR(40) DEFAULT 'Auto Detect'"),
                 ("category_detected", "VARCHAR(40) DEFAULT ''"), ("status", "VARCHAR(20) DEFAULT ''"),
                 ("admin_response", "TEXT DEFAULT ''"), ("issue_id", "VARCHAR(30) DEFAULT ''"),
                 ("updated_at", "TIMESTAMP")],
    "analysis_results": [("category", "VARCHAR(40) DEFAULT ''")],
}


def language_bucket(label):
    if label in ("English", "Tamil", "Hindi"):
        return label
    return "Mixed"


# ------------------------------------------------------------------ setup
def _migrate(engine):
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _NEW_COLUMNS.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    log.info("migration: added %s.%s", table, name)


def init_db(url):
    """Create engine + tables (+ add missing columns). Safe to call repeatedly."""
    global _engine, _Session
    kwargs = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    _engine = create_engine(url, **kwargs)
    _Session = scoped_session(sessionmaker(bind=_engine, expire_on_commit=False, future=True))
    Base.metadata.create_all(_engine)
    _migrate(_engine)
    try:
        migrate_legacy_admins()
    except Exception:
        log.exception("legacy admin migration failed (continuing)")
        _Session.remove()
    try:
        backfill()
    except Exception:
        log.exception("back-fill of older rows failed (continuing)")
        _Session.remove()
    return _engine


def get_session():
    if _Session is None:
        raise RuntimeError("Database not initialised - call init_db() first")
    return _Session()


def remove_session():
    if _Session is not None:
        _Session.remove()


def db_ok():
    try:
        get_session().execute(select(func.count(Feedback.id))).scalar()
        return True
    except Exception:
        return False


def backfill():
    """Fill category / issue data for feedback saved by an older EduPulse version."""
    from nlp.categories import categorize_aspects
    from nlp.preprocessing import preprocess
    s = get_session()
    old = s.execute(select(Feedback).options(selectinload(Feedback.results)).where(
        (Feedback.category_detected == "") | (Feedback.category_detected.is_(None)))).scalars().all()
    need_issue = []
    for fb in old:
        concept = preprocess(fb.feedback_text)["concept_tokens"]
        pairs = []
        for r in fb.results:
            try:
                clause = json.loads(r.explanation or "{}").get("clause", "")
            except Exception:
                clause = ""
            pairs.append((r.aspect, preprocess(clause)["concept_tokens"] if clause else concept))
        cmap = categorize_aspects(pairs, concept)
        for r in fb.results:
            r.category = cmap.get(r.aspect, "Others")
        negs = [r for r in fb.results if r.aspect_sentiment == "Negative"]
        top = max(negs or fb.results, key=lambda r: r.priority_score, default=None)
        fb.category = top.category if top else "Others"
        fb.category_detected = fb.category
        fb.category_selected = "Auto Detect"
        if fb.results and fb.results[0].sentiment == "Negative" and not fb.issue_id:
            need_issue.append(fb.id)
    s.commit()
    for fid in need_issue:
        ensure_issue(fid, "migration")


# --------------------------------------------------------------- settings
def get_setting(key, default=None):
    row = get_session().get(Setting, key)
    if not row:
        return default
    try:
        return json.loads(row.value)
    except Exception:
        return default


def set_setting(key, value):
    s = get_session()
    row = s.get(Setting, key)
    if row is None:
        s.add(Setting(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    s.commit()


# ------------------------------------------------------------------ users
def get_user_by_id(uid):
    try:
        return get_session().get(User, int(uid))
    except (TypeError, ValueError):
        return None


def get_user_by_username(username):
    u = (username or "").strip().lower()
    if not u:
        return None
    return get_session().execute(select(User).where(func.lower(User.username) == u)).scalars().first()


def get_user_by_email(email):
    e = (email or "").strip().lower()
    if not e:
        return None
    return get_session().execute(select(User).where(func.lower(User.email) == e)).scalars().first()


def get_user_by_identifier(identifier):
    """Look a user up by username OR e-mail address (case-insensitive)."""
    ident = (identifier or "").strip()
    if not ident:
        return None
    return get_user_by_username(ident) or get_user_by_email(ident)


def count_users():
    return get_session().execute(select(func.count(User.id))).scalar() or 0


def create_user(username, email, password_hash, role="admin"):
    """Insert a user. Raises ValueError('username_taken' | 'email_taken') on duplicates (also when two
    requests race: the UNIQUE constraint is the final arbiter)."""
    username, email = (username or "").strip(), (email or "").strip().lower()
    if get_user_by_username(username):
        raise ValueError("username_taken")
    if get_user_by_email(email):
        raise ValueError("email_taken")
    s = get_session()
    u = User(username=username, email=email, password_hash=password_hash, role=role, is_active=True)
    s.add(u)
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        raise ValueError("username_taken" if get_user_by_username(username) else "email_taken")
    return u


def set_user_password(uid, password_hash):
    s = get_session()
    u = s.get(User, int(uid))
    if u is None:
        return False
    u.password_hash = password_hash
    s.commit()
    return True


def migrate_legacy_admins():
    """Copy accounts from the legacy `admin_users` table (older versions) into `users`.
    They keep their existing password hash; the e-mail is a placeholder users can ignore."""
    s = get_session()
    if not inspect(_engine).has_table("admin_users"):
        return 0
    n = 0
    for old in s.execute(select(AdminUser)).scalars().all():
        if get_user_by_username(old.username):
            continue
        email = f"{old.username.lower()}@edupulse.local"
        if get_user_by_email(email):
            continue
        s.add(User(username=old.username, email=email, password_hash=old.password_hash, role="admin", is_active=True))
        n += 1
    s.commit()
    return n


# -------------------------------------------------------------- model runs
def record_model_run(metrics: dict):
    s = get_session()
    res = metrics.get("results", {}).get("sentiment", {})
    s.add(ModelRun(model_name=metrics.get("model_name", ""), mode=metrics.get("mode", ""),
                   dataset_size=metrics.get("dataset", {}).get("size", 0),
                   accuracy=res.get("accuracy", 0.0), macro_f1=res.get("f1_macro", 0.0),
                   metrics_json=json.dumps(metrics, ensure_ascii=False)))
    s.commit()


# ---------------------------------------------------------------- feedback
def frequency_count(aspect, before=None, window_days=30):
    """Number of stored NEGATIVE feedback items for `aspect` within the window ending at `before`."""
    before = before or utcnow()
    since = before - timedelta(days=window_days)
    q = (select(func.count(func.distinct(AnalysisResult.feedback_id))).select_from(AnalysisResult)
         .join(Feedback, Feedback.id == AnalysisResult.feedback_id)
         .where(AnalysisResult.aspect == aspect, AnalysisResult.aspect_sentiment == "Negative",
                Feedback.timestamp >= since, Feedback.timestamp <= before))
    return get_session().execute(q).scalar() or 0


def _clip(v, n):
    return (v or "").strip()[:n]


def _next_issue_code(s, when):
    prefix = f"EDU-{when.year}-"
    last = s.execute(select(func.max(Issue.issue_code)).where(Issue.issue_code.like(prefix + "%"))).scalar()
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:04d}"


def ensure_issue(fid, by="system"):
    """Make sure the feedback has an Issue (status Open). Commits. Retries on an issue-code collision
    (two requests allocating the same EDU-YYYY-NNNN). Returns the issue code or None if the feedback is missing."""
    s = get_session()
    for _ in range(6):
        fb = s.execute(select(Feedback).options(selectinload(Feedback.results), selectinload(Feedback.issue))
                       .where(Feedback.id == fid)).scalar_one_or_none()
        if fb is None:
            return None
        if fb.issue is not None:
            return fb.issue.issue_code
        negs = [r for r in fb.results if r.aspect_sentiment == "Negative"] or list(fb.results)
        top = max(negs, key=lambda r: r.priority_score, default=None)
        clause = ""
        if top is not None:
            try:
                clause = json.loads(top.explanation or "{}").get("clause", "")
            except Exception:
                clause = ""
        when = fb.timestamp or utcnow()
        code = _next_issue_code(s, when)
        issue = Issue(issue_code=code, feedback_id=fb.id, category=fb.category or "Others",
                      title=f"{top.aspect if top else 'General'}: {(clause or fb.feedback_text)[:150]}",
                      aspect=top.aspect if top else "General", priority=top.priority if top else "LOW",
                      priority_score=top.priority_score if top else 0.0, status="Open", created_at=when, updated_at=when)
        issue.history.append(IssueHistory(old_status="", new_status="Open", note="Issue created", changed_by=by,
                                          changed_at=when))
        fb.issue_id, fb.status, fb.updated_at = code, "Open", when
        s.add(issue)
        try:
            s.commit()
            return code
        except IntegrityError:
            s.rollback()
    raise RuntimeError("could not allocate an issue id")


def save_feedback(form: dict, analysis: dict, model_version="", timestamp=None):
    """Persist one feedback + its per-aspect analysis rows (+ an Issue for negative feedback)."""
    s = get_session()
    rating = form.get("rating")
    try:
        rating = int(rating) if rating not in (None, "") else None
    except (TypeError, ValueError):
        rating = None
    if rating is not None and not 1 <= rating <= 5:
        rating = None
    cat = analysis["category"]
    fb = Feedback(
        timestamp=timestamp or utcnow(),
        student_name=_clip(form.get("student_name"), 120), student_id=_clip(form.get("student_id"), 60),
        department=_clip(form.get("department"), 120), year=_clip(form.get("year"), 20),
        course=_clip(form.get("course"), 160),
        language=analysis["language"]["language"], language_hint=_clip(form.get("language"), 40) or "Auto Detect",
        feedback_text=form["text"].strip(), rating=rating,
        category=cat["final"], category_selected=cat["selected"], category_detected=cat["detected"])
    s.add(fb)
    s.flush()
    overall = analysis["sentiment"]
    rows = []
    for a in analysis["aspects"]:
        expl = {"overall": analysis["explanation"], "aspect": a["explanation"], "keywords": a["keywords"],
                "clause": a["clause"], "priority_why": a["priority"]["why"], "category": analysis["category"],
                "language": analysis["language"], "preprocessing": analysis["preprocessing"],
                "priority_detail": {k: a["priority"][k] for k in
                                    ("severity_value", "frequency", "frequency_norm", "criticality")}}
        r = AnalysisResult(
            feedback_id=fb.id, sentiment=overall["label"], sentiment_confidence=overall["confidence"],
            aspect=a["aspect"], category=a.get("category", "Others"), aspect_sentiment=a["sentiment"],
            aspect_confidence=a["confidence"], severity=a["severity"], priority=a["priority"]["level"],
            priority_score=a["priority"]["score"], frequency=a["priority"]["frequency"],
            explanation=json.dumps(expl, ensure_ascii=False),
            recommendation=json.dumps(a["recommendation"], ensure_ascii=False),
            model_version=model_version, nlp_mode=analysis["nlp_mode"])
        s.add(r)
        rows.append(r)
    s.commit()
    fid = fb.id
    if overall["label"] == "Negative" and rows:
        ensure_issue(fid, "system")
    return fid


# ------------------------------------------------------- issues / responses
def update_status(fid, new_status, note="", admin="admin"):
    """Change the status of the issue attached to a feedback (creating the issue if needed)."""
    if new_status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    if ensure_issue(fid, admin) is None:
        return None
    s = get_session()
    fb = s.execute(select(Feedback).options(selectinload(Feedback.issue)).where(Feedback.id == fid)).scalar_one()
    issue, now = fb.issue, utcnow()
    old = issue.status
    if old != new_status or note:
        issue.history.append(IssueHistory(old_status=old, new_status=new_status, note=(note or "")[:2000],
                                          changed_by=admin, changed_at=now))
    issue.status, issue.updated_at = new_status, now
    fb.status, fb.updated_at = new_status, now
    s.commit()
    return {"issue_id": issue.issue_code, "old": old, "new": new_status}


def add_response(fid, response, admin="admin", status=None):
    response = (response or "").strip()
    if not response:
        raise ValueError("response is empty")
    if len(response) > 4000:
        raise ValueError("response is too long (max 4000 characters)")
    s = get_session()
    fb = s.get(Feedback, fid)
    if fb is None:
        return None
    now = utcnow()
    s.add(AdminResponse(feedback_id=fid, response=response, admin=admin, created_at=now))
    fb.admin_response, fb.updated_at = response, now
    s.commit()
    if status:
        update_status(fid, status, note="Admin response added", admin=admin)
    return True


def create_issue_for(fid, admin="admin"):
    return ensure_issue(fid, admin)


def fetch_issues(filters=None):
    f = filters or {}
    s = get_session()
    q = (select(Issue, Feedback).join(Feedback, Feedback.id == Issue.feedback_id)
         .order_by(Issue.priority_score.desc(), Issue.created_at.desc()))
    if f.get("status"):
        q = q.where(Issue.status == f["status"])
    if f.get("category"):
        q = q.where(Issue.category == f["category"])
    if f.get("priority"):
        q = q.where(Issue.priority == f["priority"].upper())
    out = []
    for issue, fb in s.execute(q).all():
        out.append({"id": issue.id, "issue_id": issue.issue_code, "feedback_id": fb.id, "title": issue.title,
                    "category": issue.category, "aspect": issue.aspect, "priority": issue.priority,
                    "score": issue.priority_score, "status": issue.status, "department": fb.department,
                    "language": fb.language, "text": fb.feedback_text,
                    "created": issue.created_at.isoformat(timespec="seconds"),
                    "updated": issue.updated_at.isoformat(timespec="seconds") if issue.updated_at else ""})
    if f.get("search"):
        n = f["search"].lower()
        out = [i for i in out if n in i["title"].lower() or n in i["issue_id"].lower() or n in i["text"].lower()]
    return out


def issue_counts():
    s = get_session()
    c = Counter(r for r in s.execute(select(Issue.status)).scalars().all())
    crit = s.execute(select(func.count(Issue.id)).where(Issue.priority == "CRITICAL",
                                                         Issue.status.in_(["Open", "In Progress"]))).scalar() or 0
    return {"open": c["Open"], "in_progress": c["In Progress"], "resolved": c["Resolved"], "closed": c["Closed"],
            "total": sum(c.values()), "critical": crit}


# --------------------------------------------------------------- queries
def _summary(fb: Feedback):
    rows = fb.results
    aspects = [{"aspect": r.aspect, "category": r.category or fb.category, "sentiment": r.aspect_sentiment,
                "severity": r.severity, "priority": r.priority, "score": r.priority_score,
                "frequency": r.frequency} for r in rows]
    top = max(rows, key=lambda r: (r.priority_score, LEVEL_RANK.get(r.priority, 0)), default=None)
    sev = max((r.severity for r in rows), key=lambda x: SEV_RANK.get(x, 0), default="Low")
    return {
        "id": fb.id, "timestamp": fb.timestamp.isoformat(timespec="seconds"), "date": fb.timestamp.date().isoformat(),
        "updated_at": fb.updated_at.isoformat(timespec="seconds") if fb.updated_at else "",
        "language": fb.language, "language_hint": fb.language_hint, "department": fb.department, "year": fb.year,
        "course": fb.course, "student_name": fb.student_name, "student_id": fb.student_id, "rating": fb.rating,
        "text": fb.feedback_text, "sentiment": rows[0].sentiment if rows else "Neutral",
        "confidence": rows[0].sentiment_confidence if rows else 0.0,
        "category": fb.category or "Others", "category_selected": fb.category_selected,
        "category_detected": fb.category_detected, "status": fb.status or "", "issue_id": fb.issue_id or "",
        "admin_response": fb.admin_response or "",
        "aspects": aspects, "aspect_names": ", ".join(a["aspect"] for a in aspects),
        "severity": sev, "priority": top.priority if top else "LOW", "score": top.priority_score if top else 0.0,
    }


def _parse_date(v):
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        return None


def fetch_summaries(filters=None):
    """Load feedback (SQL filters on simple columns) and build summary dicts; remaining filters in Python."""
    f = filters or {}
    s = get_session()
    q = select(Feedback).options(selectinload(Feedback.results))
    d_from, d_to = _parse_date(f.get("date_from")), _parse_date(f.get("date_to"))
    if d_from:
        q = q.where(Feedback.timestamp >= d_from)
    if d_to:
        q = q.where(Feedback.timestamp < d_to + timedelta(days=1))
    for col, key in ((Feedback.department, "department"), (Feedback.year, "year"), (Feedback.course, "course"),
                     (Feedback.category, "category"), (Feedback.status, "status")):
        if f.get(key):
            q = q.where(col == f[key])
    q = q.order_by(Feedback.timestamp.desc(), Feedback.id.desc())
    items = [_summary(fb) for fb in s.execute(q).scalars().all()]

    if f.get("language"):
        lv = f["language"]
        items = [i for i in items if (language_bucket(i["language"]) == lv if lv in LANG_BUCKETS else i["language"] == lv)]
    if f.get("sentiment"):
        items = [i for i in items if i["sentiment"] == f["sentiment"]]
    if f.get("aspect"):
        items = [i for i in items if any(a["aspect"] == f["aspect"] for a in i["aspects"])]
    if f.get("priority"):
        items = [i for i in items if i["priority"] == f["priority"].upper()]
    if f.get("search"):
        needle = f["search"].lower()
        items = [i for i in items if needle in i["text"].lower() or needle in i["course"].lower()
                 or needle in i["department"].lower() or needle in i["student_name"].lower()
                 or needle in i["issue_id"].lower() or needle in i["student_id"].lower()]
    return items


SORT_KEYS = {
    "id": lambda i: i["id"],
    "date": lambda i: i["timestamp"], "language": lambda i: i["language"], "sentiment": lambda i: i["sentiment"],
    "aspect": lambda i: i["aspect_names"], "priority": lambda i: LEVEL_RANK.get(i["priority"], 0),
    "score": lambda i: i["score"], "text": lambda i: i["text"].lower(),
    "category": lambda i: i["category"], "status": lambda i: i["status"], "department": lambda i: i["department"],
    "severity": lambda i: SEV_RANK.get(i["severity"], 0), "student": lambda i: i["student_name"].lower(),
    "issue_id": lambda i: i.get("issue_id", ""), "created": lambda i: i.get("created", ""),
    "title": lambda i: i.get("title", "").lower(),
}


def paginate(items, sort="date", direction="desc", page=1, per_page=15):
    key = SORT_KEYS.get(sort, SORT_KEYS["date"])
    items = sorted(items, key=key, reverse=(direction != "asc"))
    total = len(items)
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, page), pages)
    start = (page - 1) * per_page
    return {"items": items[start:start + per_page], "total": total, "page": page, "pages": pages, "per_page": per_page}


def filter_options():
    s = get_session()

    def distinct(col):
        return sorted(v for v in s.execute(select(col).distinct()).scalars().all() if v)
    aspects = distinct(AnalysisResult.aspect)
    return {"languages": LANG_BUCKETS, "departments": distinct(Feedback.department), "years": distinct(Feedback.year),
            "courses": distinct(Feedback.course), "aspects": aspects, "categories": CATEGORIES, "statuses": STATUSES}


def fetch_rows(feedback_ids=None):
    """One dict per aspect mention (joined with its feedback) for analytics / similarity / trends."""
    s = get_session()
    q = (select(AnalysisResult, Feedback).join(Feedback, Feedback.id == AnalysisResult.feedback_id))
    if feedback_ids is not None:
        ids = list(feedback_ids)
        if not ids:
            return []
        rows = []
        for i in range(0, len(ids), 500):      # chunk to stay below SQL variable limits
            rows.extend(s.execute(q.where(AnalysisResult.feedback_id.in_(ids[i:i + 500]))).all())
    else:
        rows = s.execute(q).all()
    out = []
    for r, fb in rows:
        clause, term = "", ""
        try:
            ex = json.loads(r.explanation or "{}")
            clause = ex.get("clause", "")
            terms = ex.get("aspect", {}).get("terms", [])
            term = terms[0]["term"] if terms else ""
        except Exception:
            pass
        out.append({"feedback_id": fb.id, "timestamp": fb.timestamp, "language": fb.language,
                    "category": r.category or fb.category, "aspect": r.aspect, "sentiment": r.aspect_sentiment,
                    "severity": r.severity, "priority": r.priority, "score": r.priority_score,
                    "clause": clause or fb.feedback_text, "term": term, "department": fb.department})
    return out


def feedback_detail(fid):
    s = get_session()
    fb = s.execute(select(Feedback).options(selectinload(Feedback.results), selectinload(Feedback.issue),
                                            selectinload(Feedback.responses))
                   .where(Feedback.id == fid)).scalar_one_or_none()
    if fb is None:
        return None
    d = _summary(fb)
    rows = []
    for r in fb.results:
        ex = json.loads(r.explanation or "{}")
        rows.append({"aspect": r.aspect, "category": r.category or fb.category, "sentiment": r.aspect_sentiment,
                     "confidence": r.aspect_confidence, "severity": r.severity, "priority": r.priority,
                     "score": r.priority_score, "frequency": r.frequency, "explanation": ex,
                     "recommendation": json.loads(r.recommendation or "{}")})
    rows.sort(key=lambda x: -x["score"])
    d["rows"] = rows
    d["nlp_mode"] = fb.results[0].nlp_mode if fb.results else ""
    d["model_version"] = fb.results[0].model_version if fb.results else ""
    if rows:
        ex0 = rows[0]["explanation"]
        d["overall_explanation"] = ex0.get("overall", {})
        d["language_info"] = ex0.get("language", {})
        d["preprocessing"] = ex0.get("preprocessing", {})
        d["category_info"] = ex0.get("category", {})
    else:
        d["overall_explanation"], d["language_info"], d["preprocessing"], d["category_info"] = {}, {}, {}, {}
    d["history"] = [{"old": h.old_status, "new": h.new_status, "note": h.note, "by": h.changed_by,
                     "at": h.changed_at.isoformat(timespec="seconds")} for h in (fb.issue.history if fb.issue else [])]
    d["responses"] = [{"response": r.response, "admin": r.admin, "at": r.created_at.isoformat(timespec="seconds")}
                      for r in fb.responses]
    d["issue"] = {"issue_id": fb.issue.issue_code, "status": fb.issue.status, "title": fb.issue.title} if fb.issue else None
    return d


def delete_all_feedback():
    s = get_session()
    for fb in s.execute(select(Feedback)).scalars().all():
        s.delete(fb)
    s.commit()


def count_feedback():
    return get_session().execute(select(func.count(Feedback.id))).scalar() or 0


# ------------------------------------------------------------- aggregates
def _pct(n, total):
    return round(100.0 * n / total, 1) if total else 0.0


def dashboard_stats(items):
    total = len(items)
    sc = Counter(i["sentiment"] for i in items)
    pr = Counter(i["priority"] for i in items)
    cats = Counter(i["category"] for i in items)
    st = Counter(i["status"] for i in items if i["status"])
    asp_neg = Counter()
    for i in items:
        for a in i["aspects"]:
            if a["sentiment"] == "Negative":
                asp_neg[a["aspect"]] += 1
    langs = Counter(i["language"] for i in items)
    buckets = Counter(language_bucket(i["language"]) for i in items)
    cat_sent = {c: {"Positive": 0, "Neutral": 0, "Negative": 0} for c in CATEGORIES}
    dept = defaultdict(lambda: {c: 0 for c in CATEGORIES})
    for i in items:
        cat_sent.setdefault(i["category"], {"Positive": 0, "Neutral": 0, "Negative": 0})[i["sentiment"]] += 1
        d = i["department"] or "Unspecified"
        dept[d][i["category"]] = dept[d].get(i["category"], 0) + 1
    cat_prio = {c: {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0} for c in CATEGORIES}
    lang_cat = {b: {c: 0 for c in CATEGORIES} for b in LANG_BUCKETS}
    for i in items:
        cat_prio.setdefault(i["category"], {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0})[i["priority"]] += 1
        lang_cat[language_bucket(i["language"])][i["category"]] = lang_cat[language_bucket(i["language"])].get(i["category"], 0) + 1
    depts = [{"department": k, **v, "total": sum(v.values())} for k, v in dept.items()]
    depts.sort(key=lambda x: -x["total"])
    return {
        "total": total,
        "positive_pct": _pct(sc["Positive"], total), "neutral_pct": _pct(sc["Neutral"], total),
        "negative_pct": _pct(sc["Negative"], total), "negative_count": sc["Negative"],
        "counts": {"Positive": sc["Positive"], "Neutral": sc["Neutral"], "Negative": sc["Negative"]},
        "categories": {c: cats[c] for c in CATEGORIES},
        "category_sentiment": cat_sent, "departments": depts, "category_priority": cat_prio, "language_category": lang_cat,
        "high_priority": pr["HIGH"], "critical_priority": pr["CRITICAL"],
        "high_critical": pr["HIGH"] + pr["CRITICAL"],
        "priority_distribution": {k: pr[k] for k in ("LOW", "MEDIUM", "HIGH", "CRITICAL")},
        "issues": {"open": st["Open"], "in_progress": st["In Progress"], "resolved": st["Resolved"],
                   "closed": st["Closed"], "open_total": st["Open"] + st["In Progress"],
                   "resolved_total": st["Resolved"] + st["Closed"]},
        "most_problematic_aspect": asp_neg.most_common(1)[0][0] if asp_neg else None,
        "most_problematic_count": asp_neg.most_common(1)[0][1] if asp_neg else 0,
        "most_common_language": langs.most_common(1)[0][0] if langs else None,
        "language_buckets": {b: buckets[b] for b in LANG_BUCKETS},
    }


def dashboard_trends(items):
    by = defaultdict(lambda: {"Positive": 0, "Neutral": 0, "Negative": 0})
    for i in items:
        by[i["date"]][i["sentiment"]] += 1
    dates = sorted(by)
    return {"dates": dates, "Positive": [by[d]["Positive"] for d in dates],
            "Neutral": [by[d]["Neutral"] for d in dates], "Negative": [by[d]["Negative"] for d in dates]}


def dashboard_aspects(items, recurring_limit=8):
    dist = Counter()
    heat = {a: {"Positive": 0, "Neutral": 0, "Negative": 0} for a in ASPECTS}
    cat_of = {}
    for i in items:
        for a in i["aspects"]:
            dist[a["aspect"]] += 1
            heat.setdefault(a["aspect"], {"Positive": 0, "Neutral": 0, "Negative": 0})[a["sentiment"]] += 1
            cat_of[a["aspect"]] = a["category"]
    names = [a for a in heat if a in ASPECTS or dist.get(a)]
    return {"distribution": {a: dist.get(a, 0) for a in names}, "heatmap": {a: heat[a] for a in names},
            "categories": {a: cat_of.get(a, "Others") for a in names}}


def recurring_complaints(items_ids, limit=8):
    """Top recurring complaints: (aspect, leading negative term) pairs among negative aspect rows."""
    if not items_ids:
        return []
    c = Counter()
    for r in fetch_rows(items_ids):
        if r["sentiment"] == "Negative":
            c[(r["aspect"], r["term"] or "general dissatisfaction")] += 1
    return [{"aspect": a, "term": t, "count": n} for (a, t), n in c.most_common(limit)]


def dashboard_languages(items):
    langs = Counter(i["language"] for i in items)
    ls = defaultdict(lambda: {"Positive": 0, "Neutral": 0, "Negative": 0})
    for i in items:
        ls[i["language"]][i["sentiment"]] += 1
    names = [k for k, _ in langs.most_common()]
    return {"distribution": {k: langs[k] for k in names}, "by_sentiment": {k: ls[k] for k in names}}
