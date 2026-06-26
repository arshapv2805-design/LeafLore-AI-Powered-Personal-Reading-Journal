import logging
from datetime import date, datetime

from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user

from extensions import db, csrf
from models import Book, ReadingLog, Goal, Note, VocabularyWord
from forms import GoalForm
from utils import get_streak, goal_progress, check_new_achievements
from ml.analytics import monthly_pages_series, reading_pace, predicted_finish_dates, monthly_trend, weekly_pages_series
from ml.recommender import get_recommendations

logger = logging.getLogger(__name__)

dashboard = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def get_achievements(user_id, streak_days, completed_count, goal, pace):
    total_pages = db.session.query(db.func.sum(ReadingLog.pages_read)).join(Book).filter(Book.user_id == user_id).scalar() or 0
    notes_count = Note.query.join(Book).filter(Book.user_id == user_id).count()
    focus_count = db.session.query(db.func.count(ReadingLog.id)).join(Book).filter(Book.user_id == user_id, ReadingLog.is_focus == True).scalar() or 0

    achievements = [
        {
            "id": "novice",
            "title": "Novice Reader",
            "desc": "Logged your first page",
            "icon": "bi-journal-check",
            "unlocked": total_pages > 0,
            "progress": f"{total_pages} pages" if total_pages > 0 else "0/1 pages"
        },
        {
            "id": "streak",
            "title": "Streak Master",
            "desc": "Reached a 5-day reading streak",
            "icon": "bi-fire",
            "unlocked": streak_days >= 5,
            "progress": f"{streak_days}/5 days"
        },
        {
            "id": "bookworm",
            "title": "Bookworm",
            "desc": "Completed 5 books",
            "icon": "bi-trophy",
            "unlocked": completed_count >= 5,
            "progress": f"{completed_count}/5 books"
        },
        {
            "id": "annotator",
            "title": "Annotator",
            "desc": "Added 5 chapter notes",
            "icon": "bi-pen",
            "unlocked": notes_count >= 5,
            "progress": f"{notes_count}/5 notes"
        },
        {
            "id": "goal",
            "title": "Goal Getter",
            "desc": "Completed your reading goal",
            "icon": "bi-flag",
            "unlocked": bool(goal and completed_count >= goal.target_books and goal.target_books > 0),
            "progress": f"{completed_count}/{goal.target_books} books" if goal else "No goal set"
        },
        {
            "id": "speed",
            "title": "Speed Reader",
            "desc": "Average pace of >30 pages/day",
            "icon": "bi-speedometer2",
            "unlocked": pace["avg_pages_per_day"] >= 30.0,
            "progress": f"{pace['avg_pages_per_day']}/30 p/d"
        },
        {
            "id": "focus",
            "title": "Focus Monk",
            "desc": "Logged a timed Focus session",
            "icon": "bi-hourglass-split",
            "unlocked": focus_count > 0,
            "progress": f"{focus_count}/1 session" if focus_count > 0 else "0/1 session"
        }
    ]
    return achievements


def calculate_level(xp):
    brackets = [
        (0, 300, "Seedling"),
        (300, 800, "Sprout"),
        (800, 1800, "Sapling"),
        (1800, 3500, "Oak Reader"),
        (3500, 999999, "Forest Sage")
    ]
    for idx, (low, high, name) in enumerate(brackets):
        if xp >= low and xp < high:
            level = idx + 1
            name_title = name
            current_xp_in_level = xp - low
            range_xp = high - low
            progress_pct = int((current_xp_in_level / range_xp) * 100) if range_xp > 0 else 0
            next_xp_needed = high - xp
            return {
                "level": level,
                "title": name_title,
                "current_xp": current_xp_in_level,
                "range_xp": range_xp,
                "progress_pct": progress_pct,
                "next_xp_needed": next_xp_needed,
                "total_xp": xp
            }
    return {
        "level": 5,
        "title": "Forest Sage",
        "current_xp": xp - 3500,
        "range_xp": 5000,
        "progress_pct": 100,
        "next_xp_needed": 0,
        "total_xp": xp
    }


