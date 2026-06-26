from datetime import datetime, date

from flask import Blueprint, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import Book, ReadingLog

logs = Blueprint("logs", __name__, url_prefix="/logs")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today()


@logs.route("/add", methods=["POST"])
@login_required
def add_log():
    book_id = request.form.get("book_id", type=int)
    book = Book.query.get_or_404(book_id)
    if book.user_id != current_user.id:
        abort(403)

    log_date = _parse_date(request.form.get("date"))
    pages = request.form.get("pages_read", type=int) or 0

    if log_date > date.today():
        if request.headers.get("Accept") == "application/json":
            return jsonify({"success": False, "message": "Can't log pages for a future date."}), 400
        flash("Can't log pages for a future date.", "danger")
        return redirect(url_for("books.book_detail", book_id=book.id))
    if pages <= 0:
        if request.headers.get("Accept") == "application/json":
            return jsonify({"success": False, "message": "Enter a positive number of pages."}), 400
        flash("Enter a positive number of pages.", "danger")
        return redirect(url_for("books.book_detail", book_id=book.id))

    existing = ReadingLog.query.filter_by(book_id=book.id, date=log_date).first()
    msg = ""
    if existing:
        existing.pages_read = pages
        msg = "Updated your pages for that day."
        flash(msg, "success")
    else:
        db.session.add(ReadingLog(book_id=book.id, date=log_date, pages_read=pages))
        msg = "Reading logged!"
        flash(msg, "success")
    db.session.commit()

    if book.total_pages and book.pages_read > book.total_pages:
        warning_msg = f'Heads up — you\'ve logged more pages than "{book.title}"\'s total page count. You might want to update the page count or mark it complete.'
        flash(warning_msg, "warning")

    if request.headers.get("Accept") == "application/json":
        return jsonify({"success": True, "message": msg})

    return redirect(url_for("books.book_detail", book_id=book.id))


@logs.route("/<int:book_id>")
@login_required
def book_logs(book_id):
    # Full log history currently lives on the book detail page itself.
    return redirect(url_for("books.book_detail", book_id=book_id))
