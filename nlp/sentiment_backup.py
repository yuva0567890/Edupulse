
"""Sentiment engine: Transformer -> TF-IDF + Logistic Regression -> lexicon."""

import json
import logging
import os

from . import multilingual_utils as mu

log = logging.getLogger("edupulse.sentiment")

LABELS = ["Negative", "Neutral", "Positive"]
MODE_TRANSFORMER = "Multilingual Transformer"
MODE_FALLBACK = "Fallback / Demo"


def lexicon_sentiment(concept_tokens):
    """Last-resort sentiment scorer using shared concept tokens."""
    score = 0
    toks = list(concept_tokens)

    for i, token in enumerate(toks):
        polarity = (
            1 if token in mu.POSITIVE_WORDS
            else -1 if token in mu.NEGATIVE_WORDS
            else 0
        )

        if not polarity:
            continue

        if any(word in mu.NEGATORS for word in toks[max(0, i - 2):i]):
            polarity = -polarity

        score += polarity

    if score > 0:
        label, confidence = "Positive", min(0.9, 0.5 + 0.1 * score)
    elif score < 0:
        label, confidence = "Negative", min(0.9, 0.5 + 0.1 * abs(score))
    else:
        label, confidence = "Neutral", 0.55

    probabilities = {name: 0.0 for name in LABELS}
    probabilities[label] = confidence
    remainder = (1 - confidence) / 2

    for name in LABELS:
        if name != label:
            probabilities[name] = remainder

    return label, confidence, probabilities


