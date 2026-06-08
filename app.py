import os
from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

# ---------------------------------------------------------
# ENVIRONMENT VARIABLES CONFIGURATION
# ---------------------------------------------------------
# Render Dashboard එකේ Environment Variables වලට මේවා ඇතුළත් කරන්න.
# නැතහොත් Local එකේදී .env file එකෙන් කියවනු ඇත.

app.secret_key = os.environ.get('SECRET_KEY', 'super_secure_viscor_key_2026')

DB_HOST = os.environ.get('DB_HOST', 'mysql-3e9936af-viscorquality-0270.g.aivencloud.com')
DB_USER = os.environ.get('DB_USER', 'avnadmin')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'AVNS_gHRTw4Hzio_XlhXcm7d')
DB_NAME = os.environ.get('DB_NAME', 'defaultdb')

# ප්‍රධාන නිවැරදි කිරීම: Port එක String එකක් නොව අනිවාර්යයෙන්ම Integer (int) එකක් විය යුතුය.
try:
    DB_PORT = int(os.environ.get('DB_PORT', 28643))
except (ValueError, TypeError):
    DB_PORT = 28643


# Database එකට සම්බන්ධ වන Function එක
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
        return connection
    except Error as e:
        print(f"Database Connection Error: {e}")
        return None

# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------

# Render App එක Live ද කියා බැලීමට (Health Check) 'HEAD' request එවයි.
# එම නිසා methods වලට HEAD ඇතුළත් කර එය handle කර ඇත.
@app.route('/', methods=['GET', 'POST', 'HEAD'])
def login():
    # 1. Render Health Check සඳහා HEAD request වලට පිළිතුරු දීම
    if request.method == 'HEAD':
        return '', 200

    # 2. POST request (User ලොගින් වීමට උත්සාහ කරන විට)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = get_db_connection()
        if db is None:
            return "Database එකට සම්බන්ධ වීමට නොහැක. කරුණාකර පසුව උත්සාහ කරන්න.", 500
            
        try:
            cursor = db.cursor(dictionary=True)
            # මෙතැනින් ඔබේ ලොගින් පරීක්ෂා කිරීමේ SQL Query එක ලියන්න
            # උදාහරණ: cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            cursor.close()
            db.close()
        except Error as e:
            print(f"Query Error: {e}")
            return "දත්ත පද්ධතියේ දෝෂයකි.", 500
        
    # 3. GET request (පිටුව සාමාන්‍ය පරිදි Load වන විට)
    # වැදගත්: ඔබේ ව්‍යාපෘතියේ 'templates' නමින් folder එකක් තිබිය යුතු අතර login.html තිබිය යුත්තේ ඒ තුළයි.
    return render_template('login.html')

if __name__ == '__main__':
    # Local පරිගණකයේ run කිරීම සඳහා (Render එකේදී gunicorn මඟින් run වේ)
    app.run(debug=True, port=10000)
