from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = 'viscor_packwell_ultimate_secure_key'

# ==============================================================================
# ⚠️ DATABASE CONFIGURATION
# ==============================================================================
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://avnadmin:AVNS_gHRTw4Hzio_XlhXcm7d@mysql-3e9936af-viscorquality-0270.g.aivencloud.com:28643/defaultdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {
        "ssl": {}
    }
}

db = SQLAlchemy(app)
colombo_tz = pytz.timezone('Asia/Colombo')

SYSTEM_LOCATIONS = [
    'Viscor Lanka', 'Packwell 1', 'Packwell 2', 'Packwell 3', 
    'Packwell 4', 'Packwell 5', 'Packwell 6', 'Packwell 7'
]

# 🔐 Authorized Users Dictionary
AUTHORIZED_USERS = {
    "admin": "admin@0123",
    "dataop1": "viscor@2468",
    "dataop2": "packwell@8642",
    "super1": "vissuper@00",
    "super2": "packsuper@11"
}

# --- Database Models ---
class Reel(db.Model):
    __tablename__ = 'reels'
    id = db.Column(db.Integer, primary_key=True)
    reel_number = db.Column(db.String(100), unique=True, nullable=False)
    paper_name = db.Column(db.String(100), nullable=False)
    size_cm = db.Column(db.Float, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    gsm = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(50), nullable=False) 
    store_location = db.Column(db.String(100), default='Viscor Lanka')
    gate_pass_number = db.Column(db.String(100), nullable=True, default='-')
    supplier = db.Column(db.String(100), nullable=True, default='-')
    routing_type = db.Column(db.String(100), nullable=True, default='Standard')
    sr_number = db.Column(db.String(100), nullable=True, default='-')
    status = db.Column(db.String(50), default='Full Reel') 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))

    @property
    def reel_no(self): return self.reel_number
    @property
    def size(self): return self.size_cm
    @property
    def gate_pass(self): return self.gate_pass_number or '-'
    @property
    def sr_no(self): return self.sr_number or '-'

class ReelHistory(db.Model):
    __tablename__ = 'reel_histories'
    id = db.Column(db.Integer, primary_key=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False) 
    used_weight = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, nullable=True)
    logged_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))

    reel = db.relationship('Reel', backref=db.backref('history', lazy=True))

    @property
    def timestamp(self): return self.logged_at
    @property
    def reel_no(self): return self.reel.reel_number if self.reel else '-'
    @property
    def store_location(self): return self.reel.store_location if self.reel else '-'
    @property
    def size(self): return self.reel.size_cm if self.reel else 0.0
    @property
    def gsm(self): return self.reel.gsm if self.reel else 0
    @property
    def type(self): return self.reel.type if self.reel else '-'
    @property
    def weight_used(self): return self.used_weight
    @property
    def usage_details(self): return self.notes or f"{self.action_type} process executed"

# --- Security Routing ---
@app.before_request
def check_auth():
    allowed_routes = ['index', 'login_submit', 'static']
    if request.endpoint not in allowed_routes and 'role' not in session:
        return redirect(url_for('index'))

@app.route('/')
def index():
    if 'role' in session: return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login_submit', methods=['POST'])
def login_submit():
    username = request.form.get('username')
    password = request.form.get('password')

    # 🔐 Check Username and Password Match
    if username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password:
        session['role'] = username
        flash(f"Welcome {username}! Logged in successfully.", "success")
        return redirect(url_for('dashboard'))
    else:
        flash("Invalid Username or Password! Please try again.", "danger")
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('role', None)
    flash("You have been securely logged out.", "info")
    return redirect(url_for('index'))

