from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user

from extensions import db
from models import Book, ReadingLog
from forms import BookForm
from utils import search_google_books, check_new_achievements

books = Blueprint("books", __name__, url_prefix="/books")


def _get_owned_book(book_id):
    book = Book.query.get_or_404(book_id)
    if book.user_id != current_user.id:
        abort(403)
    return book


@books.route("/api/search")
@login_required
def api_search():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])
    res = search_google_books(query, return_error=True)
    response = jsonify(res)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@books.route("/")
@login_required
def my_books():
    check_new_achievements(current_user.id)
    all_books = (
        Book.query.filter_by(user_id=current_user.id).order_by(Book.date_added.desc()).all()
    )
    reading_books = [b for b in all_books if b.status == "reading"]
    completed_books = [b for b in all_books if b.status == "completed"]
    want_books = [b for b in all_books if b.status == "want-to-read"]
    return render_template(
        "my_books.html",
        reading_books=reading_books,
        completed_books=completed_books,
        want_books=want_books,
    )


@books.route("/add", methods=["GET", "POST"])
@login_required
def add_book():
    form = BookForm()
    if form.validate_on_submit():
        book = Book(
            user_id=current_user.id,
            title=form.title.data,
            author=form.author.data,
            genre=form.genre.data,
            total_pages=form.total_pages.data or 0,
            status=form.status.data,
            cover_url=form.cover_url.data or None,
            description=form.description.data or None,
            date_completed=datetime.utcnow() if form.status.data == "completed" else None,
        )
        db.session.add(book)
        db.session.commit()
        flash(f'"{book.title}" added to LeafLore!', "success")
        return redirect(url_for("books.my_books"))
    return render_template("add_book.html", form=form, edit_mode=False)


@books.route("/<int:book_id>")
@login_required
def book_detail(book_id):
    book = _get_owned_book(book_id)
    check_new_achievements(current_user.id)
    
    # Calculate focus session reading speed (pages per minute)
    focus_logs = (
        db.session.query(ReadingLog)
        .join(Book)
        .filter(Book.user_id == current_user.id, ReadingLog.is_focus == True, ReadingLog.duration_minutes > 0)
        .all()
    )
    
    total_focus_pages = sum(log.pages_read for log in focus_logs)
    total_focus_minutes = sum(log.duration_minutes for log in focus_logs)
    
    book_focus_logs = [log for log in focus_logs if log.book_id == book.id]
    book_pages = sum(log.pages_read for log in book_focus_logs)
    book_mins = sum(log.duration_minutes for log in book_focus_logs)
    
    if book_mins > 0:
        focus_ppm = book_pages / book_mins
    else:
        focus_ppm = (total_focus_pages / total_focus_minutes) if total_focus_minutes > 0 else 0
        
    entries = (
        ReadingLog.query.filter_by(book_id=book.id).order_by(ReadingLog.date.desc()).limit(30).all()
    )
    
    from ml.completion_predictor import get_completion_prediction
    completion_pct, completion_model = get_completion_prediction(book.id)
    
    return render_template(
        "book_detail.html",
        book=book,
        logs=entries,
        today=datetime.utcnow().date().isoformat(),
        focus_ppm=focus_ppm,
        completion_pct=completion_pct,
        completion_model=completion_model
    )


@books.route("/<int:book_id>/edit", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    book = _get_owned_book(book_id)
    form = BookForm(obj=book)

    if form.validate_on_submit():
        book.title = form.title.data
        book.author = form.author.data
        book.genre = form.genre.data
        book.total_pages = form.total_pages.data or 0
        if form.status.data == "completed":
            if not book.date_completed:
                book.date_completed = datetime.utcnow()
        else:
            book.date_completed = None
        book.status = form.status.data
        if form.cover_url.data:
            book.cover_url = form.cover_url.data
        if form.description.data:
            book.description = form.description.data
        db.session.commit()
        flash("Book updated.", "success")
        return redirect(url_for("books.book_detail", book_id=book.id))

    return render_template("add_book.html", form=form, edit_mode=True, book=book)


@books.route("/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id):
    book = _get_owned_book(book_id)
    title = book.title
    db.session.delete(book)
    db.session.commit()
    flash(f'"{title}" removed from LeafLore.', "info")
    return redirect(url_for("books.my_books"))


@books.route("/<int:book_id>/status", methods=["POST"])
@login_required
def update_status(book_id):
    book = _get_owned_book(book_id)
    new_status = request.form.get("status")
    if new_status in ("reading", "completed", "want-to-read"):
        if new_status == "completed":
            if not book.date_completed:
                book.date_completed = datetime.utcnow()
        else:
            book.date_completed = None
        book.status = new_status
        db.session.commit()
        flash(f'"{book.title}" moved to {new_status.replace("-", " ")}.', "success")
    return redirect(request.referrer or url_for("books.my_books"))