@dashboard.route("/")
@login_required
def index():
    user_id = current_user.id
    all_books = Book.query.filter_by(user_id=user_id).all()

    stats = {
        "total": len(all_books),
        "reading": sum(1 for b in all_books if b.status == "reading"),
        "completed": sum(1 for b in all_books if b.status == "completed"),
        "want": sum(1 for b in all_books if b.status == "want-to-read"),
    }

    genre_counts = {}
    for b in all_books:
        if b.status == "completed" and b.genre:
            genre_counts[b.genre] = genre_counts.get(b.genre, 0) + 1

    today = date.today()
    month_labels, month_values = monthly_pages_series(user_id)

    streak_days = get_streak(user_id)
    goal, completed_count, progress_pct = goal_progress(user_id, today.year)
    currently_reading = [b for b in all_books if b.status == "reading"][:5]

    pace = reading_pace(user_id)
    trend = monthly_trend(user_id)
    finish_predictions = predicted_finish_dates(user_id)
    finish_lookup = {p["book_id"]: p for p in finish_predictions}

    achievements = get_achievements(user_id, streak_days, completed_count, goal, pace)
    check_new_achievements(user_id)

    # XP & Level Calculation
    completed_books = sum(1 for b in all_books if b.status == "completed")
    focus_count = db.session.query(db.func.count(ReadingLog.id)).join(Book).filter(Book.user_id == user_id, ReadingLog.is_focus == True).scalar() or 0
    total_pages = db.session.query(db.func.sum(ReadingLog.pages_read)).join(Book).filter(Book.user_id == user_id).scalar() or 0
    notes_count = Note.query.join(Book).filter(Book.user_id == user_id).count()

    total_xp = (total_pages * 10) + (completed_books * 150) + (notes_count * 25) + (streak_days * 15) + (focus_count * 50)
    level_info = calculate_level(total_xp)

    from ml.insights import generate_reading_insights
    insights = generate_reading_insights(user_id)

    hero_completion = None
    if currently_reading:
        from ml.completion_predictor import get_completion_prediction
        h_pct, h_model = get_completion_prediction(currently_reading[0].id)
        hero_completion = {"pct": h_pct, "model": h_model}

    return render_template(
        "dashboard.html",
        stats=stats,
        genre_counts=genre_counts,
        month_labels=month_labels,
        month_values=month_values,
        streak_days=streak_days,
        goal=goal,
        completed_count=completed_count,
        progress_pct=progress_pct,
        current_year=today.year,
        today=today.isoformat(),
        currently_reading=currently_reading,
        pace=pace,
        trend=trend,
        finish_lookup=finish_lookup,
        achievements=achievements,
        level_info=level_info,
        insights=insights,
        hero_completion=hero_completion
    )


