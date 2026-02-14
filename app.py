from flask import render_template, Flask, request, jsonify
from database import db, User, Prediction, PeriodLog
import pickle
import os
from datetime import datetime, timedelta
import json

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///shecare.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

pcos_model = pickle.load(open("model/pcos_model.pkl", "rb"))
anemia_model = pickle.load(open("model/anemia_model.pkl", "rb"))
bc_model = pickle.load(open("model/breast_cancer_model.pkl", "rb"))


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

@app.route("/nutrition-planner")
def nutrition_planner():
    return render_template("nutrition_planner.html")

@app.route("/lifestyle")
def lifestyle():
    return render_template("lifestyle.html")


@app.route("/register", methods=["POST"])
def register():
    data = request.json
    existing_user = User.query.filter_by(email=data["email"]).first()
    if existing_user:
        return jsonify({"status": "error", "message": "User already exists"}), 400
    user = User(name=data["name"], email=data["email"], password=data["password"], is_anonymous=False)
    db.session.add(user)
    db.session.commit()
    return jsonify({"status": "registered", "user_id": user.id})


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(email=data["email"]).first()
    if user and user.password == data["password"]:
        return jsonify({"status": "success", "user_id": user.id, "name": user.name})
    return jsonify({"status": "failed", "message": "Invalid credentials"}), 401


@app.route("/anonymous-login", methods=["POST"])
def anonymous():
    user = User(name="Anonymous", email=None, password=None, is_anonymous=True)
    db.session.add(user)
    db.session.commit()
    return jsonify({"user_id": user.id, "anonymous": True})


@app.route("/predict", methods=["POST"])
def predict():
    data = request.json
    user = User.query.get(data["user_id"])
    if not user:
        return jsonify({"status": "error", "message": "Invalid user"}), 400
    features = [[
        float(data["age"]), float(data["BMI"]), float(data["cycle_variation"]),
        float(data["acne_severity"]), float(data["hair_growth"]), float(data["fatigue"]),
        float(data["hemoglobin"]), float(data["breast_lump"]), float(data["breast_pain"])
    ]]
    pcos = int(pcos_model.predict(features)[0])
    anemia = int(anemia_model.predict(features)[0])
    bc = int(bc_model.predict(features)[0])
    prediction = Prediction(user_id=data["user_id"], pcos_risk=pcos, anemia_risk=anemia, breast_cancer_risk=bc)
    db.session.add(prediction)
    db.session.commit()
    return jsonify({"pcos_risk": pcos, "anemia_risk": anemia, "breast_cancer_risk": bc})


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


@app.route("/period/log", methods=["POST"])
def log_period():
    data = request.json
    user = User.query.get(data["user_id"])
    if not user:
        return jsonify({"status": "error", "message": "Invalid user"}), 400
    start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
    end_date = datetime.strptime(data["end_date"], "%Y-%m-%d").date() if data.get("end_date") else None
    previous_period = PeriodLog.query.filter_by(user_id=data["user_id"]).order_by(PeriodLog.start_date.desc()).first()
    cycle_length = None
    if previous_period and previous_period.start_date:
        cycle_length = (start_date - previous_period.start_date).days
    period_log = PeriodLog(
        user_id=data["user_id"], start_date=start_date, end_date=end_date,
        flow_intensity=data.get("flow_intensity"), symptoms=json.dumps(data.get("symptoms", [])),
        notes=data.get("notes"), cycle_length=cycle_length
    )
    db.session.add(period_log)
    db.session.commit()
    return jsonify({"status": "success", "period_id": period_log.id, "cycle_length": cycle_length})


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
    periods = PeriodLog.query.filter_by(user_id=user_id).order_by(PeriodLog.start_date.desc()).limit(3).all()
    if len(periods) < 2:
        return jsonify({"message": "Need at least 2 periods to predict", "predictions": []})
    cycle_lengths = [p.cycle_length for p in periods if p.cycle_length]
    if not cycle_lengths:
        return jsonify({"message": "Insufficient data", "predictions": []})
    avg_cycle = sum(cycle_lengths) / len(cycle_lengths)
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
    return jsonify({"avg_cycle_length": round(avg_cycle, 1), "predictions": predictions})


