from flask import render_template, Flask, request, jsonify
from database import db, User, Prediction, PeriodLog
import pickle
import os
from datetime import datetime, timedelta
import json

app = Flask(__name__)

# database config
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///shecare.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

# load models
pcos_model = pickle.load(open("model/pcos_model.pkl", "rb"))
anemia_model = pickle.load(open("model/anemia_model.pkl", "rb"))
bc_model = pickle.load(open("model/breast_cancer_model.pkl", "rb"))


# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/history-page/<int:user_id>")
def history_page(user_id):
    return render_template("history.html")


@app.route("/period-tracker")
def period_tracker():
    return render_template("period_tracker.html")


# ---------------- API ENDPOINTS ----------------

@app.route("/register", methods=["POST"])
def register():
    data = request.json

    # Check if user already exists
    existing_user = User.query.filter_by(email=data["email"]).first()
    if existing_user:
        return jsonify({"status": "error", "message": "User already exists"}), 400

    user = User(
        name=data["name"],
        email=data["email"],
        password=data["password"],  # In production, hash this password!
        is_anonymous=False
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({"status": "registered", "user_id": user.id})


@app.route("/login", methods=["POST"])
def login():
    data = request.json

    user = User.query.filter_by(email=data["email"]).first()

    if user and user.password == data["password"]:
        return jsonify({
            "status": "success",
            "user_id": user.id,
            "name": user.name
        })

    return jsonify({"status": "failed", "message": "Invalid credentials"}), 401


@app.route("/anonymous-login", methods=["POST"])
def anonymous():
    user = User(
        name="Anonymous",
        email=None,
        password=None,
        is_anonymous=True
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "user_id": user.id,
        "anonymous": True
    })


@app.route("/predict", methods=["POST"])
def predict():
    data = request.json

    # Validate user_id
    user = User.query.get(data["user_id"])
    if not user:
        return jsonify({"status": "error", "message": "Invalid user"}), 400

    features = [[
        float(data["age"]),
        float(data["BMI"]),
        float(data["cycle_variation"]),
        float(data["acne_severity"]),
        float(data["hair_growth"]),
        float(data["fatigue"]),
        float(data["hemoglobin"]),
        float(data["breast_lump"]),
        float(data["breast_pain"])
    ]]

    pcos = int(pcos_model.predict(features)[0])
    anemia = int(anemia_model.predict(features)[0])
    bc = int(bc_model.predict(features)[0])

    prediction = Prediction(
        user_id=data["user_id"],
        pcos_risk=pcos,
        anemia_risk=anemia,
        breast_cancer_risk=bc
    )

    db.session.add(prediction)
    db.session.commit()

    return jsonify({
        "pcos_risk": pcos,
        "anemia_risk": anemia,
        "breast_cancer_risk": bc
    })


@app.route("/history/<int:user_id>")
def history(user_id):
    predictions = Prediction.query.filter_by(user_id=user_id).order_by(Prediction.created_at.desc()).all()

    result = []

    for p in predictions:
        result.append({
            "id": p.id,
            "pcos": p.pcos_risk,
            "anemia": p.anemia_risk,
            "breast_cancer": p.breast_cancer_risk,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(p, 'created_at') else None
        })

    return jsonify(result)


# ---------------- PERIOD TRACKER ----------------

@app.route("/period/log", methods=["POST"])
def log_period():
    data = request.json
    
    # Validate user
    user = User.query.get(data["user_id"])
    if not user:
        return jsonify({"status": "error", "message": "Invalid user"}), 400
    
    # Parse dates
    start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
    end_date = datetime.strptime(data["end_date"], "%Y-%m-%d").date() if data.get("end_date") else None
    
    # Calculate cycle length if there's a previous period
    previous_period = PeriodLog.query.filter_by(user_id=data["user_id"]).order_by(PeriodLog.start_date.desc()).first()
    cycle_length = None
    if previous_period and previous_period.start_date:
        cycle_length = (start_date - previous_period.start_date).days
    
    period_log = PeriodLog(
        user_id=data["user_id"],
        start_date=start_date,
        end_date=end_date,
        flow_intensity=data.get("flow_intensity"),
        symptoms=json.dumps(data.get("symptoms", [])),
        notes=data.get("notes"),
        cycle_length=cycle_length
    )
    
    db.session.add(period_log)
    db.session.commit()
    
    return jsonify({
        "status": "success",
        "period_id": period_log.id,
        "cycle_length": cycle_length
    })


