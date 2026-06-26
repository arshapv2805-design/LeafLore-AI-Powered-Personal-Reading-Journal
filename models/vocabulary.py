from datetime import datetime

from extensions import db


class VocabularyWord(db.Model):
    __tablename__ = "vocabulary_words"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id", ondelete="CASCADE"), nullable=True)
    word = db.Column(db.String(100), nullable=False)
    definition = db.Column(db.Text, nullable=False)
    context = db.Column(db.Text, nullable=True)
    chapter_or_page = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships with cascade delete
    user = db.relationship("User", backref=db.backref("vocabulary", lazy=True, cascade="all, delete-orphan"))
    book = db.relationship("Book", backref=db.backref("vocabulary", lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<VocabularyWord {self.word!r}>"
