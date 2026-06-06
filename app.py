import os
import datetime
import io
import mysql.connector
import qrcode
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from dotenv import load_dotenv

# ReportLab imports for PDF [cite: 1]
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# ==========================================
# Database Connection [cite: 1, 2]
# ==========================================
def get_db_connection():
    try:
        return mysql.connector.connect(
            host="mysql-3e9936af-viscorquality-0270.g.aivencloud.com",
            port="28643",
            user="avnadmin",
            password="AVNS_gHRTw4Hzio_XlhXcm7d",
            database="defaultdb"
        )
    except Exception as err:
        print(f"Database Error: {err}")
        return None

def initialize_database():
    """Database tables setup exactly as your original logic[cite: 3, 4, 7, 9, 10]."""
    db = get_db_connection()
    if not db: return
    cursor = db.cursor()
    
    # Active Stock [cite: 4, 5]
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_stock (
            id INT AUTO_INCREMENT PRIMARY KEY, reel_no VARCHAR(50) UNIQUE, size VARCHAR(50), gsm VARCHAR(50),
            type VARCHAR(50), supplier VARCHAR(100), weight FLOAT, gate_pass VARCHAR(50), store_location VARCHAR(50), 
            sr_no VARCHAR(50) DEFAULT '-', status VARCHAR(20) DEFAULT 'Active', is_viscor_issued INT DEFAULT 0
        )
    """)
    # Return Log [cite: 6, 7]
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS return_reel_log (
            id INT AUTO_INCREMENT PRIMARY KEY, reel_no VARCHAR(50), size VARCHAR(50), gsm VARCHAR(50), type VARCHAR(50), 
            supplier VARCHAR(100), previous_weight FLOAT, returned_weight FLOAT, consumption FLOAT, gate_pass VARCHAR(50), 
            store_location VARCHAR(50), sr_no VARCHAR(50), returned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Usage Log [cite: 9, 10]
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_reel_log (
            id INT AUTO_INCREMENT PRIMARY KEY, reel_no VARCHAR(50), size VARCHAR(50), gsm VARCHAR(50), type VARCHAR(50), 
            supplier VARCHAR(100), used_weight FLOAT, gate_pass VARCHAR(50), store_location VARCHAR(50), sr_no VARCHAR(50), 
            action_type VARCHAR(20), logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Users [cite: 10, 11]
    cursor.execute("CREATE TABLE IF NOT EXISTS users (username VARCHAR(50) PRIMARY KEY, password VARCHAR(50), role VARCHAR(40))")
    cursor.execute("INSERT IGNORE INTO users VALUES ('admin', 'admin@0123', 'Admin')")
    cursor.execute("INSERT IGNORE INTO users VALUES ('dataop1', 'viscor@1234', 'Data Operator 1')")
    cursor.execute("INSERT IGNORE INTO users VALUES ('dataop2', 'packwell@5678', 'Data Operator 2')")
    cursor.execute("INSERT IGNORE INTO users VALUES ('super1', 'super@0000', 'Supervisor 1')") # Read Only [cite: 11]
    cursor.execute("INSERT IGNORE INTO users VALUES ('super2', 'super@1111', 'Supervisor 2')") # Read Only [cite: 11]
    
    db.commit()
    cursor.close()
    db.close()

# ==========================================
# Helpers
# ==========================================
def generate_qr(reel_no):
    if not os.path.exists('static/qrcodes'): os.makedirs('static/qrcodes')
    path = f"static/qrcodes/{reel_no}.png"
    qr = qrcode.make(reel_no)
    qr.save(path)
    return path

def is_readonly():
    """Check if the user is a Supervisor (Read Only Access) [cite: 63, 64]"""
    return 'Supervisor' in session.get('role', '')

# ==========================================
# Routes
# ==========================================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT role, username FROM users WHERE username=%s AND password=%s", (request.form['username'], request.form['password']))
        user = cursor.fetchone()
        
        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid Credentials!", "danger") [cite: 28]
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session: return redirect(url_for('login'))
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # Load data for all tabs exactly as the desktop app [cite: 61, 75, 89, 96, 103, 105]
    cursor.execute("SELECT * FROM active_stock WHERE status='Active' ORDER BY id DESC")
    active_stock = cursor.fetchall()
    
    cursor.execute("SELECT * FROM active_stock WHERE status='Issued' ORDER BY id DESC")
    issued_stock = cursor.fetchall()
    
    cursor.execute("SELECT * FROM active_stock WHERE status='Issued' AND is_viscor_issued=1 ORDER BY id DESC")
    viscor_issued = cursor.fetchall()
    
    cursor.execute("SELECT * FROM usage_reel_log ORDER BY id DESC")
    usage_log = cursor.fetchall()
    
    cursor.execute("SELECT * FROM active_stock WHERE status='Finished' ORDER BY id DESC")
    finished_stock = cursor.fetchall()

    return render_template('dashboard.html', 
                           username=session['username'], role=session['role'], readonly=is_readonly(),
                           active=active_stock, issued=issued_stock, viscor=viscor_issued, 
                           usage=usage_log, finished=finished_stock)

@app.route('/add_stock', methods=['POST'])
def add_stock():
    if is_readonly(): 
        flash("You have Read-Only Access. Cannot Add Stock.", "danger")
        return redirect(url_for('dashboard'))
        
    db = get_db_connection()
    cursor = db.cursor()
    try:
        # Check duplicate [cite: 55, 56]
        cursor.execute("SELECT COUNT(*) FROM active_stock WHERE reel_no = %s", (request.form['reel_no'],))
        if cursor.fetchone()[0] > 0:
            flash("Reel Number already exists!", "warning")
            return redirect(url_for('dashboard'))

        sql = """INSERT INTO active_stock (store_location, reel_no, size, gsm, type, supplier, weight, gate_pass, status) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Active')""" [cite: 56, 57]
        cursor.execute(sql, (request.form['store_location'], request.form['reel_no'], request.form['size'], request.form['gsm'], 
                             request.form['type'], request.form['supplier'], float(request.form['weight']), request.form['gate_pass']))
        db.commit()
        generate_qr(request.form['reel_no'])
        flash("Stock added successfully!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for('dashboard'))

@app.route('/issue_stock/<int:id>', methods=['POST'])
def issue_stock(id):
    if is_readonly(): return redirect(url_for('dashboard')) [cite: 63, 64]
    
    num_val = request.form['issue_number']
    is_viscor = request.form.get('is_viscor', 0)
    issue_type = request.form['issue_type']
    
    db = get_db_connection()
    cursor = db.cursor()
    if issue_type == "SR":
        cursor.execute("UPDATE active_stock SET status='Issued', sr_no=%s, is_viscor_issued=%s WHERE id=%s", (num_val, is_viscor, id)) [cite: 65, 66]
    else:
        cursor.execute("UPDATE active_stock SET status='Issued', gate_pass=%s, is_viscor_issued=%s WHERE id=%s", (num_val, is_viscor, id)) [cite: 66]
    db.commit()
    flash("Reel Issued successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/process_return', methods=['POST'])
def process_return():
    if is_readonly(): return redirect(url_for('dashboard'))
    
    reel = request.form['ret_reel']
    new_weight = float(request.form['ret_weight'])
    
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id, size, gsm, type, supplier, weight, gate_pass, store_location, sr_no FROM active_stock WHERE reel_no=%s AND status='Issued'", (reel,)) [cite: 78, 79]
    res = cursor.fetchone()
    
    if res:
        r_id, size, gsm, r_type, supp, old_w, gp, loc, sr = res
        consumption = float(old_w) - new_weight [cite: 79]
        
        cursor.execute("UPDATE active_stock SET weight=%s, status='Active' WHERE id=%s", (new_weight, r_id)) [cite: 80]
        cursor.execute("INSERT INTO return_reel_log(reel_no, size, gsm, type, supplier, previous_weight, returned_weight, consumption, gate_pass, store_location, sr_no) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (reel, size, gsm, r_type, supp, old_w, new_weight, consumption, gp, loc, sr)) [cite: 80, 81]
        cursor.execute("INSERT INTO usage_reel_log(reel_no, size, gsm, type, supplier, used_weight, gate_pass, store_location, sr_no, action_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'PARTIAL_RETURN')", (reel, size, gsm, r_type, supp, consumption, gp, loc, sr)) [cite: 81, 82]
        
        db.commit() [cite: 82]
        generate_qr(reel)
        flash("Reel returned successfully.", "success")
    else:
        flash("Reel not found in Issued pool.", "warning") [cite: 84, 85]
    return redirect(url_for('dashboard'))

@app.route('/finish_stock/<int:row_id>', methods=['POST'])
def finish_stock(row_id):
    if is_readonly(): return redirect(url_for('dashboard'))
    
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT reel_no, size, gsm, type, supplier, weight, gate_pass, store_location, sr_no FROM active_stock WHERE id=%s", (row_id,)) [cite: 85, 86]
    res = cursor.fetchone()
    if res:
        reel, size, gsm, r_type, supp, w, gp, loc, sr = res
        cursor.execute("UPDATE active_stock SET status='Finished' WHERE id=%s", (row_id,)) [cite: 86]
        cursor.execute("INSERT INTO usage_reel_log(reel_no, size, gsm, type, supplier, used_weight, gate_pass, store_location, sr_no, action_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'FINISHED')", (reel, size, gsm, r_type, supp, w, gp, loc, sr)) [cite: 86, 87]
        db.commit() [cite: 87]
        flash("Reel marked as Finished.", "success")
    return redirect(url_for('dashboard'))

@app.route('/delete_stock/<int:id>')
def delete_stock(id):
    if is_readonly(): return redirect(url_for('dashboard')) [cite: 67, 68]
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM active_stock WHERE id=%s", (id,)) [cite: 68]
    db.commit()
    flash("Stock deleted.", "info")
    return redirect(url_for('dashboard'))

@app.route('/download_pdf/<report_type>', methods=['GET'])
def download_pdf(report_type):
    """Dynamic PDF Generation using ReportLab [cite: 1, 106, 107, 108, 109, 110, 111, 112]"""
    db = get_db_connection()
    cursor = db.cursor()
    
    if report_type == 'live':
        title_txt = "Live Stock Report"
        cursor.execute("SELECT store_location, reel_no, size, gsm, type, weight FROM active_stock WHERE status='Active'") [cite: 106, 107]
    else:
        title_txt = "Usage History Report"
        cursor.execute("SELECT store_location, reel_no, size, gsm, type, used_weight FROM usage_reel_log") [cite: 107, 108]
        
    db_data = cursor.fetchall()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4) [cite: 1, 108]
    story = []
    styles = getSampleStyleSheet() [cite: 1, 108]
    
    story.append(Paragraph(f"<b>VISCOR LANKA: {title_txt}</b>", styles['Heading1'])) [cite: 109]
    story.append(Spacer(1, 15)) [cite: 1, 109]
    
    table_content = [["Location", "Reel No", "Size", "GSM", "Type", "Weight"]] [cite: 110]
    for r in db_data: table_content.append([str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4]), f"{r[5]:.1f}"]) [cite: 110, 111]
        
    report_table = Table(table_content, colWidths=[110, 100, 50, 50, 80, 80]) [cite: 1, 111]
    report_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.grey), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER')])) [cite: 1, 111, 112]
    story.append(report_table) [cite: 112]
    doc.build(story) [cite: 112]
    
    buffer.seek(0)
    filename = f"VISCOR_{title_txt.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf" [cite: 108]
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)