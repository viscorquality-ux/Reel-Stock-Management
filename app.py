from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = 'viscor_packwell_ultimate_secure_key'

# ==============================================================================
# ⚠️ DATABASE CONNECTION & AIVEN SSL AUTO-FIX
# ==============================================================================
raw_db_url = 'mysql://avnadmin:AVNS_gHRTw4Hzio_XlhXcm7d@mysql-3e9936af-viscorquality-0270.g.aivencloud.com:28643/defaultdb?ssl-mode=REQUIRED'

# PyMySQL ඩ්‍රයිවර් එක ස්වයංක්‍රීයව එකතු කිරීම
if raw_db_url.startswith('mysql://'):
    raw_db_url = raw_db_url.replace('mysql://', 'mysql+pymysql://', 1)

# URL එක අග ඇති බිඳ වැටීම් ඇති කරන කොටස් ඉවත් කර පිරිසිදු කිරීම
if '?ssl-mode=REQUIRED' in raw_db_url:
    raw_db_url = raw_db_url.replace('?ssl-mode=REQUIRED', '')
elif '&ssl-mode=REQUIRED' in raw_db_url:
    raw_db_url = raw_db_url.replace('&ssl-mode=REQUIRED', '')

app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Aiven Cloud සඳහා අනිවාර්ය SSL ආරක්ෂණ සැකසුම් එකතු කිරීම
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"connect_args": {"ssl": {}}}

db = SQLAlchemy(app)
colombo_tz = pytz.timezone('Asia/Colombo')

class SmartRole(str):
    def __eq__(self, other):
        if not isinstance(other, str):
            return False
        return self.lower().replace(" ", "") == other.lower().replace(" ", "")
    def __ne__(self, other):
        return not self.__eq__(other)

# --- Database Models ---
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
    store_location = db.Column(db.String(100), default='VISCOR Lanka')
    gsm = db.Column(db.Integer, default=0)
    reel_type = db.Column(db.String(100), default='Standard') 
    supplier = db.Column(db.String(100), default='N/A', nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz), onupdate=lambda: datetime.now(colombo_tz))
    
    histories = db.relationship('ReelHistory', backref='reel', lazy='joined', cascade="all, delete-orphan")

    @property
    def reel_no(self): return self.reel_number
    @property
    def size(self): return self.size_cm
    @property
    def type(self): return self.reel_type or 'Standard'
    @property
    def weight(self): return self.weight_kg
    @property
    def sr_no(self): return self.sr_number or '-'
    @property
    def gate_pass(self): return self.gate_pass_number or '-'
    @property
    def is_viscor_issued(self): return 1 if self.routing_type == 'Viscor Lanka Line' else 0

class ReelHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reel.id'), nullable=False)
    usage_details = db.Column(db.String(255), nullable=False)
    weight_used = db.Column(db.Float, default=0.0)
    action_type = db.Column(db.String(50), default='LOG') 
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))

    @property
    def logged_at(self): return self.timestamp
    @property
    def reel_no(self): return self.reel.reel_number if self.reel else ''
    @property
    def store_location(self): return self.reel.store_location if self.reel else 'VISCOR Lanka'
    @property
    def size(self): return self.reel.size_cm if self.reel else 0.0
    @property
    def gsm(self): return self.reel.gsm if self.reel else 0
    @property
    def type(self): return self.reel.reel_type if self.reel else 'Standard'
    @property
    def used_weight(self): return self.weight_used

@app.context_processor
def inject_global_facilities():
    # 📝 ඔබ ඉල්ලූ පරිදි නව Locations ලැයිස්තුව මෙයට එක් කර ඇත.
    return {
        'locations': ['VISCOR Lanka', 'Packwell W1', 'Packwell W2', 'Packwell W3', 'Packwell W4', 'Packwell W5', 'Packwell W6', 'Packwell W7'],
        'f_supplier': request.args.get('supplier', '')
    }

@app.before_request
def handle_session_and_security():
    if 'role' in session and session['role']:
        session['role'] = SmartRole(session['role'])
    allowed_routes = ['login', 'login_submit', 'static', 'reset_db']
    if request.endpoint not in allowed_routes and 'role' not in session:
        return redirect(url_for('login'))

