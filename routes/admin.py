import logging
import os
from datetime import date, datetime
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user, login_user

from extensions import db
from models import User, Book, ReadingLog, Goal, Note, VocabularyWord

logger = logging.getLogger(__name__)

admin = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Decorator to require administrator privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@admin.route("/")
@login_required
@admin_required
def index():
    # Gather operations health metrics
    total_users = User.query.count()
    total_books = Book.query.count()
    total_logs = ReadingLog.query.count()
    total_pages = db.session.query(db.func.sum(ReadingLog.pages_read)).scalar() or 0
    total_goals = Goal.query.count()
    total_words = VocabularyWord.query.count()

    db_size = 0
    try:
        db_path = os.path.join(current_app.root_path, "leaflore.db")
        if os.path.exists(db_path):
            db_size = os.path.getsize(db_path)
    except Exception:
        pass
    db_size_kb = round(db_size / 1024.0, 2) if db_size else 0

    # Gather registered users and stats
    users = User.query.order_by(User.id.asc()).all()
    user_list = []
    for u in users:
        books_count = len(u.books)
        logs_count = db.session.query(db.func.count(ReadingLog.id)).join(Book).filter(Book.user_id == u.id).scalar() or 0
        user_list.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_admin": u.is_admin,
            "created_at": u.created_at,
            "books_count": books_count,
            "logs_count": logs_count
        })

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_books=total_books,
        total_logs=total_logs,
        total_pages=total_pages,
        total_goals=total_goals,
        total_words=total_words,
        db_size_kb=db_size_kb,
        users=user_list
    )


@admin.route("/toggle-role/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def toggle_role(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot revoke your own admin role.", "danger")
        return redirect(url_for("admin.index"))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    flash(f"Updated role for user {user.username}. Admin status is now {user.is_admin}.", "success")
    return redirect(url_for("admin.index"))


@admin.route("/delete-user/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own admin account.", "danger")
        return redirect(url_for("admin.index"))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f"User {username} and all of their associated data have been permanently deleted.", "success")
    return redirect(url_for("admin.index"))


@admin.route("/reset-user-data/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def reset_user_data(user_id):
    user = db.get_or_404(User, user_id)
    
    # Delete books (cascades to logs and notes)
    books = Book.query.filter_by(user_id=user.id).all()
    for book in books:
        db.session.delete(book)
    # Delete goals
    Goal.query.filter_by(user_id=user.id).delete()
    # Delete vocabulary words
    VocabularyWord.query.filter_by(user_id=user.id).delete()
    
    db.session.commit()
    flash(f"All reading data for user {user.username} has been reset to a blank slate.", "success")
    return redirect(url_for("admin.index"))


@admin.route("/seed-user-demo/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def seed_user_demo(user_id):
    user = db.get_or_404(User, user_id)

    # 1. Clean existing records for this user
    books = Book.query.filter_by(user_id=user.id).all()
    for book in books:
        db.session.delete(book)
    Goal.query.filter_by(user_id=user.id).delete()
    VocabularyWord.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    # 2. Add goal
    db.session.add(Goal(user_id=user.id, year=date.today().year, target_books=24))

    # 3. Add demo books
    import random
    from datetime import timedelta

    TITLES = [
        ("Project Hail Mary", "Andy Weir", "Sci-Fi", 476, "completed",
         "A lone astronaut wakes up with no memory of his mission and must solve a deadly "
         "science puzzle alone on a distant planet to save Earth.", 1),
        ("The Song of Achilles", "Madeline Miller", "Fiction", 416, "completed",
         "A retelling of Greek myth focused on the bond between Achilles and Patroclus, "
         "told with lyrical, emotional prose.", 25),
        ("Atomic Habits", "James Clear", "Self-Help", 320, "completed",
         "A practical guide to building good habits and breaking bad ones through small, "
         "compounding daily changes.", 40),
        ("Sapiens", "Yuval Noah Harari", "History", 443, "completed",
         "A sweeping look at how Homo sapiens came to dominate the planet, tracing "
         "cognitive, agricultural, and scientific revolutions.", 70),
        ("The Hobbit", "J.R.R. Tolkien", "Fantasy", 310, "reading",
         "A reluctant hobbit joins a band of dwarves on a quest to reclaim their "
         "mountain home from a dragon.", None),
        ("Educated", "Tara Westover", "Biography", 334, "reading",
         "A memoir about growing up in a strict, isolated household and the long path "
         "to formal education and independence.", None),
        ("Dune", "Frank Herbert", "Sci-Fi", 412, "want-to-read",
         "A desert planet, a precious resource, and a young heir caught in a sweeping "
         "political and scientific struggle for power.", None),
        ("Circe", "Madeline Miller", "Fantasy", 393, "want-to-read",
         "A reimagining of Greek myth centered on the witch Circe, exploring exile, "
         "power, and self-discovery.", None),
        ("Thinking, Fast and Slow", "Daniel Kahneman", "Non-Fiction", 499, "want-to-read",
         "An exploration of the two systems behind human thought — fast intuition and "
         "slow reasoning — and how they shape decisions.", None),
        ("The Midnight Library", "Matt Haig", "Fiction", 304, "completed",
         "A woman finds a library between life and death where each book lets her live "
         "a different version of her life.", 5),
    ]

    seeded_books = []
    for title, author, genre, pages, status, description, days_ago in TITLES:
        book = Book(
            user_id=user.id,
            title=title,
            author=author,
            genre=genre,
            total_pages=pages,
            status=status,
            description=description
        )
        if status == "completed" and days_ago is not None:
            book.date_completed = datetime.utcnow() - timedelta(days=days_ago)
        db.session.add(book)
        seeded_books.append(book)
    db.session.commit()

    # 4. Generate random reading logs
    today_dt = date.today()
    for book in seeded_books:
        if book.status == "want-to-read":
            continue
        sample_days = random.sample(range(30), k=random.randint(6, 12))  # nosec B311
        for d in sample_days:
            log_date = today_dt - timedelta(days=d)
            db.session.add(
                ReadingLog(book_id=book.id, date=log_date, pages_read=random.randint(8, 25))  # nosec B311
            )
    db.session.commit()

    # 5. Guarantee streak for "The Hobbit"
    hobbit = seeded_books[4]
    for d in range(6):
        log_date = today_dt - timedelta(days=d)
        if not ReadingLog.query.filter_by(book_id=hobbit.id, date=log_date).first():
            db.session.add(
                ReadingLog(book_id=hobbit.id, date=log_date, pages_read=random.randint(10, 20))  # nosec B311
            )
    db.session.commit()

    # 6. Add notes
    sample_notes = [
        (seeded_books[4], "Chapter 1 — An Unexpected Party",
         "Bilbo's comfort is upended; love the contrast between the Shire and the unknown."),
        (seeded_books[4], "Chapter 3 — A Short Rest",
         "Rivendell feels like the calm before things get serious."),
        (seeded_books[5], "Part 1",
         "Hard to read but so well written — the contrast between her two worlds is stark."),
    ]
    for book, chapter, content in sample_notes:
        db.session.add(Note(book_id=book.id, chapter=chapter, content=content))
    db.session.commit()

    flash(f"Seeded demo reading logs, notes, and goals for user {user.username}.", "success")
    return redirect(url_for("admin.index"))


@admin.route("/impersonate/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def impersonate(user_id):
    user = db.get_or_404(User, user_id)
    login_user(user)
    flash(f"Impersonating user {user.username}. You are now viewing their dashboard.", "info")
    return redirect(url_for("dashboard.index"))
