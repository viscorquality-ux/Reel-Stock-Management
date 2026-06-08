from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "viscor_super_secret_key"

# --- Database Configuration ---
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("mysql://"):
    database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
elif not database_url:
    database_url = "sqlite:///viscor_local.db"

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# 1. Database Models (ඔබේ PyQt System එකට සමානයි)
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
    status = db.Column(db.String(20), default='Active')
    is_viscor_issued = db.Column(db.Integer, default=0)

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
    action_type = db.Column(db.String(20))
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)

# Database සෑදීම සහ Default Users ඇතුලත් කිරීම
with app.app_context():
    db.create_all()
    if not User.query.first():
        db.session.add(User(username='admin', password='admin@0123', role='Admin'))
        db.session.add(User(username='dataop1', password='viscor@1234', role='Data Operator 1'))
        db.session.add(User(username='dataop2', password='packwell@5678', role='Data Operator 2'))
        db.session.commit()

# ==========================================
# 2. Routes (Web Pages & Functions)
# ==========================================

@app.route('/')
def login():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login_submit', methods=['POST'])
def login_submit():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username, password=password).first()
    
    if user:
        session['username'] = user.username
        session['role'] = user.role
        flash(f"Welcome back, {user.username}!", "success")
        return redirect(url_for('dashboard'))
    else:
        flash("Invalid Credentials!", "danger")
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session: return redirect(url_for('login'))
    
    active_count = ActiveStock.query.filter_by(status='Active').count()
    issued_count = ActiveStock.query.filter_by(status='Issued').count()
    return render_template('dashboard.html', active_count=active_count, issued_count=issued_count)

# --- ADD STOCK ---
@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    if 'username' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        reel_no = request.form.get('reel_no')
        
        # Check if exists
        if ActiveStock.query.filter_by(reel_no=reel_no).first():
            flash("This Reel Number is already registered!", "danger")
            return redirect(url_for('add_stock'))
            
        gate_pass = "LOCKED-OP2" if session.get('username') == "dataop2" else request.form.get('gate_pass')
        
        new_stock = ActiveStock(
            reel_no=reel_no, size=request.form.get('size'), gsm=request.form.get('gsm'),
            type=request.form.get('type'), supplier=request.form.get('supplier'),
            weight=float(request.form.get('weight')), gate_pass=gate_pass,
            store_location=request.form.get('store_location')
        )
        db.session.add(new_stock)
        db.session.commit()
        flash(f"Reel {reel_no} Added Successfully!", "success")
        return redirect(url_for('active_stock'))
        
    return render_template('add_stock.html')

# --- ACTIVE STOCK ---
@app.route('/active_stock')
def active_stock():
    if 'username' not in session: return redirect(url_for('login'))
    stocks = ActiveStock.query.filter_by(status='Active').all()
    return render_template('active_stock.html', stocks=stocks)

@app.route('/issue_reel/<int:id>', methods=['POST'])
def issue_reel(id):
    stock = ActiveStock.query.get_or_404(id)
    doc_type = request.form.get('doc_type') # SR or GP
    doc_number = request.form.get('doc_number')
    is_viscor = 1 if request.form.get('is_viscor') else 0
    
    stock.status = 'Issued'
    stock.is_viscor_issued = is_viscor
    if doc_type == 'SR':
        stock.sr_no = doc_number
    else:
        stock.gate_pass = doc_number
        
    db.session.commit()
    flash(f"Reel {stock.reel_no} Issued Successfully!", "success")
    return redirect(url_for('active_stock'))

# --- ISSUED STOCK & RETURN PROCESSING ---
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
        flash("Reel not found in Issued pool!", "danger")
        return redirect(url_for('issued_stock'))
        
    consumption = stock.weight - new_weight
    old_weight = stock.weight
    
    # Update Active Stock
    stock.weight = new_weight
    stock.status = 'Active'
    
    # Log to Return Table
    ret_log = ReturnReelLog(reel_no=stock.reel_no, size=stock.size, gsm=stock.gsm, type=stock.type, supplier=stock.supplier,
                            previous_weight=old_weight, returned_weight=new_weight, consumption=consumption, 
                            gate_pass=stock.gate_pass, store_location=stock.store_location, sr_no=stock.sr_no)
                            
    # Log to Usage Table
    usage_log = UsageReelLog(reel_no=stock.reel_no, size=stock.size, gsm=stock.gsm, type=stock.type, supplier=stock.supplier,
                             used_weight=consumption, gate_pass=stock.gate_pass, store_location=stock.store_location, 
                             sr_no=stock.sr_no, action_type="PARTIAL_RETURN")
                             
    db.session.add(ret_log)
    db.session.add(usage_log)
    db.session.commit()
    flash(f"Reel {reel_no} returned successfully. Logged usage: {consumption}kg.", "success")
    return redirect(url_for('issued_stock'))

@app.route('/finish_reel/<int:id>', methods=['POST'])
def finish_reel(id):
    stock = ActiveStock.query.get_or_404(id)
    stock.status = 'Finished'
    
    usage_log = UsageReelLog(reel_no=stock.reel_no, size=stock.size, gsm=stock.gsm, type=stock.type, supplier=stock.supplier,
                             used_weight=stock.weight, gate_pass=stock.gate_pass, store_location=stock.store_location, 
                             sr_no=stock.sr_no, action_type="FINISHED")
                             
    db.session.add(usage_log)
    db.session.commit()
    flash(f"Reel {stock.reel_no} marked as Finished.", "info")
    return redirect(url_for('issued_stock'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)