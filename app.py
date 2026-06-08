from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = 'viscor_packwell_super_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reel_management.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Timezone Setting
colombo_tz = pytz.timezone('Asia/Colombo')

# --- Database Models ---
class Reel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reel_number = db.Column(db.String(100), unique=True, nullable=False)
    size_cm = db.Column(db.Float, nullable=False)
    weight_kg = db.Column(db.Float, nullable=False) 
    paper_name = db.Column(db.String(50), nullable=False) 
    status = db.Column(db.String(30), default='Full Reel') # Full Reel, Used Reel, Issued, Finished
    gate_pass_number = db.Column(db.String(50), nullable=True)
    sr_number = db.Column(db.String(50), nullable=True) 
    routing_type = db.Column(db.String(50), nullable=True)
    store_location = db.Column(db.String(50), default='Main Store') # For issued/usage logs
    gsm = db.Column(db.Integer, default=0) # For templates that call gsm
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz), onupdate=lambda: datetime.now(colombo_tz))
    
    histories = db.relationship('ReelHistory', backref='reel', lazy='joined', cascade="all, delete-orphan")

    # Property aliases to match different HTML template variable namings
    @property
    def reel_no(self): return self.reel_number
    @property
    def size(self): return self.size_cm
    @property
    def type(self): return self.paper_name
    @property
    def weight(self): return self.weight_kg
    @property
    def sr_no(self): return self.sr_number
    @property
    def gate_pass(self): return self.gate_pass_number
    @property
    def is_viscor_issued(self): return 1 if self.routing_type == 'Viscor Lanka Line' else 0

class ReelHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reel.id'), nullable=False)
    usage_details = db.Column(db.String(255), nullable=False)
    weight_used = db.Column(db.Float, default=0.0)
    action_type = db.Column(db.String(50), default='LOG') # FINISHED, PARTIAL RETURN, INITIAL, ISSUE
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))

    # Aliases for usage_logs.html mapping
    @property
    def logged_at(self): return self.timestamp
    @property
    def reel_no(self): return self.reel.reel_number
    @property
    def store_location(self): return self.reel.store_location
    @property
    def size(self): return self.reel.size_cm
    @property
    def gsm(self): return self.reel.gsm
    @property
    def type(self): return self.reel.paper_name
    @property
    def used_weight(self): return self.weight_used

# --- Authentication Gateway ---
@app.before_request
def require_login():
    allowed_routes = ['login', 'login_submit', 'static']
    if request.endpoint not in allowed_routes and 'role' not in session:
        return redirect(url_for('login'))

# --- Application Routes ---

@app.route('/')
def home():
    return redirect(url_for('dashboard'))

# Login Routes
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/login_submit', methods=['POST'])
def login_submit():
    username = request.form.get('username')
    # Default mock login assignment for simulation. Expand this with actual DB passwords later if needed.
    if username == 'dataop1': session['role'] = 'dataop1'
    elif username == 'super1': session['role'] = 'super1'
    elif username == 'dataop2': session['role'] = 'dataop2'
    else: session['role'] = 'dataop1'
    
    flash(f"Welcome to the System! Logged in as {session['role']}", 'success')
    return redirect(url_for('dashboard'))

# Dashboard Route
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

# Active Stock Route
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

# Add Stock Route
@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    user_role = session.get('role', 'dataop1')
    if request.method == 'POST':
        reel_number = request.form['reel_number']
        size_cm = request.form['size_cm']
        weight_kg = request.form['weight_kg']
        paper_name = request.form['paper_name']
        status = request.form['status'] 
        gate_pass_number = request.form['gate_pass_number']
        
        routing_type = "Viscor Lanka Line" if user_role == 'dataop1' else request.form.get('routing_type', '')

        new_reel = Reel(
            reel_number=reel_number, size_cm=float(size_cm), weight_kg=float(weight_kg),
            paper_name=paper_name, status=status, gate_pass_number=gate_pass_number, routing_type=routing_type
        )
        db.session.add(new_reel)
        db.session.commit()
        
        initial_log = ReelHistory(reel_id=new_reel.id, usage_details=f"Initial Stock added as {status}", action_type='INITIAL')
        db.session.add(initial_log)
        db.session.commit()
        
        flash(f"Reel {reel_number} Successfully Added to the System!", "success")
        return redirect(url_for('active_stock'))
        
    return render_template('add_stock.html', user_role=user_role)

