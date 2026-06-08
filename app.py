from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import io
import qrcode

# ReportLab Libraries (PDF සඳහා)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "viscor_ultimate_secret_key_2026"

# --- Database Configuration ---
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("mysql://"):
    database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
elif not database_url:
    database_url = "sqlite:///viscor_final_prod.db"

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# DATABASE MODELS
# ==========================================
class User(db.Model):
    __tablename__ = 'users'
    username = db.Column(db.String(50), primary_key=True)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(40), nullable=False)

class ActiveStock(db.Model):
    __tablename__ = 'active_stock'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reel_no = db.Column(db.String(50), unique=True)
    size = db.Column(db.String(50))
    gsm = db.Column(db.String(50))
    type = db.Column(db.String(50))
    supplier = db.Column(db.String(100))
    weight = db.Column(db.Float)
    gate_pass = db.Column(db.String(50))
    store_location = db.Column(db.String(50))
    sr_no = db.Column(db.String(50), default='-')
    status = db.Column(db.String(20), default='Active') # Active, Issued, Finished
    is_viscor_issued = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ReturnReelLog(db.Model):
    __tablename__ = 'return_reel_log'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reel_no = db.Column(db.String(50))
    size = db.Column(db.String(50))
    gsm = db.Column(db.String(50))
    type = db.Column(db.String(50))
    supplier = db.Column(db.String(100))
    previous_weight = db.Column(db.Float)
    returned_weight = db.Column(db.Float)
    consumption = db.Column(db.Float)
    gate_pass = db.Column(db.String(50))
    store_location = db.Column(db.String(50))
    sr_no = db.Column(db.String(50))
    returned_at = db.Column(db.DateTime, default=datetime.utcnow)

class UsageReelLog(db.Model):
    __tablename__ = 'usage_reel_log'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reel_no = db.Column(db.String(50))
    size = db.Column(db.String(50))
    gsm = db.Column(db.String(50))
    type = db.Column(db.String(50))
    supplier = db.Column(db.String(100))
    used_weight = db.Column(db.Float)
    gate_pass = db.Column(db.String(50))
    store_location = db.Column(db.String(50))
    sr_no = db.Column(db.String(50))
    action_type = db.Column(db.String(50)) # PARTIAL_RETURN, FINISHED
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()
    if not User.query.first():
        db.session.add(User(username='admin', password='admin@0123', role='Admin'))
        db.session.add(User(username='dataop1', password='viscor@1234', role='Data Operator 1'))
        db.session.add(User(username='dataop2', password='packwell@5678', role='Data Operator 2'))
        db.session.commit()

# --- GLOBALS ---
LOCATIONS = ["VISCOR Lanka", "Packwell 1", "Packwell 2", "Packwell 3", "Packwell 4"]

# ==========================================
# ROUTES
# ==========================================
@app.route('/')
def login():
    if 'username' in session: return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login_submit', methods=['POST'])
def login_submit():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username, password=password).first()
    if user:
        session['username'] = user.username
        session['role'] = user.role
        return redirect(url_for('dashboard'))
    flash("Invalid Credentials", "danger")
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html',
                           active=ActiveStock.query.filter_by(status='Active').count(),
                           issued=ActiveStock.query.filter_by(status='Issued').count(),
                           finished=ActiveStock.query.filter_by(status='Finished').count(),
                           usage_count=UsageReelLog.query.count())

