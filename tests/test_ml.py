"""Unit tests for LeafLore's ML/analytics layer.

Run with:  pytest
"""
from datetime import date, timedelta

import pytest


@pytest.fixture
def app_ctx(tmp_path):
    from app import create_app
    from extensions import db

    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 't.db'}",
        "SECRET_KEY": "test-secret",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(db, username="u", email="u@example.com"):
    from models import User

    user = User(username=username, email=email)
    user.set_password("secret123")
    db.session.add(user)
    db.session.commit()
    return user


# ---- recommender ----------------------------------------------------------


def test_recommendations_rank_similar_genre_higher(app_ctx):
    from extensions import db
    from models import Book
    from ml.recommender import get_recommendations

    user = _make_user(db)
    db.session.add(
        Book(
            user_id=user.id, title="Dune-ish Anchor", author="A. Author", genre="Sci-Fi",
            description="planet science fiction space exploration mission", status="completed",
            total_pages=400, date_completed=date.today(),
        )
    )
    db.session.add(
        Book(
            user_id=user.id, title="Close Match", author="B. Author", genre="Sci-Fi",
            description="planet science fiction space exploration crew", status="want-to-read",
            total_pages=450,
        )
    )
    db.session.add(
        Book(
            user_id=user.id, title="Unrelated Pick", author="C. Author", genre="Self-Help",
            description="habits routine productivity daily life", status="want-to-read",
            total_pages=300,
        )
    )
    db.session.commit()

    recs = get_recommendations(user.id, limit=5)
    shelf_recs = [r for r in recs if r["source"] == "shelf"]

    assert shelf_recs, "expected at least one shelf-based recommendation"
    assert shelf_recs[0]["title"] == "Close Match"
    assert shelf_recs[0]["score"] > 0


def test_recommendations_cold_start_returns_empty(app_ctx):
    from extensions import db
    from ml.recommender import get_recommendations

    user = _make_user(db, username="new", email="new@example.com")
    assert get_recommendations(user.id) == []


def test_recommendations_empty_shelf_falls_back_gracefully(app_ctx):
    """No want-to-read books and no network access -> empty list, not a crash."""
    from extensions import db
    from models import Book
    from ml.recommender import get_recommendations

    user = _make_user(db, username="solo", email="solo@example.com")
    db.session.add(
        Book(
            user_id=user.id, title="Only Completed", genre="Fiction",
            description="a story", status="completed", total_pages=200,
            date_completed=date.today(),
        )
    )
    db.session.commit()

    recs = get_recommendations(user.id)
    assert isinstance(recs, list)


# ---- analytics --------------------------------------------------------------


def test_reading_pace_reflects_logged_pages(app_ctx):
    from extensions import db
    from models import Book, ReadingLog
    from ml.analytics import reading_pace

    user = _make_user(db, username="pace", email="pace@example.com")
    book = Book(user_id=user.id, title="X", status="reading", total_pages=300)
    db.session.add(book)
    db.session.commit()

    for d in range(5):
        db.session.add(ReadingLog(book_id=book.id, date=date.today() - timedelta(days=d), pages_read=20))
    db.session.commit()

    pace = reading_pace(user.id, window_days=7)
    # 5 days of 20 pages + 2 idle days, averaged over a 7-day window
    assert pace["avg_pages_per_day"] == round(100 / 7, 1)


def test_reading_pace_zero_when_no_logs(app_ctx):
    from extensions import db
    from ml.analytics import reading_pace

    user = _make_user(db, username="idle", email="idle@example.com")
    assert reading_pace(user.id)["avg_pages_per_day"] == 0.0


def test_predicted_finish_date_is_not_in_the_past(app_ctx):
    from extensions import db
    from models import Book, ReadingLog
    from ml.analytics import predicted_finish_dates

    user = _make_user(db, username="finish", email="finish@example.com")
    book = Book(user_id=user.id, title="Y", status="reading", total_pages=300)
    db.session.add(book)
    db.session.commit()
    db.session.add(ReadingLog(book_id=book.id, date=date.today(), pages_read=30))
    db.session.commit()

    preds = predicted_finish_dates(user.id)
    assert len(preds) == 1
    assert preds[0]["finish_date"] >= date.today()
    assert preds[0]["book_id"] == book.id


def test_predicted_finish_skips_books_without_total_pages(app_ctx):
    from extensions import db
    from models import Book
    from ml.analytics import predicted_finish_dates

    user = _make_user(db, username="nopages", email="nopages@example.com")
    db.session.add(Book(user_id=user.id, title="No total pages", status="reading", total_pages=0))
    db.session.commit()

    assert predicted_finish_dates(user.id) == []


def test_monthly_trend_compares_this_and_last_month(app_ctx):
    from extensions import db
    from models import Book, ReadingLog
    from ml.analytics import monthly_trend
    import calendar as cal

    user = _make_user(db, username="trend", email="trend@example.com")
    book = Book(user_id=user.id, title="Z", status="reading", total_pages=999)
    db.session.add(book)
    db.session.commit()

    today = date.today()
    last_month_date = today.replace(day=1) - timedelta(days=1)
    # clamp to a valid day in last month
    last_month_day = min(today.day, cal.monthrange(last_month_date.year, last_month_date.month)[1])
    last_month_date = last_month_date.replace(day=last_month_day)

    db.session.add(ReadingLog(book_id=book.id, date=today, pages_read=50))
    db.session.add(ReadingLog(book_id=book.id, date=last_month_date, pages_read=25))
    db.session.commit()

    trend = monthly_trend(user.id)
    assert trend["this_month"] == 50
    assert trend["last_month"] == 25
    assert trend["pct_change"] == 100.0


def test_monthly_pages_series_has_requested_length(app_ctx):
    from extensions import db
    from ml.analytics import monthly_pages_series

    user = _make_user(db, username="series", email="series@example.com")
    labels, values = monthly_pages_series(user.id, months=12)
    assert len(labels) == 12
    assert len(values) == 12
    assert all(v == 0 for v in values)
