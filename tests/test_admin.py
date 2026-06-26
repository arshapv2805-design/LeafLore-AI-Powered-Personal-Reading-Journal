import json
import pytest
from models.user import User
from models.book import Book
from extensions import db

@pytest.fixture
def client(tmp_path):
    from app import create_app
    from extensions import db

    app = create_app(config_overrides={
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'admin_test.db'}",
        "SECRET_KEY": "admin-test-secret-key",
        "RATELIMIT_ENABLED": False,
    })

    with app.app_context():
        db.create_all()
        # Seed default users
        admin = User(username="admin", email="admin@test.com", is_admin=True)
        admin.set_password("AdminPass1!")
        
        regular = User(username="regular", email="regular@test.com", is_admin=False)
        regular.set_password("RegularPass1!")
        
        db.session.add(admin)
        db.session.add(regular)
        db.session.commit()
        
        with app.test_client() as c:
            yield c
        db.session.remove()
        db.drop_all()

def test_admin_access_restricted(client):
    """Verify regular user and guest get 403 / redirect for admin routes."""
    # 1. Guest
    r = client.get("/admin/")
    assert r.status_code == 302 # Redirect to login

    # 2. Login as regular user
    client.post("/login", data={"email": "regular@test.com", "password": "RegularPass1!"}, follow_redirects=True)
    r = client.get("/admin/")
    assert r.status_code == 403

def test_admin_dashboard_loads(client):
    """Verify admin user can load the dashboard and view user list."""
    client.post("/login", data={"email": "admin@test.com", "password": "AdminPass1!"}, follow_redirects=True)
    r = client.get("/admin/")
    assert r.status_code == 200
    assert b"Admin Control Center" in r.data
    assert b"regular@test.com" in r.data
    assert b"admin@test.com" in r.data

def test_admin_toggle_role(client):
    """Verify admin can toggle role of a regular user."""
    client.post("/login", data={"email": "admin@test.com", "password": "AdminPass1!"}, follow_redirects=True)
    
    with client.application.app_context():
        u = User.query.filter_by(username="regular").first()
        user_id = u.id
        assert not u.is_admin

    r = client.post(f"/admin/toggle-role/{user_id}", follow_redirects=True)
    assert r.status_code == 200
    assert b"Updated role for user" in r.data
    
    with client.application.app_context():
        u = User.query.filter_by(username="regular").first()
        assert u.is_admin

def test_admin_reset_user_data(client):
    """Verify admin can reset user data."""
    # Add a book for regular user
    with client.application.app_context():
        u = User.query.filter_by(username="regular").first()
        b = Book(user_id=u.id, title="Test Admin Book", total_pages=100)
        db.session.add(b)
        db.session.commit()
        user_id = u.id

    client.post("/login", data={"email": "admin@test.com", "password": "AdminPass1!"}, follow_redirects=True)
    r = client.post(f"/admin/reset-user-data/{user_id}", follow_redirects=True)
    assert r.status_code == 200
    assert b"reset to a blank slate" in r.data

    with client.application.app_context():
        assert Book.query.filter_by(user_id=user_id).count() == 0

def test_admin_delete_user(client):
    """Verify admin can delete a user account."""
    with client.application.app_context():
        u = User.query.filter_by(username="regular").first()
        user_id = u.id

    client.post("/login", data={"email": "admin@test.com", "password": "AdminPass1!"}, follow_redirects=True)
    r = client.post(f"/admin/delete-user/{user_id}", follow_redirects=True)
    assert r.status_code == 200
    assert b"permanently deleted" in r.data

    with client.application.app_context():
        assert User.query.filter_by(username="regular").first() is None

def test_admin_impersonate_user(client):
    """Verify admin can impersonate another user."""
    client.post("/login", data={"email": "admin@test.com", "password": "AdminPass1!"}, follow_redirects=True)
    with client.application.app_context():
        u = User.query.filter_by(username="regular").first()
        user_id = u.id

    r = client.post(f"/admin/impersonate/{user_id}", follow_redirects=True)
    assert r.status_code == 200
    assert b"Impersonating user regular" in r.data