@app.route("/period/stats/<int:user_id>")
def period_stats(user_id):
    periods = PeriodLog.query.filter_by(user_id=user_id).order_by(PeriodLog.start_date.desc()).all()
    if not periods:
        return jsonify({"message": "No data available"})
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
    last_period = PeriodLog.query.filter_by(user_id=user_id).order_by(PeriodLog.start_date.desc()).first()
    if not last_period:
        return jsonify({"message": "No period data available", "phase": None})
    periods = PeriodLog.query.filter_by(user_id=user_id).order_by(PeriodLog.start_date.desc()).limit(3).all()
    cycle_lengths = [p.cycle_length for p in periods if p.cycle_length]
    avg_cycle = sum(cycle_lengths) / len(cycle_lengths) if cycle_lengths else 28
    today = datetime.now().date()
    days_since_period = (today - last_period.start_date).days
    phase = None
    phase_description = ""
    days_in_phase = 0
    phase_color = ""
    if days_since_period < 0:
        phase = "Unknown"
        phase_description = "Period date is in the future"
        phase_color = "#6c757d"
    elif days_since_period <= 5:
        phase = "Menstruation"
        phase_description = "Your period is happening now. Take it easy and stay hydrated."
        days_in_phase = days_since_period + 1
        phase_color = "#dc3545"
    elif days_since_period <= 13:
        phase = "Follicular Phase"
        phase_description = "Your body is preparing for ovulation. Energy levels may be rising."
        days_in_phase = days_since_period - 5
        phase_color = "#17a2b8"
    elif days_since_period <= 16:
        phase = "Ovulation"
        phase_description = "Most fertile time. You may feel energetic and confident."
        days_in_phase = days_since_period - 13
        phase_color = "#28a745"
    elif days_since_period <= avg_cycle:
        phase = "Luteal Phase"
        phase_description = "Your body is preparing for your next period. PMS symptoms may occur."
        days_in_phase = days_since_period - 16
        phase_color = "#ffc107"
    else:
        phase = "Late Period"
        days_late = days_since_period - int(avg_cycle)
        phase_description = "Your period is " + str(days_late) + " days late based on your average cycle."
        phase_color = "#6c757d"
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