@dashboard.route("/wrap")
@login_required
def reading_wrap():
    user_id = current_user.id
    current_year = date.today().year

    # 1. Fetch completed books for the year
    all_completed = Book.query.filter_by(user_id=user_id, status="completed").all()
    completed_this_year = [
        b for b in all_completed 
        if (b.date_completed or b.date_added) and (b.date_completed or b.date_added).year == current_year
    ]
    total_books_read = len(completed_this_year)

    # 2. Fetch reading logs for the year
    start_date = date(current_year, 1, 1)
    end_date = date(current_year, 12, 31)
    logs_this_year = ReadingLog.query.join(Book).filter(
        Book.user_id == user_id,
        ReadingLog.date >= start_date,
        ReadingLog.date <= end_date
    ).all()
    total_pages_read = sum(log.pages_read for log in logs_this_year)

    # Check if there is enough data
    if total_books_read == 0 and total_pages_read == 0:
        return render_template(
            "wrap.html",
            has_data=False,
            current_year=current_year
        )

    # 3. Calculate favorite genre
    genres = {}
    for b in completed_this_year:
        if b.genre:
            genres[b.genre] = genres.get(b.genre, 0) + 1
    favorite_genre = max(genres, key=genres.get) if genres else None
    favorite_genre_count = genres[favorite_genre] if favorite_genre else 0

    # 4. Calculate most active month
    pages_by_month = {}
    for log in logs_this_year:
        month_key = log.date.strftime("%B")
        pages_by_month[month_key] = pages_by_month.get(month_key, 0) + log.pages_read
    most_active_month = max(pages_by_month, key=pages_by_month.get) if pages_by_month else None
    most_active_month_pages = pages_by_month[most_active_month] if most_active_month else 0

    # 5. Calculate fastest read book
    fastest_book = None
    fastest_days = 999999
    for b in completed_this_year:
        book_logs = [log.date for log in logs_this_year if log.book_id == b.id]
        if book_logs:
            duration = (max(book_logs) - min(book_logs)).days + 1
        else:
            if b.date_completed and b.date_added:
                duration = (b.date_completed.date() - b.date_added.date()).days + 1
            else:
                duration = 1
        if duration < fastest_days:
            fastest_days = duration
            fastest_book = b

    # 6. Calculate vocabulary milestones
    start_dt = datetime(current_year, 1, 1)
    end_dt = datetime(current_year, 12, 31, 23, 59, 59)
    vocab_count = VocabularyWord.query.filter(
        VocabularyWord.user_id == user_id,
        VocabularyWord.created_at >= start_dt,
        VocabularyWord.created_at <= end_dt
    ).count()

    # 7. Get streak and XP rank level title
    streak_days = get_streak(user_id)
    focus_count = sum(1 for log in logs_this_year if log.is_focus)

    total_xp = (sum(log.pages_read for log in ReadingLog.query.join(Book).filter(Book.user_id == user_id).all()) * 10) + (len(all_completed) * 150) + (Note.query.join(Book).filter(Book.user_id == user_id).count() * 25) + (streak_days * 15) + (focus_count * 50)
    level_info = calculate_level(total_xp)

    return render_template(
        "wrap.html",
        has_data=True,
        current_year=current_year,
        total_books_read=total_books_read,
        total_pages_read=total_pages_read,
        favorite_genre=favorite_genre,
        favorite_genre_count=favorite_genre_count,
        most_active_month=most_active_month,
        most_active_month_pages=most_active_month_pages,
        fastest_book=fastest_book,
        fastest_days=fastest_days,
        vocab_count=vocab_count,
        streak_days=streak_days,
        focus_count=focus_count,
        level_info=level_info
    )


@dashboard.route("/goal", methods=["GET", "POST"])
@login_required
def set_goal():
    today = date.today()
    goal = Goal.query.filter_by(user_id=current_user.id, year=today.year).first()
    form = GoalForm()

    if request.method == "GET" and goal:
        form.target_books.data = goal.target_books

    if form.validate_on_submit():
        if goal:
            goal.target_books = form.target_books.data
        else:
            goal = Goal(user_id=current_user.id, year=today.year, target_books=form.target_books.data)
            db.session.add(goal)
        db.session.commit()
        flash("Goal updated!", "success")
        return redirect(url_for("dashboard.index"))

    _, completed_count, progress_pct = goal_progress(current_user.id, today.year)
    return render_template(
        "goal.html",
        form=form,
        goal=goal,
        current_year=today.year,
        completed_count=completed_count,
        progress_pct=progress_pct,
    )


@dashboard.route("/api/heatmap-data")
@login_required
def heatmap_data():
    rows = (
        db.session.query(ReadingLog.date, db.func.sum(ReadingLog.pages_read))
        .join(Book, ReadingLog.book_id == Book.id)
        .filter(Book.user_id == current_user.id)
        .group_by(ReadingLog.date)
        .all()
    )
    return jsonify({d.isoformat(): int(total) for d, total in rows})


@dashboard.route("/api/recommendations")
@login_required
def recommendations_api():
    return jsonify(get_recommendations(current_user.id, limit=5))


