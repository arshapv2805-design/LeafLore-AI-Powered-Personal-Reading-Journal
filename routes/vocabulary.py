from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from extensions import db
from models import Book, VocabularyWord
from forms import VocabularyWordForm

vocabulary = Blueprint("vocabulary", __name__, url_prefix="/vocabulary")


@vocabulary.route("/", methods=["GET"])
@login_required
def index():
    books = Book.query.filter_by(user_id=current_user.id).order_by(Book.title).all()
    
    form = VocabularyWordForm()
    form.book_id.choices = [(-1, "Global (No Book)")] + [(b.id, b.title) for b in books]
    
    # Handle pre-selected book filter
    filter_book_id = request.args.get("book_id", type=int)
    q = request.args.get("q", "").strip()
    
    query = VocabularyWord.query.filter_by(user_id=current_user.id)
    
    if q:
        query = query.filter(
            VocabularyWord.word.ilike(f"%{q}%") | 
            VocabularyWord.definition.ilike(f"%{q}%") |
            VocabularyWord.context.ilike(f"%{q}%")
        )
        
    if filter_book_id is not None:
        if filter_book_id == 0:
            query = query.filter(VocabularyWord.book_id.is_(None))
        elif filter_book_id > 0:
            query = query.filter_by(book_id=filter_book_id)
        
    words = query.order_by(VocabularyWord.created_at.desc()).all()
    
    # Pre-fill modal field choices
    return render_template(
        "vocabulary.html", 
        words=words, 
        books=books, 
        form=form, 
        q=q, 
        filter_book_id=filter_book_id
    )


@vocabulary.route("/add", methods=["POST"])
@login_required
def add_word():
    books = Book.query.filter_by(user_id=current_user.id).all()
    form = VocabularyWordForm()
    form.book_id.choices = [(-1, "Global (No Book)")] + [(b.id, b.title) for b in books]
    
    if form.validate_on_submit():
        book_id = form.book_id.data
        if book_id <= 0:
            book_id = None
            
        word_entry = VocabularyWord(
            user_id=current_user.id,
            book_id=book_id,
            word=form.word.data.strip(),
            definition=form.definition.data.strip(),
            context=form.context.data.strip() if form.context.data else None,
            chapter_or_page=form.chapter_or_page.data.strip() if form.chapter_or_page.data else None,
            created_at=datetime.utcnow()
        )
        db.session.add(word_entry)
        db.session.commit()
        flash(f'Word "{word_entry.word}" saved to your Word Bank.', "success")
    else:
        # Flash form errors if validation fails
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", "danger")
                
    return redirect(request.referrer or url_for("vocabulary.index"))


@vocabulary.route("/edit/<int:word_id>", methods=["POST"])
@login_required
def edit_word(word_id):
    word_entry = VocabularyWord.query.get_or_404(word_id)
    if word_entry.user_id != current_user.id:
        abort(403)
        
    books = Book.query.filter_by(user_id=current_user.id).all()
    form = VocabularyWordForm()
    form.book_id.choices = [(-1, "Global (No Book)")] + [(b.id, b.title) for b in books]
    
    if form.validate_on_submit():
        book_id = form.book_id.data
        if book_id <= 0:
            book_id = None
            
        word_entry.word = form.word.data.strip()
        word_entry.definition = form.definition.data.strip()
        word_entry.context = form.context.data.strip() if form.context.data else None
        word_entry.chapter_or_page = form.chapter_or_page.data.strip() if form.chapter_or_page.data else None
        word_entry.book_id = book_id
        
        db.session.commit()
        flash(f'Word "{word_entry.word}" updated.', "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error: {error}", "danger")
                
    return redirect(request.referrer or url_for("vocabulary.index"))


@vocabulary.route("/delete/<int:word_id>", methods=["POST"])
@login_required
def delete_word(word_id):
    word_entry = VocabularyWord.query.get_or_404(word_id)
    if word_entry.user_id != current_user.id:
        abort(403)
        
    word_name = word_entry.word
    db.session.delete(word_entry)
    db.session.commit()
    flash(f'Word "{word_name}" removed from Word Bank.', "info")
    return redirect(request.referrer or url_for("vocabulary.index"))
