from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
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
    store_location = db.Column(db.String(100), default='Viscor Lanka')
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password:
            session['role'] = SmartRole(username)
            session['username'] = username
            flash(f"Logged in successfully as {username}", "success")
            return redirect(url_for('dashboard'))
        flash("Invalid Username or Password!", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('role', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    user_role = session.get('role')
    active_query = Reel.query.filter(Reel.status.in_(['Full Reel', 'Used Reel']))
    
    if user_role == 'dataop1':
        active_query = active_query.filter(Reel.store_location == 'Viscor Lanka')
        pending_viscor = Reel.query.filter_by(status='Pending Viscor').count()
        issued = Reel.query.filter_by(status='Issued', store_location='Viscor Lanka').count()
        finished = Reel.query.filter_by(status='Finished', store_location='Viscor Lanka').count()
        damage_sell_count = Reel.query.filter(Reel.status.in_(['Damaged', 'Sold']), Reel.store_location == 'Viscor Lanka').count()
    elif user_role == 'dataop2':
        active_query = active_query.filter(Reel.store_location.like('Packwell W%'))
        pending_viscor = Reel.query.filter(Reel.status.in_(['Pending Packwell Full', 'Pending Packwell Used']), Reel.store_location.like('Packwell W%')).count()
        issued = Reel.query.filter_by(status='Issued').filter(Reel.store_location.like('Packwell W%')).count()
        finished = Reel.query.filter_by(status='Finished').filter(Reel.store_location.like('Packwell W%')).count()
        damage_sell_count = Reel.query.filter(Reel.status.in_(['Damaged', 'Sold'])).filter(Reel.store_location.like('Packwell W%')).count()
    else:
        # For super1, super2, admin based on store logic restriction for dataop2 style or broad view
        if user_role in ['super1', 'super2']:
            active_query = active_query.filter(Reel.store_location.like('Packwell W%'))
            pending_viscor = Reel.query.filter(Reel.status.in_(['Pending Packwell Full', 'Pending Packwell Used']), Reel.store_location.like('Packwell W%')).count()
            issued = Reel.query.filter_by(status='Issued').filter(Reel.store_location.like('Packwell W%')).count()
            finished = Reel.query.filter_by(status='Finished').filter(Reel.store_location.like('Packwell W%')).count()
            damage_sell_count = Reel.query.filter(Reel.status.in_(['Damaged', 'Sold'])).filter(Reel.store_location.like('Packwell W%')).count()
        else:
            pending_viscor = Reel.query.filter(Reel.status.in_(['Pending Viscor', 'Pending Packwell Full', 'Pending Packwell Used'])).count()
            issued = Reel.query.filter_by(status='Issued').count()
            finished = Reel.query.filter_by(status='Finished').count()
            damage_sell_count = Reel.query.filter(Reel.status.in_(['Damaged', 'Sold'])).count()

    active_reels = active_query.all()
    active_count = len(active_reels)
    active_weight = sum((r.weight_kg or 0.0) for r in active_reels)
    
    return render_template('dashboard.html', active_count=active_count, active_weight=active_weight,
                           pending_viscor_count=pending_viscor, issued=issued, finished=finished, damage_sell_count=damage_sell_count)

@app.route('/active_stock')
def active_stock():
    user_role = session.get('role')
    selected_loc = request.args.get('location', '')

    full_query = Reel.query.filter_by(status='Full Reel')
    used_query = Reel.query.filter_by(status='Used Reel')

    if user_role == 'dataop1':
        full_query = full_query.filter(Reel.store_location == 'Viscor Lanka')
        used_query = used_query.filter(Reel.store_location == 'Viscor Lanka')
    elif user_role in ['dataop2', 'super1', 'super2']:
        full_query = full_query.filter(Reel.store_location.like('Packwell W%'))
        used_query = used_query.filter(Reel.store_location.like('Packwell W%'))
    elif user_role == 'admin' and selected_loc:
        full_query = full_query.filter(Reel.store_location == selected_loc)
        used_query = used_query.filter(Reel.store_location == selected_loc)

    full_reels = full_query.all()
    used_reels = used_query.all()

    return render_template(
        'active_stock.html', 
        full_reels=full_reels, 
        used_reels=used_reels,
        total_full_count=len(full_reels),
        total_used_count=len(used_reels),
        user_role=user_role,
        selected_loc=selected_loc
    )

@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    user_role = session.get('role')
    if user_role in ['super1', 'super2']:
        flash("Unauthorized Action: Super users cannot add stock.", "danger")
        return redirect(url_for('dashboard'))

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
                gsm=request.form.get('gsm', 0, type=int),
                reel_type=request.form.get('reel_type', 'Liner(T)'),
                supplier='N/A'
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

@app.route('/edit_active_reel/<int:id>', methods=['POST'])
def edit_active_reel(id):
    if session.get('role') in ['super1', 'super2']:
        flash("Unauthorized Action.", "danger")
        return redirect(url_for('active_stock'))
    reel = Reel.query.get_or_404(id)
    reel.reel_number = request.form.get('reel_number', reel.reel_number)
    reel.paper_name = request.form.get('paper_name', reel.paper_name)
    reel.reel_type = request.form.get('reel_type', reel.reel_type)
    reel.size_cm = request.form.get('size_cm', reel.size_cm, type=float)
    reel.gsm = request.form.get('gsm', reel.gsm, type=int)
    reel.weight_kg = request.form.get('weight_kg', reel.weight_kg, type=float)
    
    db.session.add(ReelHistory(reel_id=reel.id, usage_details="Reel details manually edited", action_type='EDIT'))
    db.session.commit()
    flash(f"Reel {reel.reel_number} updated successfully.", "success")
    return redirect(url_for('active_stock'))

@app.route('/issue_reel/<int:id>', methods=['POST'])
def issue_reel(id):
    if session.get('role') in ['super1', 'super2']:
        flash("Unauthorized Action.", "danger")
        return redirect(url_for('active_stock'))
    reel = Reel.query.get_or_404(id)
    doc_type = request.form.get('doc_type')
    doc_number = request.form.get('doc_number')
    send_to_viscor = request.form.get('send_to_viscor')
    return_to_packwell = request.form.get('return_to_packwell')

    if doc_type == 'SR': reel.sr_number = doc_number
    else: reel.gate_pass_number = doc_number

    if return_to_packwell == 'yes':
        reel.status = 'Pending Packwell Full' if reel.status == 'Full Reel' else 'Pending Packwell Used'
        db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Returned back to Packwell via {doc_type}: {doc_number}", action_type='RETURN_TRANSIT'))
        flash(f'Reel {reel.reel_number} returned to Packwell. Pending dataop2 acceptance.', 'warning')
    elif send_to_viscor == 'yes':
        reel.status = 'Pending Viscor'
        db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Sent to Viscor Lanka via {doc_type}: {doc_number}", action_type='TRANSIT'))
        flash(f'Reel {reel.reel_number} sent to Viscor Lanka. Pending verification.', 'info')
    else:
        reel.status = 'Issued'
        db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Dispatched via {doc_type}: {doc_number}", action_type='ISSUE'))
        flash(f'Reel {reel.reel_number} dispatched successfully.', 'success')
        
    db.session.commit()
    return redirect(request.referrer or url_for('active_stock'))

@app.route('/viscor_issue')
def viscor_issue():
    user_role = session.get('role')
    if user_role == 'dataop1':
        viscor_reels = Reel.query.filter_by(status='Pending Viscor').all()
        packwell_reels = []
    elif user_role in ['dataop2', 'super1', 'super2']:
        viscor_reels = []
        packwell_reels = Reel.query.filter(Reel.status.in_(['Pending Packwell Full', 'Pending Packwell Used']), Reel.store_location.like('Packwell W%')).all()
    else:
        viscor_reels = Reel.query.filter_by(status='Pending Viscor').all()
        packwell_reels = Reel.query.filter(Reel.status.in_(['Pending Packwell Full', 'Pending Packwell Used'])).all()
        
    return render_template('viscor_issue.html', reels=viscor_reels, packwell_reels=packwell_reels, user_role=user_role)

@app.route('/accept_viscor/<int:id>', methods=['POST'])
def accept_viscor(id):
    if session.get('role') in ['super1', 'super2']:
        flash('Unauthorized Action.', 'danger')
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
    if session.get('role') in ['super1', 'super2']:
        flash('Unauthorized Action.', 'danger')
        return redirect(url_for('viscor_issue'))
    reel = Reel.query.get_or_404(id)
    reel.status = 'Full Reel' 
    reel.store_location = 'Packwell W 1' 
    db.session.add(ReelHistory(reel_id=reel.id, usage_details="Unaccepted & Returned to Packwell", action_type='REJECTED'))
    db.session.commit()
    flash(f'Reel {reel.reel_number} was Unaccepted and returned to Packwell.', 'warning')
    return redirect(url_for('viscor_issue'))

@app.route('/accept_packwell/<int:id>', methods=['POST'])
def accept_packwell(id):
    if session.get('role') in ['super1', 'super2']:
        flash('Unauthorized Action.', 'danger')
        return redirect(url_for('viscor_issue'))
    reel = Reel.query.get_or_404(id)
    selected_location = request.form.get('store_location')
    stock_type = request.form.get('stock_type', 'Full Reel')
    
    reel.status = stock_type
    reel.store_location = selected_location
    
    db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Accepted back to Packwell at {selected_location} as {stock_type}", action_type='RETURN_ACCEPTED'))
    db.session.commit()
    flash(f'Reel {reel.reel_number} successfully accepted into {selected_location} active stock.', 'success')
    return redirect(url_for('viscor_issue'))

@app.route('/reject_packwell/<int:id>', methods=['POST'])
def reject_packwell(id):
    if session.get('role') in ['super1', 'super2']:
        flash('Unauthorized Action.', 'danger')
        return redirect(url_for('viscor_issue'))
    reel = Reel.query.get_or_404(id)
    reel.status = 'Full Reel' if 'Full' in reel.status else 'Used Reel'
    reel.store_location = 'Viscor Lanka'
    db.session.add(ReelHistory(reel_id=reel.id, usage_details="Return rejected by Packwell, sent back to Viscor Lanka", action_type='RETURN_REJECTED'))
    db.session.commit()
    flash(f'Returned Reel {reel.reel_number} was rejected and sent back to Viscor Lanka.', 'warning')
    return redirect(url_for('viscor_issue'))

@app.route('/issue_damaged_reel/<int:id>', methods=['POST'])
def issue_damaged_reel(id):
    if session.get('role') in ['super1', 'super2']:
        flash('Unauthorized Action.', 'danger')
        return redirect(url_for('issued_stock'))
    reel = Reel.query.get_or_404(id)
    doc_type = request.form.get('doc_type')
    doc_number = request.form.get('doc_number')
    approval_remark = request.form.get('approval_remark')

    reel.status = 'Issued'
    if doc_type == 'SR': reel.sr_number = doc_number
    else: reel.gate_pass_number = doc_number
    
    db.session.add(ReelHistory(
        reel_id=reel.id, 
        usage_details=f"Conditionally Issued via {doc_type}: {doc_number}. Remarks: {approval_remark}", 
        action_type='COND_ISSUE'
    ))
    db.session.commit()
    flash(f'Damaged Reel {reel.reel_number} conditionally approved and logged.', 'success')
    return redirect(url_for('issued_stock'))

@app.route('/issued_stock')
def issued_stock():
    user_role = session.get('role')
    query = Reel.query.filter_by(status='Issued')
    
    if user_role == 'dataop1':
        query = query.filter(Reel.store_location == 'Viscor Lanka')
    elif user_role in ['dataop2', 'super1', 'super2']:
        query = query.filter(Reel.store_location.like('Packwell W%'))
        
    return render_template('issued_stock.html', stocks=query.all())

@app.route('/finish_reel/<int:id>', methods=['POST'])
def finish_reel(id):
    if session.get('role') in ['super1', 'super2']:
        flash('Unauthorized Action.', 'danger')
        return redirect(url_for('issued_stock'))
    reel = Reel.query.get_or_404(id)
    used_weight = reel.weight_kg or 0.0
    reel.status = 'Finished'
    db.session.add(ReelHistory(reel_id=reel.id, usage_details="Marked 100% finished", weight_used=used_weight, action_type='FINISHED'))
    db.session.commit()
    flash('Reel marked as completely finished.', 'success')
    return redirect(url_for('issued_stock'))

@app.route('/damage_sell_stock')
def damage_sell_stock():
    user_role = session.get('role')
    damaged_query = Reel.query.filter_by(status='Damaged')
    sold_query = Reel.query.filter_by(status='Sold')
    cond_query = ReelHistory.query.filter_by(action_type='COND_ISSUE')

    if user_role == 'dataop1':
        damaged_query = damaged_query.filter(Reel.store_location == 'Viscor Lanka')
        sold_query = sold_query.filter(Reel.store_location == 'Viscor Lanka')
        cond_query = cond_query.join(Reel).filter(Reel.store_location == 'Viscor Lanka')
    elif user_role in ['dataop2', 'super1', 'super2']:
        damaged_query = damaged_query.filter(Reel.store_location.like('Packwell W%'))
        sold_query = sold_query.filter(Reel.store_location.like('Packwell W%'))
        cond_query = cond_query.join(Reel).filter(Reel.store_location.like('Packwell W%'))

    damaged_reels = damaged_query.all()
    sold_reels = sold_query.all()
    cond_logs = cond_query.order_by(ReelHistory.timestamp.desc()).all()
    
    return render_template('damage_sell_stock.html', damaged_reels=damaged_reels, sold_reels=sold_reels, cond_logs=cond_logs)

@app.route('/mark_damage_sell/<int:id>', methods=['POST'])
def mark_damage_sell(id):
    if session.get('role') in ['super1', 'super2']:
        flash('Unauthorized Action.', 'danger')
        return redirect(url_for('active_stock'))
    reel = Reel.query.get_or_404(id)
    status_type = request.form.get('status_type', 'Damaged')
    notes = request.form.get('notes', 'N/A')
    reel.status = status_type
    db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Status: {status_type}. Notes: {notes}", action_type=status_type.upper()))
    db.session.commit()
    flash(f"Reel successfully marked as {status_type}.", "warning")
    return redirect(url_for('active_stock'))

@app.route('/process_return', methods=['POST'])
def process_return():
    if session.get('role') in ['super1', 'super2']:
        flash('Unauthorized Action.', 'danger')
        return redirect(url_for('active_stock'))
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
    user_role = session.get('role')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    finished_query = Reel.query.filter_by(status='Finished')
    logs_query = ReelHistory.query.join(Reel).filter(ReelHistory.action_type.in_(['PARTIAL RETURN', 'FINISHED']))

    if user_role == 'dataop1':
        finished_query = finished_query.filter(Reel.store_location == 'Viscor Lanka')
        logs_query = logs_query.filter(Reel.store_location == 'Viscor Lanka')
    elif user_role in ['dataop2', 'super1', 'super2']:
        finished_query = finished_query.filter(Reel.store_location.like('Packwell W%'))
        logs_query = logs_query.filter(Reel.store_location.like('Packwell W%'))

    if start_date and end_date:
        try:
            s_date = datetime.strptime(start_date, '%Y-%m-%d')
            e_date = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            finished_query = finished_query.filter(Reel.updated_at >= s_date, Reel.updated_at <= e_date)
            logs_query = logs_query.filter(ReelHistory.timestamp >= s_date, ReelHistory.timestamp <= e_date)
        except ValueError:
            pass

    finished_reels = finished_query.all()
    usage_logs = logs_query.all()

    return render_template('finished_stock.html', 
                           finished_reels=finished_reels, 
                           usage_logs=usage_logs,
                           total_finished_weight=sum((r.weight_kg or 0.0) for r in finished_reels),
                           total_used_weight_log=sum((log.weight_used or 0.0) for log in usage_logs),
                           start_date=start_date or '',
                           end_date=end_date or '')

@app.route('/update_finished_sr/<int:id>', methods=['POST'])
def update_finished_sr(id):
    if session.get('role') in ['super1', 'super2']:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('finished_usage_stock'))
        
    reel = Reel.query.get_or_404(id)
    new_sr = request.form.get('sr_number', '').strip()
    reel.sr_number = new_sr
    
    db.session.add(ReelHistory(reel_id=reel.id, usage_details=f"Finished SR Number updated to {new_sr}", action_type='SR_UPDATE'))
    db.session.commit()
    flash(f"SR Number for Finished Reel {reel.reel_number} updated successfully.", "success")
    return redirect(url_for('finished_usage_stock'))

if __name__ == '__main__':
    app.run(debug=True)
