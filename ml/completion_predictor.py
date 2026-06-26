import numpy as np
from sklearn.linear_model import LogisticRegression
from extensions import db
from models import Book, ReadingLog, Note

def map_features(book, logs, notes):
    """Convert a book and its activity logs/notes into a normalized feature vector."""
    total_pages = float(book.total_pages or 300)
    logs_count = float(len(logs))
    
    total_pages_logged = sum(l.pages_read for l in logs)
    avg_pages = float(total_pages_logged / len(logs)) if logs else 0.0
    
    focus_count = sum(1 for l in logs if l.is_focus)
    focus_ratio = float(focus_count / len(logs)) if logs else 0.0
    
    notes_count = float(len(notes))
    
    # Feature vector: [total_pages / 100, logs_count, avg_pages, focus_ratio, notes_count]
    return [total_pages / 100.0, logs_count, avg_pages, focus_ratio, notes_count]

def get_completion_prediction(book_id):
    """Predicts the likelihood of completing an in-progress book.
    Returns:
        prediction_pct (int): 0 to 100 percent
        model_type (str): 'Machine Learning Model (Logistic Regression)' or 'Baseline Heuristic Model'
    """
    target_book = Book.query.get(book_id)
    if not target_book:
        return 0, "Unknown Book"
        
    if target_book.status == "completed":
        return 100, "Completed"
        
    # Gather training data from all books in database
    all_books = Book.query.all()
    train_data = []
    
    for b in all_books:
        logs = ReadingLog.query.filter_by(book_id=b.id).all()
        notes = Note.query.filter_by(book_id=b.id).all()
        
        # Train on books that are either completed OR have reading activity logs
        if b.status == "completed" or len(logs) > 0:
            train_data.append((b, logs, notes))
            
    X = []
    y = []
    for b, logs, notes in train_data:
        X.append(map_features(b, logs, notes))
        y.append(1 if b.status == "completed" else 0)
        
    target_logs = ReadingLog.query.filter_by(book_id=target_book.id).all()
    target_notes = Note.query.filter_by(book_id=target_book.id).all()
    target_features = map_features(target_book, target_logs, target_notes)
    
    X = np.array(X)
    y = np.array(y)
    
    # Train Logistic Regression model if we have at least 5 samples and both classes are present
    if len(train_data) >= 5 and len(np.unique(y)) == 2:
        try:
            model = LogisticRegression(max_iter=1000)
            model.fit(X, y)
            
            # Predict probability of class 1 (completed)
            prob = model.predict_proba([target_features])[0][1]
            prediction_pct = int(round(prob * 100))
            # Bound probability to realistic ranges for predictions
            prediction_pct = max(min(prediction_pct, 98), 2)
            return prediction_pct, "Machine Learning Model (Logistic Regression)"
        except Exception as e:
            # Fall back to heuristic in case of training exception
            pass  # nosec B110
            
    # Fallback Baseline Heuristic Model (Cold-Start or sparse data)
    # Start with a base probability derived from current progress percentage
    progress_pct = target_book.progress_pct if target_book.total_pages else 0
    base_prob = 0.40 + (float(progress_pct) / 100.0) * 0.30  # ranges from 0.40 to 0.70
    
    # Notes taken indicate higher commitment
    base_prob += min(len(target_notes) * 0.08, 0.24)  # up to +24%
    
    # Focus sessions indicate dedicated reading
    focus_logs = sum(1 for l in target_logs if l.is_focus)
    base_prob += min(focus_logs * 0.06, 0.18)  # up to +18%
    
    # Very long books are harder to finish, penalize slightly
    if target_book.total_pages and target_book.total_pages > 500:
        base_prob -= 0.12
        
    # Cap probability between 5% and 95%
    prediction_pct = int(round(max(min(base_prob, 0.95), 0.05) * 100))
    return prediction_pct, "Baseline Heuristic Model"
