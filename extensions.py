"""Shared Flask extension instances.

Instantiated here (without an app) so they can be imported by both
`app.py` (which calls `.init_app()`) and any blueprint that needs them,
without creating circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ── Core ──────────────────────────────────────────────────────────────────────
db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access LeafLore."
login_manager.login_message_category = "info"

csrf = CSRFProtect()

# ── Database migrations ───────────────────────────────────────────────────────
migrate = Migrate()

# ── Rate limiting ─────────────────────────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",       # upgrade to redis:// for multi-worker prod
    headers_enabled=True,          # adds X-RateLimit-* headers
)