@dashboard.route("/api/seed-demo", methods=["POST"])
@login_required
def seed_demo():
    import random
    from datetime import datetime, timedelta
    
    user_id = current_user.id
    
    # 1. Clean existing records for this user
    books = Book.query.filter_by(user_id=user_id).all()
    for book in books:
        db.session.delete(book)
    Goal.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    
    # 2. Add goal
    db.session.add(Goal(user_id=user_id, year=date.today().year, target_books=24))
    
    # 3. Add demo books
    # title, author, genre, total_pages, status, description, days_ago_completed
    TITLES = [
        ("Project Hail Mary", "Andy Weir", "Sci-Fi", 476, "completed",
         "A lone astronaut wakes up with no memory of his mission and must solve a deadly "
         "science puzzle alone on a distant planet to save Earth.", 1),
        ("The Song of Achilles", "Madeline Miller", "Fiction", 416, "completed",
         "A retelling of Greek myth focused on the bond between Achilles and Patroclus, "
         "told with lyrical, emotional prose.", 25),
        ("Atomic Habits", "James Clear", "Self-Help", 320, "completed",
         "A practical guide to building good habits and breaking bad ones through small, "
         "compounding daily changes.", 40),
        ("Sapiens", "Yuval Noah Harari", "History", 443, "completed",
         "A sweeping look at how Homo sapiens came to dominate the planet, tracing "
         "cognitive, agricultural, and scientific revolutions.", 70),
        ("The Hobbit", "J.R.R. Tolkien", "Fantasy", 310, "reading",
         "A reluctant hobbit joins a band of dwarves on a quest to reclaim their "
         "mountain home from a dragon.", None),
        ("Educated", "Tara Westover", "Biography", 334, "reading",
         "A memoir about growing up in a strict, isolated household and the long path "
         "to formal education and independence.", None),
        ("Dune", "Frank Herbert", "Sci-Fi", 412, "want-to-read",
         "A desert planet, a precious resource, and a young heir caught in a sweeping "
         "political and scientific struggle for power.", None),
        ("Circe", "Madeline Miller", "Fantasy", 393, "want-to-read",
         "A reimagining of Greek myth centered on the witch Circe, exploring exile, "
         "power, and self-discovery.", None),
        ("Thinking, Fast and Slow", "Daniel Kahneman", "Non-Fiction", 499, "want-to-read",
         "An exploration of the two systems behind human thought — fast intuition and "
         "slow reasoning — and how they shape decisions.", None),
        ("The Midnight Library", "Matt Haig", "Fiction", 304, "completed",
         "A woman finds a library between life and death where each book lets her live "
         "a different version of her life.", 5),
    ]
    
    seeded_books = []
    for title, author, genre, pages, status, description, days_ago in TITLES:
        book = Book(
            user_id=user_id,
            title=title,
            author=author,
            genre=genre,
            total_pages=pages,
            status=status,
            description=description
        )
        if status == "completed" and days_ago is not None:
            book.date_completed = datetime.utcnow() - timedelta(days=days_ago)
        db.session.add(book)
        seeded_books.append(book)
    db.session.commit()
    
    # 4. Generate random reading logs
    today_dt = date.today()
    for book in seeded_books:
        if book.status == "want-to-read":
            continue
        sample_days = random.sample(range(30), k=random.randint(6, 12))  # nosec B311
        for d in sample_days:
            log_date = today_dt - timedelta(days=d)
            db.session.add(
                ReadingLog(book_id=book.id, date=log_date, pages_read=random.randint(8, 25))  # nosec B311
            )
    db.session.commit()
    
    # 5. Guarantee streak for "The Hobbit"
    hobbit = seeded_books[4]
    for d in range(6):
        log_date = today_dt - timedelta(days=d)
        if not ReadingLog.query.filter_by(book_id=hobbit.id, date=log_date).first():
            db.session.add(
                ReadingLog(book_id=hobbit.id, date=log_date, pages_read=random.randint(10, 20))  # nosec B311
            )
    db.session.commit()
    
    # 6. Add notes
    sample_notes = [
        (seeded_books[4], "Chapter 1 — An Unexpected Party",
         "Bilbo's comfort is upended; love the contrast between the Shire and the unknown."),
        (seeded_books[4], "Chapter 3 — A Short Rest",
         "Rivendell feels like the calm before things get serious."),
        (seeded_books[5], "Part 1",
         "Hard to read but so well written — the contrast between her two worlds is stark."),
    ]
    for book, chapter, content in sample_notes:
        db.session.add(Note(book_id=book.id, chapter=chapter, content=content))
    db.session.commit()
    
    flash("LeafLore successfully seeded with demo data! Enjoy exploring your new animated dashboard!", "success")
    return jsonify({"success": True})


