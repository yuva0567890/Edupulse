"""Training pipeline:  CSV -> preprocessing -> train/val/test split -> model training
-> evaluation -> save model + metrics.

Usage
    python training/train.py                       # TF-IDF + Logistic Regression (fast, CPU, offline)
    python training/train.py --data my_data.csv    # your own CSV (columns: text,language,sentiment,aspect,severity[,level])
    python training/train.py --transformer         # OPTIONAL: fine-tune xlm-roberta-base (needs torch + transformers + internet)

The CSV may contain a `level` column: 'clause' (single-aspect snippets) or 'full' (whole feedback).
If absent, every row is treated as 'clause' when it has a single aspect, otherwise as 'full'.
"""
import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import joblib
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from nlp.preprocessing import preprocess
from training.evaluate import evaluate_all, SENT_LABELS

SEED = 42
DEFAULT_DATA = os.path.join(ROOT, "data", "training_data.csv")
DEFAULT_MODELS = os.path.join(ROOT, "models", "saved")
REQUIRED = ["text", "sentiment", "aspect"]


def load_dataset(path):
    df = pd.read_csv(path, encoding="utf-8")
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing columns: {missing}")
    df = df.dropna(subset=["text", "sentiment"]).copy()
    df["text"] = df["text"].astype(str)
    df = df[df["text"].str.strip().str.len() > 1]
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)
    if "category" not in df.columns:
        from nlp.categories import ASPECT_CATEGORY
        df["category"] = df["aspect"].astype(str).map(lambda a: ASPECT_CATEGORY.get(a.split("|")[0], "Others"))
    for col, default in (("language", "Unknown"), ("severity", "Low")):
        if col not in df.columns:
            df[col] = default
    if "level" not in df.columns:
        df["level"] = df["aspect"].astype(str).map(lambda a: "full" if "|" in a else "clause")
    df["sentiment"] = df["sentiment"].str.strip().str.capitalize()
    df = df[df["sentiment"].isin(SENT_LABELS)]
    return df


def make_pipe(C):
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, token_pattern=r"\S+", lowercase=True, min_df=1)),
        ("clf", LogisticRegression(C=C, max_iter=3000, class_weight="balanced", random_state=SEED)),
    ])


def split(df):
    """70 / 15 / 15 stratified split on sentiment."""
    train, rest = train_test_split(df, test_size=0.30, random_state=SEED, stratify=df["sentiment"])
    val, test = train_test_split(rest, test_size=0.50, random_state=SEED, stratify=rest["sentiment"])
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)


def fit_sentiment(train, val):
    Xtr = [preprocess(t)["model_text"] for t in train["text"]]
    Xva = [preprocess(t)["model_text"] for t in val["text"]]
    best, best_f1, best_c, grid = None, -1, None, {}
    for C in (0.5, 2.0, 8.0, 32.0):
        pipe = make_pipe(C).fit(Xtr, train["sentiment"])
        f1 = f1_score(val["sentiment"], pipe.predict(Xva), average="macro")
        grid[str(C)] = round(float(f1), 4)
        if f1 > best_f1:
            best, best_f1, best_c = pipe, f1, C
    return best, best_c, best_f1, grid


def fit_aspect(train):
    c = train[train["level"] == "clause"]
    c = c[~c["aspect"].astype(str).str.contains(r"\|")]
    c = c[c["aspect"] != "General"]
    X = [preprocess(t)["model_text"] for t in c["text"]]
    return make_pipe(8.0).fit(X, c["aspect"])


