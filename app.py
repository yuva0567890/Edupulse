"""EduPulse - Multilingual Aspect-Based Sentiment & Priority Analysis for Student Feedback.

Run locally:   python app.py
Production:    gunicorn app:app
"""
import json
import logging
import os
import sys

from flask import Flask, jsonify, render_template, request, session

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import i18n
from config import Config
from database import db
from nlp.pipeline import EduPulsePipeline
from nlp.priority import PriorityConfig
from nlp.recommendations import ASPECT_I18N, LEVEL_I18N, SENT_I18N
from routes import admin as admin_routes
from routes import api as api_routes
from routes import public as public_routes
from routes.common import check_csrf, csrf_token, is_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY_FROM_ENV") and app.config.get("IS_PRODUCTION"):
        app.logger.warning("SECRET_KEY is not set - sessions will reset on every restart. Set it in the environment.")

    db.init_db(app.config["SQLALCHEMY_DATABASE_URI"])

    from nlp import categories as _cats
    if _cats.load_overrides(app.config.get("CATEGORY_RULES_FILE")):
        app.logger.info("Loaded category rules from %s", app.config["CATEGORY_RULES_FILE"])
    cfg = PriorityConfig.from_dict(db.get_setting("priority_config"))
    pipeline = EduPulsePipeline(app.config["MODELS_DIR"], app.config["TRAINING_DATA"], cfg,
                                auto_train=not app.config.get("NO_AUTO_TRAIN", False))
    app.extensions["edupulse"] = {"pipeline": pipeline}
    app.logger.info("NLP mode: %s (%s)", pipeline.mode, pipeline.engine.status)

    app.register_blueprint(public_routes.bp)
    app.register_blueprint(admin_routes.bp)
    app.register_blueprint(api_routes.bp)

    if app.config.get("AUTO_SEED") and db.count_feedback() == 0:
        try:
            from scripts.seed_database import seed
            n = seed(app)
            app.logger.info("Seeded %d demo feedback rows (AUTO_SEED)", n)
        except Exception:
            app.logger.exception("auto seed failed")

    # ------------------------------------------------------- request hooks
    @app.before_request
    def _protect():
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            if request.path.startswith("/api/"):
                return None   # JSON endpoints: Content-Type check in the handler
            if not app.config.get("TESTING") and not check_csrf():
                return render_template("error.html", code=400,
                                       message="Your session expired. Please go back, refresh the page and try again."), 400
            if app.config.get("TESTING") and app.config.get("ENFORCE_CSRF_IN_TESTS") and not check_csrf():
                return render_template("error.html", code=400, message="CSRF check failed"), 400

    @app.after_request
    def _headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.path.startswith("/admin") or request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.context_processor
    def _ctx():
        lang = session.get("ui_lang", "en")
        if lang not in i18n.LANGS:
            lang = "en"

        def t(key):
            return i18n.translate(key, lang)

        def lbl(table, key):
            e = table.get(key)
            return e.get(lang, key) if e else key

        return {"t": t, "ui_lang": lang, "ui_languages": app.config["UI_LANGUAGES"], "csrf_token": csrf_token,
                "is_admin": is_admin(), "nlp_mode": pipeline.mode,
                "sent_label": lambda k: lbl(SENT_I18N, k), "aspect_label": lambda k: lbl(ASPECT_I18N, k),
                "level_label": lambda k: lbl(LEVEL_I18N, k), "admin_page": False,
                "aspect_names": {a: lbl(ASPECT_I18N, a) for a in ASPECT_I18N}}

    # ------------------------------------------------------ error handlers
    def _err(code, message):
        if request.path.startswith("/api/"):
            return jsonify({"error": message}), code
        return render_template("error.html", code=code, message=message), code

    @app.errorhandler(404)
    def _404(_e):
        return _err(404, "The page you are looking for was not found.")

    @app.errorhandler(405)
    def _405(_e):
        return _err(405, "This action is not allowed here.")

    @app.errorhandler(413)
    def _413(_e):
        return _err(413, "The submitted data is too large.")

    @app.errorhandler(500)
    def _500(_e):
        return _err(500, "Something went wrong on our side. Please try again.")

    @app.teardown_appcontext
    def _cleanup(_exc):
        db.remove_session()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  EduPulse running at  http://127.0.0.1:{port}\n  Admin login          http://127.0.0.1:{port}/admin/login\n")
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
