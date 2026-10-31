"""Public pages: home, feedback form, result."""
from urllib.parse import urlparse

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for)

from database import db
from nlp.pipeline import FeedbackError
from .common import (CATEGORY_CHOICES, LANG_HINTS, YEARS, analyze_and_store, clean_form, client_ip, is_admin, rate_limited)

bp = Blueprint("public", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "database": db.db_ok()})


@bp.route("/set-language/<code>")
def set_language(code):
    if code in current_app.config["UI_LANGUAGES"]:
        session["ui_lang"] = code
    target = request.referrer or url_for("public.index")
    host = urlparse(target)
    if host.netloc and host.netloc != request.host:   # prevent open redirects
        target = url_for("public.index")
    return redirect(target)


@bp.route("/feedback", methods=["GET", "POST"])
def feedback():
    ctx = {"values": {}, "errors": {}, "years": YEARS, "lang_hints": LANG_HINTS, "category_choices": CATEGORY_CHOICES}
    if request.method == "POST":
        if rate_limited("submit:" + client_ip(), 20):
            flash("Too many submissions. Please wait a minute.", "error")
            return render_template("feedback.html", **ctx), 429
        cleaned, errors = clean_form(request.form)
        ctx["values"] = request.form
        if errors:
            ctx["errors"] = errors
            return render_template("feedback.html", **ctx), 400
        try:
            fid, _ = analyze_and_store(cleaned)
        except FeedbackError as e:
            ctx["errors"] = {"text": str(e)}
            return render_template("feedback.html", **ctx), 400
        except Exception:
            current_app.logger.exception("analysis failed")
            flash("Something went wrong while analysing your feedback. Please try again.", "error")
            return render_template("feedback.html", **ctx), 500
        mine = session.get("my_results", [])
        mine.append(fid)
        session["my_results"] = mine[-25:]
        return redirect(url_for("public.result", fid=fid))
    return render_template("feedback.html", **ctx)


@bp.route("/result/<int:fid>")
def result(fid):
    if not (is_admin() or fid in session.get("my_results", [])):
        abort(404)
    d = db.feedback_detail(fid)
    if d is None:
        abort(404)
    return render_template("result.html", d=d)