def train_and_save(data_path=None, models_dir=None, quiet=False):
    data_path = data_path or DEFAULT_DATA
    models_dir = models_dir or DEFAULT_MODELS
    os.makedirs(models_dir, exist_ok=True)
    log = (lambda *a: None) if quiet else print

    log(f"Loading {data_path}")
    df = load_dataset(data_path)
    train, val, test = split(df)
    log(f"Rows: total={len(df)} train={len(train)} val={len(val)} test={len(test)}")

    sent, best_c, val_f1, grid = fit_sentiment(train, val)
    log(f"Sentiment model: LogisticRegression C={best_c} (validation macro-F1={val_f1:.3f})")
    asp = fit_aspect(train)

    bundle = {
        "sentiment": sent, "aspect": asp,
        "meta": {"trained_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "sklearn_version": sklearn.__version__, "data_path": os.path.basename(data_path)},
    }
    joblib.dump(bundle, os.path.join(models_dir, "edupulse_sklearn.joblib"))
    test.to_csv(os.path.join(models_dir, "test_split.csv"), index=False, encoding="utf-8")

    res = evaluate_all(bundle, test)
    langs = sorted(df["language"].unique().tolist())
    metrics = {
        "model_name": "TF-IDF (word 1-2 grams) + Logistic Regression + multilingual rules",
        "mode": "Fallback / Demo",
        "trained_at": bundle["meta"]["trained_at"],
        "dataset": {"file": os.path.basename(data_path), "size": int(len(df)), "languages": langs,
                    "language_counts": df["language"].value_counts().to_dict(),
                    "sentiment_counts": df["sentiment"].value_counts().to_dict(),
                    "synthetic": os.path.basename(data_path) == "training_data.csv"},
        "split": {"train": int(len(train)), "validation": int(len(val)), "test": int(len(test)),
                  "ratio": "70 / 15 / 15 (stratified by sentiment, seed 42)"},
        "hyperparameters": {"C": best_c, "validation_macro_f1_by_C": grid},
        "results": res,
    }
    with open(os.path.join(models_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    s = res["sentiment"]
    log(f"TEST  accuracy={s['accuracy']:.3f}  macro-F1={s['f1_macro']:.3f}  weighted-F1={s['f1_weighted']:.3f}")
    for k, v in s["per_language"].items():
        log(f"   {k:8s} n={v['n']:4d} acc={v['accuracy']:.3f} macro-F1={v['f1_macro']:.3f}")
    cm = res.get("category_rules", {})
    log(f"Category detection (rules)  accuracy={cm.get('accuracy', 0):.3f}  macro-F1={cm.get('f1_macro', 0):.3f}")
    log(f"Saved model + metrics to {models_dir}")
    return metrics


# ---------------------------------------------------------------- optional transformer
def train_transformer(data_path=None, models_dir=None, base="xlm-roberta-base", epochs=3, batch=16, lr=2e-5):
    """Optional: fine-tune a multilingual transformer for sentiment (CPU is slow; GPU recommended).
    Saves to models/saved/transformer. The app then reports 'NLP Mode: Multilingual Transformer'."""
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    data_path = data_path or DEFAULT_DATA
    models_dir = models_dir or DEFAULT_MODELS
    df = load_dataset(data_path)
    train, val, test = split(df)
    tok = AutoTokenizer.from_pretrained(base)
    model = AutoModelForSequenceClassification.from_pretrained(base, num_labels=3)
    l2i = {l: i for i, l in enumerate(SENT_LABELS)}
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    texts = [preprocess(t)["cleaned"] for t in train["text"]]
    labels = [l2i[s] for s in train["sentiment"]]
    data = list(zip(texts, labels))
    for ep in range(epochs):
        model.train()
        order = torch.randperm(len(data)).tolist()
        for i in range(0, len(order), batch):
            chunk = [data[j] for j in order[i:i + batch]]
            enc = tok([c[0] for c in chunk], return_tensors="pt", padding=True, truncation=True, max_length=128)
            out = model(**enc, labels=torch.tensor([c[1] for c in chunk]))
            out.loss.backward()
            opt.step()
            opt.zero_grad()
        print(f"epoch {ep + 1}/{epochs} done")
    model.eval()
    preds = []
    with torch.no_grad():
        for t in test["text"]:
            enc = tok(preprocess(t)["cleaned"], return_tensors="pt", truncation=True, max_length=128)
            preds.append(SENT_LABELS[int(model(**enc).logits.argmax())])
    from training.evaluate import prf
    print("Transformer TEST:", prf(test["sentiment"].tolist(), preds, SENT_LABELS))
    out = os.path.join(models_dir, "transformer")
    os.makedirs(out, exist_ok=True)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    with open(os.path.join(out, "labels.json"), "w", encoding="utf-8") as f:
        json.dump(SENT_LABELS, f)
    print("Saved transformer to", out)


def main():
    ap = argparse.ArgumentParser(description="Train EduPulse models")
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--models-dir", default=DEFAULT_MODELS)
    ap.add_argument("--transformer", action="store_true", help="also fine-tune xlm-roberta-base (optional)")
    a = ap.parse_args()
    train_and_save(a.data, a.models_dir)
    if a.transformer:
        train_transformer(a.data, a.models_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
