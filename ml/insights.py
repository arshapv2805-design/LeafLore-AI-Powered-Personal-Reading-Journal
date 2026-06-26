from datetime import datetime, date
import pandas as pd
from collections import defaultdict
from extensions import db
from models import Book, ReadingLog, Note

def generate_reading_insights(user_id):
    """Analyze the user's reading logs and notes to generate personalized consistency insights.
    Returns:
        insights (list of dicts): list of insights, each with a title, description, and bootstrap icon.
    """
    # Load all user logs
    logs = (
        db.session.query(ReadingLog.date, ReadingLog.pages_read, ReadingLog.is_focus, ReadingLog.duration_minutes, ReadingLog.book_id)
        .join(Book, ReadingLog.book_id == Book.id)
        .filter(Book.user_id == user_id)
        .all()
    )
    
    if not logs:
        return [
            {
                "title": "A Garden Waiting to Sprout",
                "text": "Log some reading pages or complete a focus session to generate personalized habits analysis.",
                "icon": "bi-info-circle-fill",
                "color": "text-secondary"
            }
        ]
        
    df = pd.DataFrame(logs, columns=["date", "pages_read", "is_focus", "duration_minutes", "book_id"])
    df["date"] = pd.to_datetime(df["date"])
    
    insights = []
    
    # 1. Weekly active pattern
    df["day_name"] = df["date"].dt.day_name()
    day_totals = df.groupby("day_name")["pages_read"].sum()
    if not day_totals.empty:
        best_day = day_totals.idxmax()
        best_pages = int(day_totals.max())
        insights.append({
            "title": f"Peak Reading Day: {best_day}",
            "text": f"You show maximum focus on {best_day}s, having logged a total of {best_pages} pages.",
            "icon": "bi-calendar-heart-fill",
            "color": "text-success"
        })
        
    # 2. Focus Session Speed Analysis
    focus_df = df[df["is_focus"] == True]
    if not focus_df.empty:
        total_focus_pages = focus_df["pages_read"].sum()
        total_focus_mins = focus_df["duration_minutes"].sum()
        if total_focus_mins > 0:
            ppm = total_focus_pages / total_focus_mins
            insights.append({
                "title": "Focus Boost Advantage",
                "text": f"During timed Focus sessions, you read at a steady speed of {ppm:.2f} pages per minute ({ppm * 60:.1f} pages/hour).",
                "icon": "bi-lightning-charge-fill",
                "color": "text-warning"
            })
            
    # 3. Note Taking Correlation
    notes_counts = (
        db.session.query(Book.id, db.func.count(Note.id))
        .outerjoin(Note)
        .filter(Book.user_id == user_id)
        .group_by(Book.id)
        .all()
    )
    
    notes_lookup = {book_id: count for book_id, count in notes_counts}
    if notes_lookup:
        df["has_notes"] = df["book_id"].map(lambda bid: notes_lookup.get(bid, 0) > 0)
        notes_grouped = df.groupby("has_notes")["pages_read"].mean()
        
        has_notes_avg = notes_grouped.get(True, 0)
        no_notes_avg = notes_grouped.get(False, 0)
        
        if has_notes_avg > no_notes_avg and no_notes_avg > 0:
            boost = ((has_notes_avg - no_notes_avg) / no_notes_avg) * 100
            insights.append({
                "title": "Active Study Reward",
                "text": f"You log {boost:.1f}% more pages per session when reading books with active chapter notes.",
                "icon": "bi-pen-fill",
                "color": "text-info"
            })
            
    # 4. Consistency Milestone
    total_pages = int(df["pages_read"].sum())
    total_sessions = len(df)
    avg_per_session = total_pages / total_sessions if total_sessions > 0 else 0
    insights.append({
        "title": "Session Consistency",
        "text": f"You average {avg_per_session:.1f} pages per entry across {total_sessions} logged reading sessions.",
        "icon": "bi-check-circle-fill",
        "color": "text-success"
    })
    
    return insights
