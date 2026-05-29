import os
import sqlite3
import csv
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response

app = Flask(__name__)
application = app  # Render ke liye ye line bohot zaruri hai
app.secret_key = "autoaxis_premium_secret"

# Render par database file ka path sahi karne ke liye
# Ye database.db file ko app ke folder mein hi rakhega
db_path = os.path.join(os.path.dirname(__file__), 'database.db')

def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # entries table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_no TEXT, vehicle_model TEXT, owner_name TEXT,
            new_owner_name TEXT, old_mobile TEXT, new_mobile TEXT,
            chassis_no TEXT, engine_no TEXT, rto TEXT, dealer TEXT,
            dealer_mobile TEXT, submission_date TEXT, work_type TEXT,
            status TEXT, remarks TEXT, created_date TEXT,
            challan_amt REAL DEFAULT 0, puc_amt REAL DEFAULT 0,
            insurance_amt REAL DEFAULT 0, late_noc_amt REAL DEFAULT 0,
            total_billing REAL DEFAULT 0, received_amt REAL DEFAULT 0
        )
    ''')
    # users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE, password TEXT, role TEXT
        )
    ''')
    # Admin aur Staff default accounts
    conn.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
    conn.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('staff', 'staff123', 'staff')")
    conn.commit()
    conn.close()

@app.route('/')
def home():
    if 'user' in session: return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '')
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
    conn.close()
    if user:
        session['user'] = user['username']
        session['role'] = user['role']
        return redirect(url_for('dashboard'))
    flash('Invalid username or password!')
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect(url_for('home'))
    conn = get_db_connection()
    search = request.args.get('search', '').strip().upper()
    query = "SELECT *, (COALESCE(total_billing,0) - COALESCE(received_amt,0)) AS balance_amt FROM entries WHERE 1=1"
    params = []
    if search:
        query += " AND (vehicle_no LIKE ? OR owner_name LIKE ? OR dealer LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    query += " ORDER BY id DESC"
    raw = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('dashboard.html', entries=[dict(r) for r in raw], user=session.get('user'), role=session.get('role'))

@app.route('/add', methods=['GET', 'POST'])
def add_entry():
    if 'user' not in session: return redirect(url_for('home'))
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO entries (vehicle_no, vehicle_model, owner_name, status, created_date) VALUES (?,?,?,?,?)',
                     (request.form.get('vehicle_no'), request.form.get('vehicle_model'), request.form.get('owner_name'), 'PENDING', datetime.now().strftime("%d-%m-%Y")))
        conn.commit(); conn.close()
        return redirect(url_for('dashboard'))
    return render_template('add.html', role=session.get('role'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Init DB on startup
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run()
