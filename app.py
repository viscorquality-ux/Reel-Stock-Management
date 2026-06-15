from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = 'viscor_packwell_ultimate_secure_key'

# ==============================================================================
# ⚠️ DATABASE CONFIGURATION WITH SSL
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

class SmartRole(str):
    def __eq__(self, other):
        if not isinstance(other, str): return False
        return self.lower().replace(" ", "") == other.lower().replace(" ", "")
    def __ne__(self, other): return not self.__eq__(other)

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
    store_location = db.Column(db.String(100), default='Viscor Lanka')
    gsm = db.Column(db.Integer, default=0)
    reel_type = db.Column(db.String(100), default='Liner(T)') 
    supplier = db.Column(db.String(100), default='N/A', nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz), onupdate=lambda: datetime.now(colombo_tz))
    
    histories = db.relationship('ReelHistory', backref='reel', lazy='joined', cascade="all, delete-orphan")

    @property
    def reel_no(self): return self.reel_number
    @property
    def size(self): return self.size_cm
    @property
    def type(self): return self.reel_type or 'Liner(T)'
    @property
    def weight(self): return self.weight_kg or 0.0
    @property
    def sr_no(self): return self.sr_number or '-'
    @property
    def gate_pass(self): return self.gate_pass_number or '-'

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
    def store_location(self): return self.reel.store_location if self.reel else 'Viscor Lanka'
    @property
    def used_weight(self): return self.weight_used or 0.0

AUTHORIZED_USERS = {
    "admin": "admin@0123", "dataop1": "viscor@2468", "dataop2": "packwell@8642",
    "super1": "vissuper@00", "super2": "packsuper@11"
}

@app.context_processor
def inject_global_facilities():
    return {
        'locations': [
            'Viscor Lanka', 'Packwell W 1', 'Packwell W 2', 'Packwell W 3', 
            'Packwell W 4', 'Packwell W 5', 'Packwell W 6', 'Packwell W 7'
        ],
        'f_supplier': request.args.get('supplier', '')
    }

@app.before_request
def handle_session_and_security():
    if 'role' in session and session['role']:
        session['role'] = SmartRole(session['role'])
    allowed_routes = ['login', 'login_submit', 'static']
    if request.endpoint not in allowed_routes and 'role' not in session:
        return redirect(url_for('login'))

@app.route('/')
def home():
    return redirect(url_for('dashboard')) if 'role' in session else redirect(url_for('login'))

@app.route('/login')
def login(): return render_template('login.html')

@app.route('/login_submit', methods=['POST'])
def login_submit():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    if username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password:
        session['role'] = SmartRole(username)
        flash(f"Logged in successfully as {username}", "success")
        return redirect(url_for('dashboard'))
    flash("Invalid Username or Password!", "danger")
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    active_reels = Reel.query.filter(Reel.status.in_(['Full Reel', 'Used Reel'])).all()
    active_count = len(active_reels)
    active_weight = sum((r.weight_kg or 0.0) for r in active_reels)
    pending_viscor = Reel.query.filter_by(status='Pending Viscor').count()
    issued = Reel.query.filter_by(status='Issued').count()
    finished = Reel.query.filter_by(status='Finished').count()
    damage_sell_count = Reel.query.filter(Reel.status.in_(['Damaged', 'Sold'])).count()
    return render_template('dashboard.html', active_count=active_count, active_weight=active_weight,
                           pending_viscor_count=pending_viscor, issued=issued, finished=finished, damage_sell_count=damage_sell_count)

@app.route('/active_stock')
def active_stock():
    try:
        full_reels = Reel.query.filter_by(status='Full Reel').all()
        used_reels = Reel.query.filter_by(status='Used Reel').all()

        if not full_reels: full_reels = []
        if not used_reels: used_reels = []

        total_full_count = len(full_reels)
        total_used_count = len(used_reels)

        total_full_weight = sum(float(reel.weight_kg) for reel in full_reels if reel.weight_kg) or 0.0
        total_used_weight = sum(float(reel.weight_kg) for reel in used_reels if reel.weight_kg) or 0.0

        return render_template(
            'active_stock.html', 
            full_reels=full_reels, 
            used_reels=used_reels,
            total_full_count=total_full_count,
            total_used_count=total_used_count,
            total_full_weight=total_full_weight,
            total_used_weight=total_used_weight
        )
    except Exception as e:
        print(f"--- [ERROR IN ACTIVE STOCK] --- : {str(e)}")
        return f"Backend Error: {str(e)}. Please check Terminal.", 500

