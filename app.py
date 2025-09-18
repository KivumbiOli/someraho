from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os, random, smtplib
from email.mime.text import MIMEText
from functools import wraps
from datetime import datetime
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "yoursecretkey")  # Use env secret key in production

# ----------------- MONGODB CONNECTION -----------------
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["myDatabase"]   # Choose your database name
users_col = db["users"]
marks_col = db["marks"]
contacts_col = db["contacts"]

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

            if users_col.find_one({"email": email}):
                flash("Imeri isanzwe ibaho!", "error")
                return redirect(url_for("auth"))

            users_col.insert_one({
                "name": name,
                "email": email,
                "password": hashed_pw,
                "is_verified": 0,
                "otp_code": otp
            })
            send_otp_email(email, otp)
            session["pending_email"] = email
            flash("Reba email yawe kugira ngo wemeze konti.", "success")
            return redirect(url_for("verify"))

        # LOGIN
        elif form_type == "login":
            user = users_col.find_one({"email": email})
            if not user or not check_password_hash(user["password"], password):
                flash("Imeri cyangwa ijambo ry’ibanga ntabwo ari byo!", "error")
                return redirect(url_for("auth"))

            if user.get("is_verified", 0) == 0:
                flash("Banza wemeze konti yawe ukoresheje kode yo kuri email.", "warning")
                session["pending_email"] = email
                return redirect(url_for("verify"))

            session["user"] = user["name"]
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

        user = users_col.find_one({"email": email})
        if user and user.get("otp_code") == otp:
            users_col.update_one({"email": email}, {"$set": {"is_verified": 1}, "$unset": {"otp_code": ""}})
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

    user = users_col.find_one({"name": session["user"]})
    if user:
        marks_col.insert_one({
            "user_id": user["_id"],
            "score": score,
            "total": total,
            "timestamp": datetime.utcnow()
        })
        return {"status": "success"}
    return {"status": "error", "message": "User not found"}, 404

@app.route("/amanota")
@login_required
def amanota():
    user = users_col.find_one({"name": session["user"]})
    marks = []
    if user:
        marks = list(marks_col.find({"user_id": user["_id"]}).sort("timestamp", -1))
    return render_template("amanota.html", marks=marks)

# ----------------- CONTACT FORM -----------------
from datetime import datetime
@app.route("/contact", methods=["POST"])
def contact():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    message = request.form.get("message", "").strip()

    if not name or not email or not message:
        flash("Nyamuneka wuzuze izina, email, n'ubutumwa.", "error")
        return redirect(url_for("twandikire"))

    try:
        contacts_col.insert_one({
            "name": name,
            "email": email,
            "phone": phone,
            "message": message,
            "timestamp": datetime.utcnow()
        })
        flash("Ubutumwa bwawe bwoherejwe neza!", "success")
    except Exception as e:
        print("Contact form save failed:", e)
        flash("Habaye ikibazo mu kohereza ubutumwa!", "error")

    return redirect(url_for("twandikire"))


# ----------------- RUN -----------------
if __name__ == "__main__":
    print("Registered endpoints:")
    for endpoint in sorted(app.view_functions.keys()):
        print(" -", endpoint)
    app.run(debug=True)





