"""Admin area: login/logout, dashboard, feedback explorer, detail, model performance, settings."""
import csv
import io
import json
import os
import time
from collections import defaultdict
from urllib.parse import urlparse

from flask import (Blueprint, Response, abort, current_app, flash, redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import security
from database import db
from nlp import analytics
from nlp.priority import PriorityConfig
from .api import FILTER_KEYS
from .common import admin_required, client_ip, current_user, get_pipeline, is_admin, rate_limited

bp = Blueprint("admin", __name__, url_prefix="/admin")

_failed = defaultdict(list)   # ip -> timestamps of failed logins
LOCK_AFTER, LOCK_WINDOW = 5, 600


def _locked(ip):
    now = time.time()
    _failed[ip] = [t for t in _failed[ip] if now - t < LOCK_WINDOW]
    return len(_failed[ip]) >= LOCK_AFTER


def _safe_next(target):
    if not target:
        return url_for("admin.dashboard")
    p = urlparse(target)
    if p.netloc or not target.startswith("/admin"):
        return url_for("admin.dashboard")
    return target


def signup_allowed():
    """Open locally; in production only the very first account may be created unless ALLOW_SIGNUP=true."""
    flag = current_app.config.get("ALLOW_SIGNUP", "")
    if flag in ("true", "1", "yes"):
        return True
    if flag in ("false", "0", "no"):
        return db.count_users() == 0
    return (not current_app.config.get("IS_PRODUCTION")) or db.count_users() == 0


def _login_failure(reason, identifier):
    current_app.logger.info("login failed (%s) for %r", reason, identifier)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if is_admin():
        return redirect(url_for("admin.dashboard"))
    no_users = db.count_users() == 0
    if request.method == "POST":
        ip = client_ip()
        if _locked(ip) and not current_app.config.get("TESTING"):
            flash("Too many failed attempts. Try again in 10 minutes.", "error")
            return render_template("login.html", no_users=no_users, signup_open=signup_allowed()), 429
        identifier = request.form.get("identifier", request.form.get("username", "")).strip()
        password = request.form.get("password", "")
        user = db.get_user_by_identifier(identifier)
        if user is None:
            security.verify(security.hash_password("x"), password)       # keep timing similar for unknown users
            _login_failure("no such user", identifier)
        elif not user.is_active:
            _login_failure("account disabled", identifier)
        elif user.role != "admin":
            _login_failure("not an admin", identifier)
        elif not security.verify(user.password_hash, password):
            _login_failure("wrong password", identifier)
        else:
            session.clear()
            session["user_id"] = user.id
            session["admin"] = user.username
            session.permanent = False
            flash("Login successful", "success")
            return redirect(_safe_next(request.args.get("next")))
        _failed[ip].append(time.time())
        flash("Invalid username/email or password.", "error")
        return render_template("login.html", no_users=no_users, signup_open=signup_allowed(), identifier=identifier), 401
    return render_template("login.html", no_users=no_users, signup_open=signup_allowed())


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if is_admin():
        return redirect(url_for("admin.dashboard"))
    code_required = bool(current_app.config.get("ADMIN_SIGNUP_CODE")) and db.count_users() > 0
    ctx = {"errors": {}, "values": {}, "code_required": code_required,
           "min_len": current_app.config["MIN_PASSWORD_LENGTH"]}
    if not signup_allowed():
        flash("Sign up is closed. Ask an existing administrator for access.", "error")
        return render_template("signup.html", closed=True, **ctx), 403
    if request.method == "POST":
        if rate_limited("signup:" + client_ip(), 10, 600):
            flash("Too many sign-up attempts. Please try again later.", "error")
            return render_template("signup.html", closed=False, **ctx), 429
        f = request.form
        username, email = f.get("username", "").strip(), f.get("email", "").strip()
        ctx["values"] = {"username": username, "email": email}
        errors = security.validate_signup(username, email, f.get("password", ""), f.get("confirm", ""),
                                          ctx["min_len"])
        if code_required and f.get("signup_code", "").strip() != current_app.config["ADMIN_SIGNUP_CODE"]:
            errors["signup_code"] = "Invalid invitation code."
        if not errors:
            try:
                db.create_user(username, email, security.hash_password(f.get("password", "")), "admin")
            except ValueError as e:
                errors["username" if str(e) == "username_taken" else "email"] = (
                    "This username is already taken." if str(e) == "username_taken"
                    else "An account with this email already exists.")
        if errors:
            ctx["errors"] = errors
            flash("Please fix the highlighted fields.", "error")
            return render_template("signup.html", closed=False, **ctx), 400
        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("admin.login"))
    return render_template("signup.html", closed=False, **ctx)