@app.route("/period/update/<int:period_id>", methods=["PUT"])
def update_period(period_id):
    data = request.json
    
    period_log = PeriodLog.query.get(period_id)
    if not period_log:
        return jsonify({"status": "error", "message": "Period log not found"}), 404
    
    if data.get("end_date"):
        period_log.end_date = datetime.strptime(data["end_date"], "%Y-%m-%d").date()
    if data.get("flow_intensity"):
        period_log.flow_intensity = data["flow_intensity"]
    if data.get("symptoms"):
        period_log.symptoms = json.dumps(data["symptoms"])
    if data.get("notes"):
        period_log.notes = data["notes"]
    
    db.session.commit()
    
    return jsonify({"status": "success"})


@app.route("/period/delete/<int:period_id>", methods=["DELETE"])
def delete_period(period_id):
    period_log = PeriodLog.query.get(period_id)
    if not period_log:
        return jsonify({"status": "error", "message": "Period log not found"}), 404
    
    db.session.delete(period_log)
    db.session.commit()
    
    return jsonify({"status": "success"})


@app.route("/period/history/<int:user_id>")
def period_history(user_id):
    periods = PeriodLog.query.filter_by(user_id=user_id).order_by(PeriodLog.start_date.desc()).all()
    
    result = []
    for p in periods:
        result.append({
            "id": p.id,
            "start_date": p.start_date.strftime("%Y-%m-%d"),
            "end_date": p.end_date.strftime("%Y-%m-%d") if p.end_date else None,
            "flow_intensity": p.flow_intensity,
            "symptoms": json.loads(p.symptoms) if p.symptoms else [],
            "notes": p.notes,
            "cycle_length": p.cycle_length,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return jsonify(result)


@app.route("/period/predictions/<int:user_id>")
def period_predictions(user_id):
    # Get last 3 periods to calculate average cycle
    periods = PeriodLog.query.filter_by(user_id=user_id).order_by(PeriodLog.start_date.desc()).limit(3).all()
    
    if len(periods) < 2:
        return jsonify({"message": "Need at least 2 periods to predict", "predictions": []})
    
    # Calculate average cycle length
    cycle_lengths = [p.cycle_length for p in periods if p.cycle_length]
    if not cycle_lengths:
        return jsonify({"message": "Insufficient data", "predictions": []})
    
    avg_cycle = sum(cycle_lengths) / len(cycle_lengths)
    
    # Predict next 3 periods
    last_period = periods[0]
    predictions = []
    
    for i in range(1, 4):
        next_start = last_period.start_date + timedelta(days=int(avg_cycle * i))
        fertile_start = next_start - timedelta(days=14)
        fertile_end = next_start - timedelta(days=10)
        ovulation_day = next_start - timedelta(days=14)
        
        predictions.append({
            "period_number": i,
            "predicted_start": next_start.strftime("%Y-%m-%d"),
            "fertile_window_start": fertile_start.strftime("%Y-%m-%d"),
            "fertile_window_end": fertile_end.strftime("%Y-%m-%d"),
            "ovulation_day": ovulation_day.strftime("%Y-%m-%d"),
            "avg_cycle_length": round(avg_cycle, 1)
        })
    
    return jsonify({
        "avg_cycle_length": round(avg_cycle, 1),
        "predictions": predictions
    })


@app.route("/period/stats/<int:user_id>")
def period_stats(user_id):
    periods = PeriodLog.query.filter_by(user_id=user_id).order_by(PeriodLog.start_date.desc()).all()
    
    if not periods:
        return jsonify({"message": "No data available"})
    
    # Calculate statistics
    cycle_lengths = [p.cycle_length for p in periods if p.cycle_length]
    period_durations = [(p.end_date - p.start_date).days + 1 for p in periods if p.end_date]
    
    stats = {
        "total_periods_logged": len(periods),
        "avg_cycle_length": round(sum(cycle_lengths) / len(cycle_lengths), 1) if cycle_lengths else None,
        "shortest_cycle": min(cycle_lengths) if cycle_lengths else None,
        "longest_cycle": max(cycle_lengths) if cycle_lengths else None,
        "avg_period_duration": round(sum(period_durations) / len(period_durations), 1) if period_durations else None,
        "last_period": periods[0].start_date.strftime("%Y-%m-%d") if periods else None
    }
    
    return jsonify(stats)


@app.route("/period/current-phase/<int:user_id>")
def current_cycle_phase(user_id):
    """Identify which phase of the menstrual cycle the user is currently in"""
    
    # Get the most recent period
    last_period = PeriodLog.query.filter_by(user_id=user_id).order_by(PeriodLog.start_date.desc()).first()
    
    if not last_period:
        return jsonify({"message": "No period data available", "phase": None})
    
    # Get average cycle length
    periods = PeriodLog.query.filter_by(user_id=user_id).order_by(PeriodLog.start_date.desc()).limit(3).all()
    cycle_lengths = [p.cycle_length for p in periods if p.cycle_length]
    avg_cycle = sum(cycle_lengths) / len(cycle_lengths) if cycle_lengths else 28
    
    today = datetime.now().date()
    days_since_period = (today - last_period.start_date).days
    
    # Determine cycle phase
    phase = None
    phase_description = ""
    days_in_phase = 0
    phase_color = ""
    
    if days_since_period < 0:
        # Future period logged
        phase = "Unknown"
        phase_description = "Period date is in the future"
        phase_color = "#6c757d"
    elif days_since_period <= 5:
        # Menstrual phase
        phase = "Menstruation"
        phase_description = "Your period is happening now. Take it easy and stay hydrated."
        days_in_phase = days_since_period + 1
        phase_color = "#dc3545"
    elif days_since_period <= 13:
        # Follicular phase
        phase = "Follicular Phase"
        phase_description = "Your body is preparing for ovulation. Energy levels may be rising."
        days_in_phase = days_since_period - 5
        phase_color = "#17a2b8"
    elif days_since_period <= 16:
        # Ovulation phase
        phase = "Ovulation"
        phase_description = "Most fertile time. You may feel energetic and confident."
        days_in_phase = days_since_period - 13
        phase_color = "#28a745"
    elif days_since_period <= avg_cycle:
        # Luteal phase
        phase = "Luteal Phase"
        phase_description = "Your body is preparing for your next period. PMS symptoms may occur."
        days_in_phase = days_since_period - 16
        phase_color = "#ffc107"
    else:
        # Period is late
        phase = "Late Period"
        days_late = days_since_period - int(avg_cycle)
        phase_description = f"Your period is {days_late} day(s) late based on your average cycle."
        phase_color = "#6c757d"
    
    # Calculate next period prediction
    next_period_date = last_period.start_date + timedelta(days=int(avg_cycle))
    days_until_period = (next_period_date - today).days
    
    return jsonify({
        "current_phase": phase,
        "description": phase_description,
        "days_in_phase": days_in_phase,
        "days_since_last_period": days_since_period,
        "days_until_next_period": days_until_period,
        "next_period_date": next_period_date.strftime("%Y-%m-%d"),
        "phase_color": phase_color,
        "avg_cycle_length": round(avg_cycle, 1)
    })


if __name__ == "__main__":
    app.run(debug=True)