@app.route('/reset_db')
def reset_db():
    db.drop_all()
    db.create_all()
    flash("Database Tables successfully recreated/reset!", "success")
    return redirect(url_for('login'))

@app.route('/')
def home():
    if 'role' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/login_submit', methods=['POST'])
def login_submit():
    username = request.form.get('username')
    session['role'] = SmartRole(username)
    flash(f"Logged in successfully as {session['role']}", "success")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('role', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    active_reels = Reel.query.filter(Reel.status.in_(['Full Reel', 'Used Reel'])).all()
    active_count = len(active_reels)
    active_weight = sum(r.weight_kg for r in active_reels)
    pending_viscor_count = Reel.query.filter_by(routing_type='Viscor Lanka Line', status='Full Reel').count()
    issued = Reel.query.filter_by(status='Issued').count()
    finished = Reel.query.filter_by(status='Finished').count()
    return render_template('dashboard.html', active_count=active_count, active_weight=active_weight,
                           pending_viscor_count=pending_viscor_count, issued=issued, finished=finished)

@app.route('/active_stock')
def active_stock():
    full_reels = Reel.query.filter_by(status='Full Reel').all()
    used_reels = Reel.query.filter_by(status='Used Reel').all()
    total_full_count = len(full_reels)
    total_full_weight = sum(r.weight_kg for r in full_reels)
    total_used_count = len(used_reels)
    total_used_weight = sum(r.weight_kg for r in used_reels)
    return render_template('active_stock.html', 
                           full_reels=full_reels, used_reels=used_reels,
                           total_full_count=total_full_count, total_full_weight=total_full_weight,
                           total_used_count=total_used_count, total_used_weight=total_used_weight)

@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    user_role = session.get('role', 'dataop1')
    if request.method == 'POST':
        try:
            # 🔍 FIX: 400 Bad Request වැළැක්වීම සඳහා .get() භාවිතා කිරීම
            reel_number = request.form.get('reel_number', '').strip()
            paper_name = request.form.get('paper_name', '').strip()
            status = request.form.get('status', 'Full Reel').strip()
            gate_pass_number = request.form.get('gate_pass_number', '').strip()
            
            # අනිවාර්ය දත්ත හිස් නම් Flash Message එකක් මඟින් පරිශීලකයා දැනුවත් කිරීම
            if not reel_number or not paper_name:
                flash("Error: Reel Number and Paper Name are required fields!", "danger")
                return redirect(url_for('add_stock'))
            
            existing_reel = Reel.query.filter_by(reel_number=reel_number).first()
            if existing_reel:
                flash(f"Error: Reel Number '{reel_number}' already exists in the system! Duplicate entries are not allowed.", "danger")
                return redirect(url_for('add_stock'))
                
            size_cm = request.form.get('size_cm', 0.0, type=float)
            weight_kg = request.form.get('weight_kg', 0.0, type=float)
            gsm = request.form.get('gsm', 0, type=int)
            reel_type = request.form.get('reel_type', 'Standard')
            supplier = request.form.get('supplier', 'N/A') or 'N/A'
            routing_type = "Viscor Lanka Line" if user_role in ['dataop1', 'super1'] else request.form.get('routing_type', '')

            new_reel = Reel(
                reel_number=reel_number, size_cm=size_cm, weight_kg=weight_kg,
                paper_name=paper_name, status=status, gate_pass_number=gate_pass_number, routing_type=routing_type,
                gsm=gsm, reel_type=reel_type, supplier=supplier
            )
            db.session.add(new_reel)
            db.session.commit()
            
            initial_log = ReelHistory(reel_id=new_reel.id, usage_details=f"Stock initialized in {status}", action_type='INITIAL')
            db.session.add(initial_log)
            db.session.commit()
            
            flash(f"Reel {reel_number} successfully saved!", "success")
            return redirect(url_for('active_stock'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"System Error occurred: {str(e)}", "danger")
            
    return render_template('add_stock.html', user_role=user_role)

@app.route('/issue_reel/<int:id>', methods=['POST'])
def issue_reel(id):
    reel = Reel.query.get_or_404(id)
    doc_type = request.form.get('doc_type')
    doc_number = request.form.get('doc_number')
    is_viscor = request.form.get('is_viscor')
    reel.status = 'Issued'
    if doc_type == 'SR': reel.sr_number = doc_number
    else: reel.gate_pass_number = doc_number
    if is_viscor == '1': reel.routing_type = 'Viscor Lanka Line'
    
    log = ReelHistory(reel_id=reel.id, usage_details=f"Dispatched via {doc_type}: {doc_number}", action_type='ISSUE')
    db.session.add(log)
    db.session.commit()
    flash('Reel dispatched to production successfully.', 'success')
    return redirect(url_for('active_stock'))

@app.route('/issued_stock')
def issued_stock():
    stocks = Reel.query.filter_by(status='Issued').all()
    return render_template('issued_stock.html', stocks=stocks)

@app.route('/update_location/<int:id>', methods=['POST'])
def update_location(id):
    reel = Reel.query.get_or_404(id)
    reel.store_location = request.form.get('store_location')
    db.session.commit()
    flash('Location updated successfully.', 'success')
    return redirect(request.referrer)

@app.route('/finish_reel/<int:id>', methods=['POST'])
def finish_reel(id):
    reel = Reel.query.get_or_404(id)
    used_weight = reel.weight_kg
    reel.weight_kg = 0.0
    reel.status = 'Finished'
    log = ReelHistory(reel_id=reel.id, usage_details="Marked 100% finished by production line", weight_used=used_weight, action_type='FINISHED')
    db.session.add(log)
    db.session.commit()
    flash('Reel marked as completely finished.', 'success')
    return redirect(url_for('issued_stock'))

@app.route('/process_return', methods=['POST'])
def process_return():
    reel_no = request.form.get('reel_no')
    returned_weight = float(request.form.get('returned_weight'))
    reel = Reel.query.filter_by(reel_number=reel_no).first_or_404()
    used_amount = reel.weight_kg - returned_weight
    if used_amount < 0: used_amount = 0.0
    reel.weight_kg = returned_weight
    reel.status = 'Used Reel'
    log = ReelHistory(reel_id=reel.id, usage_details=f"Returned with balance {returned_weight}kg", weight_used=used_amount, action_type='PARTIAL RETURN')
    db.session.add(log)
    db.session.commit()
    flash('Partial return registered successfully.', 'info')
    return redirect(url_for('active_stock'))

@app.route('/finished_usage_stock', methods=['GET', 'POST'])
def finished_usage_stock():
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    finished_query = Reel.query.filter_by(status='Finished')
    usage_query = ReelHistory.query.join(Reel).filter(ReelHistory.action_type.in_(['PARTIAL RETURN', 'FINISHED']))
    
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
            finished_query = finished_query.filter(Reel.updated_at.between(start_date, end_date))
            usage_query = usage_query.filter(ReelHistory.timestamp.between(start_date, end_date))
        except ValueError:
            pass

    finished_reels = finished_query.all()
    usage_logs = usage_query.all()
    total_finished_weight = sum(r.weight_kg for r in finished_reels)
    total_used_weight_log = sum(log.weight_used for log in usage_logs)
    
    return render_template('finished_stock.html', 
                           finished_reels=finished_reels, usage_logs=usage_logs,
                           total_finished_weight=total_finished_weight, total_used_weight_log=total_used_weight_log,
                           start_date=start_date_str, end_date=end_date_str)

@app.route('/update_sr_number/<int:id>', methods=['POST'])
def update_sr_number(id):
    reel = Reel.query.get_or_404(id)
    reel.sr_number = request.form.get('sr_number')
    db.session.commit()
    flash(f"SR Number updated for Reel {reel.reel_number}.", "success")
    return redirect(url_for('finished_usage_stock'))

@app.route('/viscor_issue')
def viscor_issue():
    reels = Reel.query.filter_by(routing_type='Viscor Lanka Line', status='Full Reel').all()
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
    if f_date:
        try:
            date_obj = datetime.strptime(f_date, '%Y-%m-%d').date()
            query = query.filter(db.func.date(ReelHistory.timestamp) == date_obj)
        except ValueError:
            pass
    logs = query.order_by(ReelHistory.timestamp.desc()).all()
    return render_template('usage_logs.html', logs=logs, f_location=f_location, f_date=f_date, f_type=f_type, f_supplier=f_supplier)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)