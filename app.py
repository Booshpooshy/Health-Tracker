import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from collections import defaultdict, Counter
import datetime
import csv
from io import StringIO, BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')  # Use environment variable

def get_db_connection():
    conn = sqlite3.connect('health_tracker.db')
    conn.row_factory = sqlite3.Row  # This lets us access columns by name
    return conn

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email', '')
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')
        password_hash = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (username, email, first_name, last_name, password_hash) VALUES (?, ?, ?, ?, ?)',
                (username, email, first_name, last_name, password_hash)
            )
            conn.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Logged in successfully!')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.')
    return redirect(url_for('login'))

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    """Home page - shows recent symptoms"""
    conn = get_db_connection()
    recent_logs = conn.execute('''
        SELECT sl.severity, sl.log_date, sl.notes, s.name as symptom_name
        FROM symptom_logs sl
        JOIN symptoms s ON sl.symptom_id = s.id
        WHERE sl.user_id = ?                       
        ORDER BY sl.log_date DESC, sl.id DESC
        LIMIT 10
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('home.html', recent_logs=recent_logs)

@app.route('/add-symptom')
def add_symptom_form():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    """Show form to add new symptom"""
    conn = get_db_connection()
    symptoms = conn.execute('SELECT * FROM symptoms ORDER BY name').fetchall()
    conn.close()
    return render_template('add_symptom.html', symptoms=symptoms)

@app.route('/save-symptom', methods=['POST'])
def save_symptom():
    """Process form submission and save to database"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    symptom_id = request.form['symptom_id']
    severity = request.form['severity']
    notes = request.form.get('notes', '')
    user_id = session['user_id']  # Use logged-in user's ID
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO symptom_logs (user_id, symptom_id, severity, notes, log_date)
        VALUES (?, ?, ?, ?, DATE('now'))
    ''', (user_id, symptom_id, severity, notes))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    """Show all symptom history"""
    conn = get_db_connection()
    all_logs = conn.execute('''
        SELECT sl.severity, sl.log_date, sl.notes, s.name as symptom_name
        FROM symptom_logs sl
        JOIN symptoms s ON sl.symptom_id = s.id
        WHERE sl.user_id = ?               
        ORDER BY sl.log_date DESC, sl.id DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('history.html', logs=all_logs)

def analyze_symptom_patterns(logs):
    insights = []
    if not logs:
        return ["No symptom data to analyze yet."]
    # Parse logs into useful structures
    by_symptom = defaultdict(list)
    by_date = defaultdict(list)
    for log in logs:
        by_symptom[log['symptom_name']].append(log)
        by_date[log['log_date']].append(log)
    # 1. Day-of-week patterns
    dow_counter = defaultdict(lambda: Counter())
    for log in logs:
        date_obj = datetime.datetime.strptime(log['log_date'], "%Y-%m-%d")
        dow = date_obj.strftime("%A")
        dow_counter[log['symptom_name']][dow] += 1
    for symptom, counter in dow_counter.items():
        if counter:
            most_common_day, count = counter.most_common(1)[0]
            total = sum(counter.values())
            if count / total > 0.4 and total > 3:
                insights.append(f"Your {symptom.lower()}s seem to occur more frequently on {most_common_day}s.")
    # 2. Monthly improvement/worsening
    month_severity = defaultdict(lambda: defaultdict(list))
    for log in logs:
        month = log['log_date'][:7]
        month_severity[log['symptom_name']][month].append(log['severity'])
    for symptom, months in month_severity.items():
        if len(months) >= 2:
            sorted_months = sorted(months)
            last, prev = sorted_months[-1], sorted_months[-2]
            avg_last = sum(months[last]) / len(months[last])
            avg_prev = sum(months[prev]) / len(months[prev])
            if avg_prev > 0:
                change = (avg_prev - avg_last) / avg_prev * 100
                if abs(change) > 10:
                    if change > 0:
                        insights.append(f"Your {symptom.lower()} severity improved by {int(change)}% this month.")
                    else:
                        insights.append(f"Your {symptom.lower()} severity worsened by {int(-change)}% this month.")
    # 3. Frequency changes
    month_freq = defaultdict(lambda: defaultdict(int))
    for log in logs:
        month = log['log_date'][:7]
        month_freq[log['symptom_name']][month] += 1
    for symptom, months in month_freq.items():
        if len(months) >= 2:
            sorted_months = sorted(months)
            last, prev = sorted_months[-1], sorted_months[-2]
            freq_last, freq_prev = months[last], months[prev]
            if freq_prev > 0:
                change = (freq_last - freq_prev) / freq_prev * 100
                if abs(change) > 50 and freq_last > 2:
                    if change > 0:
                        insights.append(f"You logged '{symptom}' {int(change)}% more often this month.")
                    else:
                        insights.append(f"You logged '{symptom}' {int(-change)}% less often this month.")
    if not insights:
        insights.append("No strong patterns detected yet. Keep logging your symptoms for more insights!")
    return insights

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    # Get recent logs for the table
    recent_logs = conn.execute('''
        SELECT sl.severity, sl.log_date, sl.notes, s.name as symptom_name
        FROM symptom_logs sl
        JOIN symptoms s ON sl.symptom_id = s.id
        WHERE sl.user_id = ?
        ORDER BY sl.log_date DESC, sl.id DESC
        LIMIT 10
    ''', (session['user_id'],)).fetchall()
    # Frequency over time
    freq_rows = conn.execute('''
        SELECT s.name as symptom_name, sl.log_date, COUNT(*) as count, sl.severity, sl.notes
        FROM symptom_logs sl
        JOIN symptoms s ON sl.symptom_id = s.id
        WHERE sl.user_id = ?
        GROUP BY s.name, sl.log_date
        ORDER BY sl.log_date ASC
    ''', (session['user_id'],)).fetchall()
    # Severity trends
    severity_rows = conn.execute('''
        SELECT s.name as symptom_name, sl.log_date, AVG(sl.severity) as avg_severity
        FROM symptom_logs sl
        JOIN symptoms s ON sl.symptom_id = s.id
        WHERE sl.user_id = ?
        GROUP BY s.name, sl.log_date
        ORDER BY sl.log_date ASC
    ''', (session['user_id'],)).fetchall()
    # For correlation: get all logs
    all_logs = conn.execute('''
        SELECT sl.log_date, s.name as symptom_name, sl.severity, sl.notes
        FROM symptom_logs sl
        JOIN symptoms s ON sl.symptom_id = s.id
        WHERE sl.user_id = ?
        ORDER BY sl.log_date ASC
    ''', (session['user_id'],)).fetchall()
    # Get all unique dates and symptoms
    all_dates = sorted(list(set([row['log_date'] for row in freq_rows])))
    all_symptoms = sorted(list(set([row['symptom_name'] for row in freq_rows])))
    # Frequency data: {symptom: [count_per_date]}
    freq_data = {symptom: [0]*len(all_dates) for symptom in all_symptoms}
    for row in freq_rows:
        date_idx = all_dates.index(row['log_date'])
        freq_data[row['symptom_name']][date_idx] = row['count']
    # Severity data: {symptom: [avg_severity_per_date]}
    severity_data = {symptom: [None]*len(all_dates) for symptom in all_symptoms}
    for row in severity_rows:
        date_idx = all_dates.index(row['log_date'])
        severity_data[row['symptom_name']][date_idx] = row['avg_severity']
    # Correlation matrix: {symptom1: {symptom2: count}}
    date_symptoms = defaultdict(set)
    logs_for_insights = []
    for log in all_logs:
        date_symptoms[log['log_date']].add(log['symptom_name'])
        logs_for_insights.append({'symptom_name': log['symptom_name'], 'log_date': log['log_date'], 'severity': log['severity'], 'notes': log['notes']})
    co_occurrence = {s1: {s2: 0 for s2 in all_symptoms} for s1 in all_symptoms}
    for symptoms in date_symptoms.values():
        for s1 in symptoms:
            for s2 in symptoms:
                if s1 != s2:
                    co_occurrence[s1][s2] += 1
    conn.close()
    insights = analyze_symptom_patterns(logs_for_insights)
    return render_template(
        'dashboard.html',
        logs=recent_logs,
        all_dates=all_dates,
        all_symptoms=all_symptoms,
        freq_data=freq_data,
        severity_data=severity_data,
        co_occurrence=co_occurrence,
        insights=insights
    )

@app.route('/api/logs', methods=['GET'])
def api_get_logs():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    logs = conn.execute('''
        SELECT sl.severity, sl.log_date, sl.notes, s.name as symptom_name
        FROM symptom_logs sl
        JOIN symptoms s ON sl.symptom_id = s.id
        WHERE sl.user_id = ?
        ORDER BY sl.log_date DESC, sl.id DESC
        LIMIT 10
    ''', (session['user_id'],)).fetchall()
    conn.close()
    logs_list = [dict(log) for log in logs]
    chart_labels = [log['log_date'] for log in logs]
    chart_data = [log['severity'] for log in logs]
    return jsonify({'logs': logs_list, 'chart_labels': chart_labels, 'chart_data': chart_data})

@app.route('/api/log', methods=['POST'])
def api_add_log():
    if 'user_id' not in session:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        try:
            symptom_id = data['symptom_id']
            severity = data['severity']
        except KeyError:
            return jsonify({'error': 'Missing required fields'}), 400
        notes = data.get('notes', '')
        user_id = session['user_id']
        conn = get_db_connection()
    conn.execute('''
        INSERT INTO symptom_logs (user_id, symptom_id, severity, notes, log_date)
        VALUES (?, ?, ?, ?, DATE('now'))
    ''', (user_id, symptom_id, severity, notes))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/export/csv')
def export_csv():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    logs = conn.execute('''
        SELECT sl.log_date, s.name as symptom_name, sl.severity, sl.notes
        FROM symptom_logs sl
        JOIN symptoms s ON sl.symptom_id = s.id
        WHERE sl.user_id = ?
        ORDER BY sl.log_date DESC, sl.id DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Symptom', 'Severity', 'Notes'])
    for log in logs:
        cw.writerow([log['log_date'], log['symptom_name'], log['severity'], log['notes']])
    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=symptom_logs.csv'}
    )

@app.route('/export/pdf')
def export_pdf():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    logs = conn.execute('''
        SELECT sl.log_date, s.name as symptom_name, sl.severity, sl.notes
        FROM symptom_logs sl
        JOIN symptoms s ON sl.symptom_id = s.id
        WHERE sl.user_id = ?
        ORDER BY sl.log_date DESC, sl.id DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 40
    p.setFont("Helvetica-Bold", 16)
    p.drawString(40, y, "Symptom Logs Report")
    y -= 30
    p.setFont("Helvetica", 10)
    p.drawString(40, y, "Date")
    p.drawString(120, y, "Symptom")
    p.drawString(250, y, "Severity")
    p.drawString(320, y, "Notes")
    y -= 20
    p.setFont("Helvetica", 9)
    for log in logs:
        if y < 50:
            p.showPage()
            y = height - 40
        p.drawString(40, y, str(log['log_date']))
        p.drawString(120, y, str(log['symptom_name']))
        p.drawString(250, y, str(log['severity']))
        p.drawString(320, y, str(log['notes'])[:60])  # Truncate notes for width
        y -= 15
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='symptom_logs.pdf', mimetype='application/pdf')

if __name__ == '__main__':
    print("Starting Flask app...")
    app.run(debug=True)
