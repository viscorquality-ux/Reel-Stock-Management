from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import io
import qrcode

# ReportLab Libraries
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "viscor_ultimate_secret_key_2026"

# --- Database Configuration ---
database_url = os.environ.get('DATABASE_URL')
# Render සහ වෙනත් Cloud Platforms සඳහා Postgres URL එක නිවැරදි කිරීම
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    elif database_url.startswith("mysql://"):
        database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
else:
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
    status = db.Column(db.String(40), default='Active') # Active, Issued, Finished, Pending_Viscor
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

# --- Requirement 9: නව Locations 4ක් සමඟින් සම්පූර්ණ ලැයිස්තුව ---
LOCATIONS = [
    "VISCOR Lanka", "Packwell 1", "Packwell 2", "Packwell 3", 
    "Packwell 4", "Packwell 5", "Packwell 6", "Packwell 7", "Packwell 8"
]

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

# --- Requirement 6: Dashboard එක Operator මත පදනම්ව වෙන වෙනම No of Reels සහ Weight පෙන්වීම ---
@app.route('/dashboard')
def dashboard():
    if 'username' not in session: return redirect(url_for('login'))
    role = session.get('role')
    
    # Active Stock Queries based on scope
    if role == 'Data Operator 1':
        active_reels = ActiveStock.query.filter_by(status='Active', store_location='VISCOR Lanka').all()
        issued_count = ActiveStock.query.filter_by(status='Issued', store_location='VISCOR Lanka').count()
        finished_count = ActiveStock.query.filter_by(status='Finished', store_location='VISCOR Lanka').count()
    elif role == 'Data Operator 2':
        active_reels = ActiveStock.query.filter(ActiveStock.status=='Active', ActiveStock.store_location!='VISCOR Lanka').all()
        issued_count = ActiveStock.query.filter(ActiveStock.status=='Issued', ActiveStock.store_location!='VISCOR Lanka').count()
        finished_count = ActiveStock.query.filter(ActiveStock.status=='Finished', ActiveStock.store_location!='VISCOR Lanka').count()
    else: # Admin
        active_reels = ActiveStock.query.filter_by(status='Active').all()
        issued_count = ActiveStock.query.filter_by(status='Issued').count()
        finished_count = ActiveStock.query.filter_by(status='Finished').count()

    active_count = len(active_reels)
    active_weight = sum([r.weight for r in active_reels])
    pending_viscor_count = ActiveStock.query.filter_by(status='Pending_Viscor').count()

    return render_template('dashboard.html',
                           active_count=active_count,
                           active_weight=round(active_weight, 2),
                           issued=issued_count,
                           finished=finished_count,
                           pending_viscor_count=pending_viscor_count)

# --- Requirement 2: Dataop 1 හට Add Stock කිරීමේදී Location එක VISCOR Lanka පමණක් සීමා කිරීම ---
@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    if 'username' not in session: return redirect(url_for('login'))
    role = session.get('role')
    
    # Allowed locations mapping
    if role == 'Data Operator 1':
        allowed_locs = ["VISCOR Lanka"]
    elif role == 'Data Operator 2':
        allowed_locs = [l for l in LOCATIONS if l != "VISCOR Lanka"]
    else:
        allowed_locs = LOCATIONS

    if request.method == 'POST':
        reel_no = request.form.get('reel_no')
        store_location = request.form.get('store_location')
        gate_pass = request.form.get('gate_pass')

        if ActiveStock.query.filter_by(reel_no=reel_no).first():
            flash(f"Reel {reel_no} already exists!", "danger")
            return redirect(url_for('add_stock'))
        
        # Cross check backend validation
        if store_location not in allowed_locs:
            flash("Unauthorized Location Selection for your Role!", "danger")
            return redirect(url_for('add_stock'))

        gate_pass_final = "LOCKED-OP2" if role == "Data Operator 2" else gate_pass
        
        stock = ActiveStock(
            reel_no=reel_no, size=request.form.get('size'), gsm=request.form.get('gsm'),
            type=request.form.get('type'), supplier=request.form.get('supplier'),
            weight=float(request.form.get('weight')), gate_pass=gate_pass_final,
            store_location=store_location
        )
        db.session.add(stock)
        db.session.commit()
        flash("Stock added successfully!", "success")
        return redirect(url_for('active_stock', print_reel_no=reel_no))
        
    return render_template('add_stock.html', locations=allowed_locs)