@app.route("/nutrition/generate", methods=["POST"])
def generate_nutrition():
    data = request.json
    symptoms = data.get("symptoms", [])
    if not symptoms:
        return jsonify({"error": "No symptoms provided"}), 400
    
    nutrition_db = {
        "pcos": {
            "breakfast": [
                {"name": "Greek Yogurt with Berries", "ingredients": ["1 cup Greek yogurt", "1/2 cup berries", "2 tbsp almonds"], "benefits": "High protein helps manage insulin levels"},
                {"name": "Spinach Omelette", "ingredients": ["2 eggs", "1 cup spinach", "1 tbsp olive oil"], "benefits": "Protein stabilizes blood sugar"},
                {"name": "Quinoa Porridge", "ingredients": ["1/2 cup quinoa", "1 cup almond milk", "1 tsp cinnamon"], "benefits": "Low GI helps insulin sensitivity"}
            ],
            "lunch": [
                {"name": "Grilled Salmon with Vegetables", "ingredients": ["150g salmon", "1 cup broccoli", "bell peppers"], "benefits": "Omega-3s reduce inflammation"},
                {"name": "Chickpea Curry", "ingredients": ["1 cup chickpeas", "2 cups spinach", "turmeric"], "benefits": "Plant protein stabilizes blood sugar"}
            ],
            "dinner": [
                {"name": "Grilled Chicken with Sweet Potato", "ingredients": ["120g chicken", "1 sweet potato", "green beans"], "benefits": "Lean protein maintains energy"},
                {"name": "Lentil Stew", "ingredients": ["1 cup lentils", "mixed vegetables", "herbs"], "benefits": "High fiber manages insulin resistance"}
            ],
            "snacks": [
                {"name": "Apple with Almond Butter", "ingredients": ["1 apple", "2 tbsp almond butter"], "benefits": "Fiber and healthy fats"},
                {"name": "Mixed Nuts", "ingredients": ["10 almonds", "5 walnuts", "5 cashews"], "benefits": "Regulates hormones"}
            ],
            "tips": ["Choose low glycemic foods", "Include protein with meals", "Eat anti-inflammatory foods", "Limit processed foods", "Stay hydrated"]
        },
        "anemia": {
            "breakfast": [
                {"name": "Oatmeal with Apricots", "ingredients": ["1 cup oats", "dried apricots", "1 orange"], "benefits": "Iron with vitamin C"},
                {"name": "Spinach Tofu Scramble", "ingredients": ["100g tofu", "2 cups spinach", "tomatoes"], "benefits": "Iron-rich with vitamin C"}
            ],
            "lunch": [
                {"name": "Beef Lentil Soup", "ingredients": ["80g beef", "1/2 cup lentils", "vegetables"], "benefits": "Heme iron easily absorbed"},
                {"name": "Tuna Salad", "ingredients": ["100g tuna", "2 cups kale", "lemon"], "benefits": "Iron and B12"}
            ],
            "dinner": [
                {"name": "Liver with Onions", "ingredients": ["100g liver", "onions", "spinach", "rice"], "benefits": "Highest source of iron"},
                {"name": "Black Bean Bowl", "ingredients": ["1 cup black beans", "quinoa", "avocado"], "benefits": "Iron-rich plant protein"}
            ],
            "snacks": [
                {"name": "Pumpkin Seeds", "ingredients": ["1/4 cup pumpkin seeds", "dark chocolate"], "benefits": "Excellent iron sources"},
                {"name": "Strawberries with Seeds", "ingredients": ["1 cup strawberries", "sunflower seeds"], "benefits": "Vitamin C enhances absorption"}
            ],
            "tips": ["Combine iron with vitamin C", "Avoid tea with meals", "Include heme and non-heme iron", "Use cast iron cookware", "Take supplements as prescribed"]
        },
        "fatigue": {
            "breakfast": [
                {"name": "Banana Smoothie", "ingredients": ["1 banana", "1/2 cup oats", "peanut butter"], "benefits": "Complex carbs provide energy"},
                {"name": "Avocado Toast", "ingredients": ["whole grain bread", "avocado", "egg"], "benefits": "B vitamins support energy"}
            ],
            "lunch": [
                {"name": "Brown Rice with Chicken", "ingredients": ["brown rice", "120g chicken", "vegetables"], "benefits": "Sustained energy release"}
            ],
            "dinner": [
                {"name": "Salmon with Quinoa", "ingredients": ["150g salmon", "quinoa", "vegetables"], "benefits": "Omega-3s and B vitamins"}
            ],
            "snacks": [
                {"name": "Energy Balls", "ingredients": ["dates", "oats", "almond butter"], "benefits": "Natural sustained energy"}
            ],
            "tips": ["Eat frequent small meals", "Stay hydrated", "Include complex carbs", "Don't skip breakfast", "Limit caffeine"]
        },
        "cramps": {
            "breakfast": [
                {"name": "Ginger Tea with Toast", "ingredients": ["ginger tea", "whole grain toast", "almond butter"], "benefits": "Anti-inflammatory properties"}
            ],
            "lunch": [
                {"name": "Turmeric Chicken Stir-fry", "ingredients": ["chicken", "vegetables", "turmeric", "rice"], "benefits": "Reduces inflammation"}
            ],
            "dinner": [
                {"name": "Baked Salmon", "ingredients": ["150g salmon", "sweet potato", "spinach"], "benefits": "Omega-3s reduce cramping"}
            ],
            "snacks": [
                {"name": "Dark Chocolate", "ingredients": ["dark chocolate", "almonds"], "benefits": "Magnesium relaxes muscles"}
            ],
            "tips": ["Increase magnesium intake", "Stay hydrated", "Avoid excess salt", "Include ginger and turmeric", "Limit caffeine"]
        },
        "bloating": {
            "breakfast": [
                {"name": "Papaya with Yogurt", "ingredients": ["papaya", "Greek yogurt", "ginger", "mint"], "benefits": "Digestive enzymes"}
            ],
            "lunch": [
                {"name": "Grilled Chicken Salad", "ingredients": ["chicken", "cucumber", "tomato", "lemon"], "benefits": "Easily digestible"}
            ],
            "dinner": [
                {"name": "Vegetable Soup", "ingredients": ["carrots", "zucchini", "ginger", "broth"], "benefits": "Aids digestion"}
            ],
            "snacks": [
                {"name": "Fennel Tea", "ingredients": ["fennel tea", "rice crackers"], "benefits": "Relieves bloating"}
            ],
            "tips": ["Eat slowly", "Avoid carbonated drinks", "Limit sodium", "Include probiotics", "Drink herbal tea"]
        },
        "mood_swings": {
            "breakfast": [
                {"name": "Omega-3 Smoothie", "ingredients": ["spinach", "banana", "chia seeds", "walnuts"], "benefits": "Supports brain health"}
            ],
            "lunch": [
                {"name": "Salmon Bowl", "ingredients": ["salmon", "quinoa", "avocado", "greens"], "benefits": "Omega-3s and B vitamins"}
            ],
            "dinner": [
                {"name": "Turkey with Vegetables", "ingredients": ["turkey", "sweet potato", "Brussels sprouts"], "benefits": "Tryptophan produces serotonin"}
            ],
            "snacks": [
                {"name": "Banana with Nut Butter", "ingredients": ["banana", "almond butter"], "benefits": "Aids mood regulation"}
            ],
            "tips": ["Maintain stable blood sugar", "Include omega-3 foods", "Get B vitamins", "Limit caffeine and alcohol", "Stay hydrated"]
        },
        "acne": {
            "breakfast": [
                {"name": "Green Tea with Toast", "ingredients": ["green tea", "whole grain bread", "avocado"], "benefits": "Anti-inflammatory"}
            ],
            "lunch": [
                {"name": "Grilled Fish", "ingredients": ["fish", "broccoli", "carrots", "olive oil"], "benefits": "Omega-3s reduce inflammation"}
            ],
            "dinner": [
                {"name": "Chicken with Sweet Potato", "ingredients": ["chicken", "sweet potato", "spinach"], "benefits": "Zinc aids skin repair"}
            ],
            "snacks": [
                {"name": "Brazil Nuts", "ingredients": ["Brazil nuts", "berries"], "benefits": "Selenium fights inflammation"}
            ],
            "tips": ["Limit dairy", "Avoid high glycemic foods", "Include zinc-rich foods", "Eat omega-3s", "Stay hydrated"]
        },
        "hair_loss": {
            "breakfast": [
                {"name": "Eggs with Spinach", "ingredients": ["2 eggs", "spinach", "whole grain toast"], "benefits": "Biotin promotes hair growth"}
            ],
            "lunch": [
                {"name": "Salmon with Sweet Potato", "ingredients": ["salmon", "sweet potato", "vegetables"], "benefits": "Omega-3s nourish hair"}
            ],
            "dinner": [
                {"name": "Lentil Curry", "ingredients": ["lentils", "brown rice", "curry spices"], "benefits": "Protein supports hair structure"}
            ],
            "snacks": [
                {"name": "Sunflower Seeds", "ingredients": ["sunflower seeds", "berries"], "benefits": "Vitamin E promotes circulation"}
            ],
            "tips": ["Ensure adequate protein", "Include iron-rich foods", "Get biotin from eggs", "Consume omega-3s", "Include zinc and selenium"]
        }
    }
    
    combined_breakfast = []
    combined_lunch = []
    combined_dinner = []
    combined_snacks = []
    combined_tips = []
    added_meals = set()
    
    for symptom in symptoms:
        if symptom in nutrition_db:
            symptom_data = nutrition_db[symptom]
            for meal in symptom_data["breakfast"]:
                if meal["name"] not in added_meals:
                    combined_breakfast.append(meal)
                    added_meals.add(meal["name"])
            for meal in symptom_data["lunch"]:
                if meal["name"] not in added_meals:
                    combined_lunch.append(meal)
                    added_meals.add(meal["name"])
            for meal in symptom_data["dinner"]:
                if meal["name"] not in added_meals:
                    combined_dinner.append(meal)
                    added_meals.add(meal["name"])
            for meal in symptom_data["snacks"]:
                if meal["name"] not in added_meals:
                    combined_snacks.append(meal)
                    added_meals.add(meal["name"])
            combined_tips.extend(symptom_data["tips"])
    
    result = {
        "breakfast": combined_breakfast[:3],
        "lunch": combined_lunch[:3],
        "dinner": combined_dinner[:3],
        "snacks": combined_snacks[:3],
        "tips": list(set(combined_tips))[:8]
    }
    return jsonify(result)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))