@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    user_role = session.get('role', 'dataop1')
    if request.method == 'POST':
        try:
            reel_number = request.form.get('reel_number', '').strip()
            if Reel.query.filter_by(reel_number=reel_number).first():
                flash(f"Error: Reel Number '{reel_number}' already exists!", "danger")
                return redirect(url_for('add_stock'))
                
            new_reel = Reel(
                reel_number=reel_number,
                size_cm=request.form.get('size_cm', 0.0, type=float),
                weight_kg=request.form.get('weight_kg', 0.0, type=float),
                paper_name=request.form.get('paper_name', ''),
                status=request.form.get('status', 'Full Reel'), 
                store_location=request.form.get('store_location', 'Viscor Lanka'),
                gate_pass_number=request.form.get('gate_pass_number', ''),
                gsm=request.form.get('gsm', 0, type=int),
                reel_type=request.form.get('reel_type', 'Liner(T)'),
                supplier=request.form.get('supplier', 'N/A') or 'N/A'
            )
            db.session.add(new_reel)
            db.session.commit()
            
            db.session.add(ReelHistory(reel_id=new_reel.id, usage_details=f"Stock initialized in {new_reel.status}", action_type='INITIAL'))
            db.session.commit()
            
            flash(f"Reel {reel_number} saved successfully!", "success")
            return redirect(url_for('active_stock'))
        except Exception as e:
            db.session.rollback()
            flash(f"System Error: {str(e)}", "danger")
            
    return render_template('add_stock.html', user_role=user_role)

@app.route('/issue_reel/<int:id>', methods=['POST'])
def issue_reel(id):
    reel = Reel.query.get_or_404(id)
    doc_type = request.form.get('doc_type')
    doc_number = request.form.get('doc_number')
    send_to_viscor = request.form.get('send_to_viscor')

    if doc_type == 'SR': reel.sr_number = doc_number
    else: reel.gate_pass_number = doc_number

    if send_to_viscor == 'yes' and session.get('role') == 'dataop2':
        reel.status = 'Pending Viscor'
        db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Sent to Viscor Lanka via {doc_type}: {doc_number}", action_type='TRANSIT'))
        flash(f'Reel {reel.reel_number} sent to Viscor Lanka. Pending verification by DataOp1.', 'info')
    else:
        reel.status = 'Issued'
        db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Dispatched via {doc_type}: {doc_number}", action_type='ISSUE'))
        flash(f'Reel {reel.reel_number} dispatched successfully.', 'success')
        
    db.session.commit()
    return redirect(request.referrer or url_for('active_stock'))

@app.route('/viscor_issue')
def viscor_issue():
    reels = Reel.query.filter_by(status='Pending Viscor').all()
    return render_template('viscor_issue.html', reels=reels)

@app.route('/accept_viscor/<int:id>', methods=['POST'])
def accept_viscor(id):
    if session.get('role') != 'dataop1':
        flash('Unauthorized Action. Only DataOp1 can verify materials.', 'danger')
        return redirect(url_for('viscor_issue'))
        
    reel = Reel.query.get_or_404(id)
    reel.status = 'Full Reel' 
    reel.store_location = 'Viscor Lanka'
    db.session.add(ReelHistory(reel_id=reel.id, usage_details="Verified & Accepted by Viscor Lanka", action_type='ACCEPTED'))
    db.session.commit()
    flash(f'Reel {reel.reel_number} has been Verified & Accepted to Active Stock.', 'success')
    return redirect(url_for('viscor_issue'))

@app.route('/reject_viscor/<int:id>', methods=['POST'])
def reject_viscor(id):
    if session.get('role') != 'dataop1':
        flash('Unauthorized Action.', 'danger')
        return redirect(url_for('viscor_issue'))
        
    reel = Reel.query.get_or_404(id)
    reel.status = 'Full Reel' 
    reel.store_location = 'Packwell W 1' 
    db.session.add(ReelHistory(reel_id=reel.id, usage_details="Unaccepted & Returned by Viscor Lanka", action_type='REJECTED'))
    db.session.commit()
    flash(f'Reel {reel.reel_number} was Unaccepted and returned to Packwell.', 'warning')
    return redirect(url_for('viscor_issue'))

@app.route('/issue_damaged_reel/<int:id>', methods=['POST'])
def issue_damaged_reel(id):
    reel = Reel.query.get_or_404(id)
    doc_type = request.form.get('doc_type')
    doc_number = request.form.get('doc_number')
    approval_remark = request.form.get('approval_remark')

    reel.status = 'Issued'
    if doc_type == 'SR': reel.sr_number = doc_number
    else: reel.gate_pass_number = doc_number
    
    db.session.add(ReelHistory(
        reel_id=reel.id, 
        usage_details=f"Conditionally Issued via {doc_type}: {doc_number}. Approval: {approval_remark}", 
        action_type='COND. ISSUE'
    ))
    db.session.commit()
    flash(f'Damaged Reel {reel.reel_number} conditionally approved and moved to Issued Stock.', 'success')
    return redirect(url_for('issued_stock'))

