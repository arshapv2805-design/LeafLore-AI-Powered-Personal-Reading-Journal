from extensions import db


class ReadingLog(db.Model):
    __tablename__ = "reading_logs"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    pages_read = db.Column(db.Integer, nullable=False, default=0)
    is_focus = db.Column(db.Boolean, default=False, nullable=True)
    duration_minutes = db.Column(db.Integer, default=0, nullable=True)

    def __repr__(self):
        return f"<ReadingLog book={self.book_id} date={self.date} pages={self.pages_read} focus={self.is_focus} duration={self.duration_minutes}>"
