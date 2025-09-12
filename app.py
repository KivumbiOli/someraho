from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os, random, smtplib
from email.mime.text import MIMEText
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# ----------------- APP CONFIG -----------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "yoursecretkey")

# Database config (Render provides DATABASE_URL)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ----------------- MODELS -----------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(10))

class Mark(db.Model):
    __tablename__ = "marks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    score = db.Column(db.Integer)
    total = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("marks", lazy=True))

# Create tables on startup (if not exist)
with app.app_context():
    db.create_all()

# ----------------- EMAIL -----------------
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")

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

# ----------------- CONTEXT PROCESSOR -----------------
@app.context_processor
def inject_user_name():
    return dict(name=session.get("user"))

# ----------------- LOGIN REQUIRED -----------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            flash("Banza winjire mbere yo kubona iyi paji.", "warning")
            return redirect(url_for("auth"))
        return f(*args, **kwargs)
    return decorated

# ----------------- ROUTES -----------------
@app.route("/")
def root():
    if "user" in session:
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

            # check if email exists
            existing = User.query.filter_by(email=email).first()
            if existing:
                flash("Imeri isanzwe ibaho!", "error")
                return redirect(url_for("auth"))

            new_user = User(name=name, email=email, password=hashed_pw, otp_code=otp)
            db.session.add(new_user)
            db.session.commit()

            send_otp_email(email, otp)
            session["pending_email"] = email
            flash("Reba email yawe kugira ngo wemeze konti.", "success")
            return redirect(url_for("verify"))

        # LOGIN
        elif form_type == "login":
            user = User.query.filter_by(email=email).first()

            if not user or not check_password_hash(user.password, password):
                flash("Imeri cyangwa ijambo ry’ibanga ntabwo ari byo!", "error")
                return redirect(url_for("auth"))

            if not user.is_verified:
                flash("Banza wemeze konti yawe ukoresheje kode yo kuri email.", "warning")
                session["pending_email"] = email
                return redirect(url_for("verify"))

            session["user"] = user.name
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

        user = User.query.filter_by(email=email).first()
        if user and user.otp_code == otp:
            user.is_verified = True
            user.otp_code = None
            db.session.commit()
            session.pop("pending_email", None)
            flash("Konti yawe yemejwe! Injira.", "success")
            return redirect(url_for("auth"))
        else:
            flash("Kode ntabwo ari yo!", "error")

    return render_template("verify.html")

# ----------------- LOGOUT -----------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Wasohotse neza!", "success")
    return redirect(url_for("publicpage"))

# ----------------- PROTECTED PAGES -----------------
@app.route("/home")
@login_required
def home():
    return render_template("home.html")

@app.route("/index")
@login_required
def index():
    return render_template("index.html")

@app.route("/exam")
@login_required
def exam():
    return render_template("exam.html")

@app.route("/ibibazo")
@login_required
def ibibazo():
    return render_template("ibibazo.html")

@app.route("/ibyigwa")
@login_required
def ibyigwa():
    return render_template("ibyigwa.html")

@app.route("/welcom2")
@login_required
def welcom2():
    return render_template("welcom2.html")

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

    user = User.query.filter_by(name=session["user"]).first()
    if not user:
        return {"status": "error", "message": "User not found"}, 404

    new_mark = Mark(user_id=user.id, score=score, total=total)
    db.session.add(new_mark)
    db.session.commit()

    return {"status": "success"}

@app.route("/amanota")
@login_required
def amanota():
    user = User.query.filter_by(name=session["user"]).first()
    marks = []
    if user:
        marks = Mark.query.filter_by(user_id=user.id).order_by(Mark.timestamp.desc()).all()
    return render_template("amanota.html", marks=marks)

# ----------------- RUN -----------------
if __name__ == "__main__":
    print("Registered endpoints:")
    for endpoint in sorted(app.view_functions.keys()):
        print(" -", endpoint)
    app.run(debug=True)