@app.route('/issued_stock')
def issued_stock():
    return render_template('issued_stock.html', stocks=Reel.query.filter_by(status='Issued').all())

@app.route('/update_location/<int:id>', methods=['POST'])
def update_location(id):
    reel = Reel.query.get_or_404(id)
    reel.store_location = request.form.get('store_location')
    db.session.commit()
    flash('Location updated successfully.', 'success')
    return redirect(request.referrer)

# 🛠️ FIXED: weight_kg = 0.0 කිරීම ඉවත් කර ඇත. එවිට Finished එකේ බර පෙන්වයි.
@app.route('/finish_reel/<int:id>', methods=['POST'])
def finish_reel(id):
    reel = Reel.query.get_or_404(id)
    used_weight = reel.weight_kg or 0.0
    
    # රීල් එකේ අවසන් බර අමතක නොවීම සඳහා weight_kg අගය එලෙසම තබා status එක පමණක් මාරු කරයි.
    reel.status = 'Finished'
    
    db.session.add(ReelHistory(
        reel_id=reel.id, 
        usage_details="Marked 100% finished", 
        weight_used=used_weight, 
        action_type='FINISHED'
    ))
    db.session.commit()
    flash('Reel marked as completely finished.', 'success')
    return redirect(url_for('issued_stock'))

@app.route('/mark_damage_sell/<int:id>', methods=['POST'])
def mark_damage_sell(id):
    reel = Reel.query.get_or_404(id)
    status_type = request.form.get('status_type', 'Damaged')
    notes = request.form.get('notes', 'N/A')
    reel.status = status_type
    db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Status: {status_type}. Notes: {notes}", action_type=status_type.upper()))
    db.session.commit()
    flash(f"Reel successfully marked as {status_type}.", "warning")
    return redirect(url_for('active_stock'))

@app.route('/damage_reel/<int:id>', methods=['POST'])
def damage_reel(id):
    reel = Reel.query.get_or_404(id)
    damage_reason = request.form.get('damage_reason', 'No Reason')
    reel.status = 'Damaged'
    db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Marked as Damaged: {damage_reason}", action_type='DAMAGED'))
    db.session.commit()
    flash(f"Reel {reel.reel_number} marked as Damaged.", "danger")
    return redirect(url_for('active_stock'))

@app.route('/damage_sell_stock')
def damage_sell_stock():
    damaged_reels = Reel.query.filter_by(status='Damaged').all()
    sold_reels = Reel.query.filter_by(status='Sold').all()
    return render_template('damage_sell_stock.html', damaged_reels=damaged_reels, sold_reels=sold_reels)

@app.route('/sell_reel/<int:id>', methods=['POST'])
def sell_reel(id):
    reel = Reel.query.get_or_404(id)
    reel.status = 'Sold'
    db.session.add(ReelHistory(reel_id=reel.id, usage_details="Marked as Sold", action_type='SOLD'))
    db.session.commit()
    flash(f"Reel {reel.reel_number} marked as Sold.", "success")
    return redirect(url_for('active_stock'))

@app.route('/delete_reel/<int:id>', methods=['POST'])
def delete_reel(id):
    reel = Reel.query.get_or_404(id)
    db.session.delete(reel)
    db.session.commit()
    flash("Reel permanently deleted.", "success")
    return redirect(url_for('active_stock'))

@app.route('/process_return', methods=['POST'])
def process_return():
    reel_no = request.form.get('reel_no')
    returned_weight = request.form.get('returned_weight', 0.0, type=float)
    reel = Reel.query.filter_by(reel_number=reel_no).first_or_404()
    used_amount = (reel.weight_kg or 0.0) - returned_weight
    reel.weight_kg = returned_weight
    reel.status = 'Used Reel'
    db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Returned balance {returned_weight}kg", weight_used=max(0.0, used_amount), action_type='PARTIAL RETURN'))
    db.session.commit()
    flash('Partial return registered successfully.', 'info')
    return redirect(url_for('active_stock'))

@app.route('/finished_usage_stock')
def finished_usage_stock():
    finished_reels = Reel.query.filter_by(status='Finished').all()
    usage_logs = ReelHistory.query.join(Reel).filter(ReelHistory.action_type.in_(['PARTIAL RETURN', 'FINISHED'])).all()
    return render_template('finished_stock.html', 
                           finished_reels=finished_reels, 
                           usage_logs=usage_logs,
                           total_finished_weight=sum((r.weight_kg or 0.0) for r in finished_reels),
                           total_used_weight_log=sum((log.weight_used or 0.0) for log in usage_logs))

@app.route('/usage_logs')
def usage_logs():
    return render_template('usage_logs.html', logs=ReelHistory.query.order_by(ReelHistory.timestamp.desc()).all())

if __name__ == '__main__':
    app.run(debug=True)
