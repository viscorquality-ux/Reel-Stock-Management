from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)
app.secret_key = 'viscor_packwell_ultimate_secure_key'

# DATABASE CONFIGURATION
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://avnadmin:AVNS_gHRTw4Hzio_XlhXcm7d@mysql-3e9936af-viscorquality-0270.g.aivencloud.com:28643/defaultdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = { "connect_args": { "ssl": {} } }

db = SQLAlchemy(app)
colombo_tz = pytz.timezone('Asia/Colombo')

class SmartRole(str):
    def __eq__(self, other):
        if not isinstance(other, str): return False
        return self.lower().replace(" ", "") == other.lower().replace(" ", "")
    def __ne__(self, other): return not self.__eq__(other)

# AUTHORIZED USERS DICTIONARY
AUTHORIZED_USERS = {
    "admin": "admin@0123", 
    "dataop1": "viscor@2468", 
    "dataop2": "packwell@8642",
    "super1": "viscor@1357", 
    "super2": "packwell@7531",
    "programmer": "prog@7890"  # Naya user account add kiya gaya hai
}

# MODELS
class Reel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reel_number = db.Column(db.String(100), unique=True, nullable=False)
    size_cm = db.Column(db.Float, nullable=False, default=0.0)
    weight_kg = db.Column(db.Float, nullable=False, default=0.0) 
    paper_name = db.Column(db.String(50), nullable=False) 
    status = db.Column(db.String(30), default='Full Reel') 
    gate_pass_number = db.Column(db.String(50), nullable=True)
    sr_number = db.Column(db.String(50), nullable=True) 
    routing_type = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(100), default='Viscor Lanka') 
    gsm = db.Column(db.Integer, default=0)
    reel_type = db.Column(db.String(100), default='Liner(T)') 
    supplier = db.Column(db.String(100), default='N/A', nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz), onupdate=lambda: datetime.now(colombo_tz))
    histories = db.relationship('ReelHistory', backref='reel', lazy='joined', cascade="all, delete-orphan")

class ReelHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reel.id'), nullable=False)
    usage_details = db.Column(db.String(255), nullable=False)
    weight_used = db.Column(db.Float, default=0.0)
    action_type = db.Column(db.String(50), default='LOG') 
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))

