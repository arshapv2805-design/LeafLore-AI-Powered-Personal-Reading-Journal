"""LeafLore central configuration.

All sensitive values are loaded from environment variables.
A .env file can be used locally (python-dotenv loads it automatically when
the app starts via wsgi.py or `flask run`).
"""
import os
import secrets

# Load .env file for local development (no-op if python-dotenv not installed)
try:
    from dotenv import load_dotenv
    # Load .env explicitly from the project root directory where config.py resides
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration shared by all environments."""

    # ── Security ───────────────────────────────────────────────────────────────
    # In production, set SECRET_KEY as an environment variable.
    # Render auto-generates one; for local dev a random key is generated per
    # process (sessions won't survive restarts — set it explicitly for dev too).
    SECRET_KEY: str = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    # ── Database ───────────────────────────────────────────────────────────────
    _db_url: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'leaflore.db')}"
    )
    # Render/Heroku legacy postgres:// prefix fix
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI: str = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,       # reconnect if DB connection drops
        "pool_recycle": 300,         # recycle connections every 5 min
        "connect_args": (
            {}
            if _db_url.startswith("postgresql")
            else {"check_same_thread": False}   # SQLite only
        ),
    }

    # ── Sessions & Cookies ─────────────────────────────────────────────────────
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    SESSION_COOKIE_SECURE: bool = os.environ.get("FLASK_ENV") == "production"
    PERMANENT_SESSION_LIFETIME: int = 1800          # 30-minute session timeout

    # ── Request limits ─────────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH: int = 2 * 1024 * 1024       # 2 MB max upload

    # ── CSRF ───────────────────────────────────────────────────────────────────
    WTF_CSRF_ENABLED: bool = True

    # ── External APIs ──────────────────────────────────────────────────────────
    GOOGLE_BOOKS_API_URL: str = "https://www.googleapis.com/books/v1/volumes"
    GOOGLE_BOOKS_API_KEY: str = os.environ.get("GOOGLE_BOOKS_API_KEY", "")

    # ── Monitoring ─────────────────────────────────────────────────────────────
    SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "")

    # ── Rate limiting ──────────────────────────────────────────────────────────
    RATELIMIT_DEFAULT: str = "200 per day;50 per hour"
    RATELIMIT_STORAGE_URL: str = "memory://"        # swap for redis:// when available
    RATELIMIT_HEADERS_ENABLED: bool = True

    # ── Environment ────────────────────────────────────────────────────────────
    ENV: str = os.environ.get("FLASK_ENV", "development")
    DEBUG: bool = ENV == "development"
    TESTING: bool = False


class DevelopmentConfig(Config):
    """Local development — verbose errors, SQLite, no HTTPS."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """pytest — in-memory SQLite, CSRF disabled."""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    """Production — strict security, PostgreSQL required."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True

    @classmethod
    def validate(cls) -> None:
        """Raise if critical env vars are missing in production."""
        missing = []
        if not os.environ.get("SECRET_KEY"):
            missing.append("SECRET_KEY")
        if not os.environ.get("DATABASE_URL"):
            missing.append("DATABASE_URL")
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}"
            )


# Map string → class for `create_app(config_name="production")` usage
config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