@bp.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()                 # drops user_id, admin flag and the CSRF token
    flash("You have been logged out.", "info")
    return redirect(url_for("admin.login"))


def _filters():
    return {k: request.args.get(k, "").strip() for k in FILTER_KEYS if request.args.get(k, "").strip()}


@bp.route("/dashboard")
@admin_required
def dashboard():
    return render_template("dashboard.html", options=db.filter_options(), filters=_filters(), admin_page=True)


@bp.route("/analytics")
@admin_required
def analytics_page():
    return render_template("analytics.html", options=db.filter_options(), filters=_filters(), admin_page=True)


@bp.route("/feedback")
@admin_required
def explorer():
    f = _filters()
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    sort, direction = request.args.get("sort", "date"), request.args.get("dir", "desc")
    data = db.paginate(db.fetch_summaries(f), sort, direction, page, current_app.config["PER_PAGE"])
    qs = {k: v for k, v in request.args.items() if k not in ("page",)}
    return render_template("explorer.html", data=data, filters=f, options=db.filter_options(), sort=sort,
                           direction=direction, qs=qs, admin_page=True)


@bp.route("/issues")
@admin_required
def issues():
    f = _filters()
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    sort, direction = request.args.get("sort", "score"), request.args.get("dir", "desc")
    data = db.paginate(db.fetch_issues(f), sort, direction, page, current_app.config["PER_PAGE"])
    qs = {k: v for k, v in request.args.items() if k not in ("page",)}
    return render_template("issues.html", data=data, filters=f, counts=db.issue_counts(), options=db.filter_options(),
                           sort=sort, direction=direction, qs=qs, statuses=db.STATUSES, admin_page=True)


def _csv_safe(v):
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s   # CSV/Excel formula injection guard


@bp.route("/feedback/export.csv")
@admin_required
def export_csv():
    items = db.fetch_summaries(_filters())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "date", "student", "student_id", "department", "year", "course", "category", "aspects", "language",
                "feedback", "sentiment", "confidence", "severity", "priority", "priority_score", "issue_id", "status",
                "admin_response", "rating", "updated_at"])
    for i in items:
        w.writerow([i["id"], i["timestamp"], _csv_safe(i["student_name"]), _csv_safe(i["student_id"]),
                    _csv_safe(i["department"]), i["year"], _csv_safe(i["course"]), i["category"],
                    _csv_safe(i["aspect_names"]), i["language"], _csv_safe(i["text"]), i["sentiment"],
                    round(i["confidence"], 3), i["severity"], i["priority"], i["score"], i["issue_id"], i["status"],
                    _csv_safe(i["admin_response"]), i["rating"] or "", i["updated_at"]])
    data = "\ufeff" + buf.getvalue()    # BOM so Excel shows Tamil / Hindi correctly
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=edupulse_feedback.csv"})


@bp.route("/feedback/<int:fid>")
@admin_required
def detail(fid):
    d = db.feedback_detail(fid)
    if d is None:
        abort(404)
    similar = []
    try:
        rows = db.fetch_rows(None)
        clusters = analytics.cluster_complaints(rows, get_pipeline().priority_config)
        similar = analytics.similar_feedback_ids(clusters, fid)
    except Exception:
        current_app.logger.exception("similar-complaint lookup failed")
    return render_template("detail.html", d=d, similar=similar, statuses=db.STATUSES, admin_page=True)


@bp.route("/feedback/<int:fid>/update", methods=["POST"])
@admin_required
def update_feedback(fid):
    """Change status and/or add an admin response (forms on the detail page)."""
    status = request.form.get("status", "").strip()
    response = request.form.get("response", "").strip()
    note = request.form.get("note", "").strip()
    admin = session.get("admin", "admin")
    try:
        if request.form.get("action") == "create_issue":
            code = db.create_issue_for(fid, admin)
            if code is None:
                abort(404)
            flash(f"Issue {code} created.", "success")
        else:
            if response:
                if db.add_response(fid, response, admin, status or None) is None:
                    abort(404)
                flash("Response saved" + (f" and status set to {status}." if status else "."), "success")
            elif status:
                if db.update_status(fid, status, note, admin) is None:
                    abort(404)
                flash(f"Status changed to {status}.", "success")
            else:
                flash("Nothing to update: choose a status or write a response.", "error")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.detail", fid=fid))


