import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_tmp = tempfile.mkdtemp(prefix="edupulse_test_")
os.environ["EDUPULSE_SKIP_DOTENV"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "import.db").replace("\\", "/")

import pytest


@pytest.fixture(scope="session")
def pipeline():
    from nlp.pipeline import EduPulsePipeline
    return EduPulsePipeline(os.path.join(ROOT, "models", "saved"), os.path.join(ROOT, "data", "training_data.csv"))


ADMIN = {"username": "testadmin", "email": "testadmin@example.com", "password": "Test@12345"}


def make_app(tmp_path, **extra):
    from app import create_app
    from routes import admin as _admin, common as _common
    _admin._failed.clear()           # in-memory lock-out / rate-limit state must not leak between tests
    _common._hits.clear()
    cfg = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "t.db").replace("\\", "/"),
           "AUTO_SEED": False}
    cfg.update(extra)
    return create_app(cfg)


@pytest.fixture()
def app(tmp_path):
    return make_app(tmp_path)


@pytest.fixture()
def client(app):
    return app.test_client()


def signup(c, **over):
    d = {"username": ADMIN["username"], "email": ADMIN["email"], "password": ADMIN["password"],
         "confirm": ADMIN["password"], **over}
    return c.post("/admin/signup", data=d)


@pytest.fixture()
def admin_client(app):
    """A client logged in through the REAL flow: sign up -> login (no shortcuts)."""
    c = app.test_client()
    assert signup(c).status_code == 302
    r = c.post("/admin/login", data={"identifier": ADMIN["email"], "password": ADMIN["password"]})
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/dashboard")
    return c
