from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'sweet-sedna-secret'

# Load questions CSV
df = pd.read_csv('question.csv')

# Initialize the user database
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Home route
@app.route('/')
def home():
    if 'user' in session:
        subjects = df['subject'].unique()
        return render_template('home.html', username=session['user'], subjects=subjects)
    return redirect('/login')

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        try:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            return "Username already exists 💔"
    return render_template('register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[2], password):
            session['user'] = username
            return redirect('/')
        else:
            return "Invalid credentials 😢"
    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

# Quiz route
@app.route('/quiz', methods=['GET'])
def quiz():
    if 'user' not in session:
        return redirect('/login')

    subject = request.args.get('subject')
    if not subject:
        return redirect(url_for('home'))

    df_subject = df[df['subject'] == subject].sample(10).reset_index(drop=True)
    return render_template('quiz.html', questions=df_subject.to_dict(orient='records'), subject=subject)

# Submit Quiz
@app.route('/submit', methods=['POST'])
def submit_quiz():
    if 'user' not in session:
        return redirect('/login')

    subject = request.form.get('subject')
    start_time_str = request.form.get('start_time')

    # ✅ Fixing timezone-aware/naive datetime issue
    if start_time_str and start_time_str.endswith('Z'):
        start_time_str = start_time_str[:-1]

    try:
        start_time = datetime.fromisoformat(start_time_str) if start_time_str else datetime.now()
    except Exception:
        start_time = datetime.now()

    end_time = datetime.now()
    time_taken = end_time - start_time
    time_taken_str = str(time_taken).split('.')[0]

    filtered_questions = df[df['subject'] == subject]
    score = 0
    total = 0

    for _, row in filtered_questions.iterrows():
        question_id = f"q{row['id']}"
        user_answer = request.form.get(question_id)
        if user_answer:
            total += 1
            if int(user_answer) == int(row['correct']):
                score += 1

    if 'results' not in session:
        session['results'] = {}
    session['results'][subject] = score
    session.modified = True

    username = session.get('user', 'unknown')
    new_entry = pd.DataFrame([{
        'username': username,
        'subject': subject,
        'score': score,
        'total_questions': total,
        'time_taken': time_taken_str,
        'date': end_time.strftime('%Y-%m-%d %H:%M:%S')
    }])

    try:
        log_df = pd.read_csv('study_log.csv')
        log_df = pd.concat([log_df, new_entry], ignore_index=True)
    except FileNotFoundError:
        log_df = new_entry

    log_df.to_csv('study_log.csv', index=False)

    return render_template('result.html', score=score, total=total)

# Results route
@app.route('/results')
def results():
    if 'user' not in session:
        return redirect('/login')

    results = session.get('results', {})
    total_score = sum(results.values())
    return render_template('results.html', results=results, total_score=total_score)

# Study Pattern Route
@app.route('/study-pattern')
def study_pattern():
    if 'user' not in session:
        return redirect('/login')

    username = session['user']

    try:
        log_df = pd.read_csv('study_log.csv')
    except FileNotFoundError:
        log_df = pd.DataFrame()

    if log_df.empty:
        subject_summary = []
        recent_activity = []
    else:
        user_logs = log_df[log_df['username'] == username]
        subject_summary = user_logs.groupby('subject')['score'].mean().reset_index()
        subject_summary = subject_summary.to_dict(orient='records')
        recent_activity = user_logs.sort_values(by='date', ascending=False).head(10).to_dict('records')

    return render_template('study_pattern.html',
                           session=session,
                           subject_summary=subject_summary,
                           recent_activity=recent_activity)

if __name__ == '__main__':
    app.run(debug=True)
