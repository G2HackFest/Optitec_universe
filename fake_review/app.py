import re
import sqlite3
import datetime
from flask import Flask, request, render_template
from nltk.sentiment import SentimentIntensityAnalyzer

# Initialize the VADER sentiment analyzer
sia = SentimentIntensityAnalyzer()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
DATABASE = 'reviews.db'

def init_db():
    """Initialize the SQLite database and create the reviews table if it doesn't exist."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY,
            user_id TEXT,
            review_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def analyze_text(review_text):
    """
    Analyze review text for anomalies:
      - Checks for generic phrases.
      - Counts excessive exclamation marks.
      - Evaluates word count.
      - Assesses sentiment polarity.
    Returns analysis details and a preliminary credibility score.
    """
    analysis = {}
    
    # 1. Generic phrase detection.
    generic_keywords = ['best product ever', 'highly recommend', 'excellent', 'love it']
    generic_count = sum(review_text.lower().count(phrase) for phrase in generic_keywords)
    analysis['generic_phrase_count'] = generic_count
    
    # 2. Exclamation mark analysis.
    exclam_count = review_text.count('!')
    analysis['exclamation_count'] = exclam_count
    
    # 3. Word count.
    word_count = len(review_text.split())
    analysis['word_count'] = word_count
    
    # 4. Sentiment analysis using VADER.
    sentiment = sia.polarity_scores(review_text)
    analysis['sentiment'] = sentiment['compound']
    
    # 5. Compute a preliminary credibility score (starting at 10).
    score = 10
    if generic_count > 0:
        score -= generic_count
    if exclam_count > 2:
        score -= (exclam_count - 2)
    if word_count < 5:
        score -= 3
    if abs(sentiment['compound']) > 0.8:
        score -= 2
    
    analysis['credibility_score'] = max(score, 1)
    return analysis

def analyze_user(user_id):
    """
    Analyze user behavior by checking review frequency.
    If a user posts more than 5 reviews within one hour, apply a penalty.
    """
    penalty = 0
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
    time_str = one_hour_ago.strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        "SELECT COUNT(*) FROM reviews WHERE user_id=? AND timestamp>=?",
        (user_id, time_str)
    )
    count = cursor.fetchone()[0]
    conn.close()
    
    if count > 5:
        penalty = count - 5
    return penalty

def is_fake(credibility_score, threshold=6):
    """Determine if the review is likely fake based on the overall credibility score."""
    return credibility_score < threshold

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/submit_review', methods=['POST'])
def submit_review():
    user_id = request.form.get('user_id')
    review_text = request.form.get('review_text')
    
    # Store the review in the database.
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reviews (user_id, review_text) VALUES (?, ?)", (user_id, review_text))
    conn.commit()
    conn.close()
    
    # Perform text analysis.
    text_analysis = analyze_text(review_text)
    # Check user behavior penalty based on review frequency.
    user_penalty = analyze_user(user_id)
    
    # Combine both analyses for overall credibility score.
    overall_score = text_analysis['credibility_score'] - user_penalty
    overall_score = max(overall_score, 1)
    
    # Determine if review is flagged as fake/suspicious.
    verdict = is_fake(overall_score)
    
    return render_template('index.html',
                           analysis=text_analysis,
                           user_penalty=user_penalty,
                           overall_score=overall_score,
                           verdict=verdict)

if _name_ == '_main_':
    app.run(debug=True)