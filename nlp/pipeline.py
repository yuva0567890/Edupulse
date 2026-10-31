"""End-to-end EduPulse NLP pipeline.

Feedback -> language detection -> preprocessing / Tanglish normalisation -> sentiment ->
ABSA (clauses + aspects) -> severity -> priority -> TF-IDF explainability -> recommendation.
The pipeline is pure NLP (no database); frequency data is injected via `freq_lookup`.
"""
import logging

from .absa import segment_feedback, ASPECTS, GENERAL
from .categories import CATEGORIES, categorize_aspects, detect_category
from .explainability import explain_sentiment, explanation_text
from .language_detection import detect_language
from .preprocessing import preprocess
from .priority import PriorityConfig, compute_priority, detect_severity, SEVERITY_VALUES, LEVELS
from .recommendations import recommend
from .sentiment import SentimentEngine

log = logging.getLogger("edupulse.pipeline")
MIN_CHARS = 3
MAX_CHARS = 5000
SEV_RANK = SEVERITY_VALUES


class FeedbackError(ValueError):
    """Raised for input that cannot be analysed (empty / too short / no letters)."""


class EduPulsePipeline:
    def __init__(self, models_dir, data_path=None, priority_config=None, auto_train=True):
        self.engine = SentimentEngine(models_dir, data_path, auto_train=auto_train)
        self.priority_config = priority_config or PriorityConfig()

    @property
    def mode(self):
        return self.engine.mode

    def set_priority_config(self, cfg: PriorityConfig):
        self.priority_config = cfg

    def validate(self, text):
        if text is None or not isinstance(text, str):
            raise FeedbackError("Feedback text is required.")
        t = text.strip()
        if not t:
            raise FeedbackError("Feedback text is empty.")
        if len(t) > MAX_CHARS:
            raise FeedbackError(f"Feedback is too long (max {MAX_CHARS} characters).")
        prep = preprocess(t)
        if len(t) < MIN_CHARS or not prep["tokens"] or not any(ch.isalpha() for ch in t):
            raise FeedbackError("Feedback is too short or contains no readable words.")
        return prep

    def analyze(self, text, language_hint=None, freq_lookup=None, category_hint=None):
        """freq_lookup(aspect) -> int: number of earlier NEGATIVE feedback items for this aspect
        inside the configured window (from the database). The current item is added here."""
        prep = self.validate(text)
        lang = detect_language(prep["cleaned"])
        cfg = self.priority_config

        # 1) overall sentiment on the whole text
        overall = self.engine.predict(prep)

        # 2) ABSA: clauses -> aspects -> clause sentiment
        segments = segment_feedback(prep["cleaned"])
        aspect_rows = {}
        for seg in segments:
            sp = seg["prep"]
            sres = self.engine.predict(sp)
            asp_list = seg["aspects"]
            if not asp_list:
                guess, prob = self.engine.predict_aspect_fallback(sp)
                if guess and prob >= 0.5:
                    asp_list = [(guess, ["(model)"])]
                else:
                    asp_list = [(GENERAL, [])]
            for aspect, kws in asp_list:
                key = aspect
                row = aspect_rows.get(key)
                if row is None:
                    aspect_rows[key] = {"aspect": aspect, "keywords": kws, "text": seg["text"], "prep": sp,
                                        "sentiment": sres}
                else:  # same aspect mentioned twice: keep the more negative / more confident clause
                    if (sres["label"] == "Negative" and row["sentiment"]["label"] != "Negative") or \
                       (sres["label"] == row["sentiment"]["label"] and sres["confidence"] > row["sentiment"]["confidence"]):
                        row.update({"text": seg["text"], "prep": sp, "sentiment": sres})
                    row["keywords"] = list(dict.fromkeys(row["keywords"] + kws))
        
        
        
        
        # 3) reconcile overall sentiment with aspect sentiments
        labels = [r["sentiment"]["label"] for r in aspect_rows.values()]

        has_positive = "Positive" in labels
        has_negative = "Negative" in labels

        # Mixed positive and negative aspects -> Neutral overall.
        if has_positive and has_negative:
            overall = dict(
                overall,
                label="Neutral",
                method=overall["method"] + "+mixed-aspect-rule"
            )

        # If the model is unsure, use the aspect sentiment labels.
        elif overall["confidence"] < 0.55 and labels:
            if has_negative:
                agg = "Negative"
            elif has_positive:
                agg = "Positive"
            else:
                agg = "Neutral"

            if agg != overall["label"]:
                overall = dict(
                    overall,
                    label=agg,
                    method=overall["method"] + "+aspect-rule"
                )


        # 3b) category (Academics / Hostel / Others) for every aspect
        cat_map = categorize_aspects([(r["aspect"], r["prep"]["concept_tokens"]) for r in aspect_rows.values()],
                                     prep["concept_tokens"])

        # 4) per aspect: severity, priority, explanation, recommendation
        aspects_out = []
        for r in aspect_rows.values():
            s = r["sentiment"]
            sev = detect_severity(r["prep"]["concept_tokens"], s["label"])
            freq = 0
            if s["label"] == "Negative":
                try:
                    freq = int(freq_lookup(r["aspect"])) if freq_lookup else 0
                except Exception as e:
                    log.warning("frequency lookup failed: %s", e)
                    freq = 0
                freq += 1  # this feedback itself
            pr = compute_priority(sev, freq, r["aspect"], cfg)
            if s["label"] != "Negative":
                pr = compute_priority("Low", 0, r["aspect"], cfg)
                pr["score"] = min(pr["score"], cfg.medium_min - 0.1)
                pr["level"] = "LOW"
            ex = explain_sentiment(self.engine, r["prep"], s["label"])
            rec = recommend(r["aspect"], s["label"], pr["level"], freq, cfg.recurring_threshold)
            aspects_out.append({
                "aspect": r["aspect"], "category": cat_map.get(r["aspect"], "Others"), "sentiment": s["label"], "confidence": round(s["confidence"], 4),
                "keywords": r["keywords"], "clause": r["text"], "severity": sev, "priority": pr,
                "explanation": {"terms": ex["terms"], "method": ex["method"],
                                "text": explanation_text(s["label"], ex["terms"])},
                "recommendation": rec,
            })

        # order: worst priority first
        aspects_out.sort(key=lambda a: -a["priority"]["score"])
        top = aspects_out[0] if aspects_out else None
        overall_sev = "Low"
        for a in aspects_out:
            if SEV_RANK[a["severity"]] > SEV_RANK[overall_sev]:
                overall_sev = a["severity"]
        if overall["label"] == "Negative" and overall_sev == "Low":
            overall_sev = detect_severity(prep["concept_tokens"], "Negative")
        ex_all = explain_sentiment(self.engine, prep, overall["label"])
        det = detect_category([{"aspect": a["aspect"], "category": a["category"], "sentiment": a["sentiment"],
                                "priority_score": a["priority"]["score"]} for a in aspects_out])
        chosen = category_hint if category_hint in CATEGORIES else None
        final_cat = chosen or det["category"]
        category = {"detected": det["category"], "selected": chosen or "Auto Detect", "final": final_cat,
                    "confidence": det["confidence"], "method": det["method"], "scores": det["scores"],
                    "mismatch": bool(chosen and chosen != det["category"] and det["method"] != "default")}

        return {
            "language": lang, "language_hint": language_hint, "category": category,
            "nlp_mode": self.mode,
            "preprocessing": {"cleaned": prep["cleaned"], "tokens": prep["tokens"],
                              "normalized": prep["model_text"],
                              "pairs": [{"surface": s, "concept": c} for s, c in prep["pairs"]]},
            "sentiment": {"label": overall["label"], "confidence": round(overall["confidence"], 4),
                          "probs": {k: round(v, 4) for k, v in overall["probs"].items()}, "method": overall["method"]},
            "severity": overall_sev,
            "priority": {"level": top["priority"]["level"] if top else "LOW",
                         "score": top["priority"]["score"] if top else 0.0,
                         "why": top["priority"]["why"] if top else {"en": "", "ta": "", "hi": ""}},
            "aspects": aspects_out,
            "explanation": {"terms": ex_all["terms"], "method": ex_all["method"],
                            "text": explanation_text(overall["label"], ex_all["terms"])},
        }
