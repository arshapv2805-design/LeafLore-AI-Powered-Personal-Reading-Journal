"""
Smoke tests for LeafLore's core flow: register -> login -> add book ->
log pages -> set goal -> dashboard/API endpoints -> delete.

Run with:  pytest
"""
from datetime import date

import pytest


@pytest.fixture
def client(tmp_path):
    from app import create_app
    from extensions import db

    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "SECRET_KEY": "test-secret",
    })

    with app.app_context():
        db.create_all()
        with app.test_client() as test_client:
            yield test_client
        db.session.remove()
        db.drop_all()


def register(client, username="alice", email="alice@example.com", password="secret123"):
    return client.post(
        "/register",
        data={"username": username, "email": email, "password": password, "confirm_password": password},
        follow_redirects=True,
    )


def login(client, email="alice@example.com", password="secret123"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


def test_register_and_login(client):
    assert register(client).status_code == 200
    resp = login(client)
    assert resp.status_code == 200
    assert b"Dashboard" in resp.data


def test_unauthenticated_redirects_to_login(client):
    resp = client.get("/books/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_add_book_log_pages_and_streak(client):
    register(client)
    login(client)

    resp = client.post(
        "/books/add",
        data={"title": "Dune", "author": "Frank Herbert", "genre": "Sci-Fi", "total_pages": "412", "status": "reading"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Dune" in resp.data

    from models import Book

    book = Book.query.filter_by(title="Dune").first()
    assert book is not None

    resp = client.post(
        "/logs/add",
        data={"book_id": book.id, "date": date.today().isoformat(), "pages_read": "40"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert book.pages_read == 40

    from utils import get_streak

    assert get_streak(book.user_id) == 1


def test_future_date_log_is_rejected(client):
    register(client)
    login(client)
    client.post(
        "/books/add",
        data={"title": "Circe", "genre": "Fantasy", "total_pages": "393", "status": "reading"},
        follow_redirects=True,
    )
    from models import Book

    book = Book.query.filter_by(title="Circe").first()

    future = date.today().replace(year=date.today().year + 1).isoformat()
    resp = client.post(
        "/logs/add", data={"book_id": book.id, "date": future, "pages_read": "10"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert book.pages_read == 0


def test_goal_progress_and_dashboard(client):
    register(client)
    login(client)

    resp = client.post("/dashboard/goal", data={"target_books": "12"}, follow_redirects=True)
    assert resp.status_code == 200

    resp = client.get("/dashboard/")
    assert resp.status_code == 200

    resp = client.get("/dashboard/api/heatmap-data")
    assert resp.status_code == 200
    assert resp.is_json

    resp = client.get("/dashboard/api/recommendations")
    assert resp.status_code == 200
    assert resp.is_json
    assert resp.get_json() == []  # no completed books yet for this fresh user


def test_notes_and_status_change(client):
    register(client)
    login(client)
    client.post(
        "/books/add",
        data={"title": "Sapiens", "genre": "History", "total_pages": "443", "status": "want-to-read"},
        follow_redirects=True,
    )
    from models import Book

    book = Book.query.filter_by(title="Sapiens").first()

    resp = client.post("/books/" + str(book.id) + "/status", data={"status": "reading"}, follow_redirects=True)
    assert resp.status_code == 200
    assert book.status == "reading"

    resp = client.post(
        "/notes/" + str(book.id),
        data={"chapter": "Part One", "content": "Great opening chapter on the cognitive revolution."},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Part One" in resp.data


def test_cannot_access_another_users_book(client):
    register(client, username="alice", email="alice@example.com")
    login(client, email="alice@example.com")
    client.post(
        "/books/add", data={"title": "Educated", "genre": "Biography", "status": "reading"}, follow_redirects=True
    )
    from models import Book

    book = Book.query.filter_by(title="Educated").first()

    client.get("/logout")
    register(client, username="bob", email="bob@example.com")
    login(client, email="bob@example.com")

    resp = client.get("/books/" + str(book.id))
    assert resp.status_code == 403


def test_log_focus_session(client):
    register(client)
    login(client)
    client.post(
        "/books/add", data={"title": "Focus Book", "genre": "Sci-Fi", "status": "reading"}, follow_redirects=True
    )
    from models import Book, ReadingLog
    book = Book.query.filter_by(title="Focus Book").first()

    import json
    resp = client.post(
        "/dashboard/api/log-focus-session",
        data=json.dumps({"book_id": book.id, "pages_read": 15}),
        content_type="application/json"
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    log = ReadingLog.query.filter_by(book_id=book.id).first()
    assert log is not None
    assert log.pages_read == 15
    assert log.is_focus is True


def test_vocabulary_crud(client):
    # Register and login user 1
    register(client, username="alice", email="alice@example.com")
    login(client, email="alice@example.com")

    # Add a book
    client.post(
        "/books/add",
        data={"title": "Frankenstein", "author": "Mary Shelley", "genre": "Sci-Fi", "total_pages": "280", "status": "reading"},
        follow_redirects=True,
    )
    from models import Book, VocabularyWord

    book = Book.query.filter_by(title="Frankenstein").first()
    assert book is not None

    # Add a global word
    resp = client.post(
        "/vocabulary/add",
        data={"word": "Pernicious", "definition": "Short-lived", "context": "A pernicious butterfly", "chapter_or_page": "Page 10", "book_id": "-1"},
        follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Pernicious" in resp.data

    # Add a word linked to the book
    resp = client.post(
        "/vocabulary/add",
        data={"word": "Chimerical", "definition": "Imaginary", "context": "A chimerical project", "chapter_or_page": "Page 55", "book_id": str(book.id)},
        follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Chimerical" in resp.data

    # Verify filtering and searching
    # Filter by book
    resp = client.get(f"/vocabulary/?book_id={book.id}")
    assert b"Chimerical" in resp.data
    assert b"Pernicious" not in resp.data

    # Filter global
    resp = client.get("/vocabulary/?book_id=0")
    assert b"Pernicious" in resp.data
    assert b"Chimerical" not in resp.data

    # Search query
    resp = client.get("/vocabulary/?q=Imaginary")
    assert b"Chimerical" in resp.data
    assert b"Pernicious" not in resp.data

    # Edit the word
    word_entry = VocabularyWord.query.filter_by(word="Chimerical").first()
    assert word_entry is not None

    resp = client.post(
        f"/vocabulary/edit/{word_entry.id}",
        data={"word": "Chimerical-Updated", "definition": "Highly unrealistic", "context": "A chimerical plan", "chapter_or_page": "Page 60", "book_id": str(book.id)},
        follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Chimerical-Updated" in resp.data

    # User 2 cannot edit or delete User 1's word
    client.get("/logout")
    register(client, username="bob", email="bob@example.com")
    login(client, email="bob@example.com")

    # Bob tries to edit Alice's word
    resp = client.post(
        f"/vocabulary/edit/{word_entry.id}",
        data={"word": "Stolen", "definition": "Hack", "book_id": "-1"},
        follow_redirects=True
    )
    assert resp.status_code == 403

    # Bob tries to delete Alice's word
    resp = client.post(
        f"/vocabulary/delete/{word_entry.id}",
        follow_redirects=True
    )
    assert resp.status_code == 403

    # Alice logs back in and deletes her word
    client.get("/logout")
    login(client, email="alice@example.com")
    resp = client.post(
        f"/vocabulary/delete/{word_entry.id}",
        follow_redirects=True
    )
    assert resp.status_code == 200
    assert VocabularyWord.query.get(word_entry.id) is None
    assert b"removed from Word Bank" in resp.data


def test_reading_wrap_flow(client):
    # 1. Unauthenticated redirect
    client.get("/logout")
    resp = client.get("/dashboard/wrap", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]

    # Login
    register(client)
    login(client)

    # 2. Empty state check
    resp = client.get("/dashboard/wrap")
    assert resp.status_code == 200
    assert b"A Journey Waiting to Grow" in resp.data
    assert b"We couldn't find any reading activity logged" in resp.data

    # 3. Add data for this year
    from models import Book, ReadingLog, VocabularyWord
    from extensions import db
    from datetime import datetime

    # Add a completed book
    client.post(
        "/books/add",
        data={"title": "Test Book", "author": "Test Author", "genre": "Sci-Fi", "total_pages": "300", "status": "completed"},
        follow_redirects=True,
    )
    book = Book.query.filter_by(title="Test Book").first()
    assert book is not None

    # Ensure dates are set to current year
    book.date_completed = datetime.utcnow()
    book.date_added = datetime.utcnow()
    db.session.commit()

    # Log pages
    client.post(
        "/logs/add",
        data={"book_id": book.id, "date": date.today().isoformat(), "pages_read": "55"},
        follow_redirects=True,
    )

    # Add a vocab word
    client.post(
        "/vocabulary/add",
        data={"word": "Serendipity", "definition": "Happy accident", "context": "By serendipity", "chapter_or_page": "Page 5", "book_id": str(book.id)},
        follow_redirects=True
    )

    # 4. Filled state check
    resp = client.get("/dashboard/wrap")
    assert resp.status_code == 200
    assert b"Reading Wrap" in resp.data
    assert b"Books Completed" in resp.data
    assert b"55" in resp.data  # Pages Logged
    assert b"Sci-Fi" in resp.data  # Genre Sanctuary
    assert b"Words Mastered" in resp.data


def test_map_category_to_genre():
    from utils import map_category_to_genre
    assert map_category_to_genre("Science Fiction & Fantasy") == "Sci-Fi"
    assert map_category_to_genre("Biography & Autobiography") == "Biography"
    assert map_category_to_genre("Juvenile Fiction") == "Fiction"
    assert map_category_to_genre("Computers / Web Design") == "Non-Fiction"
    assert map_category_to_genre("History / Ancient") == "History"
    assert map_category_to_genre("Self-Help / Personal Growth") == "Self-Help"
    assert map_category_to_genre("Fantasy / Magic") == "Fantasy"
    assert map_category_to_genre("Cooking") == "Non-Fiction"
    assert map_category_to_genre("") == "Fiction"
    assert map_category_to_genre(None) == "Fiction"
    
    # Test title/description keyword matching overrides
    assert map_category_to_genre("Fiction", title="The Hobbit") == "Fantasy"
    assert map_category_to_genre("Juvenile Fiction", title="Harry Potter and the Sorcerer's Stone") == "Fantasy"
    assert map_category_to_genre("Fiction", title="Project Hail Mary", description="A lone astronaut in space") == "Sci-Fi"
    assert map_category_to_genre("Fiction", title="Dune", description="Set on a desert planet") == "Sci-Fi"
    assert map_category_to_genre("", title="Who Was Steve Jobs?") == "Biography"
    assert map_category_to_genre("Fiction", title="Atomic Habits: Build Good Habits") == "Self-Help"
    assert map_category_to_genre("", title="Summary of Sapiens") == "Non-Fiction"


def test_completion_predictor_heuristic_fallback(client):
    register(client)
    login(client)
    client.post(
        "/books/add",
        data={"title": "Single Book", "genre": "Fiction", "total_pages": "300", "status": "reading"},
        follow_redirects=True,
    )
    from models import Book
    book = Book.query.filter_by(title="Single Book").first()
    assert book is not None

    from ml.completion_predictor import get_completion_prediction
    prob, model_name = get_completion_prediction(book.id)
    assert "Baseline Heuristic Model" in model_name
    assert 5 <= prob <= 95


def test_completion_predictor_logistic_regression(client):
    register(client)
    login(client)
    from extensions import db
    from models import Book, ReadingLog
    
    for i in range(3):
        b = Book(user_id=1, title=f"Comp Book {i}", genre="Fiction", total_pages=300, status="completed")
        db.session.add(b)
        db.session.commit()
        db.session.add(ReadingLog(book_id=b.id, date=date.today(), pages_read=100))
        db.session.commit()
        
    for i in range(3):
        b = Book(user_id=1, title=f"InProg Book {i}", genre="Fiction", total_pages=300, status="reading")
        db.session.add(b)
        db.session.commit()
        db.session.add(ReadingLog(book_id=b.id, date=date.today(), pages_read=10))
        db.session.commit()
        
    target = Book.query.filter_by(title="InProg Book 0").first()
    from ml.completion_predictor import get_completion_prediction
    prob, model_name = get_completion_prediction(target.id)
    
    assert "Logistic Regression" in model_name
    assert isinstance(prob, int)


def test_login_rate_limiting(client):
    from routes.auth import login_attempts
    login_attempts.clear()
    
    for i in range(5):
        resp = client.post("/login", data={"email": "hacker@example.com", "password": "wrong"})
        assert resp.status_code != 429
        
    resp = client.post("/login", data={"email": "hacker@example.com", "password": "wrong"})
    assert resp.status_code == 429
    assert b"Too many login attempts" in resp.data


def test_security_headers(client):
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "Content-Security-Policy" in resp.headers


def test_dashboard_customization_configs(client):
    from routes.auth import login_attempts
    login_attempts.clear()
    register(client)
    login(client)
    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    assert b"widgetCustomizerModal" in resp.data
    assert b"customizer-heatmap" in resp.data
    assert b"customizer-focus-oasis" in resp.data
    assert b"customizer-insights" in resp.data
    assert b"customizer-recommendations" in resp.data
    assert b"onboardingTourModal" in resp.data
    assert b"onboardingCarousel" in resp.data


def test_reduced_motion_classes(client):
    from routes.auth import login_attempts
    login_attempts.clear()
    register(client)
    login(client)
    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    assert b"calm-toggle" in resp.data




