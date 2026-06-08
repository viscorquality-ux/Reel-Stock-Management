from flask import Flask, render_template, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
# flash messages සහ session සඳහා රහස්‍ය යතුරක්
app.secret_key = "super_secure_viscor_key_2026" 

# --- Database Configuration ---
# Render Environment Variables වලින් DATABASE_URL එක ලබා ගැනීම
database_url = os.environ.get('DATABASE_URL')

# Aiven MySQL URI එක SQLAlchemy වලට ගැලපෙන ලෙස සැකසීම
if database_url and database_url.startswith("mysql://"):
    database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
elif not database_url:
    # Render එකේ DATABASE_URL එක add කරලා නැත්නම් හෝ Local test කරනවා නම්
    database_url = "sqlite:///local_test.db"

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database එක Initialize කිරීම
db = SQLAlchemy(app)

# --- Database Models (උදාහරණයක්) ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

# App එක run වෙද්දී අලුතින් tables හැදීමට (දැනටමත් නැත්නම් පමණක්)
with app.app_context():
    db.create_all()

# --- Routes ---

@app.route('/')
def login():
    # templates/login.html ගොනුව අනිවාර්යයෙන් තිබිය යුතුය
    return render_template('login.html')

@app.route('/login_submit', methods=['POST'])
def login_submit():
    username = request.form.get('username')
    password = request.form.get('password')
    
    # මෙතනට ඔබගේ login check කරන logic එක එකතු කරන්න පුළුවන්
    # උදාහරණයක් ලෙස:
    # user = User.query.filter_by(username=username, password=password).first()
    
    return f"Login submitted for {username}!"

if __name__ == '__main__':
    # Render සඳහා port එක සහ host සැකසීම
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)