@dashboard.route("/api/log-focus-session", methods=["POST"])
@login_required
def log_focus_session():
    data = request.get_json() or {}
    book_id = data.get("book_id")
    pages_read = data.get("pages_read")
    duration_minutes = data.get("duration_minutes", 0)
    
    if not book_id or not pages_read:
        return jsonify({"success": False, "message": "Missing book ID or pages read."}), 400
        
    try:
        pages_read = int(pages_read)
        if pages_read <= 0:
            raise ValueError()
    except ValueError:
        return jsonify({"success": False, "message": "Pages read must be a positive integer."}), 400
        
    try:
        duration_minutes = int(duration_minutes)
        if duration_minutes < 0:
            duration_minutes = 0
    except (ValueError, TypeError):
        duration_minutes = 0
        
    book = Book.query.filter_by(id=book_id, user_id=current_user.id).first()
    if not book:
        return jsonify({"success": False, "message": "Book not found."}), 404
        
    today_date = date.today()
    existing = ReadingLog.query.filter_by(book_id=book.id, date=today_date).first()
    if existing:
        existing.pages_read += pages_read
        existing.is_focus = True
        if duration_minutes:
            existing.duration_minutes = (existing.duration_minutes or 0) + duration_minutes
    else:
        db.session.add(ReadingLog(book_id=book.id, date=today_date, pages_read=pages_read, is_focus=True, duration_minutes=duration_minutes))
        
    db.session.commit()
    
    newly_unlocked = check_new_achievements(current_user.id)
    
    flash(f"Focus session complete! Logged {pages_read} pages and earned 50 bonus XP!", "success")
    return jsonify({
        "success": True,
        "newly_unlocked": [{"title": a["title"], "desc": a["desc"], "icon": a["icon"]} for a in newly_unlocked]
    })

@dashboard.route("/api/offline-sync", methods=["POST"])
@login_required
@csrf.exempt
def offline_sync():
    """CSRF-exempt batch endpoint for offline-queued reading log actions.
    Called by the service worker's background sync and by offline_sync.js
    manual fallback when the user comes back online.

    Accepts JSON: {items: [{id, type, book_id, pages_read, date?, duration_minutes?}, ...]}
    Returns JSON: {processed: [id, ...], errors: [{id, reason}, ...]}
    """
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    if not isinstance(items, list):
        return jsonify({"success": False, "message": "items must be a list"}), 400

    processed = []
    errors = []

    for item in items:
        item_id = item.get("id")
        item_type = item.get("type")

        try:
            if item_type in ("focus_log", "quick_log"):
                book_id = item.get("book_id")
                pages_read = int(item.get("pages_read", 0))
                duration_minutes = int(item.get("duration_minutes", 0))

                if not book_id or pages_read <= 0:
                    errors.append({"id": item_id, "reason": "Missing book_id or invalid pages_read"})
                    continue

                book = Book.query.filter_by(id=book_id, user_id=current_user.id).first()
                if not book:
                    errors.append({"id": item_id, "reason": "Book not found"})
                    continue

                # Determine log date
                raw_date = item.get("date")
                try:
                    log_date = date.fromisoformat(raw_date) if raw_date else date.today()
                except (ValueError, TypeError):
                    log_date = date.today()

                existing = ReadingLog.query.filter_by(book_id=book.id, date=log_date).first()
                if existing:
                    existing.pages_read += pages_read
                    if item_type == "focus_log":
                        existing.is_focus = True
                        existing.duration_minutes = (existing.duration_minutes or 0) + duration_minutes
                else:
                    db.session.add(ReadingLog(
                        book_id=book.id,
                        date=log_date,
                        pages_read=pages_read,
                        is_focus=(item_type == "focus_log"),
                        duration_minutes=duration_minutes,
                    ))

                db.session.commit()
                check_new_achievements(current_user.id)
                processed.append(item_id)

            else:
                errors.append({"id": item_id, "reason": "Unknown item type: " + str(item_type)})

        except Exception as exc:
            db.session.rollback()
            errors.append({"id": item_id, "reason": str(exc)})

    return jsonify({"success": True, "processed": processed, "errors": errors})


