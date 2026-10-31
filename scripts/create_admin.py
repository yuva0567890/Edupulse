"""OPTIONAL setup helper: create or reset an admin account (the password is HASHED before it is stored).

You do NOT need this script: open /admin/signup in the browser to create an account.
Use it for headless setups, resetting a forgotten password, or seeding a demo account.

    python scripts/create_admin.py --username demo --email demo@example.com --password "Demo@12345"
    python scripts/create_admin.py --prompt          # asks for everything interactively
    python scripts/create_admin.py --list            # shows existing accounts (never passwords)
"""
import argparse
import getpass
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--username")
    ap.add_argument("--email")
    ap.add_argument("--password")
    ap.add_argument("--prompt", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    import security
    from app import create_app
    from database import db
    app = create_app()
    with app.app_context():
        if a.list:
            from sqlalchemy import select
            from database.models import User
            rows = db.get_session().execute(select(User)).scalars().all()
            print(f"{len(rows)} account(s):")
            for u in rows:
                print(f"  #{u.id}  {u.username:<20} {u.email:<32} role={u.role} active={bool(u.is_active)}")
            return 0
        username, email, password = a.username, a.email, a.password
        if a.prompt or not (username and email and password):
            username = username or input("Username: ").strip()
            email = email or input("Email: ").strip()
            password = password or getpass.getpass(f"Password (min {security.MIN_PASSWORD_LENGTH} chars): ")
            if a.prompt and password != getpass.getpass("Repeat password: "):
                print("Passwords do not match.")
                return 1
        errors = security.validate_signup(username, email, password, password)
        if errors:
            for k, v in errors.items():
                print(f"  {k}: {v}")
            return 1
        existing = db.get_user_by_username(username) or db.get_user_by_email(email)
        if existing:
            db.set_user_password(existing.id, security.hash_password(password))
            print(f"Password reset for '{existing.username}'. Log in with username or email '{existing.email}'.")
        else:
            db.create_user(username, email, security.hash_password(password), "admin")
            print(f"Admin '{username}' created. Log in at http://127.0.0.1:5000/admin/login")
    return 0


if __name__ == "__main__":
    sys.exit(main())
