"""Application configuration (environment based).

Settings come from the process environment and from the project's ``.env`` file
(``.env`` values win, so editing the file and restarting always takes effect).
A tiny built-in parser is used, so it also works if python-dotenv is not installed.
"""
import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _load_env_file(path):
    """Minimal .env parser: KEY=VALUE, '#' comments, optional quotes. Non-empty values override existing
    variables. Set EDUPULSE_SKIP_DOTENV=1 to ignore the file (used by the test-suite)."""
    if not os.path.exists(path) or os.environ.get("EDUPULSE_SKIP_DOTENV") == "1":
        return
    try:
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                elif " #" in v:
                    v = v.split(" #", 1)[0].strip()
                if k and (v or k not in os.environ):
                    os.environ[k] = v
    except Exception:
        pass


_load_env_file(os.path.join(BASE_DIR, ".env"))


def _db_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
        return "sqlite:///" + os.path.join(BASE_DIR, "instance", "edupulse.db").replace("\\", "/")
    if url.startswith("postgres://"):           # Render / Heroku style
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _secret_key():
    """SECRET_KEY from the environment; otherwise a key generated once and kept in instance/.secret_key
    so sessions survive restarts in local development."""
    key = os.environ.get("SECRET_KEY", "").strip()
    if key:
        return key, True
    try:
        d = os.path.join(BASE_DIR, "instance")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, ".secret_key")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                k = f.read().strip()
            if k:
                return k, False
        k = secrets.token_hex(32)
        with open(p, "w", encoding="utf-8") as f:
            f.write(k)
        return k, False
    except Exception:
        return secrets.token_hex(32), False


_SK, _SK_ENV = _secret_key()


class Config:
    IS_PRODUCTION = bool(os.environ.get("RENDER")) or os.environ.get("FLASK_ENV") == "production"
    SECRET_KEY = _SK
    SECRET_KEY_FROM_ENV = _SK_ENV
    SQLALCHEMY_DATABASE_URI = _db_url()
    # Authentication is database based (users table). Accounts are created on /admin/signup.
    # ALLOW_SIGNUP: "true" / "false". Unset = open for local use; in production only the FIRST account may sign up.
    ALLOW_SIGNUP = os.environ.get("ALLOW_SIGNUP", "").strip().lower()
    ADMIN_SIGNUP_CODE = os.environ.get("ADMIN_SIGNUP_CODE", "").strip()      # optional invitation code
    MIN_PASSWORD_LENGTH = 8
    MODELS_DIR = os.path.join(BASE_DIR, "models", "saved")
    TRAINING_DATA = os.path.join(BASE_DIR, "data", "training_data.csv")
    SAMPLE_DATA = os.path.join(BASE_DIR, "data", "sample_feedback.csv")
    CATEGORY_RULES_FILE = os.path.join(BASE_DIR, "data", "category_rules.json")
    AUTO_SEED = os.environ.get("AUTO_SEED", "false").lower() in ("1", "true", "yes")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    MAX_CONTENT_LENGTH = 256 * 1024
    PER_PAGE = 15
    UI_LANGUAGES = {"en": "English", "ta": "தமிழ்", "hi": "हिन्दी"}
    TESTING = False
