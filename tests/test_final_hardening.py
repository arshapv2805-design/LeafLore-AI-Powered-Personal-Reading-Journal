import json
import pytest
from models.user import User
from models.book import Book
from models.reading_log import ReadingLog
from extensions import db

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
def logged_in_client(client):
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

@pytest.fixture
def logged_in_user_id(logged_in_client):
    with logged_in_client.application.app_context():
        user = User.query.filter_by(username="produser").first()
        return user.id

def test_settings_page_loads(logged_in_client):
    """GET /dashboard/settings returns 200."""
    r = logged_in_client.get("/dashboard/settings")
    assert r.status_code == 200
    assert b"Settings" in r.data
    assert b"Calm Mode" in r.data

def test_update_settings(logged_in_client, logged_in_user_id):
    """POST /dashboard/settings updates user settings (calm_mode, daily_target)."""
    r = logged_in_client.post("/dashboard/settings", data={
        "action": "update_profile",
        "daily_target": "25",
        "calm_mode": "on"
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"Profile settings updated successfully!" in r.data
    
    with logged_in_client.application.app_context():
        user = db.session.get(User, logged_in_user_id)
        assert user.daily_target == 25
        assert user.calm_mode is True

def test_export_endpoints(logged_in_client):
    """Verify data exports generate correct mime-types and file structures."""
    # 1. Logs export (CSV)
    r = logged_in_client.get("/dashboard/settings/export/logs")
    assert r.status_code == 200
    assert r.headers.get("Content-Type") == "text/csv"
    assert b"Log ID,Book Title,Author,Date,Pages Read" in r.data

    # 2. Notes export (Markdown)
    r = logged_in_client.get("/dashboard/settings/export/notes")
    assert r.status_code == 200
    assert r.headers.get("Content-Type") == "text/markdown"

    # 3. Archive export (JSON)
    r = logged_in_client.get("/dashboard/settings/export/archive")
    assert r.status_code == 200
    assert r.headers.get("Content-Type") == "application/json"
    archive = json.loads(r.data)
    assert "username" in archive
    assert "books" in archive
    assert "goals" in archive

def test_ajax_log_addition(logged_in_client, logged_in_user_id):
    """POST /logs/add with AJAX Accept header returns JSON."""
    with logged_in_client.application.app_context():
        book = Book(
            user_id=logged_in_user_id,
            title="Test Book For AJAX",
            author="AJAX Author",
            total_pages=300,
            status="reading"
        )
        db.session.add(book)
        db.session.commit()
        book_id = book.id

    r = logged_in_client.post("/logs/add", data={
        "book_id": str(book_id),
        "pages_read": "15",
        "date": "2026-06-25"
    }, headers={"Accept": "application/json"})
    assert r.status_code == 200
    res = json.loads(r.data)
    assert res["success"] is True
    assert "logged" in res["message"].lower()


def test_reset_data(logged_in_client, logged_in_user_id):
    """POST /dashboard/settings with action=reset_data deletes books, goals, vocabulary, and session cache."""
    from datetime import date
    
    # 1. Add some data for the user
    with logged_in_client.application.app_context():
        from models import Book, Goal, VocabularyWord, ReadingLog
        
        # Add a book
        book = Book(user_id=logged_in_user_id, title="Temp Book", total_pages=100)
        db.session.add(book)
        db.session.commit()
        
        # Add a reading log
        log = ReadingLog(book_id=book.id, date=date.today(), pages_read=10)
        db.session.add(log)
        
        # Add a goal
        goal = Goal(user_id=logged_in_user_id, year=2026, target_books=12)
        db.session.add(goal)
        
        # Add a vocabulary word
        word = VocabularyWord(user_id=logged_in_user_id, word="temp", definition="test definition")
        db.session.add(word)
        
        db.session.commit()
        
        # Set unlocked achievements in session
        with logged_in_client.session_transaction() as sess:
            sess["unlocked_achievements"] = ["novice"]

    # 2. Trigger reset_data POST request
    r = logged_in_client.post("/dashboard/settings", data={
        "action": "reset_data"
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"reset successfully" in r.data
    
    # 3. Verify data is gone in the database
    with logged_in_client.application.app_context():
        from models import Book, Goal, VocabularyWord, ReadingLog
        assert Book.query.filter_by(user_id=logged_in_user_id).count() == 0
        assert Goal.query.filter_by(user_id=logged_in_user_id).count() == 0
        assert VocabularyWord.query.filter_by(user_id=logged_in_user_id).count() == 0
        assert db.session.query(ReadingLog).count() == 0
        
    # 4. Verify session is cleared of achievements
    with logged_in_client.session_transaction() as sess:
        assert "unlocked_achievements" not in sess


def test_delete_account(logged_in_client, logged_in_user_id):
    """POST /dashboard/settings with action=delete_account deletes the user from database."""
    r = logged_in_client.post("/dashboard/settings", data={
        "action": "delete_account"
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"permanently deleted" in r.data
    
    with logged_in_client.application.app_context():
        assert db.session.get(User, logged_in_user_id) is None