@dashboard.route("/insights")
@login_required
def insights():
    # Gather analytics
    stats = {
        "total": Book.query.filter_by(user_id=current_user.id).count(),
        "reading": Book.query.filter_by(user_id=current_user.id, status="reading").count(),
        "completed": Book.query.filter_by(user_id=current_user.id, status="completed").count(),
        "want": Book.query.filter_by(user_id=current_user.id, status="want-to-read").count(),
    }
    
    # ML pace
    pace = reading_pace(current_user.id)
    
    # ML finish predictions
    raw_predictions = predicted_finish_dates(current_user.id)
    predictions = []
    from ml.completion_predictor import get_completion_prediction
    for p in raw_predictions:
        book = db.session.get(Book, p["book_id"])
        if book:
            prob, model_name = get_completion_prediction(book.id)
            finish_date_str = p["finish_date"].strftime("%b %d, %Y") if isinstance(p["finish_date"], (date, datetime)) else str(p["finish_date"])
            predictions.append({
                "book_id": book.id,
                "title": book.title,
                "author": book.author or "Unknown Author",
                "confidence_pct": prob,
                "predicted_finish_date": finish_date_str,
                "pace": p["pace"],
                "days_needed": p["days_needed"]
            })
    
    # Weekly trend pages
    weekly_trend_data = weekly_pages_series(current_user.id, days=7)
    
    # Recommendations
    recs = get_recommendations(current_user.id, limit=5)
    
    return render_template(
        "insights.html",
        stats=stats,
        pace=pace,
        predictions=predictions,
        weekly_trend_data=weekly_trend_data,
        recommendations=recs,
    )


@dashboard.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_profile":
            daily_target = request.form.get("daily_target", type=int)
            calm_mode = request.form.get("calm_mode") == "on"
            
            current_user.daily_target = daily_target if daily_target and daily_target > 0 else 20
            current_user.calm_mode = calm_mode
            db.session.commit()
            flash("Profile settings updated successfully!", "success")
            
        elif action == "update_goal":
            target_books = request.form.get("target_books", type=int)
            if target_books and target_books > 0:
                current_year = datetime.utcnow().year
                goal = Goal.query.filter_by(user_id=current_user.id, year=current_year).first()
                if goal:
                    goal.target_books = target_books
                else:
                    db.session.add(Goal(user_id=current_user.id, year=current_year, target_books=target_books))
                db.session.commit()
                flash("Yearly reading goal updated!", "success")
            else:
                flash("Invalid goal targets.", "danger")
                
        elif action == "reset_data":
            user_id = current_user.id
            books = Book.query.filter_by(user_id=user_id).all()
            for book in books:
                db.session.delete(book)
            Goal.query.filter_by(user_id=user_id).delete()
            VocabularyWord.query.filter_by(user_id=user_id).delete()
            db.session.commit()
            
            from flask import session
            session.pop("unlocked_achievements", None)
            
            flash("All your reading data, progress, and achievements have been reset successfully.", "success")
            return redirect(url_for("dashboard.settings"))
            
        elif action == "delete_account":
            user = current_user
            from flask_login import logout_user
            logout_user()
            db.session.delete(user)
            db.session.commit()
            flash("Your LeafLore account has been permanently deleted.", "info")
            return redirect(url_for("auth.login"))
            
        return redirect(url_for("dashboard.settings"))
        
    current_year = datetime.utcnow().year
    goal = Goal.query.filter_by(user_id=current_user.id, year=current_year).first()
    target_books = goal.target_books if goal else 0
    
    return render_template(
        "settings.html",
        target_books=target_books,
        calm_mode=current_user.calm_mode or False,
        daily_target=current_user.daily_target or 20,
    )


