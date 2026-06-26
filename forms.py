from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SelectField,
    IntegerField,
    TextAreaField,
    HiddenField,
    SubmitField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional


class RegistrationForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Log in")


GENRE_CHOICES = [
    ("Fiction", "Fiction"),
    ("Non-Fiction", "Non-Fiction"),
    ("Sci-Fi", "Sci-Fi"),
    ("Fantasy", "Fantasy"),
    ("Biography", "Biography"),
    ("Self-Help", "Self-Help"),
    ("History", "History"),
    ("Other", "Other"),
]

STATUS_CHOICES = [
    ("want-to-read", "Want to read"),
    ("reading", "Reading"),
    ("completed", "Completed"),
]


class BookForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    author = StringField("Author", validators=[Optional(), Length(max=100)])
    genre = SelectField("Genre", choices=GENRE_CHOICES, validators=[Optional()])
    total_pages = IntegerField("Total pages", validators=[Optional(), NumberRange(min=0, max=20000)])
    status = SelectField("Status", choices=STATUS_CHOICES, validators=[DataRequired()])
    cover_url = HiddenField("Cover URL", validators=[Optional()])
    description = HiddenField("Description", validators=[Optional()])
    submit = SubmitField("Save book")


class NoteForm(FlaskForm):
    chapter = StringField("Chapter", validators=[DataRequired(), Length(max=100)])
    content = TextAreaField("Note", validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField("Save note")


class GoalForm(FlaskForm):
    target_books = IntegerField("Target books this year", validators=[DataRequired(), NumberRange(min=1, max=365)])
    submit = SubmitField("Set goal")


class VocabularyWordForm(FlaskForm):
    word = StringField("Word or phrase", validators=[DataRequired(), Length(max=100)])
    definition = TextAreaField("Definition", validators=[DataRequired(), Length(max=1000)])
    context = TextAreaField("Context sentence (Optional)", validators=[Optional(), Length(max=1000)])
    chapter_or_page = StringField("Page or chapter (Optional)", validators=[Optional(), Length(max=50)])
    book_id = SelectField("Link to book (Optional)", coerce=int, validators=[Optional()])
    submit = SubmitField("Save Word")
