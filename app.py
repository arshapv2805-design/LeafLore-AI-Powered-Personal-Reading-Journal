"""LeafLore Flask application factory.

Production features integrated here:
- Sentry error monitoring (optional — set SENTRY_DSN env var)
- Flask-Talisman HTTPS enforcement + HSTS (production only)
- Flask-Limiter rate limiting
- WhiteNoise compressed static file serving
- Flask-Migrate database migrations
- Structured logging to stdout
- Security headers (CSP, X-Frame-Options, etc.)
- PWA routes (/sw.js, /manifest.json, /offline.html)
"""
import logging
import os

from flask import Flask, redirect, url_for, send_from_directory, make_response
from flask_login import current_user

from config import config_map, Config

# ── Logging setup (before app creation so import-time messages are captured) ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("leaflore")


def create_app(config_name: str | None = None, config_overrides: dict | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config_name: One of 'development', 'testing', 'production'.
                     Falls back to FLASK_ENV env var, then 'development'.
        config_overrides: Dict of config values to override (useful in tests).

    Returns:
        Configured Flask application instance.
    """
    # ── Resolve config ────────────────────────────────────────────────────────
    if isinstance(config_name, dict):
        config_overrides = config_name
        config_name = "testing"

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")
    cfg_class = config_map.get(config_name, config_map["default"])

    # ── Initialise Sentry before anything else so it captures startup errors ──
    sentry_dsn = os.environ.get("SENTRY_DSN", "")
    if sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[FlaskIntegration(), SqlalchemyIntegration()],
                traces_sample_rate=0.05,          # 5% perf tracing
                environment=config_name,
                send_default_pii=False,            # GDPR-friendly
                release=os.environ.get("GIT_COMMIT", "unknown"),
            )
            logger.info("Sentry initialised (env=%s)", config_name)
        except ImportError:
            logger.warning("sentry-sdk not installed; error monitoring disabled")

    # ── Create app ────────────────────────────────────────────────────────────
    app = Flask(__name__)
    app.config.from_object(cfg_class)
    if config_overrides:
        app.config.update(config_overrides)

    # ── Extensions ────────────────────────────────────────────────────────────
    from extensions import db, login_manager, csrf, migrate, limiter
    from models import User

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # ── WhiteNoise — compressed static file serving ───────────────────────────
    try:
        from whitenoise import WhiteNoise
        app.wsgi_app = WhiteNoise(
            app.wsgi_app,
            root=os.path.join(app.root_path, "static"),
            prefix="static",
            max_age=31_536_000 if config_name == "production" else 0,
            autorefresh=config_name != "production",
        )
        logger.info("WhiteNoise static serving enabled")
    except ImportError:
        logger.warning("whitenoise not installed; static files served by Flask")

    # ── HTTPS enforcement (production only) ───────────────────────────────────
    if config_name == "production":
        try:
            from flask_talisman import Talisman
            Talisman(
                app,
                force_https=True,
                strict_transport_security=True,
                strict_transport_security_max_age=31_536_000,
                session_cookie_secure=True,
                content_security_policy=False,    # we set CSP manually below
            )
            logger.info("Talisman HTTPS enforcement enabled")
        except ImportError:
            logger.warning("flask-talisman not installed; HTTPS not enforced")

    # ── Session & security config ─────────────────────────────────────────────
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", 1800)
    app.config.setdefault("MAX_CONTENT_LENGTH", 2 * 1024 * 1024)

    # ── Security headers ──────────────────────────────────────────────────────
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://books.google.com https://images.unsplash.com "
            "https://lh3.googleusercontent.com; "
            "connect-src 'self'; "
            "worker-src 'self';"
        )
        return response

    # ── User loader ───────────────────────────────────────────────────────────
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ── Blueprints ────────────────────────────────────────────────────────────
    from routes.auth import auth
    from routes.books import books
    from routes.notes import notes
    from routes.logs import logs
    from routes.dashboard import dashboard
    from routes.vocabulary import vocabulary
    from routes.admin import admin

    app.register_blueprint(auth)
    app.register_blueprint(books)
    app.register_blueprint(notes)
    app.register_blueprint(logs)
    app.register_blueprint(dashboard)
    app.register_blueprint(vocabulary)
    app.register_blueprint(admin)

    # ── PWA routes ────────────────────────────────────────────────────────────
    @app.route("/sw.js")
    def service_worker():
        """Serve service worker from root scope with required headers."""
        resp = make_response(send_from_directory("static", "sw.js"))
        resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
        resp.headers["Service-Worker-Allowed"] = "/"
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    @app.route("/manifest.json")
    def pwa_manifest():
        return send_from_directory("static", "manifest.json")

    @app.route("/offline.html")
    def offline_page():
        return send_from_directory("static", "offline.html")

    # ── Root redirect ─────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))

    # ── Health check (used by Render / UptimeRobot) ───────────────────────────
    @app.route("/health")
    @limiter.exempt
    def health():
        """Lightweight health-check endpoint — no auth, no DB hit."""
        return {"status": "ok", "env": config_name}, 200

    # ── Error handlers ────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        logger.warning("404: %s", e)
        return render_404(), 404

    @app.errorhandler(429)
    def rate_limited(e):
        logger.warning("429 Rate limit: %s", e)
        from flask import jsonify
        return jsonify(error="Rate limit exceeded. Please slow down."), 429

    @app.errorhandler(500)
    def server_error(e):
        logger.error("500 Internal error: %s", e, exc_info=True)
        return render_500(), 500

    logger.info(
        "LeafLore created (env=%s, db=%s)",
        config_name,
        "postgres" if "postgresql" in app.config.get("SQLALCHEMY_DATABASE_URI", "") else "sqlite",
    )
    return app


def render_404():
    """Minimal 404 HTML without template dependency."""
    return (
        "<!DOCTYPE html><html><head><title>404 - LeafLore</title></head>"
        "<body style='font-family:sans-serif;text-align:center;padding:60px'>"
        "<h1>🍃 Page Not Found</h1>"
        "<p>The page you're looking for doesn't exist.</p>"
        "<a href='/'>Go home</a></body></html>"
    )


def render_500():
    """Minimal 500 HTML without template dependency."""
    return (
        "<!DOCTYPE html><html><head><title>500 - LeafLore</title></head>"
        "<body style='font-family:sans-serif;text-align:center;padding:60px'>"
        "<h1>🍃 Something went wrong</h1>"
        "<p>We've been notified and are looking into it.</p>"
        "<a href='/'>Go home</a></body></html>"
    )


# ── Module-level app instance (used by flask CLI and gunicorn fallback) ───────
app = create_app()

if __name__ == "__main__":
    with app.app_context():
        from extensions import db
        db.create_all()
    app.run(debug=app.config.get("DEBUG", False))
