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
db_path = os.path.join(os.path.dirname(__file__), 'database.db')

def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_no TEXT,
            vehicle_model TEXT,
            owner_name TEXT,
            new_owner_name TEXT,
            old_mobile TEXT,
            new_mobile TEXT,
            chassis_no TEXT,
            engine_no TEXT,
            rto TEXT,
            dealer TEXT,
            dealer_mobile TEXT,
            submission_date TEXT,
            work_type TEXT,
            status TEXT,
            remarks TEXT,
            created_date TEXT,
            challan_amt REAL DEFAULT 0,
            puc_amt REAL DEFAULT 0,
            insurance_amt REAL DEFAULT 0,
            late_noc_amt REAL DEFAULT 0,
            total_billing REAL DEFAULT 0,
            received_amt REAL DEFAULT 0
        )
    ''')
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
    if username == 'admin' and password == 'admin123':
        session['user'] = 'admin'; session['role'] = 'admin'
        return redirect(url_for('dashboard'))
    elif username == 'staff' and password == 'staff123':
        session['user'] = 'staff'; session['role'] = 'staff'
        return redirect(url_for('dashboard'))
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect(url_for('home'))
    conn = get_db_connection()
    search_query = request.args.get('search', '').strip().upper()
    query = "SELECT *, (COALESCE(total_billing,0) - COALESCE(received_amt,0)) AS balance_amt FROM entries WHERE 1=1"
    params = []
    if search_query:
        query += " AND (vehicle_no LIKE ? OR owner_name LIKE ? OR dealer LIKE ?)"
        like_str = f"%{search_query}%"
        params.extend([like_str, like_str, like_str])
    query += " ORDER BY id DESC"
    raw_entries = conn.execute(query, params).fetchall()
    entries, total_count, pending_count, in_process_count, objection_count, done_count = [], 0, 0, 0, 0, 0
    current_date = datetime.now()
    for row in raw_entries:
        entry = dict(row)
        total_count += 1
        if entry['status'] == 'PENDING' and entry['created_date']:
            try:
                created_dt = datetime.strptime(entry['created_date'], '%d-%m-%Y')
                if (current_date - created_dt).days > 60: entry['status'] = 'HOLD'
            except: pass
        if entry['status'] in ['HOLD', 'PENDING']: pending_count += 1
        elif entry['status'] == 'IN PROCESS': in_process_count += 1
        elif entry['status'] == 'OBJECTION': objection_count += 1
        elif entry['status'] == 'DONE': done_count += 1
        entries.append(entry)
    finance_stats = conn.execute("SELECT SUM(COALESCE(challan_amt,0)) as total_challan, SUM(COALESCE(total_billing,0)) as total_bill, SUM(COALESCE(received_amt,0)) as total_recv, SUM(COALESCE(total_billing,0) - COALESCE(received_amt,0)) as total_bal FROM entries").fetchone()
    conn.close()
    return render_template('dashboard.html', entries=entries, total_count=total_count, pending_count=pending_count, in_process_count=in_process_count, objection_count=objection_count, done_count=done_count, finance_stats=finance_stats, user=session.get('user'), role=session.get('role'))

@app.route('/add', methods=['GET', 'POST'])
def add_entry():
    if 'user' not in session: return redirect(url_for('home'))
    if request.method == 'POST':
        v_no = request.form.get('vehicle_no', '').strip().upper()
        v_model = request.form.get('vehicle_model', '').strip().upper()
        o_name = request.form.get('owner_name', '').strip().upper()
        n_name = request.form.get('new_owner_name', '').strip().upper()
        o_mob = request.form.get('old_mobile', '').strip()
        n_mob = request.form.get('new_mobile', '').strip()
        ch_no = request.form.get('chassis_no', '').strip().upper()
        en_no = request.form.get('engine_no', '').strip().upper()
        rto_loc = request.form.get('rto', '').strip().upper()
        dlr = request.form.get('dealer', '').strip().upper()
        dlr_mob = request.form.get('dealer_mobile', '').strip()
        w_type = request.form.get('work_type', '')
        rem = request.form.get('remarks', '').strip().upper()
        try: c_amt = float(request.form.get('challan_amt') or 0.0)
        except: c_amt = 0.0
        try: p_amt = float(request.form.get('puc_amt') or 0.0)
        except: p_amt = 0.0
        try: i_amt = float(request.form.get('insurance_amt') or 0.0)
        except: i_amt = 0.0
        conn = get_db_connection()
        conn.execute('''INSERT INTO entries (vehicle_no, vehicle_model, owner_name, new_owner_name, old_mobile, new_mobile, chassis_no, engine_no, rto, dealer, dealer_mobile, submission_date, work_type, status, remarks, created_date, challan_amt, puc_amt, insurance_amt, late_noc_amt, total_billing, received_amt) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
        (v_no, v_model, o_name, n_name, o_mob, n_mob, ch_no, en_no, rto_loc, dlr, dlr_mob, '-', w_type, 'PENDING', rem, datetime.now().strftime("%d-%m-%Y"), c_amt, p_amt, i_amt, 0.0, 0.0, 0.0))
        conn.commit(); conn.close()
        return redirect(url_for('dashboard'))
    return render_template('add.html', role=session.get('role'))

