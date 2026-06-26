from extensions import db


class Goal(db.Model):
    __tablename__ = "goals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    target_books = db.Column(db.Integer, nullable=False, default=12)

    __table_args__ = (db.UniqueConstraint("user_id", "year", name="uq_goal_user_year"),)

    def __repr__(self):
        return f"<Goal user={self.user_id} year={self.year} target={self.target_books}>"
