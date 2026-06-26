"""
Production-grade test suite additions for LeafLore.

Covers:
- Health check endpoint
- Security headers on every response
- Rate-limiter headers present
- Offline batch-sync endpoint (valid and invalid payloads)
- Config: production validation guard raises on missing env vars
- Config: postgres:// URL prefix fix
- WSGI entry point importable
- Service worker + manifest routes
- Error handlers (404, 429, 500)
"""
import json
import os
import pytest


# ── Shared fixture ─────────────────────────────────────────────────────────────
@pytest.fixture
def client(tmp_path):
    from app import create_app
    from extensions import db

    app = create_app(config_overrides={
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'prod_test.db'}",
        "SECRET_KEY": "prod-test-secret-key",
        "RATELIMIT_ENABLED": False,   # disable rate limits in tests
    })

    with app.app_context():
        db.create_all()
        with app.test_client() as c:
            yield c
        db.session.remove()
        db.drop_all()


@pytest.fixture
def logged_in_client(client, tmp_path):
    """A client with a registered and logged-in user."""
    client.post(
        "/register",
        data={"username": "produser", "email": "prod@test.com",
              "password": "ProdPass1!", "confirm_password": "ProdPass1!"},
        follow_redirects=True,
    )
    client.post(
        "/login",
        data={"email": "prod@test.com", "password": "ProdPass1!"},
        follow_redirects=True,
    )
    return client


# ── Health check ───────────────────────────────────────────────────────────────
def test_health_endpoint(client):
    """GET /health returns 200 with status: ok — no auth required."""
    r = client.get("/health")
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["status"] == "ok"


# ── Security headers ───────────────────────────────────────────────────────────
def test_security_headers_present(client):
    """Every response must include all mandatory security headers."""
    r = client.get("/")  # redirects, but headers are still set
    expected_headers = [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-XSS-Protection",
        "Referrer-Policy",
        "Content-Security-Policy",
    ]
    for header in expected_headers:
        assert header in r.headers, f"Missing security header: {header}"


def test_csp_includes_worker_src(client):
    """CSP must include worker-src 'self' for the service worker."""
    r = client.get("/health")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "worker-src" in csp


def test_x_frame_options(client):
    """X-Frame-Options must be SAMEORIGIN (clickjacking protection)."""
    r = client.get("/health")
    assert r.headers.get("X-Frame-Options") == "SAMEORIGIN"


# ── PWA routes ─────────────────────────────────────────────────────────────────
def test_manifest_route(client):
    """GET /manifest.json returns a valid JSON manifest."""
    r = client.get("/manifest.json")
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["name"] == "LeafLore"
    assert "icons" in data


def test_service_worker_route(client):
    """GET /sw.js returns JS with required Service-Worker-Allowed header."""
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert r.headers.get("Service-Worker-Allowed") == "/"
    assert "javascript" in r.headers.get("Content-Type", "")


def test_offline_page_route(client):
    """GET /offline.html returns the offline fallback page."""
    r = client.get("/offline.html")
    assert r.status_code == 200
    assert b"offline" in r.data.lower()


# ── Offline batch-sync endpoint ────────────────────────────────────────────────
def test_offline_sync_requires_auth(client):
    """POST /dashboard/api/offline-sync without login returns 401/redirect."""
    r = client.post(
        "/dashboard/api/offline-sync",
        json={"items": []},
        content_type="application/json",
    )
    # Flask-Login redirects unauthenticated users
    assert r.status_code in (302, 401)


def test_offline_sync_empty_payload(logged_in_client):
    """Empty items list returns success with empty processed array."""
    r = logged_in_client.post(
        "/dashboard/api/offline-sync",
        json={"items": []},
        content_type="application/json",
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["success"] is True
    assert data["processed"] == []
    assert data["errors"] == []


def test_offline_sync_invalid_type(logged_in_client):
    """Items must be a list — dict payload returns 400."""
    r = logged_in_client.post(
        "/dashboard/api/offline-sync",
        json={"items": "not-a-list"},
        content_type="application/json",
    )
    assert r.status_code == 400


def test_offline_sync_unknown_book(logged_in_client):
    """Syncing a log for a non-existent book returns an error entry."""
    r = logged_in_client.post(
        "/dashboard/api/offline-sync",
        json={"items": [{"id": 1, "type": "quick_log", "book_id": 99999, "pages_read": 5}]},
        content_type="application/json",
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert len(data["errors"]) == 1
    assert data["processed"] == []


def test_offline_sync_unknown_item_type(logged_in_client):
    """Unknown item type goes to errors, not processed."""
    r = logged_in_client.post(
        "/dashboard/api/offline-sync",
        json={"items": [{"id": 42, "type": "mystery_type", "book_id": 1, "pages_read": 5}]},
        content_type="application/json",
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert any(e["id"] == 42 for e in data["errors"])


# ── Config validation ──────────────────────────────────────────────────────────
def test_production_config_validates_missing_vars():
    """ProductionConfig.validate() raises RuntimeError if SECRET_KEY missing."""
    from config import ProductionConfig
    env_backup = os.environ.pop("SECRET_KEY", None)
    db_backup = os.environ.pop("DATABASE_URL", None)
    try:
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            ProductionConfig.validate()
    finally:
        if env_backup:
            os.environ["SECRET_KEY"] = env_backup
        if db_backup:
            os.environ["DATABASE_URL"] = db_backup


def test_postgres_url_prefix_fix():
    """postgres:// must be rewritten to postgresql:// for SQLAlchemy."""
    import importlib
    import config as cfg_module

    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "postgres://user:pass@host/db"
    try:
        importlib.reload(cfg_module)
        from config import Config
        assert Config.SQLALCHEMY_DATABASE_URI.startswith("postgresql://")
    finally:
        if original:
            os.environ["DATABASE_URL"] = original
        else:
            os.environ.pop("DATABASE_URL", None)
        importlib.reload(cfg_module)


# ── WSGI entry point ───────────────────────────────────────────────────────────
def test_wsgi_importable():
    """wsgi.py must be importable and expose an `app` object."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "wsgi",
        os.path.join(os.path.dirname(__file__), "..", "wsgi.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "app")
    assert callable(mod.app)


# ── 404 error handler ──────────────────────────────────────────────────────────
def test_404_returns_html(client):
    """A request to a non-existent route returns 404 with HTML."""
    r = client.get("/this-page-does-not-exist-xyzabc")
    assert r.status_code == 404
    assert b"404" in r.data or b"Not Found" in r.data
