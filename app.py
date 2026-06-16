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
    location = db.Column(db.String(100), default='Viscor Lanka') # මෙහි නම 'location' වේ
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
    # fix_db route එක allowed_routes වලට එකතු කර ඇත
    allowed_routes = ['login', 'login_submit', 'static', 'fix_db']
    if request.endpoint not in allowed_routes and 'role' not in session:
        return redirect(url_for('login'))

@app.route('/fix_db')
def fix_db():
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE reel ADD COLUMN location VARCHAR(100) DEFAULT 'Viscor Lanka';"))
            conn.commit()
        return "Database එක සාර්ථකව Update විය! දැන් Dashboard එකට යන්න පුළුවන්."
    except Exception as e:
        return f"දෝෂයක්: {e}"

@app.route('/')
def home():
    return redirect(url_for('dashboard')) if 'role' in session else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        
        users = {
            'admin': 'admin@0123',
            'dataop1': 'viscor@2468',
            'dataop2': 'packwell@8642',
            'super1': 'viscor@1357',
            'super2': 'packwell@7531'
        }
        
        if username in users and users[username] == password:
            # මෙහිදී 'username' වෙනුවට 'role' ලෙස session එක සෑදීම නිවැරදි කර ඇත
            session['role'] = username
            flash(f'Successfully logged in as {username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Username or Password!', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/dashboard') 
def dashboard():
    current_user = session.get('role')
    query = Reel.query
    
    if current_user == 'dataop1':
        query = query.filter_by(location='Viscor Lanka')
    elif current_user == 'dataop2':
        # Packwell සෙවීම LIKE හරහා පහසුවෙන් කිරීමට සකසා ඇත
        query = query.filter(Reel.location.like('Packwell W%'))
        
    reels_data = query.all()
    is_read_only = True if current_user in ['super1', 'super2'] else False
    
    return render_template('dashboard.html', 
                           reels=reels_data, 
                           is_read_only=is_read_only, 
                           current_user=current_user)

@app.route('/active_stock')
def active_stock():
    user_role = session.get('role')
    query = Reel.query.filter(Reel.status.in_(['Full Reel', 'Used Reel']))
    
    if user_role == 'dataop1':
        query = query.filter(Reel.location == 'Viscor Lanka') # store_location යන්න location ලෙස වෙනස් විය
    elif user_role == 'dataop2':
        query = query.filter(Reel.location.like('Packwell W%'))
        
    return render_template('active_stock.html', active_stocks=query.all())

@app.route('/add_stock', methods=['GET', 'POST'])
def add_stock():
    user_role = session.get('role')
    return render_template('add_stock.html', user_role=user_role)

@app.route('/edit_active_reel/<int:id>', methods=['POST'])
def edit_active_reel(id):
    reel = Reel.query.get_or_404(id)
    return redirect(url_for('dashboard'))

@app.route('/viscor_issue')
def viscor_issue():
    user_role = session.get('role')
    if user_role == 'dataop1':
        viscor_reels = Reel.query.filter_by(status='Pending Viscor').all()
        packwell_reels = []
    elif user_role == 'dataop2':
        viscor_reels = []
        packwell_reels = Reel.query.filter(Reel.status.in_(['Pending Packwell Full', 'Pending Packwell Used']), Reel.location.like('Packwell W%')).all()
    else:
        viscor_reels = Reel.query.filter_by(status='Pending Viscor').all()
        packwell_reels = Reel.query.filter(Reel.status.in_(['Pending Packwell Full', 'Pending Packwell Used'])).all()
        
    return render_template('viscor_issue.html', reels=viscor_reels, packwell_reels=packwell_reels, user_role=user_role)

@app.route('/accept_viscor/<int:id>', methods=['POST'])
def accept_viscor(id):
    return redirect(url_for('viscor_issue'))

@app.route('/issued_stock')
def issued_stock():
    user_role = session.get('role')
    query = Reel.query.filter_by(status='Issued')
    
    if user_role == 'dataop1':
        query = query.filter(Reel.location == 'Viscor Lanka')
    elif user_role == 'dataop2':
        query = query.filter(Reel.location.like('Packwell W%'))
        
    return render_template('issued_stock.html', stocks=query.all())

@app.route('/finish_reel/<int:id>', methods=['POST'])
def finish_reel(id):
    return redirect(url_for('issued_stock'))

@app.route('/damage_sell_stock')
def damage_sell_stock():
    user_role = session.get('role')
    damaged_query = Reel.query.filter_by(status='Damaged')
    sold_query = Reel.query.filter_by(status='Sold')
    cond_query = ReelHistory.query.filter_by(action_type='COND_ISSUE')

    if user_role == 'dataop1':
        damaged_query = damaged_query.filter(Reel.location == 'Viscor Lanka')
        sold_query = sold_query.filter(Reel.location == 'Viscor Lanka')
        cond_query = cond_query.join(Reel).filter(Reel.location == 'Viscor Lanka')
    elif user_role == 'dataop2':
        damaged_query = damaged_query.filter(Reel.location.like('Packwell W%'))
        sold_query = sold_query.filter(Reel.location.like('Packwell W%'))
        cond_query = cond_query.join(Reel).filter(Reel.location.like('Packwell W%'))

    damaged_reels = damaged_query.all()
    sold_reels = sold_query.all()
    cond_logs = cond_query.order_by(ReelHistory.timestamp.desc()).all()
    
    return render_template('damage_sell_stock.html', damaged_reels=damaged_reels, sold_reels=sold_reels, cond_logs=cond_logs)

@app.route('/mark_damage_sell/<int:id>', methods=['POST'])
def mark_damage_sell(id):
    return redirect(url_for('damage_sell_stock'))

@app.route('/finished_usage_stock')
def finished_usage_stock():
    user_role = session.get('role')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    finished_data = []
    logs_data = []

    try:
        finished_query = Reel.query.filter_by(status='Finished')
        logs_query = ReelHistory.query.join(Reel).filter(ReelHistory.action_type.in_(['PARTIAL RETURN', 'FINISHED']))

        if user_role == 'dataop1':
            finished_query = finished_query.filter(Reel.location == 'Viscor Lanka')
            logs_query = logs_query.filter(Reel.location == 'Viscor Lanka')
        elif user_role == 'dataop2':
            finished_query = finished_query.filter(Reel.location.like('Packwell W%'))
            logs_query = logs_query.filter(Reel.location.like('Packwell W%'))

        if start_date and end_date:
            try:
                s_date = datetime.strptime(start_date, '%Y-%m-%d')
                e_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                
                finished_query = finished_query.filter(Reel.updated_at >= s_date, Reel.updated_at < e_date)
                logs_query = logs_query.filter(ReelHistory.timestamp >= s_date, ReelHistory.timestamp < e_date)
            except ValueError:
                pass

        finished_data = finished_query.all()
        logs_data = logs_query.all()

    except Exception as e:
        db.session.rollback() 
        print(f"Database Error in finished_usage_stock: {e}")
        flash("දත්ත පද්ධතියෙන් දත්ත ලබාගැනීමේදී දෝෂයක් සිදුවිය.", "danger")

    return render_template('finished_usage_stock.html',
                           finished_query=finished_data,
                           logs_query=logs_data,
                           start_date=start_date,
                           end_date=end_date)

@app.route('/update_finished_sr/<int:id>', methods=['POST'])
def update_finished_sr(id):
    if session.get('role') != 'dataop1':
        flash("Unauthorized Access", "danger")
        return redirect(url_for('finished_usage_stock'))
    return redirect(url_for('finished_usage_stock'))

if __name__ == '__main__':
    app.run(debug=True)