# --- Core Views ---
@app.route('/dashboard')
def dashboard():
    active_count = Reel.query.filter(Reel.status.in_(['Full Reel', 'Partial Reel'])).count()
    active_reels = Reel.query.filter(Reel.status.in_(['Full Reel', 'Partial Reel'])).all()
    active_weight = sum(r.weight for r in active_reels)
    pending_viscor_count = Reel.query.filter_by(store_location='Viscor Lanka', status='Full Reel').count()
    issued = Reel.query.filter_by(status='Issued').count()
    return render_template('dashboard.html', active_count=active_count, active_weight=active_weight, pending_viscor_count=pending_viscor_count, issued=issued)

@app.route('/active_stock')
def active_stock():
    stocks = Reel.query.filter(Reel.status.in_(['Full Reel', 'Partial Reel'])).all()
    return render_template('active_stock.html', stocks=stocks, locations=SYSTEM_LOCATIONS)

@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    if request.method == 'POST':
        reel = Reel(
            reel_number=request.form.get('reel_number'),
            paper_name=request.form.get('paper_name'),
            size_cm=float(request.form.get('size_cm', 0)),
            weight=float(request.form.get('weight', 0)),
            gsm=int(request.form.get('gsm', 0)),
            type=request.form.get('type'), 
            store_location=request.form.get('store_location'), 
            gate_pass_number=request.form.get('gate_pass_number', '-'),
            supplier=request.form.get('supplier', '-'),
            routing_type='Standard'
        )
        db.session.add(reel)
        db.session.commit()
        flash(f"New Reel {reel.reel_number} Added Successfully!", "success")
        return redirect(url_for('active_stock'))
    return render_template('add_stock.html', user_role=session.get('role', 'dataop1'))

@app.route('/issued_stock')
def issued_stock():
    stocks = Reel.query.filter_by(status='Issued').all()
    return render_template('issued_stock.html', stocks=stocks)

@app.route('/finished_usage_stock')
def finished_usage_stock():
    start_date = request.args.get('start_date', '2026-06-01')
    end_date = request.args.get('end_date', '2026-06-30')
    reels = ReelHistory.query.filter_by(action_type='FINISHED').all()
    usage_logs = ReelHistory.query.filter(ReelHistory.action_type.in_(['PARTIAL_RETURN', 'FINISHED'])).all()
    total_finished_weight = sum(item.reel.weight for item in reels if item.reel)
    total_used_weight_log = sum(log.used_weight for log in usage_logs)
    return render_template('finished_stock.html', start_date=start_date, end_date=end_date, reels=reels, usage_logs=usage_logs, total_finished_weight=total_finished_weight, total_used_weight_log=total_used_weight_log)

@app.route('/damage_sell_stock')
def damage_sell_stock():
    stocks = Reel.query.filter(Reel.status.in_(['Damaged', 'Sold'])).all()
    return render_template('damage_sell_stock.html', stocks=stocks)

@app.route('/viscor_issue')
def viscor_issue():
    reels = Reel.query.filter_by(store_location='Viscor Lanka', status='Full Reel').all()
    return render_template('viscor_issue_main.html', reels=reels)

@app.route('/usage_logs')
def usage_logs():
    f_location = request.args.get('location', '')
    f_date = request.args.get('filter_date', '')
    f_type = request.args.get('type', '')
    f_supplier = request.args.get('supplier', '')
    query = ReelHistory.query.join(Reel)
    if f_location: query = query.filter(Reel.store_location == f_location)
    if f_type: query = query.filter(Reel.paper_name.ilike(f"%{f_type}%"))
    if f_supplier: query = query.filter(Reel.supplier.ilike(f"%{f_supplier}%"))
    logs = query.all()
    return render_template('usage_logs.html', logs=logs, locations=SYSTEM_LOCATIONS, f_location=f_location, f_date=f_date, f_type=f_type, f_supplier=f_supplier)

