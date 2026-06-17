from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, timedelta
import pytz
import random

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
    size_cm = db.Column(db.Float, nullable=False)
    gsm = db.Column(db.Integer, nullable=False)
    material_name = db.Column(db.String(100), nullable=False)
    reel_type = db.Column(db.String(100), nullable=True) 
    weight_kg = db.Column(db.Float, nullable=False)
    current_weight = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Full')  
    store_location = db.Column(db.String(100), nullable=False)
    supplier_name = db.Column(db.String(100), nullable=True)
    received_date = db.Column(db.Date, nullable=False)
    sr_request_id = db.Column(db.Integer, db.ForeignKey('sr_request.id'), nullable=True)

class SRRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sr_number = db.Column(db.String(100), unique=True, nullable=True) # අලුත් Column එක
    po_number = db.Column(db.String(100), nullable=False)
    reel_size = db.Column(db.Float, nullable=False)
    gsm = db.Column(db.Integer, nullable=False)
    material_name = db.Column(db.String(100), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    calculated_weight = db.Column(db.Float, nullable=False)
    board_width = db.Column(db.Float, nullable=True)
    board_length = db.Column(db.Float, nullable=True)
    component_type = db.Column(db.String(50), nullable=True)
    flute_type = db.Column(db.String(10), nullable=True)
    excess_weight = db.Column(db.Float, default=0.0)
    total_weight = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    reels = db.relationship('Reel', backref='associated_sr', lazy=True)

class ReelHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reel.id'), nullable=False)
    usage_type = db.Column(db.String(100), nullable=False)
    weight_before = db.Column(db.Float, nullable=False)
    weight_after = db.Column(db.Float, nullable=False)
    doc_number = db.Column(db.String(100), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    reel = db.relationship('Reel', backref=db.backref('history', lazy=True))

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
            "programmer2": ("packwell@3457", "programmer2")
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
    
    total_active = Reel.query.filter(Reel.status.in_(['Full', 'Used', 'SR_Requested'])).count()
    full_count = Reel.query.filter_by(status='Full').count()
    used_count = Reel.query.filter_by(status='Used').count()
    sr_req_count = Reel.query.filter_by(status='SR_Requested').count()
    
    finished = Reel.query.filter_by(status='Issued').count()
    damage_sell = Reel.query.filter(Reel.status.in_(['Damaged', 'Sold'])).count()
    active_weight = 0
    
    return render_template('dashboard.html', 
                           total_active=total_active, active_weight=active_weight,
                           full_count=full_count, used_count=used_count,
                           sr_req_count=sr_req_count, finished=finished,
                           damage_sell_count=damage_sell, user_role=get_user_role())

@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    user_role = get_user_role()
    if user_role in ['programmer1', 'programmer2', 'super1', 'super2']:
        flash("❌ Access Denied: Unauthorized tab.", "danger")
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        try:
            reel_num = request.form.get('reel_number').strip()
            if Reel.query.filter_by(reel_number=reel_num).first():
                flash(f"❌ Reel Number '{reel_num}' already exists!", "danger")
                return redirect(url_for('add_stock'))

            date_str = request.form.get('received_date')
            if date_str:
                rcv_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                rcv_date = datetime.now(colombo_tz).date()

            new_reel = Reel(
                reel_number=reel_num,
                size_cm=float(request.form.get('size_cm')),
                gsm=int(request.form.get('gsm')),
                material_name=request.form.get('material_name'),
                reel_type=request.form.get('reel_type'),
                weight_kg=float(request.form.get('weight_kg')),
                current_weight=float(request.form.get('weight_kg')),
                store_location=request.form.get('store_location'),
                supplier_name=request.form.get('supplier_name'),
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
    user_role = get_user_role()
    if 'role' not in session: return redirect(url_for('login'))
    
    full_reels = Reel.query.filter_by(status='Full').order_by(Reel.received_date.asc()).all()
    used_reels = Reel.query.filter_by(status='Used').order_by(Reel.received_date.asc()).all()
    sr_requested_reels = Reel.query.filter_by(status='SR_Requested').order_by(Reel.received_date.asc()).all()
    
    return render_template('active_stock.html', full_reels=full_reels, used_reels=used_reels, sr_requested_reels=sr_requested_reels, user_role=user_role)

# --- නව Active Stock Action Routes ---
@app.route('/edit_active_reel/<int:id>', methods=['POST'])
def edit_active_reel(id):
    if get_user_role() in ['super1', 'super2']:
        flash("❌ Action Not Allowed.", "danger")
        return redirect(url_for('active_stock'))
        
    reel = Reel.query.get_or_404(id)
    reel.size_cm = float(request.form.get('size_cm', reel.size_cm))
    reel.gsm = int(request.form.get('gsm', reel.gsm))
    reel.current_weight = float(request.form.get('current_weight', reel.current_weight))
    db.session.commit()
    flash(f"✅ Reel {reel.reel_number} Updated Successfully!", "success")
    return redirect(url_for('active_stock'))

@app.route('/mark_damage_sell/<int:id>', methods=['POST'])
def mark_damage_sell(id):
    if get_user_role() in ['super1', 'super2']:
        flash("❌ Action Not Allowed.", "danger")
        return redirect(url_for('active_stock'))
        
    reel = Reel.query.get_or_404(id)
    action_type = request.form.get('action_type')
    reel.status = action_type
    db.session.commit()
    flash(f"✅ Reel {reel.reel_number} marked as {action_type}!", "success")
    return redirect(url_for('active_stock'))

@app.route('/mark_return/<int:id>', methods=['POST'])
def mark_return(id):
    if get_user_role() in ['super1', 'super2']:
        flash("❌ Action Not Allowed.", "danger")
        return redirect(url_for('active_stock'))
        
    reel = Reel.query.get_or_404(id)
    reel.status = 'Returned'
    db.session.commit()
    flash(f"✅ Reel {reel.reel_number} has been Returned!", "success")
    return redirect(url_for('active_stock'))
# ----------------------------------------

@app.route('/sr_request', methods=['GET', 'POST'])
def sr_request():
    user_role = get_user_role()
    if 'role' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        if user_role in ['super1', 'super2', 'dataop1', 'dataop2']:
            flash("❌ Action Not Allowed for your role.", "danger")
            return redirect(url_for('sr_request'))
            
        try:
            b_width = float(request.form.get('board_width', 0.0))
            b_length = float(request.form.get('board_length', 0.0))
            gsm = int(request.form.get('gsm', 0))
            qty = int(request.form.get('qty', 0))
            comp_type = request.form.get('component_type')
            
            calc_weight = ((b_width * b_length) * (gsm / 1000.0)) / 2.0 * qty
            if comp_type == 'Corru':
                calc_weight = calc_weight * 1.5

            excess_w = float(request.form.get('excess_weight', 0.0))
            tot_weight = calc_weight + excess_w
            
            # Auto Generate SR Number
            new_sr_num = f"SR-{datetime.now(colombo_tz).strftime('%Y%m%d%H%M')}-{random.randint(10,99)}"
            
            new_sr = SRRequest(
                sr_number=new_sr_num,
                po_number=request.form.get('po_number'),
                reel_size=float(request.form.get('reel_size')),
                gsm=gsm,
                material_name=request.form.get('material_name'),
                qty=qty,
                calculated_weight=round(calc_weight, 2),
                board_width=b_width,
                board_length=b_length,
                component_type=comp_type,
                flute_type=request.form.get('flute_type'),
                excess_weight=excess_w,
                total_weight=round(tot_weight, 2)
            )
            db.session.add(new_sr)
            db.session.commit()
            flash(f"📊 SR Request Logged Successfully! Assigned SR Number: {new_sr_num}", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error logging request: {str(e)}", "danger")
            
    all_requests = SRRequest.query.order_by(SRRequest.created_at.desc()).all()
    grouped_requests = {}
    for r in all_requests:
        if r.status in ['Pending', 'Approved']:
            size = r.reel_size
            if size not in grouped_requests:
                grouped_requests[size] = { 'po_list': set(), 'papers': [] }
            grouped_requests[size]['po_list'].add(r.po_number)
            grouped_requests[size]['papers'].append(r)

    return render_template('sr_request.html', all_requests=all_requests, grouped_requests=grouped_requests, user_role=user_role)

# --- නව Programmer Edit SR Route ---
@app.route('/edit_sr/<int:id>', methods=['POST'])
def edit_sr(id):
    user_role = get_user_role()
    if user_role not in ['programmer1', 'programmer2', 'admin']:
        flash("❌ Unauthorized Action.", "danger")
        return redirect(url_for('sr_request'))
        
    sr = SRRequest.query.get_or_404(id)
    
    b_width = float(request.form.get('board_width', sr.board_width))
    b_length = float(request.form.get('board_length', sr.board_length))
    gsm = int(request.form.get('gsm', sr.gsm))
    qty = int(request.form.get('qty', sr.qty))
    comp_type = request.form.get('component_type', sr.component_type)
    excess_w = float(request.form.get('excess_weight', sr.excess_weight))
    
    calc_weight = ((b_width * b_length) * (gsm / 1000.0)) / 2.0 * qty
    if comp_type == 'Corru':
        calc_weight = calc_weight * 1.5
        
    sr.board_width = b_width
    sr.board_length = b_length
    sr.gsm = gsm
    sr.qty = qty
    sr.component_type = comp_type
    sr.excess_weight = excess_w
    sr.calculated_weight = round(calc_weight, 2)
    sr.total_weight = round(calc_weight + excess_w, 2)
    
    db.session.commit()
    flash(f"✅ SR Request {sr.sr_number} Edited Successfully!", "success")
    return redirect(url_for('sr_request'))
# -----------------------------------

@app.route('/approve_sr/<int:id>', methods=['POST'])
def approve_sr(id):
    user_role = get_user_role()
    if user_role in ['programmer1', 'programmer2', 'dataop1', 'dataop2']:
        flash("❌ Unauthorized Action.", "danger")
        return redirect(url_for('sr_request'))
    sr = SRRequest.query.get_or_404(id)
    if sr.status == 'Pending':
        sr.status = 'Approved'
        db.session.commit()
        flash(f"✅ SR Request for PO {sr.po_number} has been Approved!", "success")
    return redirect(url_for('sr_request'))

@app.route('/proceed_sr/<int:id>', methods=['POST'])
def proceed_sr(id):
    user_role = get_user_role()
    if user_role in ['programmer1', 'programmer2', 'super1', 'super2']:
        flash("❌ Unauthorized Action.", "danger")
        return redirect(url_for('sr_request'))
        
    sr = SRRequest.query.get_or_404(id)
    if sr.status != 'Approved':
        flash("❌ SR Request must be Approved first.", "warning")
        return redirect(url_for('sr_request'))
        
    target_weight = sr.total_weight
    allocated_weight = 0.0
    matched_reels = []
    
    available_reels = Reel.query.filter(
        Reel.size_cm == sr.reel_size,
        Reel.gsm == sr.gsm,
        Reel.material_name == sr.material_name,
        Reel.status.in_(['Full', 'Used'])
    ).order_by(text("FIELD(status, 'Full', 'Used')"), Reel.received_date.asc()).all()
    
    for reel in available_reels:
        if allocated_weight >= target_weight:
            break
        matched_reels.append(reel)
        allocated_weight += reel.current_weight
        
    if allocated_weight < target_weight:
        flash(f"❌ ප්‍රමාණවත් සක්‍රීය තොග නොමැත! අවශ්‍යයි: {target_weight}kg, තිබෙන්නේ: {allocated_weight}kg", "danger")
        return redirect(url_for('sr_request'))
        
    for reel in matched_reels:
        reel.status = 'SR_Requested'
        reel.sr_request_id = sr.id
        
    sr.status = 'Processed'
    db.session.commit()
    flash(f"🚀 FIFO Allocation Completed! Reels moved to Active Stock (SR Requested Mini Tab).", "success")
    return redirect(url_for('active_stock'))

# --- නව Direct Issue Route (SR Requested සිට Issued Stock එකට) ---
@app.route('/issue_reel_direct/<int:id>', methods=['POST'])
def issue_reel_direct(id):
    user_role = get_user_role()
    if user_role in ['super1', 'super2']:
        flash("❌ Access Denied.", "danger")
        return redirect(url_for('active_stock'))
        
    reel = Reel.query.get_or_404(id)
    
    if reel.status == 'SR_Requested':
        sr_num = reel.associated_sr.sr_number if reel.associated_sr else 'N/A'
        old_weight = reel.current_weight
        reel.status = 'Issued'
        
        db.session.add(ReelHistory(
            reel_id=reel.id,
            usage_type='Issued to Production',
            weight_before=old_weight,
            weight_after=0.0,
            doc_number=sr_num,
            remarks='Directly Issued from SR Request'
        ))
        db.session.commit()
        flash(f"✅ Reel {reel.reel_number} successfully Issued! SR Number ({sr_num}) automatically applied.", "success")
        
    return redirect(url_for('active_stock'))
# -------------------------------------------------------------

@app.route('/issue_reel/<int:id>', methods=['POST'])
def issue_reel(id):
    # පරණ issue function එක Damaged ඒවාට භාවිත වේ
    user_role = get_user_role()
    if user_role in ['programmer1', 'programmer2', 'super1', 'super2']:
        flash("❌ Access Denied.", "danger")
        return redirect(url_for('active_stock'))
        
    reel = Reel.query.get_or_404(id)
    doc_num = request.form.get('doc_number', '').strip()
    remarks = request.form.get('remarks', '').strip()
    
    if reel.status == 'Damaged':
        old_weight = reel.current_weight
        reel.status = 'Issued'
        db.session.add(ReelHistory(
            reel_id=reel.id,
            usage_type='Conditional Issue (Damaged)',
            weight_before=old_weight,
            weight_after=0.0,
            doc_number=doc_num,
            remarks=remarks
        ))
        db.session.commit()
        flash(f"✅ Damaged Reel {reel.reel_number} conditionally issued!", "success")
        return redirect(url_for('damage_sell_stock'))
        
    return redirect(url_for('active_stock'))

@app.route('/viscor_issue')
def viscor_issue():
    if 'role' not in session: return redirect(url_for('login'))
    user_role = get_user_role()
    viscor_reels = Reel.query.filter_by(status='Pending_Verify', store_location='Viscor Lanka').all()
    packwell_reels = Reel.query.filter(Reel.status == 'Pending_Verify', Reel.store_location.like('Packwell%')).all()
    return render_template('viscor_issue.html', reels=viscor_reels, packwell_reels=packwell_reels, user_role=user_role)

@app.route('/accept_viscor/<int:id>', methods=['POST'])
def accept_viscor(id):
    user_role = get_user_role()
    if user_role not in ['dataop1', 'admin']:
        flash("❌ Unauthorized Action.", "danger")
        return redirect(url_for('viscor_issue'))
    reel = Reel.query.get_or_404(id)
    reel.status = 'Used' if reel.current_weight < reel.weight_kg else 'Full'
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
    if new_loc:
        reel.store_location = new_loc
    reel.status = 'Used' if reel.current_weight < reel.weight_kg else 'Full'
    db.session.commit()
    flash(f"✅ Reel {reel.reel_number} Returned & Accepted at {new_loc}!", "success")
    return redirect(url_for('viscor_issue'))

@app.route('/partial_return/<int:id>', methods=['POST'])
def partial_return(id):
    user_role = get_user_role()
    if user_role in ['programmer1', 'programmer2', 'super1', 'super2']:
        flash("❌ Access Denied.", "danger")
        return redirect(url_for('issued_stock'))
    reel = Reel.query.get_or_404(id)
    try:
        new_w = float(request.form.get('new_weight', 0.0))
        if new_w <= 0 or new_w > reel.weight_kg:
            flash("❌ Invalid remaining weight specified.", "danger")
            return redirect(url_for('issued_stock'))
            
        old_w = reel.current_weight
        reel.current_weight = new_w
        reel.status = 'Used'
        reel.sr_request_id = None
        
        db.session.add(ReelHistory(
            reel_id=reel.id,
            usage_type='Partial Return',
            weight_before=old_w,
            weight_after=new_w,
            remarks="Returned from production floor"
        ))
        db.session.commit()
        flash(f"↩️ Reel {reel.reel_number} is back in Active Stock as a Used Reel.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error handling return: {str(e)}", "danger")
    return redirect(url_for('active_stock'))

@app.route('/issued_stock')
def issued_stock():
    if 'role' not in session: return redirect(url_for('login'))
    reels = Reel.query.filter_by(status='Issued').order_by(Reel.id.desc()).all()
    return render_template('issued_stock.html', stocks=reels, user_role=get_user_role()) # Fixed parameter names

@app.route('/finished_usage_stock')
def finished_usage_stock():
    if 'role' not in session: return redirect(url_for('login'))
    reels = Reel.query.filter_by(status='Issued').all()
    return render_template('finished_usage_stock.html', reels=reels, user_role=get_user_role())

@app.route('/damage_sell_stock')
def damage_sell_stock():
    if 'role' not in session: return redirect(url_for('login'))
    reels = Reel.query.filter(Reel.status.in_(['Damaged', 'Sold', 'Returned'])).all() # Added Returned mapping here optionally
    return render_template('damage_sell_stock.html', reels=reels, user_role=get_user_role())

@app.route('/update_location/<int:id>', methods=['POST'])
def update_location(id):
    user_role = get_user_role()
    if user_role in ['super1', 'super2']:
        flash("❌ Action Not Allowed.", "danger")
        return redirect(url_for('active_stock'))
    reel = Reel.query.get_or_404(id)
    new_loc = request.form.get('location')
    if new_loc:
        reel.store_location = new_loc
        db.session.commit()
        flash("📍 Location Updated.", "success")
    return redirect(url_for('active_stock'))

@app.route('/reset_db_now')
def reset_db_now():
    try:
        db.session.execute(text('SET FOREIGN_KEY_CHECKS = 0;'))
        db.drop_all()
        db.session.execute(text('SET FOREIGN_KEY_CHECKS = 1;'))
        db.create_all()
        db.session.commit()
        return "✅ Database Updated Successfully (Force Reset Applied)! All new columns (SR Number included) are ready. <br><br> <a href='/'>Click Here to go back to Login Page</a>"
    except Exception as e:
        db.session.rollback()
        return f"❌ Error resetting database: {str(e)}"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