# --- Requirement 3: Active Stock පෙරහන (Filter) කිරීම ---
@app.route('/active_stock')
def active_stock():
    if 'username' not in session: return redirect(url_for('login'))
    role = session.get('role')
    
    if role == 'Data Operator 1':
        stocks = ActiveStock.query.filter_by(status='Active', store_location='VISCOR Lanka').all()
    elif role == 'Data Operator 2':
        stocks = ActiveStock.query.filter(ActiveStock.status=='Active', ActiveStock.store_location!='VISCOR Lanka').all()
    else:
        stocks = ActiveStock.query.filter_by(status='Active').all()
        
    return render_template('active_stock.html', stocks=stocks, locations=LOCATIONS)

# --- Requirement 7 & 8: Dataop 2 මඟින් VISCOR Lanka වෙත කරන Issue/Transfer එක විශේෂ Tab එකක් ලෙස හැසිරවීම ---
@app.route('/issue_reel/<int:id>', methods=['POST'])
def issue_reel(id):
    if 'username' not in session: return redirect(url_for('login'))
    stock = ActiveStock.query.get_or_404(id)
    doc_type = request.form.get('doc_type')
    doc_number = request.form.get('doc_number')
    is_viscor_line = request.form.get('is_viscor')
    role = session.get('role')
    
    if role == 'Data Operator 2' and is_viscor_line:
        # Requirement 7: status එක Pending_Viscor ලෙස වෙනස් කර IssueMain Tab එකට යොමු කිරීම
        stock.status = 'Pending_Viscor'
        stock.is_viscor_issued = 1
        if doc_type == 'SR': stock.sr_no = doc_number
        else: stock.gate_pass = doc_number
        db.session.commit()
        flash("Reel transferred to VISCOR Lanka IssueMain. Pending Dataop1 verification.", "warning")
        return redirect(url_for('active_stock'))
        
    # සාමාන්‍ය Issue කිරීම්
    stock.status = 'Issued'
    stock.is_viscor_issued = 1 if is_viscor_line else 0
    if doc_type == 'SR': stock.sr_no = doc_number
    else: stock.gate_pass = doc_number
    
    db.session.commit()
    flash("Reel issued successfully!", "success")
    return redirect(url_for('active_stock'))

# --- Requirement 7 & 8: Viscor Lanka IssueMain Registry View & Verification Route ---
@app.route('/viscor_issue_main')
def viscor_issue_main():
    if 'username' not in session: return redirect(url_for('login'))
    # මෙම ටැබ් එක ඕනෑම කෙනෙකුට නැරඹිය හැකි මුත් Verify කළ හැක්කේ Dataop 1 ට පමණි
    stocks = ActiveStock.query.filter_by(status='Pending_Viscor').all()
    return render_template('viscor_issue_main.html', stocks=stocks)

@app.route('/verify_viscor_issue/<int:id>', methods=['POST'])
def verify_viscor_issue(id):
    if 'username' not in session: return redirect(url_for('login'))
    role = session.get('role')
    
    # Requirement 8: dataop 2 හට Verify කිරීමට කිසිසේත්ම ඉඩ නොදීම
    if role not in ['Admin', 'Data Operator 1']:
        flash("Unauthorized Control! Data Operator 2 is strictly forbidden from verifying transfers.", "danger")
        return redirect(url_for('viscor_issue_main'))
        
    stock = ActiveStock.query.get_or_404(id)
    stock.store_location = "VISCOR Lanka"
    stock.status = "Active"
    stock.is_viscor_issued = 0
    db.session.commit()
    
    flash(f"Reel '{stock.reel_no}' Verified! Added back to VISCOR Lanka Active Stock Registry.", "success")
    return redirect(url_for('active_stock'))

# --- Requirement 4: Issued Stock පෙරහන කිරීම ---
@app.route('/issued_stock')
def issued_stock():
    if 'username' not in session: return redirect(url_for('login'))
    role = session.get('role')
    
    if role == 'Data Operator 1':
        stocks = ActiveStock.query.filter_by(status='Issued', store_location='VISCOR Lanka').all()
    elif role == 'Data Operator 2':
        # Requirement 4: Viscor Lanka වලට Issue නොකරපු, සහ තමන්ගේ Location වල ඒවා පමණක් පෙන්වීම
        stocks = ActiveStock.query.filter(ActiveStock.status=='Issued', ActiveStock.store_location!='VISCOR Lanka', ActiveStock.is_viscor_issued==0).all()
    else:
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

