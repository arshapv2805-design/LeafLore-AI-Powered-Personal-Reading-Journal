# LeafLore

A gamified reading journal and analytics dashboard designed to address the "reading abandonment trap." While most readers abandon over 60% of the books they start due to a lack of consistency and feedback, LeafLore uses custom machine learning models, personalized behavioral insights, and timed focus environments to help users maintain reading habits.

## Tech stack

- **Backend:** Flask + SQLAlchemy + SQLite
- **Auth:** Flask-Login + Werkzeug password hashing
- **Forms:** Flask-WTF (with CSRF protection enabled globally)
- **Frontend:** Bootstrap 5, Chart.js, FullCalendar.js
- **External API:** Google Books API (cover art + description + metadata autofill)
- **ML / Data Science:** scikit-learn (TF-IDF + cosine similarity recommender), pandas (reading-pace and trend analytics)

## Project structure

```
leaflore/
├── app.py              ← application factory + entry point
├── config.py           ← configuration (reads env vars, falls back to local defaults)
├── extensions.py       ← shared db / login_manager / csrf instances
├── forms.py            ← all Flask-WTF form classes
├── utils.py            ← streak + goal-progress calculations
├── seed.py             ← demo data generator
├── requirements.txt
├── models/             ← User, Book, ReadingLog, Note, Goal
├── ml/                 ← recommender.py (TF-IDF/cosine), analytics.py (pandas)
├── routes/             ← auth, books, notes, logs, dashboard blueprints
├── templates/          ← Jinja2 templates (Bootstrap 5)
├── static/css/         ← style.css (design tokens, theming)
├── static/js/          ← charts.js, calendar.js, add_book.js, recommendations.js
└── tests/              ← pytest suite (routes + ML layer)
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Visit `http://127.0.0.1:5000`, click **Sign up**, and create an account.

### Optional: load demo data

```bash
python seed.py
```

This drops and recreates the database with sample books, logs, notes, and
a goal, then prints demo login credentials. Use this for a quick look at
a populated dashboard, or skip it and start from a clean account.

## Run tests

```bash
pip install pytest
pytest
```

Tests cover registration/login, adding a book and logging pages, the
streak calculation, future-date rejection, goal progress, notes, status
changes, that one user can't access another user's book, the
recommender (similarity ranking + cold start), and the analytics
functions (pace, finish-date prediction, monthly trend).

## Analytics, Machine Learning & Security features

- **Book Completion Predictor** (`ml/completion_predictor.py`): Uses scikit-learn's `LogisticRegression` classifier to predict the completion probability of currently-read books based on reading behavior (length, logs frequency, note-taking counts, focus ratios). It falls back to a weighted baseline heuristic model during the cold-start phase.
- **Personalized Behavioral Insights** (`ml/insights.py`): Automatically computes reading habits from data logs (e.g. peak reading day of week, focus session speed boost in pages/hour, and note-taking consistency correlations) to give users actionable feedback on building reading discipline.
- **Content-based recommendations** (`ml/recommender.py`): Ranks your wishlist shelf by cosine similarity to the book you most recently completed using a TF-IDF text vectorizer.
- **Pace Analytics** (`ml/analytics.py`, pandas): Aggregates daily reading logs to provide rolling averages, monthly comparison trends, and page count chart series.
- **Hardened Security Architecture**:
  - Session security configuration (`HTTPOnly`, SameSite=`Lax`, 30-minute lifetimes).
  - Custom Content Security Policy (CSP) headers protecting against script injection.
  - In-memory rate limiter on the login endpoint to prevent brute-force login attacks.
  - Payloads restricted to 2MB maximum limit.

⚠️ **Schema change:** `Book` gained a `description` column. If you
already have a `leaflore.db` from before this update, delete it (or run
`python seed.py`, which recreates it) — `db.create_all()` only creates
missing tables, it won't add a column to one that already exists.

## Notable decisions

- **CSRF protection is global** (`CSRFProtect` in `extensions.py`), not
  per-form. Plain HTML forms (status change, delete, log-pages) include
  `{{ csrf_token() }}` directly rather than needing a WTForms class each.
- **FullCalendar.js** powers the reading-activity calendar instead of a
  hand-rolled grid — it gives you real month navigation and a click-to-see
  detail panel for any day, colored by how many pages you read that day.
- **Pages-read validation is soft, not hard.** Logging more pages than a
  book's total page count is allowed (editions vary, page counts can be
  estimates) but shows a gentle warning. Logging a *future* date is
  blocked outright, since that's never meaningful.
- **`Book.pages_read` and `Book.progress_pct`** are computed properties
  (summed from `ReadingLog` rows), not stored columns — so they can never
  drift out of sync with the actual logged entries.
- **Pillow was dropped from the original plan's requirements** — nothing
  in this build resizes or caches cover images locally; book covers are
  hot-linked from Google Books. Add it back if you want local thumbnail
  processing instead.

## Next ideas

- Pagination on the full reading-log history (currently capped at the 30
  most recent entries per book).
- Password reset flow.
- Export reading history to CSV.