# Finished and Usage Stock Board
@app.route('/finished_usage_stock', methods=['GET', 'POST'])
@app.route('/finished_stock', methods=['GET', 'POST'])
def finished_usage_stock():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    finished_query = Reel.query.filter_by(status='Finished')
    usage_query = ReelHistory.query.join(Reel).filter(ReelHistory.action_type.in_(['PARTIAL RETURN', 'FINISHED']))
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
        
        finished_query = finished_query.filter(Reel.updated_at.between(start_date, end_date))
        usage_query = usage_query.filter(ReelHistory.timestamp.between(start_date, end_date))

    finished_reels = finished_query.all()
    usage_logs = usage_query.all()
    
    total_finished_weight = sum(r.weight_kg for r in finished_reels)
    total_used_weight_log = sum(log.weight_used for log in usage_logs)
    
    return render_template('finished_stock.html', 
                           finished_reels=finished_reels, usage_logs=usage_logs,
                           total_finished_weight=total_finished_weight, total_used_weight_log=total_used_weight_log,
                           start_date=start_date_str, end_date=end_date_str)

# Manual Dataop1 Update Route (Supports URL both with and without trailing slash as requested by form)
@app.route('/update_sr_number<int:id>', methods=['POST'])
@app.route('/update_sr_number/<int:id>', methods=['POST'])
def update_sr_number(id):
    if session.get('role') != 'dataop1':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('finished_usage_stock'))
        
    reel = Reel.query.get_or_404(id)
    sr_number = request.form['sr_number']
    reel.sr_number = sr_number
    db.session.commit()
    
    flash(f"SR Number '{sr_number}' updated successfully.", "success")
    return redirect(url_for('finished_usage_stock'))

# Viscor Verify Route
@app.route('/viscor_issue')
@app.route('/viscor_issue_main')
def viscor_issue():
    reels = Reel.query.filter_by(routing_type='Viscor Lanka Line', status='Full Reel').all()
    return render_template('viscor_issue_main.html', reels=reels)

# Issued Stock Board
@app.route('/issued_stock')
def issued_stock():
    stocks = Reel.query.filter_by(status='Issued').all()
    return render_template('issued_stock.html', stocks=stocks)

# Dispatch / Issue Reel Logic
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
    
    log = ReelHistory(reel_id=reel.id, usage_details=f"Dispatched to production. Ref: {doc_type} {doc_number}", action_type='ISSUE')
    db.session.add(log)
    db.session.commit()
    flash('Reel dispatched to production successfully.', 'success')
    return redirect(request.referrer or url_for('active_stock'))

# Location Update
@app.route('/update_location/<int:id>', methods=['POST'])
def update_location(id):
    reel = Reel.query.get_or_404(id)
    reel.store_location = request.form.get('store_location')
    db.session.commit()
    flash('Store location updated.', 'success')
    return redirect(url_for('issued_stock'))

# Mark Finished completely
@app.route('/finish_reel/<int:id>', methods=['POST'])
def finish_reel(id):
    reel = Reel.query.get_or_404(id)
    used_weight = reel.weight_kg
    reel.weight_kg = 0.0 # 100% Consumed
    reel.status = 'Finished'
    
    log = ReelHistory(reel_id=reel.id, usage_details="Marked 100% finished via Production line", weight_used=used_weight, action_type='FINISHED')
    db.session.add(log)
    db.session.commit()
    flash('Reel marked as completely finished.', 'success')
    return redirect(url_for('issued_stock'))

# Process Partial Return
@app.route('/process_return', methods=['POST'])
def process_return():
    reel_no = request.form.get('reel_no')
    returned_weight = float(request.form.get('returned_weight'))
    
    reel = Reel.query.filter_by(reel_number=reel_no).first()
    if reel:
        used_amount = reel.weight_kg - returned_weight
        reel.weight_kg = returned_weight
        reel.status = 'Used Reel'
        
        log = ReelHistory(reel_id=reel.id, usage_details=f"Returned to Stock. New balance: {returned_weight}kg", weight_used=used_amount, action_type='PARTIAL RETURN')
        db.session.add(log)
        db.session.commit()
        flash('Partial return executed and moved to Used Stock.', 'info')
        
    return redirect(url_for('issued_stock'))

# Comprehensive Usage Logs
@app.route('/usage_logs')
def usage_logs():
    f_location = request.args.get('location', '')
    f_date = request.args.get('filter_date', '')
    f_type = request.args.get('type', '')
    
    query = ReelHistory.query.join(Reel)
    
    if f_location:
        query = query.filter(Reel.store_location == f_location)
    if f_type:
        query = query.filter(Reel.paper_name.ilike(f"%{f_type}%"))
    if f_date:
        try:
            # Check strictly by date string match mapped against timestamp
            date_obj = datetime.strptime(f_date, '%Y-%m-%d').date()
            # In SQLite db.func.date() pulls just the date part for comparison
            query = query.filter(db.func.date(ReelHistory.timestamp) == date_obj)
        except ValueError:
            pass
            
    logs = query.order_by(ReelHistory.timestamp.desc()).all()
    
    # Render locations dropdown explicitly based on distinct available entries
    db_locations = db.session.query(Reel.store_location).distinct().all()
    locations = [loc[0] for loc in db_locations if loc[0]]

    return render_template('usage_logs.html', logs=logs, locations=locations, f_location=f_location, f_date=f_date, f_type=f_type)


# --- Application Runner Setup ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)