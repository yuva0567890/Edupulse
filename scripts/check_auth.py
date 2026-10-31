"""Self-test of the authentication stack on YOUR machine (uses a throw-away database, never your real one).

    python scripts/check_auth.py

It signs up an account, logs in by username and by e-mail, checks wrong-password rejection, logout and route
protection, and prints exactly which step fails (with library versions) if something is wrong.
"""
import os
import platform
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["EDUPULSE_SKIP_DOTENV"] = "1"
_tmp = tempfile.mkdtemp(prefix="edupulse_check_")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "check.db").replace("\\", "/")

results = []


def step(name, ok, detail=""):
    results.append(ok)
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   -> {detail}" if detail and not ok else ""))


def main():
    from importlib import metadata

    def ver(pkg):
        try:
            return metadata.version(pkg)
        except Exception:
            return "unknown"
    print(f"Python {platform.python_version()} | Flask {ver('flask')} | Werkzeug {ver('werkzeug')} | SQLAlchemy {ver('sqlalchemy')}")
    import hashlib
    print("scrypt available:", hasattr(hashlib, "scrypt"), "(PBKDF2 fallback is used otherwise)")
    from app import create_app
    app = create_app({"TESTING": True, "AUTO_SEED": False, "SQLALCHEMY_DATABASE_URI": os.environ["DATABASE_URL"]})
    c = app.test_client()
    d = {"username": "checkadmin", "email": "checkadmin@example.com", "password": "Check@12345", "confirm": "Check@12345"}
    r = c.post("/admin/signup", data=d)
    step("sign up", r.status_code == 302 and r.headers["Location"].endswith("/admin/login"), f"HTTP {r.status_code}")
    r = c.post("/admin/signup", data=d)
    step("duplicate sign-up is rejected", r.status_code == 400, f"HTTP {r.status_code}")
    r = c.post("/admin/login", data={"identifier": "checkadmin", "password": "wrong"})
    step("wrong password rejected", r.status_code == 401)
    r = c.post("/admin/login", data={"identifier": "checkadmin@example.com", "password": "Check@12345"})
    step("login with e-mail", r.status_code == 302 and r.headers["Location"].endswith("/admin/dashboard"), f"HTTP {r.status_code}")
    step("dashboard after login", c.get("/admin/dashboard").status_code == 200)
    c.post("/admin/logout")
    step("dashboard blocked after logout", c.get("/admin/dashboard").status_code == 302)
    c2 = app.test_client()
    r = c2.post("/admin/login", data={"identifier": "CheckAdmin", "password": "Check@12345"})
    step("login with username", r.status_code == 302, f"HTTP {r.status_code}")
    from database import db
    with app.app_context():
        u = db.get_user_by_username("checkadmin")
        step("password stored hashed", bool(u) and "Check@12345" not in u.password_hash)
    print("\nALL CHECKS PASSED" if all(results) else "\nSOME CHECKS FAILED - send this output to the developer")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
