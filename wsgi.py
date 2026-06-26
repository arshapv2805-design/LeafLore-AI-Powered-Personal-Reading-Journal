"""WSGI entry point for production (gunicorn).

Usage:
    gunicorn wsgi:app --workers 2 --threads 2 --timeout 120 --bind 0.0.0.0:$PORT

The module-level `app` is created once; gunicorn forks workers from it.
"""
from app import create_app

app = create_app()
