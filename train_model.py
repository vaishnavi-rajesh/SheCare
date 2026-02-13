import pandas as pd
import pickle
import os
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression

# create model folder if not exists
os.makedirs("model", exist_ok=True)

# load dataset
df = pd.read_csv("shecare_dataset_large.csv")

# features
features = [
    "age",
    "BMI",
    "cycle_variation",
    "acne_severity",
    "hair_growth",
    "fatigue",
    "hemoglobin",
    "breast_lump",
    "breast_pain"
]

X = df[features]

# ================= PCOS MODEL =================

y_pcos = df["pcos_risk"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y_pcos, test_size=0.2, random_state=42
)

pcos_model = LogisticRegression(max_iter=1000)
pcos_model.fit(X_train, y_train)

pickle.dump(pcos_model, open("model/pcos_model.pkl", "wb"))

print("PCOS model saved")


# ================= ANEMIA MODEL =================

y_anemia = df["anemia_risk"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y_anemia, test_size=0.2, random_state=42
)

anemia_model = LogisticRegression(max_iter=1000)
anemia_model.fit(X_train, y_train)

pickle.dump(anemia_model, open("model/anemia_model.pkl", "wb"))

print("Anemia model saved")


# ================= BREAST CANCER MODEL =================

y_bc = df["breast_cancer_risk"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y_bc, test_size=0.2, random_state=42
)

bc_model = LogisticRegression(max_iter=1000)
bc_model.fit(X_train, y_train)

pickle.dump(bc_model, open("model/breast_cancer_model.pkl", "wb"))

print("Breast Cancer model saved")


print("All models trained successfully")
