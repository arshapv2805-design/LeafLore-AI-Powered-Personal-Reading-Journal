"""Populate LeafLore with realistic demo data.

Run with:  python seed.py
Then log in with the printed demo credentials.

WARNING: this drops and recreates all tables — only use on a dev database.
"""
import random
from datetime import date, datetime, timedelta

from app import app
from extensions import db
from models import User, Book, ReadingLog, Note, Goal

DEMO_EMAIL = "demo@leaflore.app"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "leaflore123"

ADMIN_EMAIL = "admin@leaflore.app"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "adminpassword"

# title, author, genre, total_pages, status, description, days_since_completed
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


def run():
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Create demo user
        user = User(username=DEMO_USERNAME, email=DEMO_EMAIL)
        user.set_password(DEMO_PASSWORD)
        db.session.add(user)

        # Create admin user
        admin = User(username=ADMIN_USERNAME, email=ADMIN_EMAIL, is_admin=True)
        admin.set_password(ADMIN_PASSWORD)
        db.session.add(admin)

        db.session.commit()

        books = []
        for title, author, genre, pages, status, description, days_ago in TITLES:
            book = Book(
                user_id=user.id,
                title=title,
                author=author,
                genre=genre,
                total_pages=pages,
                status=status,
                description=description,
            )
            if status == "completed" and days_ago is not None:
                book.date_completed = datetime.utcnow() - timedelta(days=days_ago)
            db.session.add(book)
            books.append(book)
        db.session.commit()

        today = date.today()
        for book in books:
            if book.status == "want-to-read":
                continue
            sample_days = random.sample(range(30), k=random.randint(6, 12))
            for d in sample_days:
                log_date = today - timedelta(days=d)
                db.session.add(
                    ReadingLog(book_id=book.id, date=log_date, pages_read=random.randint(8, 25))
                )
        db.session.commit()

        # Guarantee a visible active streak on "The Hobbit" for the demo.
        hobbit = books[4]
        for d in range(6):
            log_date = today - timedelta(days=d)
            if not ReadingLog.query.filter_by(book_id=hobbit.id, date=log_date).first():
                db.session.add(
                    ReadingLog(book_id=hobbit.id, date=log_date, pages_read=random.randint(10, 20))
                )
        db.session.commit()

        sample_notes = [
            (books[4], "Chapter 1 — An Unexpected Party",
             "Bilbo's comfort is upended; love the contrast between the Shire and the unknown."),
            (books[4], "Chapter 3 — A Short Rest",
             "Rivendell feels like the calm before things get serious."),
            (books[5], "Part 1",
             "Hard to read but so well written — the contrast between her two worlds is stark."),
        ]
        for book, chapter, content in sample_notes:
            db.session.add(Note(book_id=book.id, chapter=chapter, content=content))

        db.session.add(Goal(user_id=user.id, year=today.year, target_books=24))
        db.session.commit()

        print(f"Seeded LeafLore.")
        print(f"  - Regular User: {DEMO_EMAIL} / {DEMO_PASSWORD} (username: {DEMO_USERNAME})")
        print(f"  - Admin User:   {ADMIN_EMAIL} / {ADMIN_PASSWORD} (username: {ADMIN_USERNAME})")
        print('Tip: the dashboard should recommend "Dune" first — it shares Sci-Fi genre and')
        print('themes with "Project Hail Mary", the most recently completed book.')


if __name__ == "__main__":
    run()
