from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
# Session සහ Flash messages සඳහා රහස්‍ය යතුරක් (මෙය වෙනස් නොකර තබාගන්න)
app.secret_key = "your_super_secret_key_here" 

# --- Database Configuration ---
database_url = os.environ.get('DATABASE_URL')

if database_url and database_url.startswith("mysql://"):
    database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
elif not database_url:
    database_url = "sqlite:///local_test.db"

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

with app.app_context():
    db.create_all()

# --- Routes ---

@app.route('/')
def login():
    # දැනටමත් login වෙලා නම් කෙලින්ම dashboard එකට යවන්න
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login_submit', methods=['POST'])
def login_submit():
    username = request.form.get('username')
    password = request.form.get('password')
    
    # දැනට සරලව ඕනෑම username/password එකක් login වෙන්න දීලා තියෙනවා.
    # (පසුව මෙය Database එක හරහා check වෙන විදිහට හදාගන්න පුළුවන්)
    if username and password:
        session['username'] = username # User ව මතක තියාගන්නවා (Session)
        return redirect(url_for('dashboard')) # Dashboard එකට යවනවා
    else:
        flash("කරුණාකර Username සහ Password ඇතුලත් කරන්න.")
        return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    # Login වෙලා නැත්නම් Dashboard එකට යන්න දෙන්නේ නැහැ
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Login වෙලා නම් dashboard.html එක පෙන්වනවා
    return render_template('dashboard.html', username=session['username'])

@app.route('/logout')
def logout():
    # Session එකෙන් user ව අයින් කරනවා (Logout)
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)