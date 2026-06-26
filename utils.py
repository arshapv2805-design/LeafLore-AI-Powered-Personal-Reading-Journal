from datetime import date, timedelta

import requests
from config import Config
from extensions import db
from models import Book, ReadingLog, Goal


def get_streak(user_id):
    """Return the current consecutive-day reading streak for a user.

    A streak counts backward from today. If neither today nor yesterday
    has a logged entry, the streak is considered broken (0), since "today"
    may not have happened yet for the user.
    """
    rows = (
        db.session.query(ReadingLog.date)
        .join(Book, ReadingLog.book_id == Book.id)
        .filter(Book.user_id == user_id)
        .distinct()
        .all()
    )
    logged_dates = {row[0] for row in rows}
    if not logged_dates:
        return 0

    today = date.today()
    yesterday = today - timedelta(days=1)

    if today not in logged_dates and yesterday not in logged_dates:
        return 0

    cursor = today if today in logged_dates else yesterday
    streak = 0
    while cursor in logged_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def goal_progress(user_id, year):
    """Return (goal, completed_count, progress_pct) for a user/year."""
    goal = Goal.query.filter_by(user_id=user_id, year=year).first()
    completed = Book.query.filter_by(user_id=user_id, status="completed").count()
    target = goal.target_books if goal else 0
    pct = min(round((completed / target) * 100), 100) if target else 0
    return goal, completed, pct


def map_category_to_genre(category, title="", description=""):
    """Map a raw Google Books category and book content metadata to our standard GENRE_CHOICES."""
    cat = (category or "").lower().strip()
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()
    
    # Combined context for keyword searching
    content = f"{title_lower} {desc_lower}"
    
    # 1. BIOGRAPHY
    if "biography" in cat or "autobiography" in cat or "memoir" in cat or "biographies" in cat:
        return "Biography"
    if ("biography" in title_lower or "memoir" in title_lower or "autobiography" in title_lower) and not ("fiction" in cat):
        return "Biography"
    if title_lower.startswith("who was") or title_lower.startswith("who is"):
        return "Biography"
    
    # 2. SELF-HELP
    if "self-help" in cat or "self help" in cat or "motivation" in cat or "success" in cat:
        return "Self-Help"
    if "habits" in title_lower or "mindset" in title_lower or "productivity" in title_lower:
        return "Self-Help"

    # 3. HISTORY
    if "history" in cat or "historical" in cat or "archaeology" in cat:
        if "natural history" not in cat:
            return "History"
        
    # 4. SCI-FI (Science Fiction)
    if "science fiction" in cat or "sci-fi" in cat or "dystopian" in cat or "steampunk" in cat or "cyberpunk" in cat:
        return "Sci-Fi"
    if "fiction" in cat or not cat:
        sf_keywords = ["space", "astronaut", "alien", "mars", "galaxy", "spaceships", "interstellar", "time travel", "post-apocalyptic", "teleportation", "extraterrestrial", "planet"]
        if any(kw in content for kw in sf_keywords):
            return "Sci-Fi"
            
    # 5. FANTASY
    if "fantasy" in cat or "magic" in cat or "mythology" in cat:
        return "Fantasy"
    if "fiction" in cat or not cat:
        fantasy_keywords = ["magic", "wizard", "hobbit", "dwarf", "elves", "elf", "spell", "witch", "dragon", "hogwarts", "sorcerer", "orc", "goblins", "spellcasting"]
        if any(kw in content for kw in fantasy_keywords):
            return "Fantasy"

    # 6. NON-FICTION
    nf_categories = [
        "science", "computers", "technology", "philosophy", "religion", "non-fiction", "nonfiction",
        "social science", "essays", "business", "economics", "finance", "education", "study aids",
        "art", "performing arts", "nature", "political science", "health", "medical", "law",
        "literary criticism", "sports", "games", "architecture", "gardening", "cooking"
    ]
    if any(nf in cat for nf in nf_categories):
        return "Non-Fiction"
    if "guide" in title_lower or "summary of" in title_lower or "workbook" in title_lower or "handbook" in title_lower or "how to" in title_lower:
        return "Non-Fiction"
        
    # 7. FICTION
    if "fiction" in cat or "novel" in cat or "literature" in cat or "poetry" in cat or "drama" in cat or "humor" in cat or "classics" in cat or "mystery" in cat or "thriller" in cat:
        return "Fiction"
        
    # Fallbacks for empty category
    if not cat:
        if any(kw in title_lower for kw in ["summary", "guide", "how to", "principles"]):
            return "Non-Fiction"
        return "Fiction"
        
    return "Other"


def search_google_books(query, return_error=False):
    """Query the Google Books API and return a short, normalized result list.

    Network or parsing failures return an empty list rather than raising,
    so a flaky API never breaks the add-book page.
    """
    error_code = None
    data = {}
    try:
        params = {"q": query, "maxResults": 5}
        if Config.GOOGLE_BOOKS_API_KEY:
            params["key"] = Config.GOOGLE_BOOKS_API_KEY
        resp = requests.get(
            Config.GOOGLE_BOOKS_API_URL,
            params=params,
            timeout=3,
        )
        if resp.status_code == 429:
            error_code = "quota_exceeded"
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            error_code = "quota_exceeded"
        else:
            error_code = "api_failed"
        print(f"Google Books API error: {e}")
    except Exception as e:
        error_code = "api_failed"
        print(f"Google Books API error: {e}")

    if return_error and error_code:
        return {"error": error_code}

    results = []
    for item in data.get("items", []):
        info = item.get("volumeInfo", {})
        title = info.get("title", "")
        desc = info.get("description", "")
        raw_cat = (info.get("categories") or [""])[0]
        cover_url = info.get("imageLinks", {}).get("thumbnail", "")
        if cover_url.startswith("http://"):
            cover_url = cover_url.replace("http://", "https://", 1)
        results.append(
            {
                "title": title,
                "author": ", ".join(info.get("authors", [])) if info.get("authors") else "",
                "cover_url": cover_url,
                "total_pages": info.get("pageCount", 0),
                "genre": map_category_to_genre(raw_cat, title, desc),
                "description": desc,
            }
        )
    return results


def check_new_achievements(user_id):
    """Calculates achievements and checks against the session cache.
    Flashes newly unlocked achievements with category 'achievement'.
    """
    from flask import session, flash
    from models import Book, ReadingLog, Note
    from datetime import date
    
    # Avoid circular imports by doing local imports
    from routes.dashboard import get_achievements
    from ml.analytics import reading_pace
    
    # Calculate everything needed
    all_books = Book.query.filter_by(user_id=user_id).all()
    completed_books = sum(1 for b in all_books if b.status == "completed")
    today = date.today()
    goal, completed_count, progress_pct = goal_progress(user_id, today.year)
    pace = reading_pace(user_id)
    streak_days = get_streak(user_id)
    
    achievements = get_achievements(user_id, streak_days, completed_count, goal, pace)
    
    previously_unlocked = session.get("unlocked_achievements", None)
    currently_unlocked = [a["id"] for a in achievements if a["unlocked"]]
    
    if previously_unlocked is None:
        session["unlocked_achievements"] = currently_unlocked
        return []
        
    newly_unlocked = [a for a in achievements if a["unlocked"] and a["id"] not in previously_unlocked]
    
    if newly_unlocked:
        for ach in newly_unlocked:
            flash(f"{ach['title']}|{ach['desc']}|{ach['icon']}", "achievement")
        session["unlocked_achievements"] = currently_unlocked
        
    return newly_unlocked
