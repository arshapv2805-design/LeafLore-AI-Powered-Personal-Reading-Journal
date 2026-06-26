from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    calm_mode = db.Column(db.Boolean, default=False, nullable=True)
    daily_target = db.Column(db.Integer, default=20, nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    books = db.relationship("Book", backref="owner", lazy=True, cascade="all, delete-orphan")
    goals = db.relationship("Goal", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)

    def __repr__(self):
        return f"<User {self.username}>"
