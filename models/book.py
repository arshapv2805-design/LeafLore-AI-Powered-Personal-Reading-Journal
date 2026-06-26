from datetime import datetime

from extensions import db


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100))
    genre = db.Column(db.String(50))
    cover_url = db.Column(db.String(300))
    description = db.Column(db.Text)
    total_pages = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="want-to-read")  # reading / completed / want-to-read
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    date_completed = db.Column(db.DateTime, nullable=True)

    logs = db.relationship("ReadingLog", backref="book", lazy=True, cascade="all, delete-orphan")
    notes = db.relationship("Note", backref="book", lazy=True, cascade="all, delete-orphan")

    @property
    def pages_read(self):
        return sum(log.pages_read for log in self.logs)

    @property
    def progress_pct(self):
        if not self.total_pages:
            return 0
        return min(round((self.pages_read / self.total_pages) * 100), 100)

    def __repr__(self):
        return f"<Book {self.title!r}>"