@bp.route("/issues/<int:fid>/status", methods=["POST"])
@admin_required
def issue_status(fid):
    """Quick status change from the Issues list."""
    try:
        if db.update_status(fid, request.form.get("status", ""), request.form.get("note", ""), session.get("admin", "admin")) is None:
            abort(404)
        flash("Status updated.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(request.referrer if (request.referrer or "").startswith(request.host_url) else url_for("admin.issues"))


# ---------------------------------------------------------------- model page
def load_metrics():
    p = os.path.join(current_app.config["MODELS_DIR"], "metrics.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


@bp.route("/model-performance")
@admin_required
def model_performance():
    return render_template("model_performance.html", m=load_metrics(), info=get_pipeline().engine.info(),
                           admin_page=True)


@bp.route("/model-performance/retrain", methods=["POST"])
@admin_required
def retrain():
    from training.train import train_and_save
    try:
        metrics = train_and_save(data_path=current_app.config["TRAINING_DATA"],
                                 models_dir=current_app.config["MODELS_DIR"], quiet=True)
        get_pipeline().engine.reload()
        db.record_model_run(metrics)
        flash("Model retrained and evaluated on the held-out test split.", "success")
    except Exception as e:
        current_app.logger.exception("retrain failed")
        flash(f"Training failed: {e}", "error")
    return redirect(url_for("admin.model_performance"))


# ------------------------------------------------------------------ settings
@bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    pipe = get_pipeline()
    if request.method == "POST":
        action = request.form.get("action", "priority")
        if action == "password":
            cur, new, new2 = (request.form.get(k, "") for k in ("current_password", "new_password", "new_password2"))
            user = current_user()
            if not user or not security.verify(user.password_hash, cur):
                flash("Current password is incorrect.", "error")
            elif len(new) < current_app.config["MIN_PASSWORD_LENGTH"] or new != new2:
                flash("New password must be at least %d characters and match the confirmation."
                      % current_app.config["MIN_PASSWORD_LENGTH"], "error")
            else:
                db.set_user_password(user.id, security.hash_password(new))
                flash("Password updated.", "success")
            return redirect(url_for("admin.settings"))
        try:
            cfg = pipe.priority_config.to_dict()
            for a in list(cfg["criticality"]):
                v = request.form.get(f"crit_{a}")
                if v not in (None, ""):
                    x = float(v)
                    if not 0.05 <= x <= 1.0:
                        raise ValueError(f"Criticality for {a} must be between 0.05 and 1.0")
                    cfg["criticality"][a] = x
            for k, caster, lo, hi in (("frequency_cap", int, 1, 1000), ("window_days", int, 1, 365),
                                      ("recurring_threshold", int, 1, 1000), ("min_frequency", float, 0.0, 1.0),
                                      ("similarity_threshold", float, 0.05, 1.0),
                                      ("medium_min", float, 0, 100), ("high_min", float, 0, 100),
                                      ("critical_min", float, 0, 100)):
                v = request.form.get(k)
                if v not in (None, ""):
                    x = caster(v)
                    if not lo <= x <= hi:
                        raise ValueError(f"{k} must be between {lo} and {hi}")
                    cfg[k] = x
            if not cfg["medium_min"] < cfg["high_min"] < cfg["critical_min"]:
                raise ValueError("Thresholds must satisfy medium < high < critical")
            new_cfg = PriorityConfig.from_dict(cfg)
            db.set_setting("priority_config", new_cfg.to_dict())
            pipe.set_priority_config(new_cfg)
            flash("Priority settings saved. They apply to new feedback.", "success")
        except ValueError as e:
            flash(f"Invalid value: {e}", "error")
        return redirect(url_for("admin.settings"))
    return render_template("settings.html", cfg=pipe.priority_config, info=pipe.engine.info(),
                           db_kind=current_app.config["SQLALCHEMY_DATABASE_URI"].split(":")[0], admin_page=True,
                           aspects=list(pipe.priority_config.criticality))