class SentimentEngine:
    def __init__(self, models_dir, data_path=None, auto_train=True):
        self.models_dir = models_dir
        self.data_path = data_path
        self.auto_train = auto_train
        self.bundle = None
        self.transformer = None
        self.mode = MODE_FALLBACK
        self.status = "not loaded"
        self.load()

    @property
    def bundle_path(self):
        return os.path.join(self.models_dir, "edupulse_sklearn.joblib")

    def load(self):
        self._try_transformer()
        self._try_bundle()

        if self.bundle is None and self.auto_train:
            self._train_now()

        if self.transformer is not None:
            self.mode = MODE_TRANSFORMER
            self.status = "transformer loaded"
        elif self.bundle is not None:
            self.mode = MODE_FALLBACK
            self.status = "tfidf+logreg loaded"
        else:
            self.mode = MODE_FALLBACK
            self.status = "lexicon only (training required)"

    def _try_transformer(self):
        transformer_dir = os.path.join(self.models_dir, "transformer")

        if not os.path.exists(os.path.join(transformer_dir, "config.json")):
            return

        try:
            import torch  # noqa: F401
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            tokenizer = AutoTokenizer.from_pretrained(transformer_dir)
            model = AutoModelForSequenceClassification.from_pretrained(
                transformer_dir
            )
            model.eval()

            labels = LABELS
            labels_path = os.path.join(transformer_dir, "labels.json")

            if os.path.exists(labels_path):
                with open(labels_path, encoding="utf-8") as file:
                    labels = json.load(file)

            self.transformer = (tokenizer, model, labels)

        except Exception as error:
            log.warning("Transformer unavailable: %s", error)
            self.transformer = None

    def _try_bundle(self):
        if not os.path.exists(self.bundle_path):
            return

        try:
            import joblib

            bundle = joblib.load(self.bundle_path)

            if isinstance(bundle, dict) and "sentiment" in bundle:
                self.bundle = bundle

        except Exception as error:
            log.warning("Could not load saved model: %s", error)
            self.bundle = None

    def _train_now(self):
        try:
            from training.train import train_and_save

            train_and_save(
                data_path=self.data_path,
                models_dir=self.models_dir,
                quiet=True,
            )
            self._try_bundle()

        except Exception as error:
            log.warning("Auto-training failed: %s", error)
            self.bundle = None

    def reload(self):
        self.bundle = None
        self.transformer = None
        self.load()

    def predict(self, prep: dict) -> dict:
        """Predict sentiment from preprocessing.preprocess() output."""

        tokens = [str(token).lower() for token in prep["concept_tokens"]]

        if not tokens:
            return {
                "label": "Neutral",
                "confidence": 0.5,
                "probs": {
                    "Negative": 0.25,
                    "Neutral": 0.5,
                    "Positive": 0.25,
                },
                "method": "empty",
            }

        # Explicit negation patterns for working-condition feedback.
        for index, token in enumerate(tokens):
            if token != "working":
                continue

            previous = tokens[max(0, index - 2):index]

            if any(word in mu.NEGATORS for word in previous):
                return {
                    "label": "Negative",
                    "confidence": 0.90,
                    "probs": {
                        "Negative": 0.90,
                        "Neutral": 0.05,
                        "Positive": 0.05,
                    },
                    "method": "working-condition-rule",
                }

        # Mixed polarity: check before any positive working-condition rule.
        has_positive = any(token in mu.POSITIVE_WORDS for token in tokens)
        has_negative = any(token in mu.NEGATIVE_WORDS for token in tokens)

        if has_positive and has_negative:
            return {
                "label": "Neutral",
                "confidence": 0.90,
                "probs": {
                    "Negative": 0.05,
                    "Neutral": 0.90,
                    "Positive": 0.05,
                },
                "method": "mixed-sentiment-rule",
            }

        # Positive working-condition feedback.
        positive_working_words = {"perfectly", "properly", "correctly"}

        if "working" in tokens and any(
            word in tokens for word in positive_working_words
        ):
            return {
                "label": "Positive",
                "confidence": 0.90,
                "probs": {
                    "Negative": 0.05,
                    "Neutral": 0.05,
                    "Positive": 0.90,
                },
                "method": "working-condition-rule",
            }

        # Factual numeric statements without sentiment terms.
        has_polarity = has_positive or has_negative

        if any(token.isdigit() for token in tokens) and not has_polarity:
            return {
                "label": "Neutral",
                "confidence": 0.90,
                "probs": {
                    "Negative": 0.05,
                    "Neutral": 0.90,
                    "Positive": 0.05,
                },
                "method": "factual-neutral-rule",
            }

        if self.transformer is not None:
            try:
                return self._predict_transformer(prep["cleaned"])
            except Exception as error:
                log.warning("Transformer inference failed: %s", error)

        if self.bundle is not None:
            try:
                pipeline = self.bundle["sentiment"]
                probabilities = pipeline.predict_proba([prep["model_text"]])[0]
                classes = list(pipeline.classes_)
                probs = {
                    name: float(probability)
                    for name, probability in zip(classes, probabilities)
                }
                label = max(probs, key=probs.get)

                return {
                    "label": label,
                    "confidence": probs[label],
                    "probs": probs,
                    "method": "tfidf-logreg",
                }

            except Exception as error:
                log.warning("Sklearn inference failed: %s", error)

        label, confidence, probs = lexicon_sentiment(tokens)

        return {
            "label": label,
            "confidence": confidence,
            "probs": probs,
            "method": "lexicon",
        }

    def _predict_transformer(self, text):
        import torch

        tokenizer, model, labels = self.transformer
        encoded = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=128,
        )

        with torch.no_grad():
            logits = model(**encoded).logits[0]

        probabilities = torch.softmax(logits, dim=-1).tolist()
        probs = {
            labels[index]: float(probability)
            for index, probability in enumerate(probabilities)
        }
        label = max(probs, key=probs.get)

        return {
            "label": label,
            "confidence": probs[label],
            "probs": probs,
            "method": "transformer",
        }

    def predict_aspect_fallback(self, prep: dict):
        """Predict an aspect when keyword matching did not find one."""

        if (
            self.bundle is None
            or "aspect" not in self.bundle
            or not prep["concept_tokens"]
        ):
            return None, 0.0

        try:
            pipeline = self.bundle["aspect"]
            probabilities = pipeline.predict_proba([prep["model_text"]])[0]
            index = int(probabilities.argmax())

            return pipeline.classes_[index], float(probabilities[index])

        except Exception:
            return None, 0.0

    def info(self) -> dict:
        metadata = (self.bundle or {}).get("meta", {})

        if self.transformer:
            model_name = "XLM-RoBERTa (fine-tuned)"
        elif self.bundle:
            model_name = "TF-IDF + Logistic Regression + multilingual rules"
        else:
            model_name = "Lexicon rules only"

        return {
            "mode": self.mode,
            "status": self.status,
            "trained_at": metadata.get("trained_at"),
            "model_name": model_name,
        }
