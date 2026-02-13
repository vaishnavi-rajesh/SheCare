from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=True)
    password = db.Column(db.String(100), nullable=True)
    is_anonymous = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    predictions = db.relationship('Prediction', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.name}>'


class Prediction(db.Model):
    __tablename__ = 'predictions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pcos_risk = db.Column(db.Integer, nullable=False)
    anemia_risk = db.Column(db.Integer, nullable=False)
    breast_cancer_risk = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Prediction {self.id} for User {self.user_id}>'


class PeriodLog(db.Model):
    __tablename__ = 'period_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    flow_intensity = db.Column(db.String(20), nullable=True)  # light, medium, heavy
    symptoms = db.Column(db.Text, nullable=True)  # JSON string of symptoms
    notes = db.Column(db.Text, nullable=True)
    cycle_length = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PeriodLog {self.id} for User {self.user_id}>'