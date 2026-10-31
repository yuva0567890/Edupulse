"""Model evaluation. Every number shown in the dashboard comes from real predictions
made here on the held-out TEST split (never the training rows).

Run:  python training/evaluate.py            (re-evaluates the saved model on models/saved/test_split.csv)
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support)

from nlp.language_detection import primary_language
from nlp.preprocessing import preprocess
from nlp.absa import segment_feedback, ALL_ASPECTS as ASPECTS
from nlp.categories import CATEGORIES, categorize_aspects, detect_category
from nlp.priority import detect_severity

SENT_LABELS = ["Negative", "Neutral", "Positive"]


def prf(y_true, y_pred, labels):
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    pw, rw, fw, _ = precision_recall_fscore_support(y_true, y_pred, labels=labels, average="weighted", zero_division=0)
    return {
        "n": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision_macro": round(float(p), 4), "recall_macro": round(float(r), 4),
        "f1_macro": round(float(f), 4), "f1_weighted": round(float(fw), 4),
    }


def sentiment_metrics(pipe, df):
    X = [preprocess(t)["model_text"] for t in df["text"]]
    y = df["sentiment"].tolist()
    pred = pipe.predict(X)
    out = prf(y, pred, SENT_LABELS)
    out["confusion_matrix"] = {"labels": SENT_LABELS,
                               "matrix": confusion_matrix(y, pred, labels=SENT_LABELS).tolist()}
    # per primary language (Tamil / English / Hindi / Mixed) and fine-grained labels
    d = df.copy()
    d["pred"] = pred
    d["primary"] = d["language"].map(primary_language)
    out["per_language"] = {}
    for name, g in d.groupby("primary"):
        out["per_language"][name] = prf(g["sentiment"].tolist(), g["pred"].tolist(), SENT_LABELS)
    out["per_language_detailed"] = {}
    for name, g in d.groupby("language"):
        out["per_language_detailed"][name] = prf(g["sentiment"].tolist(), g["pred"].tolist(), SENT_LABELS)
    out["per_language"]["Overall"] = prf(y, pred, SENT_LABELS)
    return out


def aspect_classifier_metrics(pipe, df):
    c = df[df["level"] == "clause"]
    if c.empty:
        return {}
    X = [preprocess(t)["model_text"] for t in c["text"]]
    y = c["aspect"].tolist()
    pred = pipe.predict(X)
    out = prf(y, pred, ASPECTS)
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=ASPECTS, zero_division=0)
    out["per_aspect"] = {a: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4),
                             "f1": round(float(f[i]), 4), "support": int(s[i])} for i, a in enumerate(ASPECTS)}
    out["confusion_matrix"] = {"labels": ASPECTS, "matrix": confusion_matrix(y, pred, labels=ASPECTS).tolist()}
    return out


def rule_absa_metrics(df):
    """Evaluate the rule-based multi-aspect detector (clause splitting + keyword lexicon)."""
    tp = fp = fn = exact = 0
    per = {a: {"tp": 0, "fp": 0, "fn": 0} for a in ASPECTS}
    for text, gold in zip(df["text"], df["aspect"]):
        gold_set = set(gold.split("|"))
        found = set()
        for seg in segment_feedback(text):
            for a, _ in seg["aspects"]:
                found.add(a)
        tp += len(gold_set & found)
        fp += len(found - gold_set)
        fn += len(gold_set - found)
        exact += int(found == gold_set)
        for a in ASPECTS:
            per[a]["tp"] += int(a in gold_set and a in found)
            per[a]["fp"] += int(a not in gold_set and a in found)
            per[a]["fn"] += int(a in gold_set and a not in found)
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    F = 2 * P * R / (P + R) if P + R else 0.0
    per_out = {}
    for a, v in per.items():
        p = v["tp"] / (v["tp"] + v["fp"]) if v["tp"] + v["fp"] else 0.0
        r = v["tp"] / (v["tp"] + v["fn"]) if v["tp"] + v["fn"] else 0.0
        per_out[a] = {"precision": round(p, 4), "recall": round(r, 4),
                      "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0, "support": v["tp"] + v["fn"]}
    return {"n": int(len(df)), "precision_micro": round(P, 4), "recall_micro": round(R, 4),
            "f1_micro": round(F, 4), "exact_match": round(exact / max(len(df), 1), 4), "per_aspect": per_out}


def category_metrics(df):
    """End-to-end rule-based category detection (clause splitting + aspect keywords + category rules).
    * single-aspect rows (level=clause): single-label accuracy / P / R / F1 per category
    * multi-aspect rows (level=full): the SET of detected categories vs the set of labelled categories
    """
    from nlp.categories import ASPECT_CATEGORY

    def detected(text):
        segs = segment_feedback(text)
        pairs = [(a, s["prep"]["concept_tokens"]) for s in segs for a, _ in s["aspects"]]
        cmap = categorize_aspects(pairs, preprocess(text)["concept_tokens"])
        rows = [{"aspect": a, "category": cmap[a], "sentiment": "Neutral", "priority_score": 0} for a, _ in pairs]
        return detect_category(rows)["category"], {cmap[a] for a, _ in pairs}

    clause = df[df["level"] == "clause"]
    y_true, y_pred = [], []
    for text, asp in zip(clause["text"], clause["aspect"]):
        y_true.append(ASPECT_CATEGORY.get(asp, "Others"))
        y_pred.append(detected(text)[0])
    out = prf(y_true, y_pred, CATEGORIES)
    out["confusion_matrix"] = {"labels": CATEGORIES, "matrix": confusion_matrix(y_true, y_pred, labels=CATEGORIES).tolist()}
    p, r, f, sup = precision_recall_fscore_support(y_true, y_pred, labels=CATEGORIES, zero_division=0)
    out["per_category"] = {c: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4),
                               "f1": round(float(f[i]), 4), "support": int(sup[i])} for i, c in enumerate(CATEGORIES)}
    full = df[df["level"] == "full"]
    exact = 0
    for text, asp in zip(full["text"], full["aspect"]):
        gold = {ASPECT_CATEGORY.get(a, "Others") for a in asp.split("|")}
        exact += int(detected(text)[1] == gold)
    out["multi_aspect_set_match"] = round(exact / max(len(full), 1), 4)
    out["multi_aspect_n"] = int(len(full))
    return out


def severity_metrics(pipe, df):
    """Rule-based severity vs labelled severity (using the model's predicted sentiment)."""
    X = [preprocess(t) for t in df["text"]]
    pred_s = pipe.predict([p["model_text"] for p in X])
    pred_sev = [detect_severity(p["concept_tokens"], s) for p, s in zip(X, pred_s)]
    y = df["severity"].tolist()
    labels = ["Low", "Medium", "High", "Critical"]
    out = prf(y, pred_sev, labels)
    out["confusion_matrix"] = {"labels": labels, "matrix": confusion_matrix(y, pred_sev, labels=labels).tolist()}
    return out


def evaluate_all(bundle, test_df):
    return {
        "sentiment": sentiment_metrics(bundle["sentiment"], test_df),
        "aspect_classifier": aspect_classifier_metrics(bundle["aspect"], test_df),
        "aspect_rules": rule_absa_metrics(test_df),
        "severity_rules": severity_metrics(bundle["sentiment"], test_df),
        "category_rules": category_metrics(test_df),
    }


def main():
    import joblib
    mdir = os.path.join(ROOT, "models", "saved")
    bpath = os.path.join(mdir, "edupulse_sklearn.joblib")
    tpath = os.path.join(mdir, "test_split.csv")
    if not (os.path.exists(bpath) and os.path.exists(tpath)):
        print("Training required: run `python training/train.py` first.")
        return 1
    bundle = joblib.load(bpath)
    test_df = pd.read_csv(tpath)
    res = evaluate_all(bundle, test_df)
    s = res["sentiment"]
    print(f"Test rows: {s['n']}")
    print(f"Accuracy {s['accuracy']:.3f} | Macro-F1 {s['f1_macro']:.3f} | Weighted-F1 {s['f1_weighted']:.3f}")
    for k, v in s["per_language"].items():
        print(f"  {k:8s} n={v['n']:4d} acc={v['accuracy']:.3f} macroF1={v['f1_macro']:.3f}")
    print("Confusion matrix (rows=true, cols=pred):", s["confusion_matrix"]["labels"])
    for row in s["confusion_matrix"]["matrix"]:
        print("  ", row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
