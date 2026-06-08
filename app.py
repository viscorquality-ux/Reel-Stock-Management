from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = 'viscor_packwell_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reel_management.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Colombo Timezone සකස් කිරීම
colombo_tz = pytz.timezone('Asia/Colombo')

# --- Database Models ---
class Reel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reel_number = db.Column(db.String(100), unique=True, nullable=False)
    size_cm = db.Column(db.Float, nullable=False)
    weight_kg = db.Column(db.Float, nullable=False) 
    paper_name = db.Column(db.String(50), nullable=False) 
    status = db.Column(db.String(30), default='Full Reel') # 'Full Reel', 'Used Reel', 'Issued', 'Finished'
    gate_pass_number = db.Column(db.String(50), nullable=True)
    sr_number = db.Column(db.String(50), nullable=True) 
    routing_type = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz), onupdate=lambda: datetime.now(colombo_tz))
    
    histories = db.relationship('ReelHistory', backref='reel', lazy='joined', cascade="all, delete-orphan")

class ReelHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reel.id'), nullable=False)
    usage_details = db.Column(db.String(255), nullable=False)
    weight_used = db.Column(db.Float, default=0.0)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))

# --- Role Management (Simulation සඳහා) ---
@app.before_request
def set_mock_session():
    # පරීක්ෂණ කටයුතු සඳහා භූමිකාව මෙතනින් වෙනස් කර බැලිය හැක: 'dataop1', 'super1', 'dataop2', 'super2'
    if 'role' not in session:
        session['role'] = 'dataop1' 

# --- Routes ---

# Home Route (404 Error Fix: ප්‍රධාන ලින්ක් එකට ආවම Active Stock එකට redirect කිරීම)
@app.route('/')
def home():
    return redirect(url_for('active_stock'))

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
        reel_number = request.form['reel_number']
        size_cm = request.form['size_cm']
        weight_kg = request.form['weight_kg']
        paper_name = request.form['paper_name']
        status = request.form['status'] 
        gate_pass_number = request.form['gate_pass_number']
        
        routing_type = "Viscor Lanka Line" if user_role == 'dataop1' else request.form.get('routing_type', '')

        new_reel = Reel(
            reel_number=reel_number,
            size_cm=float(size_cm),
            weight_kg=float(weight_kg),
            paper_name=paper_name,
            status=status,
            gate_pass_number=gate_pass_number,
            routing_type=routing_type
        )
        db.session.add(new_reel)
        db.session.commit()
        
        initial_log = ReelHistory(reel_id=new_reel.id, usage_details=f"Initial Stock added as {status}")
        db.session.add(initial_log)
        db.session.commit()
        
        flash(f"Reel {reel_number} Successfully Added to the System!", "success")
        return redirect(url_for('active_stock'))
        
    return render_template('add_stock.html', user_role=user_role)

@app.route('/return_partial/<int:id>', methods=['POST'])
def return_partial(id):
    reel = Reel.query.get_or_404(id)
    used_weight = float(request.form['used_weight'])
    
    old_weight = reel.weight_kg
    reel.weight_kg = max(0.0, old_weight - used_weight)
    reel.status = 'Used Reel'
    
    history_log = ReelHistory(
        reel_id=reel.id,
        usage_details=f"Partial Return. Used: {used_weight} kg. Remaining: {reel.weight_kg} kg.",
        weight_used=used_weight
    )
    db.session.add(history_log)
    db.session.commit()
    
    flash("Reel moved to Used Stock with updated usage history.", "info")
    return redirect(url_for('active_stock'))

@app.route('/finished_usage_stock', methods=['GET', 'POST'])
def finished_usage_stock():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    finished_query = Reel.query.filter_by(status='Finished')
    usage_query = ReelHistory.query.join(Reel).filter(Reel.status == 'Used Reel')
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
        
        finished_query = finished_query.filter(Reel.updated_at.between(start_date, end_date))
        usage_query = usage_query.filter(ReelHistory.timestamp.between(start_date, end_date))

    finished_reels = finished_query.all()
    usage_logs = usage_query.all()
    
    total_finished_weight = sum(r.weight_kg for r in finished_reels)
    total_used_weight_log = sum(log.weight_used for log in usage_logs)
    
    return render_template('finished_usage_stock.html', 
                           finished_reels=finished_reels, usage_logs=usage_logs,
                           total_finished_weight=total_finished_weight, total_used_weight_log=total_used_weight_log,
                           start_date=start_date_str, end_date=end_date_str)

@app.route('/update_sr_number/<int:id>', methods=['POST'])
def update_sr_number(id):
    if session.get('role') != 'dataop1':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('finished_usage_stock'))
        
    reel = Reel.query.get_or_404(id)
    sr_number = request.form['sr_number']
    reel.sr_number = sr_number
    db.session.commit()
    
    flash(f"SR Number '{sr_number}' updated successfully for Reel {reel.reel_number}.", "success")
    return redirect(url_for('finished_usage_stock'))

@app.route('/viscor_issue')
def viscor_issue():
    pending_reels = Reel.query.all()
    return render_template('viscor_issue.html', reels=pending_reels)

# Gunicorn හරහා Render එකේ Run වන විටත් Database tables සෑදීම සඳහා මෙය එළියට ගෙන ඇත (New Fix)
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)