# 1. ADD STOCK (With Location Rules Validation)
@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    if 'username' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        reel_no = request.form.get('reel_no')
        store_location = request.form.get('store_location')
        gate_pass = request.form.get('gate_pass')
        user_role = session.get('role')

        if ActiveStock.query.filter_by(reel_no=reel_no).first():
            flash(f"Reel {reel_no} already exists!", "danger")
            return redirect(url_for('add_stock'))
        
        # Requirement 3: dataop2 profile එකට location එක 'VISCOR Lanka' දීමට නොහැකි කිරීම
        if user_role == 'Data Operator 2' and store_location == 'VISCOR Lanka':
            flash("Data Operator 2 profiles are NOT allowed to select VISCOR Lanka location!", "danger")
            return redirect(url_for('add_stock'))
            
        # Requirement 3: dataop1 profile එකට location එක 'VISCOR Lanka' නම් Gate Pass එක අනිවාර්ය කිරීම
        if user_role == 'Data Operator 1' and store_location == 'VISCOR Lanka':
            if not gate_pass or gate_pass.strip() == "" or gate_pass == "LOCKED-OP2":
                flash("Gate Pass Reference Number is mandatory for Data Operator 1 when location is VISCOR Lanka!", "danger")
                return redirect(url_for('add_stock'))

        gate_pass_final = "LOCKED-OP2" if session.get('username') == "dataop2" else gate_pass
        
        stock = ActiveStock(
            reel_no=reel_no, size=request.form.get('size'), gsm=request.form.get('gsm'),
            type=request.form.get('type'), supplier=request.form.get('supplier'),
            weight=float(request.form.get('weight')), gate_pass=gate_pass_final,
            store_location=store_location
        )
        db.session.add(stock)
        db.session.commit()
        flash("Stock added successfully!", "success")
        
        # Requirement 1: Reel එකක් add කරපු සැනින් QR එක print වීමට active_stock වෙත parameter එකක් සමඟ යැවීම
        return redirect(url_for('active_stock', print_reel_no=reel_no))
    return render_template('add_stock.html', locations=LOCATIONS)

# 2. ACTIVE STOCK (Passed Locations for updating feature)
@app.route('/active_stock')
def active_stock():
    if 'username' not in session: return redirect(url_for('login'))
    stocks = ActiveStock.query.filter_by(status='Active').all()
    return render_template('active_stock.html', stocks=stocks, locations=LOCATIONS)

# Requirement 4: Active Stock Location එක වෙනම Update කිරීමට Route එකක් සැකසීම
@app.route('/update_location/<int:id>', methods=['POST'])
def update_location(id):
    if 'username' not in session: return redirect(url_for('login'))
    stock = ActiveStock.query.get_or_404(id)
    new_location = request.form.get('store_location')
    user_role = session.get('role')
    
    # Validation rules matching update actions
    if user_role == 'Data Operator 2' and new_location == 'VISCOR Lanka':
        flash("Data Operator 2 cannot change location to VISCOR Lanka!", "danger")
        return redirect(url_for('active_stock'))
        
    stock.store_location = new_location
    db.session.commit()
    flash(f"Location updated successfully for Reel: {stock.reel_no}!", "success")
    return redirect(url_for('active_stock'))

# Requirement 6: Row එකක් Delete කිරීමට Delete Route එකක් සැකසීම (Admin, Data Operator 1, Data Operator 2 සඳහා පමණි)
@app.route('/delete_stock/<int:id>', methods=['POST'])
def delete_stock(id):
    if 'username' not in session: return redirect(url_for('login'))
    user_role = session.get('role')
    
    if user_role in ['Admin', 'Data Operator 1', 'Data Operator 2']:
        stock = ActiveStock.query.get_or_404(id)
        db.session.delete(stock)
        db.session.commit()
        flash(f"Reel Row '{stock.reel_no}' deleted successfully!", "success")
    else:
        flash("Unauthorized! You do not have permission to delete stock data.", "danger")
    return redirect(url_for('active_stock'))

@app.route('/issue_reel/<int:id>', methods=['POST'])
def issue_reel(id):
    stock = ActiveStock.query.get_or_404(id)
    doc_type = request.form.get('doc_type')
    doc_number = request.form.get('doc_number')
    
    stock.status = 'Issued'
    stock.is_viscor_issued = 1 if request.form.get('is_viscor') else 0
    if doc_type == 'SR': stock.sr_no = doc_number
    else: stock.gate_pass = doc_number
    
    db.session.commit()
    flash("Reel issued successfully!", "success")
    return redirect(url_for('active_stock'))

# 3. ISSUED STOCK
@app.route('/issued_stock')
def issued_stock():
    if 'username' not in session: return redirect(url_for('login'))
    stocks = ActiveStock.query.filter_by(status='Issued').all()
    return render_template('issued_stock.html', stocks=stocks)

