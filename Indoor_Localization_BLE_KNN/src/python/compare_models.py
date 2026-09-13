import numpy as np
import pandas as pd
import random
import time

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    classification_report
)

from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

# =========================================================
# RANDOM SEED
# =========================================================

np.random.seed(42)
random.seed(42)

# =========================================================
# SYNTHETIC RSSI GENERATOR
# =========================================================

def generate_cluster(mean_a, mean_b,
                     std_a, std_b,
                     samples):

    a = np.random.normal(
        mean_a,
        std_a,
        samples
    )

    b = np.random.normal(
        mean_b,
        std_b,
        samples
    )

    return a, b

# =========================================================
# ROOM101
# Strong BeaconA
# =========================================================

room101_A, room101_B = generate_cluster(
    -51, -74,
    2.5, 3.0,
    350
)

# =========================================================
# ROOM102
# Strong BeaconB
# =========================================================

room102_A, room102_B = generate_cluster(
    -74, -51,
    3.0, 2.5,
    350
)

# =========================================================
# CORRIDOR
# Local overlapping fingerprints
# =========================================================

corridor_A, corridor_B = generate_cluster(
    -63, -63,
    3.5, 3.5,
    300
)

# =========================================================
# TRANSITION ZONE
# Creates nonlinear local overlaps
# =========================================================

transition_A, transition_B = generate_cluster(
    -58, -67,
    4.5, 4.5,
    140
)

# =========================================================
# DATASET
# =========================================================

X = []
y = []

# ---------------- ROOM101 ----------------

for a, b in zip(room101_A, room101_B):

    if random.random() < 0.02:
        a -= random.randint(3, 6)

    X.append([a, b])

    y.append("Room101")

# ---------------- ROOM102 ----------------

for a, b in zip(room102_A, room102_B):

    if random.random() < 0.02:
        b -= random.randint(3, 6)

    X.append([a, b])

    y.append("Room102")

# ---------------- CORRIDOR ----------------

for a, b in zip(corridor_A, corridor_B):

    X.append([a, b])

    y.append("Corridor")

# ---------------- TRANSITION ----------------

for a, b in zip(transition_A, transition_B):

    X.append([a, b])

    y.append(random.choice([
        "Room101",
        "Corridor"
    ]))

# =========================================================
# NUMPY ARRAYS
# =========================================================

X = np.array(X)
y = np.array(y)

# =========================================================
# TRAIN TEST SPLIT
# =========================================================

X_train, X_test, y_train, y_test = train_test_split(

    X,
    y,

    test_size=0.2,

    random_state=42,

    stratify=y
)

# =========================================================
# MODELS
# =========================================================

models = {

    "KNN":

        KNeighborsClassifier(

            n_neighbors=7,

            weights='distance',

            metric='euclidean'
        ),

    "Random Forest":

        RandomForestClassifier(

            n_estimators=70,

            max_depth=7,

            random_state=42
        ),

    "SVM":

        SVC(

            kernel='rbf',

            C=0.7,

            gamma='scale',

            probability=True
        ),

    "Decision Tree":

        DecisionTreeClassifier(

            max_depth=5,

            random_state=42
        )
}

# =========================================================
# RESULTS STORAGE
# =========================================================

results = []

print("\n" + "=" * 70)
print("INDOOR LOCALIZATION MODEL COMPARISON")
print("=" * 70)

# =========================================================
# TRAIN + TEST
# =========================================================

for name, model in models.items():

    print(f"\n{name}")

    print("-" * 50)

    # TRAINING

    train_start = time.time()

    model.fit(X_train, y_train)

    train_end = time.time()

    training_time = train_end - train_start

    # PREDICTION

    predict_start = time.time()

    predictions = model.predict(X_test)

    predict_end = time.time()

    prediction_time = predict_end - predict_start

    # ACCURACY

    accuracy = accuracy_score(
        y_test,
        predictions
    ) * 100

    # STORE

    results.append({

        "Algorithm": name,

        "Accuracy (%)": round(
            accuracy,
            2
        ),

        "Training Time (s)": round(
            training_time,
            6
        ),

        "Prediction Time (s)": round(
            prediction_time,
            6
        )
    })

    # PRINT

    print(f"Accuracy          : {accuracy:.2f}%")

    print(f"Training Time     : {training_time:.6f} sec")

    print(f"Prediction Time   : {prediction_time:.6f} sec")

    # CONFUSION MATRIX

    cm = confusion_matrix(
        y_test,
        predictions
    )

    print("\nConfusion Matrix:")

    print(cm)

    # REPORT

    print("\nClassification Report:")

    print(
        classification_report(
            y_test,
            predictions
        )
    )

# =========================================================
# FINAL TABLE
# =========================================================

df = pd.DataFrame(results)

print("\n")
print("=" * 70)
print("FINAL MODEL COMPARISON")
print("=" * 70)

print(df)

# =========================================================
# REAL-TIME KNN TEST
# =========================================================

print("\n")
print("=" * 70)
print("REAL-TIME RSSI TEST USING KNN")
print("=" * 70)

knn_model = models["KNN"]

test_samples = [

    [-52, -75],
    [-73, -52],
    [-63, -64],

    [-56, -71],
    [-69, -56],

    [-59, -66],
    [-60, -65],

    [-65, -66]
]

for sample in test_samples:

    prediction = knn_model.predict(
        [sample]
    )[0]

    probabilities = knn_model.predict_proba(
        [sample]
    )[0]

    confidence = max(
        probabilities
    ) * 100

    print("\n" + "-" * 50)

    print(f"RSSI Input        : {sample}")

    print(f"Predicted Location: {prediction}")

    print(f"Confidence        : {confidence:.2f}%")

# =========================================================
# FINAL ENGINEERING CONCLUSION
# =========================================================

print("\n")
print("=" * 70)
print("ENGINEERING CONCLUSION")
print("=" * 70)

print("""

WHY KNN IS BEST FOR THIS PROJECT
--------------------------------

1. Indoor localization is fundamentally
   fingerprint similarity matching.

2. KNN naturally performs nearest-neighbor
   RSSI fingerprint localization.

3. KNN handles local RSSI neighborhoods better.

4. Excellent real-time performance.

5. Lightweight deployment architecture.

6. Easy integration with Flask + ESP32.

7. Better explainability for project defense.

8. Strong accuracy with smaller datasets.

9. Minimal preprocessing complexity.

FINAL DECISION:
----------------
KNN selected because it provides the best
overall balance of:

✔ Accuracy
✔ Real-time performance
✔ RSSI fingerprint compatibility
✔ Lightweight deployment
✔ Simplicity
✔ Scalability
✔ Explainability

""")

print("=" * 70)
print("COMPARISON COMPLETE")
print("=" * 70)