# --- Action Processors ---
@app.route('/viscor_accept/<int:id>', methods=['POST'])
@app.route('/verify_accept/<int:id>', methods=['POST'])
def verify_accept(id):
    reel = Reel.query.get_or_404(id)
    reel_condition = request.form.get('reel_condition', 'Full Reel')
    
    reel.routing_type = 'Standard'
    if reel_condition == 'Partial Reel':
        reel.status = 'Used Reel'
    else:
        reel.status = 'Full Reel'
        
    log = ReelHistory(reel_id=reel.id, usage_details=f"Verified & Accepted from Viscor as {reel_condition}", action_type='VISCOR_ACCEPT')
    db.session.add(log)
    db.session.commit()
    flash(f"Reel {reel.reel_number} committed to Active Stock.", "success")
    return redirect(url_for('viscor_issue'))

@app.route('/send_to_viscor/<int:id>', methods=['POST'])
def send_to_viscor(id):
    reel = Reel.query.get_or_404(id)
    reel.routing_type = 'Viscor Lanka Line'
    log = ReelHistory(reel_id=reel.id, usage_details="Routed to Viscor Lanka Production Line", action_type='SEND_VISCOR')
    db.session.add(log)
    db.session.commit()
    flash(f"Reel {reel.reel_number} sent to Viscor Line.", "success")
    return redirect(url_for('active_stock'))

@app.route('/update_status/<int:id>', methods=['POST'])
@app.route('/mark_damage_sell/<int:id>', methods=['POST'])
def update_status(id):
    reel = Reel.query.get_or_404(id)
    status_type = request.form.get('status_type')
    if not status_type: status_type = 'Damaged'
    notes = request.form.get('notes', 'Updated via Registry Screen')
    
    if status_type in ['Damaged', 'Sold', 'Finished']:
        reel.status = status_type
        if status_type == 'Finished': reel.weight = 0.0
        log = ReelHistory(reel_id=reel.id, usage_details=f"Status changed to {status_type}. Notes: {notes}", action_type=status_type.upper())
        db.session.add(log)
        db.session.commit()
        flash(f"Reel status updated to {status_type} successfully.", "success")
    else:
        flash("Invalid status type.", "danger")
    return redirect(request.referrer or url_for('active_stock'))

@app.route('/issue_reel/<int:id>', methods=['POST'])
def issue_reel(id):
    reel = Reel.query.get_or_404(id)
    doc_type = request.form.get('doc_type')
    doc_number = request.form.get('doc_number')
    if doc_type == 'SR': reel.sr_number = doc_number
    else: reel.gate_pass_number = doc_number
    reel.status = 'Issued'
    db.session.commit()
    flash(f"Reel {reel.reel_number} Dispatch Executed Successfully.", "success")
    return redirect(url_for('active_stock'))

@app.route('/update_location/<int:id>', methods=['POST'])
def update_location(id):
    reel = Reel.query.get_or_404(id)
    reel.store_location = request.form.get('store_location')
    db.session.commit()
    flash(f"Location Updated for Reel {reel.reel_number}.", "success")
    return redirect(url_for('active_stock'))

@app.route('/process_return', methods=['POST'])
def process_return():
    reel_no = request.form.get('reel_no')
    returned_weight = float(request.form.get('returned_weight', 0))
    reel = Reel.query.filter_by(reel_number=reel_no).first_or_404()
    consumed = reel.weight - returned_weight
    
    history = ReelHistory(reel_id=reel.id, action_type='PARTIAL_RETURN', used_weight=consumed, notes=f"Partial Return. Consumed: {consumed} kg")
    reel.weight = returned_weight
    reel.status = 'Partial Reel'
    db.session.add(history)
    db.session.commit()
    flash(f"Partial Return Processed for {reel_no}.", "success")
    return redirect(url_for('issued_stock'))

@app.route('/update_sr_number/<int:id>', methods=['POST'])
def update_sr_number(id):
    reel = Reel.query.get_or_404(id)
    reel.sr_number = request.form.get('sr_number')
    db.session.commit()
    flash(f"SR Number Updated.", "success")
    return redirect(url_for('finished_usage_stock'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)