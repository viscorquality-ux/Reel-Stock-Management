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
        pending_viscor = Reel.query.filter(Reel.status.in_(['Pending Viscor', 'Pending Packwell Full', 'Pending Packwell Used'])).count()
        issued = Reel.query.filter_by(status='Issued').count()
        finished = Reel.query.filter_by(status='Finished').count()
        damage_sell_count = Reel.query.filter(Reel.status.in_(['Damaged', 'Sold'])).count()

    active_reels = active_query.all()
    active_count = len(active_reels)
    active_weight = sum((r.weight_kg or 0.0) for r in active_reels)

    pending_viscor = Reel.query.filter_by(status='Pending Viscor').count()
    issued = Reel.query.filter_by(status='Issued').count()
    finished = Reel.query.filter_by(status='Finished').count()
    damage_sell_count = Reel.query.filter(Reel.status.in_(['Damaged', 'Sold'])).count()
    
    return render_template('dashboard.html', active_count=active_count, active_weight=active_weight,
                           pending_viscor_count=pending_viscor, issued=issued, finished=finished, damage_sell_count=damage_sell_count)


    return render_template('add_stock.html', user_role=user_role)

# -- Active Reel Edit Route අලුතින් එක් කළ කොටස --
@app.route('/edit_active_reel/<int:id>', methods=['POST'])
def edit_active_reel(id):
    reel = Reel.query.get_or_404(id)
@app.route('/viscor_issue')
def viscor_issue():
    user_role = session.get('role')
    viscor_reels = Reel.query.filter_by(status='Pending Viscor').all()
    packwell_reels = Reel.query.filter(Reel.status.in_(['Pending Packwell Full', 'Pending Packwell Used'])).all()
    if user_role == 'dataop1':
        viscor_reels = Reel.query.filter_by(status='Pending Viscor').all()
        packwell_reels = []
    elif user_role == 'dataop2':
        viscor_reels = []
        packwell_reels = Reel.query.filter(Reel.status.in_(['Pending Packwell Full', 'Pending Packwell Used']), Reel.store_location.like('Packwell W%')).all()
    else:
        viscor_reels = Reel.query.filter_by(status='Pending Viscor').all()
        packwell_reels = Reel.query.filter(Reel.status.in_(['Pending Packwell Full', 'Pending Packwell Used'])).all()
        
    return render_template('viscor_issue.html', reels=viscor_reels, packwell_reels=packwell_reels, user_role=user_role)

@app.route('/accept_viscor/<int:id>', methods=['POST'])

@app.route('/issued_stock')
def issued_stock():
    return render_template('issued_stock.html', stocks=Reel.query.filter_by(status='Issued').all())
    user_role = session.get('role')
    query = Reel.query.filter_by(status='Issued')
    
    if user_role == 'dataop1':
        query = query.filter(Reel.store_location == 'Viscor Lanka')
    elif user_role == 'dataop2':
        query = query.filter(Reel.store_location.like('Packwell W%'))
        
    return render_template('issued_stock.html', stocks=query.all())

@app.route('/finish_reel/<int:id>', methods=['POST'])
def finish_reel(id):


@app.route('/damage_sell_stock')
def damage_sell_stock():
    damaged_reels = Reel.query.filter_by(status='Damaged').all()
    sold_reels = Reel.query.filter_by(status='Sold').all()
    cond_logs = ReelHistory.query.filter_by(action_type='COND_ISSUE').order_by(ReelHistory.timestamp.desc()).all()
    user_role = session.get('role')
    damaged_query = Reel.query.filter_by(status='Damaged')
    sold_query = Reel.query.filter_by(status='Sold')
    cond_query = ReelHistory.query.filter_by(action_type='COND_ISSUE')

    if user_role == 'dataop1':
        damaged_query = damaged_query.filter(Reel.store_location == 'Viscor Lanka')
        sold_query = sold_query.filter(Reel.store_location == 'Viscor Lanka')
        cond_query = cond_query.join(Reel).filter(Reel.store_location == 'Viscor Lanka')
    elif user_role == 'dataop2':
        damaged_query = damaged_query.filter(Reel.store_location.like('Packwell W%'))
        sold_query = sold_query.filter(Reel.store_location.like('Packwell W%'))
        cond_query = cond_query.join(Reel).filter(Reel.store_location.like('Packwell W%'))

    damaged_reels = damaged_query.all()
    sold_reels = sold_query.all()
    cond_logs = cond_query.order_by(ReelHistory.timestamp.desc()).all()
    
    return render_template('damage_sell_stock.html', damaged_reels=damaged_reels, sold_reels=sold_reels, cond_logs=cond_logs)

@app.route('/mark_damage_sell/<int:id>', methods=['POST'])


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
    elif user_role == 'dataop2':
        finished_query = finished_query.filter(Reel.store_location.like('Packwell W%'))
        logs_query = logs_query.filter(Reel.store_location.like('Packwell W%'))

    if start_date and end_date:
        try:
            s_date = datetime.strptime(start_date, '%Y-%m-%d')
            # මෙතනට දිනයන් අනුව filter වන කේතයක් අවශ්‍ය නම් එක් කර ගන්න
        except Exception as e:
            pass

    # වරහන් සියල්ල අවසානයේ පමණක් ක්‍රමවත්ව වැසී ඇති බව තහවුරු කරගන්න
    return render_template('finished_usage_stock.html',
                           finished_query=finished_query.all(),
                           logs_query=logs_query.all(),
                           start_date=start_date or '',
                           end_date=end_date or '')

# -- Finished SR Update Route අලුතින් එක් කළ කොටස --
@app.route('/update_finished_sr/<int:id>', methods=['POST'])
def update_finished_sr(id):
    if session.get('role') != 'dataop1':
