import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd
import joblib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    classification_report
)

from nlp.preprocessing import preprocess


DATA_PATH = os.path.join(ROOT, "data", "training_data.csv")
MODEL_PATH = os.path.join(
    ROOT, "models", "saved", "english_sentiment.joblib"
)

SEED = 42
LABELS = ["Negative", "Neutral", "Positive"]


def make_model(c, use_char_features, class_weight):
    if use_char_features:
        features = FeatureUnion([
            (
                "word_tfidf",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                    token_pattern=r"\S+",
                    lowercase=True,
                    min_df=1
                )
            ),
            (
                "char_tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    sublinear_tf=True,
                    lowercase=True,
                    min_df=2,
                    max_features=100000
                )
            )
        ])
    else:
        features = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            token_pattern=r"\S+",
            lowercase=True,
            min_df=1
        )

    return Pipeline([
        ("tfidf", features),
        (
            "clf",
            LogisticRegression(
                C=c,
                max_iter=3000,
                class_weight=class_weight,
                random_state=SEED
            )
        )
    ])


# 1. Load English samples only
df = pd.read_csv(DATA_PATH)

df = df[
    df["language"]
    .astype(str)
    .str.strip()
    .str.lower()
    .eq("english")
].dropna(subset=["text", "sentiment"]).copy()

df["text"] = df["text"].astype(str).str.strip()
df["sentiment"] = (
    df["sentiment"].astype(str).str.strip().str.capitalize()
)

df = df[
    df["sentiment"].isin(LABELS) & df["text"].ne("")
].copy()

# Remove duplicate text without changing other language data
df["_normalized_text"] = (
    df["text"].str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
)
df = df.drop_duplicates(subset=["_normalized_text"])
df = df.drop(columns=["_normalized_text"]).reset_index(drop=True)

print("English dataset size:", len(df))
print("\nClass distribution:")
print(df["sentiment"].value_counts())

if len(df) < 30 or df["sentiment"].nunique() < 3:
    raise ValueError(
        "Not enough English data or one/more sentiment classes are missing."
    )


# 2. Split data: train / validation / test
train_val, test = train_test_split(
    df,
    test_size=0.15,
    random_state=SEED,
    stratify=df["sentiment"]
)

train, val = train_test_split(
    train_val,
    test_size=0.1765,
    random_state=SEED,
    stratify=train_val["sentiment"]
)


# 3. Preprocess text using the existing project function
X_train = [preprocess(t)["model_text"] for t in train["text"]]
X_val = [preprocess(t)["model_text"] for t in val["text"]]
X_test = [preprocess(t)["model_text"] for t in test["text"]]

y_train = train["sentiment"]
y_val = val["sentiment"]
y_test = test["sentiment"]


# 4. Compare baseline and word + character features
best_model = None
best_config = None
best_accuracy = -1
best_macro_f1 = -1

for use_char in [False, True]:
    for class_weight in [None, "balanced"]:
        for c in [0.5, 1, 2, 4, 8, 16, 32]:

            model = make_model(c, use_char, class_weight)
            model.fit(X_train, y_train)

            val_pred = model.predict(X_val)

            val_accuracy = accuracy_score(y_val, val_pred)
            val_macro_f1 = f1_score(
                y_val, val_pred, average="macro"
            )

            feature_type = (
                "Word + Character TF-IDF"
                if use_char else "Word TF-IDF baseline"
            )

            print(
                f"{feature_type} | C={c} | "
                f"class_weight={class_weight} | "
                f"val_accuracy={val_accuracy:.4f} | "
                f"val_macro_F1={val_macro_f1:.4f}"
            )

            # Select primarily by validation accuracy;
            # use macro-F1 to break ties.
            if (
                val_accuracy > best_accuracy
                or (
                    val_accuracy == best_accuracy
                    and val_macro_f1 > best_macro_f1
                )
            ):
                best_model = model
                best_config = (use_char, class_weight, c)
                best_accuracy = val_accuracy
                best_macro_f1 = val_macro_f1


# 5. Evaluate the selected model once on the held-out test set
test_pred = best_model.predict(X_test)

test_accuracy = accuracy_score(y_test, test_pred)
test_macro_f1 = f1_score(
    y_test, test_pred, average="macro"
)

print("\n========== BEST ENGLISH MODEL ==========")
print("Samples:", len(df))
print("Character features enabled:", best_config[0])
print("Class weight:", best_config[1])
print("Best C:", best_config[2])
print("Validation accuracy:", round(best_accuracy, 4))
print("Validation macro-F1:", round(best_macro_f1, 4))
print("Test accuracy:", round(test_accuracy, 4))
print("Test macro-F1:", round(test_macro_f1, 4))

print("\nClassification report:")
print(
    classification_report(
        y_test,
        test_pred,
        labels=LABELS,
        zero_division=0
    )
)


# 6. Save only the English model
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
joblib.dump(best_model, MODEL_PATH)

print("\nEnglish model saved to:", MODEL_PATH)
print("Multilingual model was not modified.")