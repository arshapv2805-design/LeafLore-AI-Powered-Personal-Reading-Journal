"""Content-based 'read next' recommendations.

Approach: treat each book's title + author + genre + description as a
short document, vectorize with TF-IDF, and rank a user's own
want-to-read shelf by cosine similarity to their most recently completed
book. This is the classic content-based recommender pattern, scoped to
a personal library instead of a global catalog.

Cold start: a user with no completed books has no "taste anchor" yet,
so no shelf-based ranking is possible — this is the standard cold-start
limitation of content-based recommenders, not a bug. The dashboard
explains this in plain language rather than showing an empty card with
no context.

Fallback: when the want-to-read shelf doesn't have enough candidates,
a few external suggestions are pulled from the Google Books API using
the anchor book's genre/author, so the feature still has something to
show for a thin library.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from models import Book
from utils import search_google_books


def _book_text(book):
    parts = [book.title or "", book.author or "", book.genre or "", book.description or ""]
    return " ".join(parts).strip()


def _most_recent_completed(user_id):
    completed = Book.query.filter_by(user_id=user_id, status="completed").all()
    if not completed:
        return None
    completed.sort(key=lambda b: b.date_completed or b.date_added, reverse=True)
    return completed[0]


def get_recommendations(user_id, limit=5):
    anchor = _most_recent_completed(user_id)
    if anchor is None:
        return []

    want_to_read = Book.query.filter_by(user_id=user_id, status="want-to-read").all()
    results = _rank_shelf(anchor, want_to_read, limit)

    if len(results) < limit:
        exclude = {r["title"] for r in results}
        results += _fallback_from_google_books(anchor, limit - len(results), exclude)

    return results[:limit]


def _rank_shelf(anchor, candidates, limit):
    if not candidates:
        return []

    corpus = [_book_text(anchor)] + [_book_text(b) for b in candidates]
    try:
        matrix = TfidfVectorizer(stop_words="english").fit_transform(corpus)
    except ValueError:
        # Empty vocabulary — every field was blank. Nothing to rank on.
        return []

    similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    ranked = sorted(zip(candidates, similarities), key=lambda pair: pair[1], reverse=True)

    return [
        {
            "source": "shelf",
            "book_id": book.id,
            "title": book.title,
            "author": book.author,
            "genre": book.genre,
            "cover_url": book.cover_url,
            "score": round(float(score), 3),
            "reason": f'Similar to "{anchor.title}"',
        }
        for book, score in ranked[:limit]
        if score > 0
    ]


def _fallback_from_google_books(anchor, limit, exclude_titles):
    if limit <= 0:
        return []

    query = anchor.genre or anchor.author or anchor.title
    if not query:
        return []



    candidates = search_google_books(query)
    results = []
    for c in candidates:
        if not c.get("title") or c["title"] in exclude_titles:
            continue
        results.append(
            {
                "source": "external",
                "book_id": None,
                "title": c["title"],
                "author": c.get("author", ""),
                "genre": c.get("genre"),
                "cover_url": c.get("cover_url"),
                "score": None,
                "reason": f'More {anchor.genre or "books"} like "{anchor.title}"',
            }
        )
        if len(results) >= limit:
            break
    return results
