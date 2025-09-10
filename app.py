from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, random, smtplib
from email.mime.text import MIMEText
from functools import wraps

# ----------------- CONFIG -----------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "yoursecretkey")  # Use env variable in production

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")

# ----------------- ENVIRONMENT VARIABLES -----------------
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")

if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
    raise RuntimeError("EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be set as environment variables!")

# ----------------- DATABASE -----------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_verified INTEGER DEFAULT 0,
                otp_code TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS marks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                score INTEGER,
                total INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        conn.commit()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------- EMAIL -----------------
def send_otp_email(email, otp):
    msg = MIMEText(f"Kode yo kwemeza konti yawe ni: {otp}")
    msg["Subject"] = "Kwemeza Konti yawe"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print("Email ntishoboye koherezwa:", e)
        return False

# ----------------- LOGIN REQUIRED -----------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Banza winjire mbere yo kubona iyi paji.", "warning")
            return redirect(url_for("auth"))
        return f(*args, **kwargs)
    return decorated

# ----------------- ROUTES -----------------
@app.route("/")
def root():
    if "user_id" in session:
        return redirect(url_for("home"))
    return redirect(url_for("publicpage"))

# ----------------- LOGIN / SIGNUP -----------------
@app.route("/auth", methods=["GET", "POST"])
def auth():
    if request.method == "POST":
        form_type = request.form.get("form_type")
        email = request.form["email"].strip()
        password = request.form["password"].strip()

        # SIGNUP
        if form_type == "signup":
            name = request.form["name"].strip()
            hashed_pw = generate_password_hash(password)
            otp = str(random.randint(100000, 999999))
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO users (name, email, password, otp_code) VALUES (?, ?, ?, ?)",
                        (name, email, hashed_pw, otp)
                    )
                    conn.commit()
                send_otp_email(email, otp)
                session["pending_email"] = email
                flash("Reba email yawe kugira ngo wemeze konti.", "success")
                return redirect(url_for("verify"))
            except sqlite3.IntegrityError:
                flash("Imeri isanzwe ibaho!", "error")
            return redirect(url_for("auth"))

        # LOGIN
        elif form_type == "login":
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE email=?", (email,))
                user = cursor.fetchone()

            if not user or not check_password_hash(user["password"], password):
                flash("Imeri cyangwa ijambo ry’ibanga ntabwo ari byo!", "error")
                return redirect(url_for("auth"))

            if user["is_verified"] == 0:
                flash("Banza wemeze konti yawe ukoresheje kode yo kuri email.", "warning")
                session["pending_email"] = email
                return redirect(url_for("verify"))

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("home"))

    return render_template("auth.html")

# ----------------- OTP Verification -----------------
@app.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "POST":
        otp = request.form["otp"].strip()
        email = session.get("pending_email")
        if not email:
            flash("Nta konti iri kwemezwa!", "error")
            return redirect(url_for("auth"))

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT otp_code FROM users WHERE email=?", (email,))
            record = cursor.fetchone()
            if record and record["otp_code"] == otp:
                cursor.execute("UPDATE users SET is_verified=1, otp_code=NULL WHERE email=?", (email,))
                conn.commit()
                session.pop("pending_email", None)
                flash("Konti yawe yemejwe! Injira.", "success")
                return redirect(url_for("auth"))
            else:
                flash("Kode ntabwo ari yo!", "error")

    return render_template("verify.html")

# ----------------- LOGOUT -----------------
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    flash("Wasohotse neza!", "success")
    return redirect(url_for("publicpage"))

# ----------------- PROTECTED PAGES -----------------
@app.route("/home")
@login_required
def home():
    return render_template("home.html", name=session["user_name"])

@app.route("/index")
@login_required
def index():
    return render_template("index.html", name=session["user_name"])

@app.route("/exam")
@login_required
def exam():
    return render_template("exam.html", name=session["user_name"])

@app.route("/ibibazo")
@login_required
def ibibazo():
    return render_template("ibibazo.html", name=session["user_name"])

@app.route("/ibyigwa")
@login_required
def ibyigwa():
    return render_template("ibyigwa.html", name=session["user_name"])

@app.route("/welcom2")
@login_required
def welcom2():
    return render_template("welcom2.html", name=session["user_name"])

# ----------------- PUBLIC PAGES -----------------
@app.route("/publicpage")
def publicpage():
    return render_template("publicpage.html")

@app.route("/welcom")
def welcom():
    return render_template("welcom.html")

@app.route("/twandikire")
def twandikire():
    return render_template("twandikire.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

# ----------------- MARKS -----------------
@app.route("/save_score", methods=["POST"])
@login_required
def save_score():
    data = request.get_json()
    score = data.get("score")
    total = data.get("total")
    if score is None or total is None:
        return {"status": "error", "message": "Invalid data"}, 400

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE id=?", (session["user_id"],))
        user = cursor.fetchone()
        if user:
            cursor.execute(
                "INSERT INTO marks (user_id, score, total) VALUES (?, ?, ?)",
                (session["user_id"], score, total)
            )
            conn.commit()
            return {"status": "success"}
    return {"status": "error", "message": "User not found"}, 404

@app.route("/amanota")
@login_required
def amanota():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT score, total, timestamp FROM marks WHERE user_id=? ORDER BY timestamp DESC",
            (session["user_id"],)
        )
        marks = cursor.fetchall()
    return render_template("amanota.html", marks=marks)

# ----------------- RUN -----------------
if __name__ == "__main__":
    print("Registered endpoints:")
    for endpoint in sorted(app.view_functions.keys()):
        print(" -", endpoint)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
