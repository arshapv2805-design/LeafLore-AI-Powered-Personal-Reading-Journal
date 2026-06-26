"""Reading analytics built on pandas: rolling pace, predicted finish
dates for in-progress books, and month-over-month trend comparison.
All three read from the same ReadingLog rows, just aggregated three
different ways — the kind of work pandas is built for.
"""
from datetime import date, timedelta

import pandas as pd

from extensions import db
from models import Book, ReadingLog


def _logs_dataframe(user_id):
    rows = (
        db.session.query(ReadingLog.date, ReadingLog.pages_read, ReadingLog.book_id)
        .join(Book, ReadingLog.book_id == Book.id)
        .filter(Book.user_id == user_id)
        .all()
    )
    df = pd.DataFrame(rows, columns=["date", "pages_read", "book_id"])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def reading_pace(user_id, window_days=7):
    """Rolling average pages/day across all of a user's books, over the
    trailing `window_days` (missing days count as zero, so an idle
    week pulls the average down rather than just being ignored).
    """
    df = _logs_dataframe(user_id)
    if df.empty:
        return {"avg_pages_per_day": 0.0, "window_days": window_days}

    daily = df.groupby("date")["pages_read"].sum()
    full_range = pd.date_range(end=pd.Timestamp(date.today()), periods=window_days)
    daily = daily.reindex(full_range, fill_value=0)

    return {"avg_pages_per_day": round(float(daily.mean()), 1), "window_days": window_days}


def predicted_finish_dates(user_id):
    """For each book currently being read, estimate a finish date from
    that book's own logged pace, falling back to the user's overall
    rolling pace if the book has no logs yet.
    """
    df = _logs_dataframe(user_id)
    overall_pace = reading_pace(user_id)["avg_pages_per_day"]

    predictions = []
    for book in Book.query.filter_by(user_id=user_id, status="reading").all():
        remaining = max((book.total_pages or 0) - book.pages_read, 0)
        if not book.total_pages or remaining == 0:
            continue

        book_logs = df[df["book_id"] == book.id] if not df.empty else df
        if not book_logs.empty:
            span_days = max((book_logs["date"].max() - book_logs["date"].min()).days + 1, 1)
            pace = book_logs["pages_read"].sum() / span_days
        else:
            pace = 0

        pace = pace or overall_pace
        if not pace:
            continue

        days_needed = max(int(remaining / pace) + 1, 1)
        predictions.append(
            {
                "book_id": book.id,
                "pace": round(float(pace), 1),
                "days_needed": days_needed,
                "finish_date": date.today() + timedelta(days=days_needed),
            }
        )

    return predictions


def monthly_trend(user_id):
    """This month's pages read vs. last month's, as a percent change."""
    df = _logs_dataframe(user_id)
    if df.empty:
        return {"this_month": 0, "last_month": 0, "pct_change": None}

    periods = df["date"].dt.to_period("M")
    totals = df.groupby(periods)["pages_read"].sum()

    this_period = pd.Timestamp(date.today()).to_period("M")
    last_period = this_period - 1

    this_month = int(totals.get(this_period, 0))
    last_month = int(totals.get(last_period, 0))
    pct_change = round(((this_month - last_month) / last_month) * 100, 1) if last_month else None

    return {"this_month": this_month, "last_month": last_month, "pct_change": pct_change}


def monthly_pages_series(user_id, months=12):
    """Trailing `months` of total pages read, for the dashboard bar chart."""
    today = date.today()
    period_index = pd.period_range(end=pd.Timestamp(today).to_period("M"), periods=months, freq="M")

    df = _logs_dataframe(user_id)
    if df.empty:
        totals = pd.Series(0, index=period_index)
    else:
        periods = df["date"].dt.to_period("M")
        grouped = df.groupby(periods)["pages_read"].sum()
        totals = grouped.reindex(period_index, fill_value=0)

    labels = [p.strftime("%b '%y") for p in period_index]
    values = [int(v) for v in totals.to_numpy()]
    return labels, values


def weekly_pages_series(user_id, days=7):
    """Trailing `days` of daily pages read, returned as a dictionary {date_str: page_count} for a user."""
    today = date.today()
    date_range = [today - timedelta(days=i) for i in range(days)]
    date_range.reverse()
    
    df = _logs_dataframe(user_id)
    if df.empty:
        return {d.strftime("%b %d"): 0 for d in date_range}
        
    df["date_only"] = df["date"].dt.date
    daily = df.groupby("date_only")["pages_read"].sum()
    
    result = {}
    for d in date_range:
        result[d.strftime("%b %d")] = int(daily.get(d, 0))
    return result
