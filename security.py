"""Password hashing and sign-up validation (no Flask / database imports, so it is easy to unit-test)."""
import re

from werkzeug.security import check_password_hash, generate_password_hash

MIN_PASSWORD_LENGTH = 8
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,39}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")


def hash_password(password: str) -> str:
    """Salted, slow hash (werkzeug default: scrypt). The plain password is never stored.
    Falls back to PBKDF2-SHA256 on Python builds that lack hashlib.scrypt."""
    try:
        return generate_password_hash(password)
    except (AttributeError, ValueError, TypeError):
        return generate_password_hash(password, method="pbkdf2:sha256")


def verify(password_hash: str, password: str) -> bool:
    try:
        return bool(password_hash) and check_password_hash(password_hash, password or "")
    except Exception:
        return False


def validate_signup(username, email, password, confirm, min_len=MIN_PASSWORD_LENGTH):
    """Return {field: message}. Empty dict = valid. Messages are plain English; the UI shows them as-is."""
    errors = {}
    username, email = (username or "").strip(), (email or "").strip()
    if not username:
        errors["username"] = "Username is required."
    elif not USERNAME_RE.match(username):
        errors["username"] = "Use 3-40 letters, numbers, dots, dashes or underscores (start with a letter or number)."
    if not email:
        errors["email"] = "Email is required."
    elif len(email) > 255 or not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    if not password:
        errors["password"] = "Password is required."
    elif len(password) < min_len:
        errors["password"] = f"Password must be at least {min_len} characters."
    elif len(password) > 200:
        errors["password"] = "Password is too long."
    if not confirm:
        errors["confirm"] = "Please confirm your password."
    elif password and confirm != password:
        errors["confirm"] = "Passwords do not match."
    return errors