@app.route('/process_return', methods=['POST'])
def process_return():
    reel_no = request.form.get('reel_no')
    new_weight = float(request.form.get('returned_weight'))
    stock = ActiveStock.query.filter_by(reel_no=reel_no, status='Issued').first()
    
    if not stock:
        flash("Issued Reel not found!", "danger")
        return redirect(url_for('issued_stock'))
        
    consumption = stock.weight - new_weight
    if consumption < 0:
        flash("Return weight cannot be higher than issued weight!", "danger")
        return redirect(url_for('issued_stock'))

    ret_log = ReturnReelLog(reel_no=stock.reel_no, size=stock.size, gsm=stock.gsm, type=stock.type, supplier=stock.supplier,
                            previous_weight=stock.weight, returned_weight=new_weight, consumption=consumption,
                            gate_pass=stock.gate_pass, store_location=stock.store_location, sr_no=stock.sr_no)
                            
    usage_log = UsageReelLog(reel_no=stock.reel_no, size=stock.size, gsm=stock.gsm, type=stock.type, supplier=stock.supplier,
                             used_weight=consumption, gate_pass=stock.gate_pass, store_location=stock.store_location,
                             sr_no=stock.sr_no, action_type="PARTIAL_RETURN")
                             
    stock.weight = new_weight
    stock.status = 'Active'
    db.session.add(ret_log)
    db.session.add(usage_log)
    db.session.commit()
    flash(f"Reel {reel_no} returned with consumption {consumption}kg.", "success")
    
    # Requirement 5: Partial Return එකක් සබ්මිට් කරපු සැනින් ඒ Reel එකට QR code එකක් auto print වීමට යැවීම
    return redirect(url_for('issued_stock', print_reel_no=reel_no))

@app.route('/finish_reel/<int:id>', methods=['POST'])
def finish_reel(id):
    stock = ActiveStock.query.get_or_404(id)
    stock.status = 'Finished'
    usage_log = UsageReelLog(reel_no=stock.reel_no, size=stock.size, gsm=stock.gsm, type=stock.type, supplier=stock.supplier,
                             used_weight=stock.weight, gate_pass=stock.gate_pass, store_location=stock.store_location,
                             sr_no=stock.sr_no, action_type="FINISHED")
    db.session.add(usage_log)
    db.session.commit()
    flash("Reel marked as completely Finished.", "info")
    return redirect(url_for('issued_stock'))

# 4. FINISHED STOCK
@app.route('/finished_stock')
def finished_stock():
    if 'username' not in session: return redirect(url_for('login'))
    stocks = ActiveStock.query.filter_by(status='Finished').all()
    return render_template('finished_stock.html', stocks=stocks)

# 5. USAGE LOGS & REPORTS (With Filtering)
@app.route('/usage_logs', methods=['GET'])
def usage_logs():
    if 'username' not in session: return redirect(url_for('login'))
    
    f_location = request.args.get('location', '')
    f_type = request.args.get('type', '')
    f_supplier = request.args.get('supplier', '')
    
    query = UsageReelLog.query
    if f_location: query = query.filter(UsageReelLog.store_location == f_location)
    if f_type: query = query.filter(UsageReelLog.type.like(f"%{f_type}%"))
    if f_supplier: query = query.filter(UsageReelLog.supplier.like(f"%{f_supplier}%"))
    
    logs = query.order_by(UsageReelLog.logged_at.desc()).all()
    return render_template('usage_logs.html', logs=logs, locations=LOCATIONS, f_location=f_location, f_type=f_type, f_supplier=f_supplier)

# 6. GENERATE QR CODE (On-the-fly)
@app.route('/generate_qr/<string:reel_no>')
def generate_qr(reel_no):
    stock = ActiveStock.query.filter_by(reel_no=reel_no).first_or_404()
    qr_data = f"REEL:{stock.reel_no}|SIZE:{stock.size}|GSM:{stock.gsm}|WGT:{stock.weight}|LOC:{stock.store_location}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=3)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# 7. EXPORT PDF REPORTS (ReportLab A4 implementation)
@app.route('/export_pdf')
def export_pdf():
    f_location = request.args.get('location', '')
    query = UsageReelLog.query
    if f_location: query = query.filter(UsageReelLog.store_location == f_location)
    logs = query.all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    story.append(Paragraph("<b>VISCOR LANKA - USAGE SUMMARY REPORT</b>", styles['Title']))
    story.append(Spacer(1, 15))
    
    data = [["Reel No", "Location", "Type", "Used Wgt (kg)", "Action", "Logged At"]]
    for l in logs:
        data.append([l.reel_no, l.store_location, l.type, str(l.used_weight), l.action_type, l.logged_at.strftime('%Y-%m-%d')])
        
    t = Table(data, colWidths=[90, 90, 80, 80, 100, 90])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8)
    ]))
    story.append(t)
    doc.build(story)
    
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name="viscor_usage_report.pdf")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)