@dashboard.route("/settings/export/logs")
@login_required
def export_logs():
    import csv
    from io import StringIO
    
    logs = (
        ReadingLog.query
        .join(Book)
        .filter(Book.user_id == current_user.id)
        .order_by(ReadingLog.date.desc())
        .all()
    )
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["Log ID", "Book Title", "Author", "Date", "Pages Read", "Focus Session", "Duration (Minutes)"])
    
    for l in logs:
        cw.writerow([
            l.id,
            l.book.title,
            l.book.author,
            l.date.isoformat(),
            l.pages_read,
            "Yes" if l.is_focus else "No",
            l.duration_minutes or 0
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=leaflore_reading_logs.csv"
    output.headers["Content-type"] = "text/csv"
    return output


@dashboard.route("/settings/export/notes")
@login_required
def export_notes():
    notes = (
        Note.query
        .join(Book)
        .filter(Book.user_id == current_user.id)
        .order_by(Note.created_at.desc())
        .all()
    )
    
    md_content = "# LeafLore Reading Notes\n\n"
    for n in notes:
        md_content += f"## {n.title}\n"
        md_content += f"**Book:** {n.book.title} by {n.book.author}\n"
        md_content += f"**Created:** {n.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        md_content += f"{n.content}\n\n"
        md_content += "---\n\n"
        
    output = make_response(md_content)
    output.headers["Content-Disposition"] = "attachment; filename=leaflore_reading_notes.md"
    output.headers["Content-type"] = "text/markdown"
    return output


@dashboard.route("/settings/export/archive")
@login_required
def export_archive():
    import json
    
    books = Book.query.filter_by(user_id=current_user.id).all()
    goals = Goal.query.filter_by(user_id=current_user.id).all()
    words = VocabularyWord.query.filter_by(user_id=current_user.id).all()
    
    archive = {
        "username": current_user.username,
        "email": current_user.email,
        "daily_target": current_user.daily_target or 20,
        "calm_mode": current_user.calm_mode or False,
        "books": [],
        "goals": [],
        "vocabulary": []
    }
    
    for b in books:
        book_data = {
            "title": b.title,
            "author": b.author,
            "genre": b.genre,
            "total_pages": b.total_pages,
            "status": b.status,
            "rating": b.rating,
            "logs": [],
            "notes": []
        }
        for l in b.logs:
            book_data["logs"].append({
                "date": l.date.isoformat(),
                "pages_read": l.pages_read,
                "is_focus": l.is_focus,
                "duration_minutes": l.duration_minutes
            })
        for n in b.notes:
            book_data["notes"].append({
                "title": n.title,
                "content": n.content,
                "created_at": n.created_at.isoformat()
            })
        archive["books"].append(book_data)
        
    for g in goals:
        archive["goals"].append({
            "year": g.year,
            "target_books": g.target_books
        })
        
    for w in words:
        archive["vocabulary"].append({
            "word": w.word,
            "definition": w.definition,
            "context": w.context,
            "created_at": w.created_at.isoformat()
        })
        
    output = make_response(json.dumps(archive, indent=2))
    output.headers["Content-Disposition"] = "attachment; filename=leaflore_account_archive.json"
    output.headers["Content-type"] = "application/json"
    return output


@dashboard.route("/admin/health")
@login_required
def admin_health():
    # Redirect to the new dedicated Admin Dashboard
    return redirect(url_for("admin.index"))

