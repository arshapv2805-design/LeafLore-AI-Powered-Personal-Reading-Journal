from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from extensions import db
from models import Book, Note
from forms import NoteForm
from utils import check_new_achievements

notes = Blueprint("notes", __name__, url_prefix="/notes")


def _get_owned_book(book_id):
    book = Book.query.get_or_404(book_id)
    if book.user_id != current_user.id:
        abort(403)
    return book


@notes.route("/<int:book_id>", methods=["GET", "POST"])
@login_required
def book_notes(book_id):
    book = _get_owned_book(book_id)
    check_new_achievements(current_user.id)
    form = NoteForm()

    if form.validate_on_submit():
        note = Note(
            book_id=book.id,
            chapter=form.chapter.data,
            content=form.content.data,
            created_at=datetime.utcnow(),
        )
        db.session.add(note)
        db.session.commit()
        flash("Note saved.", "success")
        return redirect(url_for("notes.book_notes", book_id=book.id))

    note_list = Note.query.filter_by(book_id=book.id).order_by(Note.created_at.desc()).all()
    return render_template("notes.html", book=book, notes=note_list, form=form)


@notes.route("/<int:note_id>/delete", methods=["POST"])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.book.user_id != current_user.id:
        abort(403)
    book_id = note.book_id
    db.session.delete(note)
    db.session.commit()
    flash("Note deleted.", "info")
    return redirect(url_for("notes.book_notes", book_id=book_id))