# NAYA MODEL: SR REQUEST TRACKING KE LIYE
class SRRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reel_size = db.Column(db.Float, nullable=False)
    po_number = db.Column(db.String(100), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    gsm = db.Column(db.Integer, nullable=False)
    board_size = db.Column(db.String(50), nullable=False) # Store format: "Width * Length"
    material_name = db.Column(db.String(100), nullable=False)
    layer_type = db.Column(db.String(30), nullable=False) # Top, Bottom, Corru
    calculated_weight = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending Approval') # Pending Approval, Approved, Processed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))

@app.before_request
def handle_session_and_security():
    if 'role' in session and session['role']:
        session['role'] = SmartRole(session['role'])
    allowed_routes = ['login', 'static', 'fix_db']
    if request.endpoint not in allowed_routes and 'role' not in session:
        return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password:
            session['username'] = username
            session['role'] = username
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid Username or Password!", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('role', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    full_reels = Reel.query.filter_by(status='Full Reel').count()
    used_reels = Reel.query.filter_by(status='Used Reel').count()
    finished = Reel.query.filter_by(status='Finished').count()
    damage_sell_count = Reel.query.filter(Reel.status.in_(['Damaged', 'Sold'])).count()
    return render_template('dashboard.html', full=full_reels, used=used_reels, finished=finished, damage_sell_count=damage_sell_count)

@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    user_role = session.get('role', '')
    if user_role in ['super1', 'super2', 'programmer']:
        flash("Unauthorized Action. This account has read-only access here.", "danger")
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        try:
            r_num = request.form.get('reel_number').strip()
            if Reel.query.filter_by(reel_number=r_num).first():
                flash("Reel Number already exists!", "danger")
                return redirect(url_for('add_stock'))
            
            new_reel = Reel(
                reel_number=r_num,
                size_cm=float(request.form.get('size_cm')),
                weight_kg=float(request.form.get('weight_kg')),
                paper_name=request.form.get('paper_name'),
                location=request.form.get('store_location'),
                gsm=int(request.form.get('gsm')),
                reel_type=request.form.get('reel_type'),
                supplier=request.form.get('supplier', 'N/A')
            )
            db.session.add(new_reel)
            db.session.commit()
            db.session.add(ReelHistory(reel_id=new_reel.id, usage_details="Initial Entry Added to System", action_type='ADD'))
            db.session.commit()
            flash("Stock Entry Saved Successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding stock: {str(e)}", "danger")
    return render_template('add_stock.html')

@app.route('/active_stock')
def active_stock():
    user_role = session.get('role', '')
    full_reels = Reel.query.filter_by(status='Full Reel').all()
    used_reels = Reel.query.filter_by(status='Used Reel').all()
    return render_template('active_stock.html', full_reels=full_reels, used_reels=used_reels, user_role=user_role)

@app.route('/issue_reel/<int:id>', methods=['POST'])
def issue_reel(id):
    user_role = session.get('role', '')
    if user_role in ['super1', 'super2', 'programmer']:
        flash("Unauthorized Action. This account has read-only access.", "danger")
        return redirect(url_for('active_stock'))
        
    reel = Reel.query.get_or_404(id)
    doc_type = request.form.get('doc_type')
    doc_number = request.form.get('doc_number')
    
    reel.status = 'Issued'
    if doc_type == 'SR':
        reel.sr_number = doc_number
    else:
        reel.gate_pass_number = doc_number
        
    db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Issued via {doc_type}: {doc_number}", action_type='ISSUE'))
    db.session.commit()
    flash(f"Reel {reel.reel_number} successfully dispatched!", "success")
    return redirect(url_for('active_stock'))

@app.route('/change_status/<int:id>', methods=['POST'])
def change_status(id):
    user_role = session.get('role', '')
    if user_role in ['super1', 'super2', 'programmer']:
        flash("Unauthorized Action.", "danger")
        return redirect(url_for('active_stock'))
        
    reel = Reel.query.get_or_404(id)
    status_type = request.form.get('status_type')
    notes = request.form.get('notes')
    
    reel.status = status_type
    db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Status changed to {status_type}. Notes: {notes}", action_type='STATUS'))
    db.session.commit()
    flash(f"Reel {reel.reel_number} moved to {status_type} registry.", "warning")
    return redirect(url_for('active_stock'))

# NAYE ROUTES: SR REQUEST SYSTEM OPERATIONS
@app.route('/sr_request', methods=['GET', 'POST'])
def sr_request():
    user_role = session.get('role', '')
    
    if request.method == 'POST':
        if user_role != 'programmer':
            flash("❌ Only the Programmer role can submit SR Requests.", "danger")
            return redirect(url_for('sr_request'))
            
        try:
            reel_size = float(request.form.get('reel_size', 0))
            po_number = request.form.get('po_number', '').strip()
            qty = int(request.form.get('qty', 0))
            gsm = int(request.form.get('gsm', 0))
            board_width = request.form.get('board_width', '').strip()
            board_length = request.form.get('board_length', '').strip()
            material_name = request.form.get('material_name', '').strip()
            layer_type = request.form.get('layer_type', 'Top')
            
            board_size = f"{board_width} * {board_length}"
            
            # Formuala Calculation: (board size(cm) * GSM/1000 * (Top/Bottom=1 or Corru=1.5)) / 2 * Qty
            w = float(board_width) if board_width else 0.0
            l = float(board_length) if board_length else 0.0
            multiplier = 1.5 if layer_type == 'Corru' else 1.0
            calculated_weight = ((w * l) * (gsm / 1000.0) * multiplier) / 2.0 * qty
            
            new_sr = SRRequest(
                reel_size=reel_size,
                po_number=po_number,
                qty=qty,
                gsm=gsm,
                board_size=board_size,
                material_name=material_name,
                layer_type=layer_type,
                calculated_weight=calculated_weight,
                status='Pending Approval'
            )
            db.session.add(new_sr)
            db.session.commit()
            flash("✅ SR Request submitted successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error submitting SR: {str(e)}", "danger")
        return redirect(url_for('sr_request'))
        
    sr_logs = SRRequest.query.order_by(SRRequest.id.desc()).all()
    return render_template('sr_request.html', sr_logs=sr_logs, user_role=user_role)

@app.route('/approve_sr/<int:id>', methods=['POST'])
def approve_sr(id):
    user_role = session.get('role', '')
    if user_role not in ['super1', 'super2', 'admin']:
        flash("❌ Unauthorized to approve SR Requests.", "danger")
        return redirect(url_for('sr_request'))
        
    sr = SRRequest.query.get_or_404(id)
    if sr.status == 'Pending Approval':
        sr.status = 'Approved'
        db.session.commit()
        flash(f"✅ SR Request for PO {sr.po_number} has been Approved!", "success")
    return redirect(url_for('sr_request'))

@app.route('/proceed_sr/<int:id>', methods=['POST'])
def proceed_sr(id):
    user_role = session.get('role', '')
    if user_role not in ['dataop1', 'dataop2', 'admin']:
        flash("❌ Unauthorized to proceed SR Requests.", "danger")
        return redirect(url_for('sr_request'))
        
    sr = SRRequest.query.get_or_404(id)
    if sr.status == 'Approved':
        sr.status = 'Processed'
        db.session.commit()
        flash(f"✅ SR Request for PO {sr.po_number} has been Proceeded!", "success")
    return redirect(url_for('sr_request'))

@app.route('/fix_db')
def fix_db():
    db.create_all()
    return "Database synced successfully with SRRequest table!"

if __name__ == '__main__':
    app.run(debug=True, port=5000)
