"""JSON API. Public: POST /api/analyze, POST /api/feedback. Admin session required for the rest."""
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from database import db
from nlp import analytics
from nlp.categories import ASPECT_FAMILY, CATEGORIES
from nlp.pipeline import FeedbackError
from .common import (admin_required, analyze_and_store, analyze_only, clean_form, client_ip, get_pipeline, rate_limited)

bp = Blueprint("api", __name__, url_prefix="/api")

FILTER_KEYS = ["date_from", "date_to", "language", "sentiment", "aspect", "priority", "department", "year",
               "course", "search", "category", "status"]
PERIODS = (7, 30, 90)


def _filters(ignore_dates=False):
    f = {k: request.args.get(k, "").strip() for k in FILTER_KEYS if request.args.get(k, "").strip()}
    if ignore_dates:
        f.pop("date_from", None)
        f.pop("date_to", None)
    return f


def _json_body():
    if not request.is_json:
        return None, (jsonify({"error": "Content-Type must be application/json"}), 415)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "invalid JSON body"}), 400)
    return data, None


def _period():
    try:
        p = int(request.args.get("period", 7))
    except ValueError:
        p = 7
    return p if p in PERIODS else 7


def _dt(items):
    for i in items:
        i["_dt"] = datetime.fromisoformat(i["timestamp"])
    return items


def analytics_data(filters):
    """items (summaries), rows (aspect mentions) and clusters for the given filters."""
    items = db.fetch_summaries(filters)
    rows = db.fetch_rows([i["id"] for i in items])
    cfg = get_pipeline().priority_config
    clusters = analytics.cluster_complaints(rows, cfg)
    return items, rows, clusters, cfg


def _strip(items):
    return [{k: v for k, v in i.items() if k != "_dt"} for i in items]


def _post(store):
    if rate_limited("api:" + client_ip(), 60):
        return jsonify({"error": "rate limit exceeded"}), 429
    data, err = _json_body()
    if err:
        return err
    cleaned, errors = clean_form(data)
    if errors:
        return jsonify({"error": "validation failed", "fields": errors}), 400
    try:
        if store:
            fid, analysis = analyze_and_store(cleaned)
            return jsonify({"id": fid, "analysis": analysis}), 201
        return jsonify({"analysis": analyze_only(cleaned)}), 200
    except FeedbackError as e:
        return jsonify({"error": str(e)}), 422
    except Exception:
        current_app.logger.exception("api analysis failed")
        return jsonify({"error": "internal error"}), 500


@bp.route("/analyze", methods=["POST"])
def analyze():
    return _post(store=False)


@bp.route("/feedback", methods=["POST"])
def create_feedback():
    return _post(store=True)


@bp.route("/categories")
def categories():
    return jsonify({"categories": CATEGORIES, "aspects": ASPECT_FAMILY})


@bp.route("/feedback", methods=["GET"])
@admin_required
def list_feedback():
    items = db.fetch_summaries(_filters())
    try:
        page = int(request.args.get("page", 1))
        per_page = min(max(int(request.args.get("per_page", 15)), 1), 100)
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    return jsonify(db.paginate(items, request.args.get("sort", "date"), request.args.get("dir", "desc"), page, per_page))


@bp.route("/feedback/<int:fid>", methods=["GET"])
@admin_required
def get_feedback(fid):
    d = db.feedback_detail(fid)
    if d is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(d)


@bp.route("/feedback/<int:fid>/status", methods=["POST"])
@admin_required
def set_status(fid):
    data, err = _json_body()
    if err:
        return err
    from flask import session
    try:
        res = db.update_status(fid, str(data.get("status", "")), str(data.get("note", "")), session.get("admin", "admin"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if res is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(res)


@bp.route("/feedback/<int:fid>/response", methods=["POST"])
@admin_required
def set_response(fid):
    data, err = _json_body()
    if err:
        return err
    from flask import session
    status = data.get("status") or None
    if status and status not in db.STATUSES:
        return jsonify({"error": f"status must be one of {db.STATUSES}"}), 400
    try:
        res = db.add_response(fid, str(data.get("response", "")), session.get("admin", "admin"), status)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if res is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@bp.route("/issues")
@admin_required
def issues():
    items = db.fetch_issues(_filters())
    return jsonify({"items": items, "counts": db.issue_counts(), "total": len(items)})


@bp.route("/dashboard/stats")
@admin_required
def dash_stats():
    items = db.fetch_summaries(_filters())
    out = db.dashboard_stats(items)
    out["recurring_complaints"] = db.recurring_complaints([i["id"] for i in items])
    return jsonify(out)


@bp.route("/dashboard/trends")
@admin_required
def dash_trends():
    return jsonify(db.dashboard_trends(db.fetch_summaries(_filters())))


@bp.route("/dashboard/aspects")
@admin_required
def dash_aspects():
    return jsonify(db.dashboard_aspects(db.fetch_summaries(_filters())))


@bp.route("/dashboard/languages")
@admin_required
def dash_languages():
    return jsonify(db.dashboard_languages(db.fetch_summaries(_filters())))


@bp.route("/dashboard/trending")
@admin_required
def dash_trending():
    period = _period()
    items = db.fetch_summaries(_filters(ignore_dates=True))
    rows = db.fetch_rows([i["id"] for i in items])
    times = [datetime.fromisoformat(i["timestamp"]) for i in items]
    return jsonify(analytics.trending_issues(rows, times, period, db.utcnow()))


@bp.route("/dashboard/similar")
@admin_required
def dash_similar():
    items, rows, clusters, cfg = analytics_data(_filters())
    min_size = 2 if request.args.get("recurring", "1") == "1" else 1
    out = [c for c in clusters if c["count"] >= min_size]
    return jsonify({"threshold": cfg.similarity_threshold, "clusters": out[:30], "total_clusters": len(out)})


@bp.route("/dashboard/critical")
@admin_required
def dash_critical():
    items, rows, clusters, cfg = analytics_data(_filters())
    alerts = analytics.critical_alerts(clusters, cfg)
    status_of = {i["id"]: i["status"] for i in items}
    for a in alerts:
        sts = [status_of.get(f, "") for f in a["feedback_ids"]]
        a["open_count"] = sum(1 for x in sts if x in ("Open", "In Progress"))
        a["status"] = ("Open" if "Open" in sts else "In Progress" if "In Progress" in sts
                       else "Resolved" if "Resolved" in sts else "Closed" if "Closed" in sts else "No issue")
    return jsonify({"threshold": cfg.critical_min, "alerts": alerts})


@bp.route("/dashboard/summary")
@admin_required
def dash_summary():
    period = _period()
    items, rows, clusters, cfg = analytics_data(_filters(ignore_dates=True))
    now = db.utcnow()
    _dt(items)
    times = [i["_dt"] for i in items]
    trend = analytics.trending_issues(rows, times, period, now)
    out = analytics.build_summary(items, rows, clusters, trend, db.issue_counts(), period, now, cfg)
    return jsonify(out)


@bp.route("/dashboard/recent")
@admin_required
def dash_recent():
    items = db.fetch_summaries(_filters())[:8]
    return jsonify({"items": _strip(items)})


@bp.route("/model/performance")
@admin_required
def model_performance():
    from .admin import load_metrics
    m = load_metrics()
    if not m:
        return jsonify({"status": "training required", "mode": get_pipeline().mode}), 200
    m["live_mode"] = get_pipeline().mode
    return jsonify(m)


@bp.errorhandler(404)
def api_404(_e):
    return jsonify({"error": "not found"}), 404
