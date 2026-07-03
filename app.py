from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta
import pytz
import random
import re
import json

app = Flask(__name__)
app.secret_key = 'viscor_packwell_ultimate_secure_key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', ping_timeout=60, ping_interval=25)

# DATABASE CONFIGURATION
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://avnadmin:AVNS_gHRTw4Hzio_XlhXcm7d@mysql-3e9936af-viscorquality-0270.g.aivencloud.com:28643/defaultdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {"ssl": {}},
    "pool_size": 15,
    "max_overflow": 25,
    "pool_timeout": 30,
    "pool_recycle": 1800
}
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
    reel_number = db.Column(db.String(100), unique=True, nullable=False, index=True)
    size_cm = db.Column(db.Float, nullable=False, index=True)
    gsm = db.Column(db.Integer, nullable=False)
    material_name = db.Column(db.String(100), nullable=False)
    reel_type = db.Column(db.String(100), nullable=True) 
    weight_kg = db.Column(db.Float, nullable=False)
    current_weight = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Full', index=True)  
    store_location = db.Column(db.String(100), nullable=False, index=True)
    supplier_name = db.Column(db.String(100), nullable=True)
    received_date = db.Column(db.Date, nullable=False)
    sr_request_id = db.Column(db.Integer, db.ForeignKey('sr_request.id'), nullable=True)

class SRRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sr_number = db.Column(db.String(100), unique=True, nullable=True, index=True)
    po_number = db.Column(db.String(100), nullable=False, index=True)
    reel_size = db.Column(db.Float, nullable=False)
    gsm = db.Column(db.Integer, nullable=False)
    material_name = db.Column(db.String(100), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    calculated_weight = db.Column(db.Float, nullable=False)
    board_width = db.Column(db.Float, nullable=True)
    board_length = db.Column(db.Float, nullable=True)
    cartoon_amount = db.Column(db.Integer, default=1)
    component_type = db.Column(db.String(50), nullable=True)
    flute_type = db.Column(db.String(10), nullable=True)
    excess_weight = db.Column(db.Float, default=0.0)
    total_weight = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending', index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    reels = db.relationship('Reel', backref='associated_sr', lazy=True)
    warehouse = db.Column(db.String(100), nullable=True)
    
class ReelHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reel.id'), nullable=False, index=True)
    usage_type = db.Column(db.String(100), nullable=False, index=True)
    weight_before = db.Column(db.Float, nullable=False)
    weight_after = db.Column(db.Float, nullable=False)
    doc_number = db.Column(db.String(100), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    reel = db.relationship('Reel', backref=db.backref('history', lazy=True))

class CustomerProduct(db.Model):
    __tablename__ = 'customer_product'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.String(50), nullable=False, index=True)
    customer_name = db.Column(db.String(150), nullable=False)
    customer_address = db.Column(db.Text, nullable=True)
    product_code = db.Column(db.String(50), nullable=False, index=True)
    product_name = db.Column(db.String(150), nullable=False)
    cartoon_size = db.Column(db.String(50), nullable=False) 
    position = db.Column(db.String(20), nullable=False) 
    flute = db.Column(db.String(20), nullable=False)
    ply = db.Column(db.Integer, nullable=False) 

class ProgrammePlan(db.Model):
    __tablename__ = 'programme_plan'
    id = db.Column(db.Integer, primary_key=True)
    po_no = db.Column(db.String(50), nullable=False, index=True)
    customer_id = db.Column(db.String(50), nullable=False)
    product_code = db.Column(db.String(50), nullable=False)
    selected_reel_size = db.Column(db.Float, nullable=False)
    selected_ups = db.Column(db.Integer, nullable=False)
    materials_json = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='Draft') 
    created_by = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))