@app.route('/edit/<int:id>', methods=['POST'])
def edit_entry(id):
    if 'user' not in session: return redirect(url_for('home'))
    status = request.form.get('status')
    remarks = request.form.get('remarks', '').strip().upper()
    conn = get_db_connection()
    entry = conn.execute('SELECT * FROM entries WHERE id = ?', (id,)).fetchone()
    submission_date = entry['submission_date']
    if status == 'IN PROCESS' and (entry['submission_date'] == '-' or entry['status'] == 'PENDING'):
        submission_date = datetime.now().strftime("%d-%m-%Y")
    if session['role'] == 'admin':
        c_amt = float(request.form.get('challan_amt') or entry['challan_amt'] or 0.0)
        p_amt = float(request.form.get('puc_amt') or entry['puc_amt'] or 0.0)
        i_amt = float(request.form.get('insurance_amt') or entry['insurance_amt'] or 0.0)
        t_bill = float(request.form.get('total_billing') or entry['total_billing'] or 0.0)
        r_amt = float(request.form.get('received_amt') or entry['received_amt'] or 0.0)
        if t_bill == 0.0: t_bill = c_amt + p_amt + i_amt
        conn.execute('UPDATE entries SET status = ?, remarks = ?, submission_date = ?, challan_amt = ?, puc_amt = ?, insurance_amt = ?, total_billing = ?, received_amt = ? WHERE id = ?', (status, remarks, submission_date, c_amt, p_amt, i_amt, t_bill, r_amt, id))
    else:
        conn.execute('UPDATE entries SET status = ?, remarks = ?, submission_date = ? WHERE id = ?', (status, remarks, submission_date, id))
    conn.commit(); conn.close()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ... (baaki routes like print_pdf, hold_cases, export_csv waisa hi rehne dein) ...
@app.route('/print_pdf')
def print_pdf():
    if 'user' not in session: return redirect(url_for('home'))
    search_query = request.args.get('search', '').strip().upper()
    conn = get_db_connection()
    query = "SELECT *, (COALESCE(total_billing,0) - COALESCE(received_amt,0)) as balance_amt FROM entries WHERE 1=1"
    params = []
    if search_query:
        query += " AND (vehicle_no LIKE ? OR owner_name LIKE ? OR dealer LIKE ?)"
        like_str = f"%{search_query}%"
        params.extend([like_str, like_str, like_str])
    query += " ORDER BY id DESC"
    raw_rows = conn.execute(query, params).fetchall()
    entries = [dict(r) for r in raw_rows]
    conn.close()
    return render_template('pdf_report.html', entries=entries, search_query=search_query, role=session.get('role'))

@app.route('/hold_cases')
def hold_cases():
    if 'user' not in session: return redirect(url_for('home'))
    conn = get_db_connection()
    entries = [dict(r) for r in conn.execute("SELECT * FROM entries WHERE status IN ('PENDING', 'HOLD') ORDER BY id DESC").fetchall()]
    conn.close()
    return render_template('hold_report.html', entries=entries, user=session.get('user'), role=session.get('role'))

@app.route('/export')
def export_csv():
    if 'user' not in session: return redirect(url_for('home'))
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM entries").fetchall()
    conn.close()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['VEHICLE NO', 'MODEL', 'CLIENT', 'STATUS', 'REMARKS'])
    for r in rows: writer.writerow([r['vehicle_no'], r['vehicle_model'], r['owner_name'], r['status'], r['remarks']])
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=Report.csv"
    return response

if __name__ == '__main__':
    init_db()
    app.run()