# --- Requirement 5: Finished Stock පෙරහන කිරීම ---
@app.route('/finished_stock')
def finished_stock():
    if 'username' not in session: return redirect(url_for('login'))
    role = session.get('role')
    
    if role == 'Data Operator 1':
        stocks = ActiveStock.query.filter_by(status='Finished', store_location='VISCOR Lanka').all()
    elif role == 'Data Operator 2':
        stocks = ActiveStock.query.filter(ActiveStock.status=='Finished', ActiveStock.store_location!='VISCOR Lanka').all()
    else:
        stocks = ActiveStock.query.filter_by(status='Finished').all()
        
    return render_template('finished_stock.html', stocks=stocks)

# --- Requirement 1: Usage & Reports වල Calendar View, Date Filtering සහ Dataop 2 හට Viscor Lanka බ්ලොක් කිරීම ---
@app.route('/usage_logs', methods=['GET'])
def usage_logs():
    if 'username' not in session: return redirect(url_for('login'))
    role = session.get('role')
    
    f_location = request.args.get('location', '')
    f_type = request.args.get('type', '')
    f_supplier = request.args.get('supplier', '')
    f_date = request.args.get('filter_date', '') # Calendar Date string (YYYY-MM-DD)
    
    query = UsageReelLog.query
    
    # Operator සීමාවන් සහ Viscor Block කිරීම්
    if role == 'Data Operator 1':
        query = query.filter(UsageReelLog.store_location == 'VISCOR Lanka')
        current_allowed_locs = ["VISCOR Lanka"]
    elif role == 'Data Operator 2':
        query = query.filter(UsageReelLog.store_location != 'VISCOR Lanka')
        current_allowed_locs = [l for l in LOCATIONS if l != "VISCOR Lanka"]
        if f_location == 'VISCOR Lanka': f_location = '' # Force remove if manipulated
    else:
        current_allowed_locs = LOCATIONS

    # Dynamic Inputs Filtering
    if f_location: query = query.filter(UsageReelLog.store_location == f_location)
    if f_type: query = query.filter(UsageReelLog.type.like(f"%{f_type}%"))
    if f_supplier: query = query.filter(UsageReelLog.supplier.like(f"%{f_supplier}%"))
    
    # Calendar Filter Query Integration (Cross-database compatible)
    if f_date:
        query = query.filter(db.cast(UsageReelLog.logged_at, db.Date) == f_date)
    
    logs = query.order_by(UsageReelLog.logged_at.desc()).all()
    return render_template('usage_logs.html', logs=logs, locations=current_allowed_locs, 
                           f_location=f_location, f_type=f_type, f_supplier=f_supplier, f_date=f_date)

@app.route('/update_location/<int:id>', methods=['POST'])
def update_location(id):
    if 'username' not in session: return redirect(url_for('login'))
    stock = ActiveStock.query.get_or_404(id)
    new_location = request.form.get('store_location')
    role = session.get('role')
    
    if role == 'Data Operator 2' and new_location == 'VISCOR Lanka':
        flash("Data Operator 2 cannot change location to VISCOR Lanka!", "danger")
        return redirect(url_for('active_stock'))
    if role == 'Data Operator 1' and new_location != 'VISCOR Lanka':
        flash("Data Operator 1 cannot move items outside VISCOR Lanka!", "danger")
        return redirect(url_for('active_stock'))
        
    stock.store_location = new_location
    db.session.commit()
    flash(f"Location updated for Reel: {stock.reel_no}!", "success")
    return redirect(url_for('active_stock'))

@app.route('/delete_stock/<int:id>', methods=['POST'])
def delete_stock(id):
    if 'username' not in session: return redirect(url_for('login'))
    if session.get('role') in ['Admin', 'Data Operator 1', 'Data Operator 2']:
        stock = ActiveStock.query.get_or_404(id)
        db.session.delete(stock)
        db.session.commit()
        flash(f"Reel Row '{stock.reel_no}' deleted!", "success")
    return redirect(url_for('active_stock'))

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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)