with app.app_context():
    db.create_all()
    try:
        db.session.execute(text("ALTER TABLE programme_plan ADD COLUMN materials_json TEXT;"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %I:%M %p'):
    if value is None: return ""
    if value.tzinfo is None:
        value = pytz.utc.localize(value).astimezone(colombo_tz)
    else:
        value = value.astimezone(colombo_tz)
    return value.strftime(format)

def get_user_role():
    return SmartRole(session.get('role', ''))

def get_sr_prefix(role):
    if role in ['dataop1', 'programmer1', 'super1']:
        return "SRVL"
    elif role in ['dataop2', 'programmer2', 'super2']:
        return "SRPL"
    return "SR"

def apply_location_filter(query, model):
    role = session.get('role', '')
    if role in ['dataop2', 'super2', 'programmer2']:
        return query.filter(model.store_location.like('Packwell%'))
    elif role == 'super1':
        return query.filter(model.store_location == 'Viscor Lanka')
    return query

def safe_float(val, default=0.0):
    try:
        if val is None or str(val).strip() == '': return float(default)
        return float(val)
    except (ValueError, TypeError): return float(default)

def safe_int(val, default=0):
    try:
        if val is None or str(val).strip() == '': return int(default)
        return int(float(val))
    except (ValueError, TypeError): return int(default)

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        users = {
            "admin": ("admin@0123", "admin"),
            "dataop1": ("viscor@2468", "dataop1"),
            "dataop2": ("packwell@8642", "dataop2"),
            "super1": ("viscor@1357", "super1"),
            "super2": ("packwell@7531", "super2"),
            "programmer1": ("viscor@1235", "programmer1"),
            "programmer2": ("packwell@3457", "programmer2"),
            "viewer": ("view@123", "viewer")
        }
        
        if username in users and users[username][0] == password:
            session['username'] = username
            session['role'] = users[username][1]
            flash(f"👋 Welcome back, {username}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("❌ Invalid Username or Password.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("🔒 Logged out successfully.", "info")
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'role' not in session: return redirect(url_for('login'))
    
    stats_query = db.session.query(
        func.count(Reel.id),
        func.sum(Reel.current_weight)
    ).filter(Reel.status.in_(['Full', 'Used', 'SR_Requested']))
    
    stats_query = apply_location_filter(stats_query, Reel)
    active_count, active_weight = stats_query.first()
    
    active_count = active_count or 0
    active_weight = active_weight or 0.0
    
    base_query = apply_location_filter(Reel.query, Reel)
    pending_viscor_count = base_query.filter(Reel.status.in_(['Pending_Verify', 'Pending_Return'])).count()
    issued_count = base_query.filter_by(status='Issued').count()
    finished_count = base_query.filter_by(status='Finished').count()
    damage_sell_count = base_query.filter(Reel.status.in_(['Damaged', 'Sold'])).count()
    
    return render_template('dashboard.html', 
                           active_count=active_count, 
                           active_weight=round(active_weight, 2),
                           pending_viscor_count=pending_viscor_count,
                           issued=issued_count,
                           finished=finished_count,
                           damage_sell_count=damage_sell_count, 
                           user_role=get_user_role())

@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    user_role = get_user_role()
    if user_role in ['programmer1', 'programmer2', 'super1', 'super2', 'viewer']:
        flash("❌ Access Denied: Unauthorized tab.", "danger")
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        try:
            reel_num = request.form.get('reel_number', '').strip()
            if Reel.query.filter_by(reel_number=reel_num).first():
                flash(f"❌ Reel Number '{reel_num}' already exists!", "danger")
                return redirect(url_for('add_stock'))

            date_str = request.form.get('received_date')
            rcv_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now(colombo_tz).date()

            status_input = request.form.get('status')
            reel_status = 'Used' if status_input == 'Used Reel' else 'Full'

            new_reel = Reel(
                reel_number=reel_num, size_cm=safe_float(request.form.get('size_cm')),
                gsm=safe_int(request.form.get('gsm')), material_name=request.form.get('material_name', ''),
                reel_type=request.form.get('reel_type', ''), weight_kg=safe_float(request.form.get('weight_kg')),
                current_weight=safe_float(request.form.get('weight_kg')), status=reel_status, 
                store_location=request.form.get('store_location', ''), supplier_name=request.form.get('supplier_name', ''),
                received_date=rcv_date
            )
            db.session.add(new_reel)
            db.session.commit()
            flash("✨ Stock Entry Saved Successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving entry: {str(e)}", "danger")
            
    return render_template('add_stock.html', user_role=user_role)

@app.route('/active_stock')
def active_stock():
    if 'role' not in session: return redirect(url_for('login'))
    user_role = get_user_role()
    
    base_query = apply_location_filter(Reel.query, Reel)
    full_reels = base_query.filter_by(status='Full').order_by(Reel.received_date.asc()).all()
    used_reels = base_query.filter_by(status='Used').order_by(Reel.received_date.asc()).all()
    sr_requested_reels = base_query.filter_by(status='SR_Requested').order_by(Reel.received_date.asc()).all()
    
    return render_template('active_stock.html', full_reels=full_reels, used_reels=used_reels, sr_requested_reels=sr_requested_reels, user_role=user_role)

@app.route('/edit_active_reel/<int:id>', methods=['POST'])
def edit_active_reel(id):
    user_role = get_user_role()
    if user_role not in ['dataop1', 'dataop2']:
        flash("❌ Action Not Allowed. Only Data Operators can edit stock.", "danger")
        return redirect(url_for('active_stock'))
        
    try:
        reel = Reel.query.get_or_404(id)
        reel.size_cm = safe_float(request.form.get('size_cm'), reel.size_cm)
        reel.gsm = safe_int(request.form.get('gsm'), reel.gsm)
        new_weight = safe_float(request.form.get('current_weight'), reel.current_weight)
        
        reel.current_weight = new_weight
        if reel.status == 'Full':
            reel.weight_kg = new_weight
            
        db.session.commit()
        flash(f"✅ Reel {reel.reel_number} Updated Successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Update Error: {str(e)}", "danger")
    return redirect(url_for('active_stock'))

@app.route('/update_location/<int:id>', methods=['POST'])
def update_location(id):
    if get_user_role() in ['super1', 'super2', 'viewer']:
        flash("❌ Action Not Allowed.", "danger")
        return redirect(url_for('active_stock'))
        
    reel = Reel.query.get_or_404(id)
    new_location = request.form.get('location')
    if new_location:
        reel.store_location = new_location
        db.session.commit()
        flash(f"✅ Reel {reel.reel_number} Location Updated Successfully!", "success")
    else:
        flash("❌ Location update failed. Invalid data.", "danger")
    return redirect(url_for('active_stock'))

@app.route('/mark_damage_sell/<int:id>', methods=['POST'])
def mark_damage_sell(id):
    if get_user_role() in ['super1', 'super2', 'viewer', 'programmer1', 'programmer2']:
        flash("❌ Action Not Allowed.", "danger")
        return redirect(url_for('active_stock'))
        
    reel = Reel.query.get_or_404(id)
    action_type = request.form.get('action_type')
    remarks = request.form.get('remarks', '')
    
    if action_type == 'Finished':  
        old_w = reel.current_weight
        reel.status = 'Finished'
        reel.current_weight = 0.0
        db.session.add(ReelHistory(
            reel_id=reel.id, usage_type='Finished Usage', weight_before=old_w, weight_after=0.0, remarks=remarks
        ))
        flash(f"✅ Reel {reel.reel_number} marked as Fully Finished!", "success")
    else:
        reel.status = action_type
        flash(f"✅ Reel {reel.reel_number} marked as {action_type}!", "success")

    db.session.commit()
    return redirect(url_for('active_stock'))

@app.route('/mark_finished/<int:id>', methods=['POST'])
def mark_finished(id):
    if get_user_role() == 'viewer':
        flash("❌ Action Not Allowed.", "danger")
        return redirect(url_for('finished_usage_stock'))
        
    reel = Reel.query.get_or_404(id)
    old_weight = reel.current_weight
    reel.status = 'Finished' 
    reel.current_weight = 0.0 
    
    db.session.add(ReelHistory(
        reel_id=reel.id, usage_type='Finished Usage', weight_before=old_weight, weight_after=0.0,
        remarks=f"Reel {reel.reel_number} fully consumed."
    ))
    db.session.commit()
    flash(f"✅ Reel {reel.reel_number} marked as Finished!", "success")
    return redirect(url_for('finished_usage_stock'))
    
@app.route('/sr_request', methods=['GET', 'POST'])
def sr_request():
    user_role = get_user_role()
    if 'role' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        if user_role in ['super1', 'super2', 'dataop1', 'dataop2', 'viewer']:
            flash("❌ Action Not Allowed for your role.", "danger")
            return redirect(url_for('sr_request'))
            
        try:
            po_number = request.form.get('po_number', '').strip()
            r_size = safe_float(request.form.get('reel_size'))
            b_width = safe_float(request.form.get('board_width'))
            b_length = safe_float(request.form.get('board_length'))
            cartoon_amt = safe_float(request.form.get('cartoon_amount'), 1.0)
            if cartoon_amt <= 0: cartoon_amt = 1.0
            qty = safe_int(request.form.get('qty'))
            excess_w_total = safe_float(request.form.get('excess_weight'))
            
            valid_materials = []
            for i in range(1, 6):
                m_name = request.form.get(f'material_name_{i}', '').strip()
                m_gsm_str = request.form.get(f'gsm_{i}', '').strip()
                
                if m_name and m_gsm_str:
                    valid_materials.append({
                        'name': m_name, 'gsm': safe_int(m_gsm_str),
                        'comp_type': request.form.get(f'component_type_{i}', ''),
                        'flute': request.form.get(f'flute_type_{i}', '')
                    })

            if not valid_materials:
                flash("❌ Please enter at least one valid material component.", "danger")
                return redirect(url_for('sr_request'))

            prefix = get_sr_prefix(user_role)
            base_sr_num = f"{prefix}-{datetime.now(colombo_tz).strftime('%Y%m%d%H%M')}-{random.randint(10,99)}"
            excess_per_comp = excess_w_total / len(valid_materials)

            for idx, mat in enumerate(valid_materials):
                calc_weight = ((b_width * b_length) * (mat['gsm'] / 1000.0)) / cartoon_amt * qty
                if mat['comp_type'] == 'Corru':
                    calc_weight = calc_weight * 1.5

                tot_weight = calc_weight + excess_per_comp
                comp_sr_num = base_sr_num if len(valid_materials) == 1 else f"{base_sr_num}-L{idx+1}"

                new_sr = SRRequest(
                    sr_number=comp_sr_num, po_number=po_number, reel_size=r_size, cartoon_amount=cartoon_amt,
                    gsm=mat['gsm'], material_name=mat['name'], qty=qty, calculated_weight=round(calc_weight, 2),
                    board_width=b_width, board_length=b_length, component_type=mat['comp_type'], flute_type=mat['flute'],
                    excess_weight=round(excess_per_comp, 2), total_weight=round(tot_weight, 2)
                )
                db.session.add(new_sr)

            db.session.commit()
            flash(f"📊 SR Request Logged Successfully! Base SR Number: {base_sr_num}", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error logging request: {str(e)}", "danger")
            
    if user_role in ['dataop2', 'super2', 'programmer2']:
        all_requests = SRRequest.query.filter(SRRequest.sr_number.like('SRPL%')).order_by(SRRequest.created_at.desc()).all()
    else:
        all_requests = SRRequest.query.order_by(SRRequest.created_at.desc()).all()
        
    grouped_requests = {}
    for r in all_requests:
        if r.status in ['Pending', 'Approved']:
            size = r.reel_size
            if size not in grouped_requests:
                grouped_requests[size] = { 'po_list': set(), 'groups': {} }
            grouped_requests[size]['po_list'].add(r.po_number)
            
            group_key = f"{r.material_name}_{r.gsm}"
            if group_key not in grouped_requests[size]['groups']:
                grouped_requests[size]['groups'][group_key] = {
                    'material_name': r.material_name, 'gsm': r.gsm, 'total_mat_srs': 0, 'comp_groups': {}   
                }
                
            flute_str = str(r.flute_type).strip() if r.flute_type else ""
            comp_type_str = str(r.component_type).strip() if r.component_type else "Unknown"
            comp_key = f"{comp_type_str}_{flute_str}"

            if comp_key not in grouped_requests[size]['groups'][group_key]['comp_groups']:
                grouped_requests[size]['groups'][group_key]['comp_groups'][comp_key] = {
                    'component_type': r.component_type, 'flute_type': r.flute_type, 'total_weight': 0.0, 'srs': []
                }
                
            grouped_requests[size]['groups'][group_key]['comp_groups'][comp_key]['total_weight'] += r.total_weight
            grouped_requests[size]['groups'][group_key]['comp_groups'][comp_key]['srs'].append(r)
            grouped_requests[size]['groups'][group_key]['total_mat_srs'] += 1

    return render_template('sr_request.html', all_requests=all_requests, grouped_requests=grouped_requests, user_role=user_role)

@app.route('/edit_sr/<int:id>', methods=['POST'])
def edit_sr(id):
    user_role = get_user_role()
    if user_role not in ['programmer1', 'programmer2', 'admin']:
        flash("❌ Unauthorized Action.", "danger")
        return redirect(url_for('sr_request'))
        
    try:
        sr = SRRequest.query.get_or_404(id)
        b_width = safe_float(request.form.get('board_width'), sr.board_width)
        b_length = safe_float(request.form.get('board_length'), sr.board_length)
        gsm = safe_int(request.form.get('gsm'), sr.gsm)
        qty = safe_int(request.form.get('qty'), sr.qty)
        comp_type = request.form.get('component_type', sr.component_type)
        excess_w = safe_float(request.form.get('excess_weight'), sr.excess_weight)
        cartoon_amt = safe_float(request.form.get('cartoon_amount'), sr.cartoon_amount)
        if cartoon_amt <= 0: cartoon_amt = 1.0
            
        calc_weight = ((b_width * b_length) * (gsm / 1000.0)) / cartoon_amt * qty
        if comp_type == 'Corru': calc_weight = calc_weight * 1.5
            
        sr.board_width = b_width
        sr.board_length = b_length
        sr.gsm = gsm
        sr.qty = qty
        sr.cartoon_amount = cartoon_amt
        sr.component_type = comp_type
        sr.excess_weight = excess_w
        sr.calculated_weight = round(calc_weight, 2)
        sr.total_weight = round(calc_weight + excess_w, 2)
        
        db.session.commit()
        flash(f"✅ SR Request {sr.sr_number} Edited Successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error Editing SR: {str(e)}", "danger")
    return redirect(url_for('sr_request'))

@app.route('/approve_sr/<int:id>', methods=['POST'])
def approve_sr(id):
    user_role = get_user_role()
    if user_role in ['programmer1', 'programmer2', 'dataop1', 'dataop2', 'viewer']:
        flash("❌ Unauthorized Action.", "danger")
        return redirect(url_for('sr_request'))
    sr = SRRequest.query.get_or_404(id)
    if sr.status == 'Pending':
        sr.status = 'Approved'
        db.session.commit()
        flash(f"✅ SR Request for PO {sr.po_number} has been Approved!", "success")
    return redirect(url_for('sr_request'))

@app.route('/proceed_sr_batch/<int:sr_id>', methods=['POST'])
def proceed_sr_batch(sr_id):
    if get_user_role() == 'viewer':
        flash("❌ Action Not Allowed.", "danger")
        return redirect(url_for('sr_request'))
        
    sr = SRRequest.query.get_or_404(sr_id)
    total_needed = sr.total_weight
    current_allocated = 0.0
    allocated_reels = []
    
    full_reels = Reel.query.filter(
        Reel.size_cm == sr.reel_size, Reel.material_name == sr.material_name, Reel.gsm == sr.gsm, Reel.status == 'Full'
    ).order_by(Reel.received_date.asc()).all()
    
    for reel in full_reels:
        if current_allocated < total_needed:
            allocated_reels.append(reel)
            current_allocated += reel.current_weight
        else: break
            
    if current_allocated < total_needed:
        used_reels = Reel.query.filter(
            Reel.size_cm == sr.reel_size, Reel.material_name == sr.material_name, Reel.gsm == sr.gsm, Reel.status == 'Used'
        ).order_by(Reel.received_date.asc()).all()
        
        for reel in used_reels:
            if current_allocated < total_needed:
                allocated_reels.append(reel)
                current_allocated += reel.current_weight
            else: break
                
    if current_allocated >= total_needed:
        for reel in allocated_reels:
            old_weight = reel.current_weight
            reel.status = 'Issued'
            reel.sr_request_id = sr.id
            
            db.session.add(ReelHistory(
                reel_id=reel.id, usage_type='Issued to Production', weight_before=old_weight,
                weight_after=0.0, doc_number=sr.sr_number, remarks='Auto-Dispatched via SR Matrix Proceed'
            ))
        sr.status = 'Processed'
        db.session.commit()
        flash("🚀 Batch Processing Completed! Reels successfully Issued to the factory floor.", "success")
    else:
        db.session.rollback()
        flash(f"❌ Not enough stock to satisfy this request. (Required: {total_needed} kg | Available: {current_allocated} kg)", "danger")
    return redirect(url_for('sr_request'))

@app.route('/issue_reel_direct/<int:id>', methods=['POST'])
def issue_reel_direct(id):
    user_role = get_user_role()
    if user_role in ['super1', 'super2', 'viewer']:
        flash("❌ Access Denied.", "danger")
        return redirect(url_for('active_stock'))
        
    reel = Reel.query.get_or_404(id)
    if reel.status == 'SR_Requested':
        sr_num = reel.associated_sr.sr_number if reel.associated_sr else 'N/A'
        old_weight = reel.current_weight
        reel.status = 'Issued'
        
        db.session.add(ReelHistory(
            reel_id=reel.id, usage_type='Issued to Production', weight_before=old_weight,
            weight_after=0.0, doc_number=sr_num, remarks='Directly Issued from SR Request'
        ))
        db.session.commit()
        flash(f"✅ Reel {reel.reel_number} successfully Issued!", "success")
    return redirect(url_for('active_stock'))

@app.route('/issue_reel/<int:id>', methods=['POST'])
def issue_reel(id):
    user_role = get_user_role()
    if user_role in ['programmer1', 'programmer2', 'super1', 'super2', 'viewer']:
        flash("❌ Access Denied.", "danger")
        return redirect(url_for('active_stock'))
        
    reel = Reel.query.get_or_404(id)
    doc_num = request.form.get('doc_number', '').strip()
    remarks = request.form.get('remarks', '').strip()
    
    send_to_viscor = request.form.get('send_to_viscor')
    return_to_packwell = request.form.get('return_to_packwell')

    if send_to_viscor == 'yes':
        old_weight = reel.current_weight
        reel.status = 'Pending_Verify'
        reel.store_location = 'Viscor Lanka'
        db.session.add(ReelHistory(
            reel_id=reel.id, usage_type='Transferred for Verification', weight_before=old_weight, weight_after=old_weight,
            doc_number=doc_num if doc_num else 'Transfer Without Doc Number', remarks='Sent to Viscor Lanka by Packwell'
        ))
        db.session.commit()
        flash(f"✅ Reel {reel.reel_number} successfully transferred to Viscor Lanka Verification!", "success")
        return redirect(url_for('active_stock'))

    if return_to_packwell == 'yes':
        old_weight = reel.current_weight
        reel.status = 'Pending_Return'
        db.session.add(ReelHistory(
            reel_id=reel.id, usage_type='Returned to Packwell', weight_before=old_weight, weight_after=old_weight,
            doc_number=doc_num if doc_num else 'Return Without Doc Number', remarks='Returned to Packwell by Viscor Lanka'
        ))
        db.session.commit()
        flash(f"✅ Reel {reel.reel_number} successfully sent to Packwell Returns!", "success")
        return redirect(url_for('active_stock'))
        
    if reel.status == 'Damaged':
        old_weight = reel.current_weight
        reel.status = 'Issued'
        prefix = get_sr_prefix(user_role)
        auto_sr = f"{prefix}-COND-{datetime.now(colombo_tz).strftime('%Y%m%d%H%M')}-{random.randint(10,99)}"
        final_doc_num = doc_num if doc_num else auto_sr
        
        db.session.add(ReelHistory(
            reel_id=reel.id, usage_type='Conditional Issue (Damaged)', weight_before=old_weight, weight_after=0.0,
            doc_number=final_doc_num, remarks=remarks if remarks else 'Damaged stock conditionally issued'
        ))
        db.session.commit()
        flash(f"✅ Damaged Reel {reel.reel_number} conditionally issued!", "success")
        return redirect(url_for('damage_sell_stock'))
        
    elif reel.status in ['Full', 'Used']:
        old_weight = reel.current_weight
        reel.status = 'Issued'
        db.session.add(ReelHistory(
            reel_id=reel.id, usage_type='Issued to Production', weight_before=old_weight, weight_after=0.0,
            doc_number=doc_num if doc_num else 'Manual Dispatch', remarks="Manual Dispatch"
        ))
        db.session.commit()
        flash(f"✅ Reel {reel.reel_number} successfully Dispatched!", "success")
    return redirect(url_for('active_stock'))

@app.route('/viscor_issue')
def viscor_issue():
    if 'role' not in session: return redirect(url_for('login'))
    user_role = get_user_role()
    
    viscor_reels = Reel.query.filter_by(status='Pending_Verify', store_location='Viscor Lanka').all()
    packwell_reels = Reel.query.filter(Reel.status == 'Pending_Verify', Reel.store_location.like('Packwell%')).all()
    packwell_returns = Reel.query.filter_by(status='Pending_Return').all()
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    history_query = ReelHistory.query.filter(
        ReelHistory.usage_type.in_(['Transferred for Verification', 'Returned to Packwell', 'Viscor Return Accepted', 'Packwell Return Accepted'])
    )
    
    if start_date and end_date:
        try:
            s_date = datetime.strptime(start_date, '%Y-%m-%d')
            e_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            history_query = history_query.filter(ReelHistory.timestamp >= s_date, ReelHistory.timestamp < e_date)
        except Exception: pass
            
    transfer_history = history_query.order_by(ReelHistory.timestamp.desc()).all()
    return render_template('viscor_issue.html', reels=viscor_reels, packwell_reels=packwell_reels, packwell_returns=packwell_returns, transfer_history=transfer_history, start_date=start_date or '', end_date=end_date or '', user_role=user_role)

@app.route('/accept_return/<int:id>', methods=['POST'])
def accept_return(id):
    user_role = get_user_role()
    if user_role not in ['dataop2', 'admin']:
        flash("❌ Unauthorized Action. Only DataOp2 can accept Packwell Returns.", "danger")
        return redirect(url_for('viscor_issue'))
        
    reel = Reel.query.get_or_404(id)
    new_loc = request.form.get('accept_location')
    if new_loc: reel.store_location = new_loc
    reel.status = 'Used' if reel.current_weight < reel.weight_kg else 'Full'
    
    db.session.add(ReelHistory(
        reel_id=reel.id, usage_type='Packwell Return Accepted', weight_before=reel.current_weight,
        weight_after=reel.current_weight, doc_number='Accepted', remarks=f'Accepted at {new_loc} by Packwell'
    ))
    db.session.commit()
    flash(f"✅ Reel {reel.reel_number} Accepted & Moved to Active Stock!", "success")
    return redirect(url_for('viscor_issue'))

@app.route('/accept_viscor/<int:id>', methods=['POST'])
def accept_viscor(id):
    user_role = get_user_role()
    if user_role not in ['dataop1', 'admin']:
        flash("❌ Unauthorized Action.", "danger")
        return redirect(url_for('viscor_issue'))
    reel = Reel.query.get_or_404(id)
    reel.status = 'Used' if reel.current_weight < reel.weight_kg else 'Full'
    
    db.session.add(ReelHistory(
        reel_id=reel.id, usage_type='Viscor Return Accepted', weight_before=reel.current_weight,
        weight_after=reel.current_weight, doc_number='Accepted', remarks='Verified & Accepted at Viscor Lanka'
    ))
    db.session.commit()
    flash(f"✅ Reel {reel.reel_number} Verified & Accepted at Viscor!", "success")
    return redirect(url_for('viscor_issue'))

@app.route('/accept_packwell/<int:id>', methods=['POST'])
def accept_packwell(id):
    user_role = get_user_role()
    if user_role not in ['dataop2', 'admin']:
        flash("❌ Unauthorized Action.", "danger")
        return redirect(url_for('viscor_issue'))
    reel = Reel.query.get_or_404(id)
    new_loc = request.form.get('accept_location')
    if new_loc: reel.store_location = new_loc
    reel.status = 'Used' if reel.current_weight < reel.weight_kg else 'Full'
    db.session.commit()
    flash(f"✅ Reel {reel.reel_number} Verified & Accepted!", "success")
    return redirect(url_for('viscor_issue'))

@app.route('/partial_return/<int:id>', methods=['POST'])
def partial_return(id):
    user_role = get_user_role()
    if user_role in ['programmer1', 'programmer2', 'super1', 'super2', 'viewer']:
        flash("❌ Access Denied.", "danger")
        return redirect(url_for('issued_stock'))
        
    reel = Reel.query.get_or_404(id)
    try:
        new_w = safe_float(request.form.get('new_weight'))
        if new_w <= 0 or new_w > reel.weight_kg:
            flash("❌ Invalid remaining weight specified.", "danger")
            return redirect(url_for('issued_stock'))
            
        old_w = reel.current_weight
        reel.current_weight = new_w
        reel.status = 'Used'
        reel.sr_request_id = None
        
        db.session.add(ReelHistory(
            reel_id=reel.id, usage_type='Partial Return', weight_before=old_w,  
            weight_after=new_w, remarks="Returned from production floor"
        ))
        db.session.commit()
        flash(f"↩️ Reel {reel.reel_number} is back in Active Stock.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error handling return: {str(e)}", "danger")
    return redirect(url_for('active_stock'))

@app.route('/issued_stock')
def issued_stock():
    if 'role' not in session: return redirect(url_for('login'))
    reels = apply_location_filter(Reel.query, Reel).filter(Reel.status.in_(['Issued', 'SR_Requested'])).order_by(Reel.id.desc()).all()
    logs_query = ReelHistory.query.join(Reel).filter(ReelHistory.usage_type == 'Issued to Production')
    logs_query = apply_location_filter(logs_query, Reel)
    manual_issue_logs = logs_query.order_by(ReelHistory.timestamp.desc()).all()
    return render_template('issued_stock.html', stocks=reels, manual_logs=manual_issue_logs, user_role=get_user_role()) 

@app.route('/finished_usage_stock')
def finished_usage_stock():
    if 'role' not in session: return redirect(url_for('login'))
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    finished_reels_query = apply_location_filter(Reel.query, Reel).filter_by(status='Finished')
    usage_logs_query = ReelHistory.query.join(Reel).filter(ReelHistory.usage_type.in_(['Finished Usage', 'Partial Return']))
    usage_logs_query = apply_location_filter(usage_logs_query, Reel)
    
    if start_date and end_date:
        try:
            s_date = datetime.strptime(start_date, '%Y-%m-%d')
            e_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            usage_logs_query = usage_logs_query.filter(ReelHistory.timestamp >= s_date, ReelHistory.timestamp < e_date)
        except Exception: pass
            
    finished_reels = finished_reels_query.order_by(Reel.id.desc()).all()
    usage_logs = usage_logs_query.order_by(ReelHistory.timestamp.desc()).all()
    
    total_finished_weight = sum([r.weight_kg for r in finished_reels])
    total_used_weight_log = sum([(l.weight_before - l.weight_after) for l in usage_logs if l.weight_before is not None and l.weight_after is not None])
    
    return render_template('finished_usage_stock.html', finished_reels=finished_reels, usage_logs=usage_logs, total_finished_weight=round(total_finished_weight, 2), total_used_weight_log=round(total_used_weight_log, 2), start_date=start_date or '', end_date=end_date or '', user_role=get_user_role())

@app.route('/update_finished_sr/<int:id>', methods=['POST'])
def update_finished_sr(id):
    user_role = get_user_role()
    if user_role not in ['admin', 'dataop1']:
        flash("❌ Unauthorized Action.", "danger")
        return redirect(url_for('finished_usage_stock'))
        
    reel = Reel.query.get_or_404(id)
    new_sr = request.form.get('sr_number')
    if reel.history:
        reel.history[-1].doc_number = new_sr
        db.session.commit()
        flash(f"✅ SR Number updated for {reel.reel_number}", "success")
    else:
        flash("❌ No history log found to update.", "danger")
    return redirect(url_for('finished_usage_stock'))

@app.route('/damage_sell_stock')
def damage_sell_stock():
    if 'role' not in session: return redirect(url_for('login'))
    damaged_reels = apply_location_filter(Reel.query, Reel).filter_by(status='Damaged').all()
    sold_reels = apply_location_filter(Reel.query, Reel).filter_by(status='Sold').all()
    
    cond_logs = ReelHistory.query.join(Reel).filter(ReelHistory.usage_type == 'Conditional Issue (Damaged)')
    cond_logs = apply_location_filter(cond_logs, Reel).order_by(ReelHistory.timestamp.desc()).all()
    
    return render_template('damage_sell_stock.html', damaged_reels=damaged_reels, sold_reels=sold_reels, cond_logs=cond_logs, user_role=get_user_role())

@app.route('/reset_db_now')
def reset_db_now():
    if 'role' in session and session.get('role') == 'admin':
        try:
            db.session.execute(text('SET FOREIGN_KEY_CHECKS = 0;'))
            db.drop_all()
            db.session.execute(text('SET FOREIGN_KEY_CHECKS = 1;'))
            db.create_all()
            db.session.commit()
            return "✅ Database Reset Successful! <br><br> <a href='/'>Go to Login</a>"
        except Exception as e:
            db.session.rollback()
            return f"❌ Error: {str(e)}"
    else:
        return "❌ Access Denied: Unauthorized Reset Attempt.", 403

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'role' not in session: return redirect(url_for('login'))
    user_role = get_user_role()
    
    if request.method == 'POST':
        try:
            c_id = request.form.get('customer_id', '').strip()
            c_name = request.form.get('customer_name', '').strip()
            c_address = request.form.get('address', '').strip()
            p_code = request.form.get('product_code', '').strip()
            p_name = request.form.get('product_name', '').strip()
            c_size = request.form.get('cartoon_size', '').strip()
            position = request.form.get('position', '').strip()
            flute = request.form.get('flute', '').strip()
            ply = safe_int(request.form.get('ply', 3))
            
            existing = CustomerProduct.query.filter_by(
                customer_name=c_name, product_name=p_name, cartoon_size=c_size
            ).first()
            
            if existing:
                flash(f"⚠️ This Product ({p_name}) already exists!", "warning")
                return redirect(url_for('add_product'))
                
            new_prod = CustomerProduct(
                customer_id=c_id, customer_name=c_name, customer_address=c_address,
                product_code=p_code, product_name=p_name, cartoon_size=c_size,
                position=position, flute=flute, ply=ply
            )
            db.session.add(new_prod)
            db.session.commit()
            flash("✅ Product Registered Successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error adding product: {str(e)}", "danger")
        return redirect(url_for('add_product'))

    return render_template('add_product.html', user_role=user_role)

# UPDATE: Reel Size calculation logic to add trimming allowance (+2) only once per formula
def calculate_reel_size(length, width, height, position, ply):
    standard_sizes = list(range(75, 155, 5))
    options = []
    
    for ups in range(1, 6):
        if position.lower() == 'internal':
            if ply == 3:
                req_size = ((width + 0.4) + (height + 0.3)) * ups + 2
            elif ply == 5:
                req_size = ((width + 0.8) + (height + 0.3)) * ups + 2
            else:
                req_size = (width + height) * ups + 2
        else:
            req_size = (width + height) * ups + 2
            
        for std in standard_sizes:
            if std >= req_size:
                options.append({'ups': ups, 'required_size': round(req_size, 2), 'suggested_reel': std, 'wastage': round(std - req_size, 2)})
                break
                
    options.sort(key=lambda x: x['wastage'])
    return options

@app.route('/programme_plan')
def programme_plan():
    if 'role' not in session: return redirect(url_for('login'))
    return render_template('programme_plan.html', user_role=get_user_role())

# API ENDPOINTS FOR PRODUCTS
@app.route('/api/get_products', methods=['GET'])
def get_products():
    products = CustomerProduct.query.all()
    return jsonify([{
        'id': p.id, 'customer_id': p.customer_id, 'customer_name': p.customer_name,
        'product_code': p.product_code, 'product_name': p.product_name,
        'cartoon_size': p.cartoon_size, 'position': p.position, 'flute': p.flute, 'ply': p.ply
    } for p in products])

@app.route('/api/update_product', methods=['POST'])
def update_product():
    data = request.json
    prod = CustomerProduct.query.get(data.get('id'))
    if prod:
        prod.customer_id = data.get('customer_id')
        prod.customer_name = data.get('customer_name')
        prod.product_code = data.get('product_code')
        prod.product_name = data.get('product_name')
        prod.cartoon_size = data.get('cartoon_size')
        prod.position = data.get('position')
        prod.flute = data.get('flute')
        prod.ply = int(data.get('ply'))
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Product not found'})

# UPDATE: API Reel size calculation matching the same +2 isolated logic
@app.route('/api/get_product_info', methods=['GET'])
def get_product_info():
    customer_id = request.args.get('customer_id')
    product_code = request.args.get('product_code')
    product = CustomerProduct.query.filter_by(customer_id=customer_id, product_code=product_code).first() 
    
    if product:
        dims = [float(x) for x in re.findall(r'\d+\.?\d*', product.cartoon_size)]
        l = dims[0] if len(dims) > 0 else 30.0
        w = dims[1] if len(dims) > 1 else 20.0
        h = dims[2] if len(dims) > 2 else 10.0
        
        options = []
        for ups in range(1, 6):
            if product.position.lower() == 'internal':
                if product.ply == 3:
                    req_size = ((w + 0.4) + (h + 0.3)) * ups + 2
                elif product.ply == 5:
                    req_size = ((w + 0.8) + (h + 0.3)) * ups + 2
                else:
                    req_size = (w + h) * ups + 2
            else: # external
                req_size = (w + h) * ups + 2
                
            for std in range(75, 155, 5):
                if std >= req_size:
                    options.append({'ups': ups, 'required_size': round(req_size, 2), 'suggested_reel': std, 'wastage': round(std - req_size, 2)})
                    break
                    
        return jsonify({"success": True, "customer_name": product.customer_name, "product_name": product.product_name, "cartoon_size": product.cartoon_size, "ply": product.ply, "flute": product.flute, "position": product.position, "options": options})
    return jsonify({"success": False, "message": "Product not found"})

@app.route('/api/check_stock_detailed', methods=['POST'])
def check_stock_detailed():
    data = request.json
    size = float(data.get('size'))
    materials = data.get('materials', [])
    qty = int(data.get('qty', 0))
    sheet_length = float(data.get('sheet_length', 0))
    
    results = []
    for idx, mat in enumerate(materials):
        gsm = int(mat.get('gsm', 0))
        name = mat.get('name', '')
        layer_role = f"L{idx+1}" 
        
        calc_weight = (size * sheet_length * (gsm / 10000.0) * qty) / 1000.0
        if idx == 1: calc_weight *= 1.5
            
        active_reels = Reel.query.filter(
            Reel.size_cm == size, Reel.material_name == name, Reel.gsm == gsm, Reel.status.in_(['Full', 'Used'])
        ).all()
        
        available_stock = sum([r.current_weight for r in active_reels])
        has_stock = available_stock >= calc_weight if calc_weight > 0 else available_stock > 0
        shortage = max(0.0, calc_weight - available_stock)
        
        results.append({
            'layer': layer_role, 'name': name, 'gsm': gsm, 'has_stock': has_stock,
            'required_weight': round(calc_weight, 2), 'available_stock': round(available_stock, 2), 'shortage': round(shortage, 2)
        })
        
    papers_data = db.session.query(Reel.material_name).filter(Reel.status.in_(['Full', 'Used'])).distinct().all()
    return jsonify({'results': results, 'all_papers': [p.material_name for p in papers_data]})

@app.route('/api/save_programme_plan', methods=['POST'])
def save_programme_plan():
    data = request.json
    new_plan = ProgrammePlan(
        po_no=data.get('po_no'), customer_id=data.get('customer_id'), product_code=data.get('product_code'),
        selected_reel_size=safe_float(data.get('selected_reel_size')), selected_ups=safe_int(data.get('selected_ups')),
        materials_json=json.dumps(data.get('materials', [])), created_by=session.get('username', 'System')
    )
    db.session.add(new_plan)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/get_saved_plans')
def get_saved_plans():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = ProgrammePlan.query
    if start_date and end_date:
        try:
            s_date = datetime.strptime(start_date, '%Y-%m-%d')
            e_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(ProgrammePlan.created_at >= s_date, ProgrammePlan.created_at < e_date)
        except Exception: pass

    plans = query.order_by(ProgrammePlan.created_at.desc()).all()
    
    result = {}
    for p in plans:
        size = str(p.selected_reel_size)
        if size not in result: result[size] = []
        prod = CustomerProduct.query.filter_by(customer_id=p.customer_id, product_code=p.product_code).first()
        c_name = prod.customer_name if prod else "Unknown"
        
        # New Feature: Add Cut length calculation based on the DB Product dims
        cut_length = 0
        if prod and prod.cartoon_size:
            dims = [float(x) for x in re.findall(r'\d+\.?\d*', prod.cartoon_size)]
            l = dims[0] if len(dims) > 0 else 0
            w = dims[1] if len(dims) > 1 else 0
            cut_length = (w + l) * 2
            
        # Format Date to display in Table
        date_str = p.created_at.strftime('%Y-%m-%d %I:%M %p') if p.created_at else ""
        
        result[size].append({
            'id': p.id, 'po_no': p.po_no, 'customer_id': p.customer_id, 'customer_name': c_name,
            'product_code': p.product_code, 'ups': p.selected_ups, 'ply': prod.ply if prod else 3,
            'remarks': f"{prod.position} / Flute: {prod.flute}" if prod else "",
            'materials': json.loads(p.materials_json) if p.materials_json else [],
            'created_at': date_str,
            'cut_length': cut_length
        })
    return jsonify(result)

# WEBSOCKET FOR EMERGENCY TRANSFER REQUESTS
@socketio.on('send_reel_request_packwell')
def handle_packwell_request(data):
    emit('receive_packwell_alert', data, broadcast=True)

@app.route('/api/execute_packwell_transfer', methods=['POST'])
def execute_packwell_transfer():
    data = request.json
    size = float(data.get('size'))
    paper_name = data.get('name')
    
    reel = Reel.query.filter(
        Reel.size_cm == size, Reel.material_name == paper_name,
        Reel.store_location.like('Packwell%'), Reel.status.in_(['Full', 'Used'])
    ).first()
    
    if reel:
        old_w = reel.current_weight
        reel.status = 'Pending_Verify'
        reel.store_location = 'Viscor Lanka' 
        
        db.session.add(ReelHistory(
            reel_id=reel.id, usage_type='Transferred for Verification',
            weight_before=old_w, weight_after=old_w,
            doc_number="AUTO-REQ-TRANSFER", remarks="Emergency low stock auto-request trigger approved"
        ))
        db.session.commit()
        return jsonify({'success': True, 'reel_number': reel.reel_number})
    return jsonify({'success': False, 'message': 'No matching active reels found in Packwell Stock.'})
    
if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
