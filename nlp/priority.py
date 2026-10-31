"""Severity detection and configurable priority scoring.

    Priority = Severity x Frequency x Aspect Criticality    (normalised to 0-100)

Concretely:
    severity_value  in {Low:1, Medium:2, High:3, Critical:4}
    frequency_norm  = max(min_frequency, min(count, frequency_cap) / frequency_cap)
                      where count = number of NEGATIVE feedback items about the same aspect in the
                      last `window_days` days (taken from the database, including this one)
    criticality     per aspect weight in (0, 1]
    score           = 100 * (severity_value / 4) * frequency_norm * criticality
Levels: LOW < medium_min <= MEDIUM < high_min <= HIGH < critical_min <= CRITICAL
All numbers are configurable (Admin -> Settings).
"""
from dataclasses import dataclass, field, asdict
from . import multilingual_utils as mu

SEVERITY_VALUES = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

CRITICAL_PHRASES = [("not", "working"), ("completely",), ("never",), ("unusable",), ("broken",),
                    ("major", "problem"), ("big", "problem"), ("big", "problems"), ("dangerous",), ("unsafe",),
                    ("nothing", "works"), ("worst",), ("not", "working", "at", "all")]
HIGH_WORDS = {"very", "bad", "poor", "terrible", "awful", "horrible", "useless", "waste", "slow", "problem",
              "disconnect", "disconnects", "disconnecting", "outdated", "boring", "difficult", "dirty",
              "pathetic", "unusable", "irrelevant", "old", "unavailable", "unclear", "confusing", "hard"}
MEDIUM_HINTS = {"lacking", "better", "enough", "less", "average", "little", "somewhat"}


def _contains(seq, phrase):
    n = len(phrase)
    return any(tuple(seq[i:i + n]) == phrase for i in range(len(seq) - n + 1))


def detect_severity(concept_tokens, sentiment):
    """Rule-based severity on the language-independent concept tokens."""
    if sentiment != "Negative":
        return "Low"
    toks = list(concept_tokens)
    if any(_contains(toks, ph) for ph in CRITICAL_PHRASES):
        return "Critical"
    if "not" in toks and any(w in ("working", "available") for w in toks):
        return "High" if "available" in toks and "working" not in toks else "Critical"
    if sum(1 for t in toks if t in HIGH_WORDS) >= 1 and not (set(toks) & {"little"}):
        return "High"
    return "Medium"


@dataclass
class PriorityConfig:
    criticality: dict = field(default_factory=lambda: {
        "Teaching": 1.0, "Lab/Infrastructure": 0.9, "Course Content": 0.8, "Wi-Fi": 0.85, "General": 0.6,
        "Exams": 0.9, "Assignments": 0.6, "Academic Support": 0.7,
        "Food": 0.9, "Room": 0.7, "Cleanliness": 0.8, "Water": 0.95, "Electricity": 0.9, "Security": 1.0,
        "Maintenance": 0.7, "Hostel Facilities": 0.7,
        "Transport": 0.7, "Library": 0.6, "Sports": 0.4, "Events": 0.4, "Administration": 0.7,
        "Campus Facilities": 0.6})
    frequency_cap: int = 5
    min_frequency: float = 0.3
    window_days: int = 30
    medium_min: float = 25.0
    high_min: float = 50.0
    critical_min: float = 85.0
    recurring_threshold: int = 3   # count at which an issue is "recurring" -> escalation advice
    similarity_threshold: float = 0.45   # cosine similarity above which two complaints are 'the same issue'

    @classmethod
    def from_dict(cls, d):
        base = cls()
        if not d:
            return base
        for k, v in d.items():
            if k == "criticality" and isinstance(v, dict):
                base.criticality.update({a: float(x) for a, x in v.items()})
            elif hasattr(base, k):
                setattr(base, k, type(getattr(base, k))(v))
        return base

    def to_dict(self):
        return asdict(self)


def level_for(score, cfg: PriorityConfig):
    if score >= cfg.critical_min:
        return "CRITICAL"
    if score >= cfg.high_min:
        return "HIGH"
    if score >= cfg.medium_min:
        return "MEDIUM"
    return "LOW"


def compute_priority(severity, frequency_count, aspect, cfg: PriorityConfig = None):
    cfg = cfg or PriorityConfig()
    sev_val = SEVERITY_VALUES.get(severity, 1)
    count = max(int(frequency_count), 0)
    freq_norm = max(cfg.min_frequency, min(count, cfg.frequency_cap) / float(cfg.frequency_cap))
    crit = float(cfg.criticality.get(aspect, cfg.criticality.get("General", 0.6)))
    score = round(100.0 * (sev_val / 4.0) * freq_norm * crit, 1)
    score = max(0.0, min(100.0, score))
    level = level_for(score, cfg)
    why = {
        "en": (f"Severity {severity} ({sev_val}/4) x frequency {freq_norm:.2f} ({count} similar complaint(s) in the last "
               f"{cfg.window_days} days) x {aspect} criticality {crit:.2f} = {score:.0f}/100."),
        "ta": (f"தீவிரம் {severity} ({sev_val}/4) × அதிர்வெண் {freq_norm:.2f} (கடந்த {cfg.window_days} நாட்களில் "
               f"{count} ஒத்த புகார்கள்) × {aspect} முக்கியத்துவம் {crit:.2f} = {score:.0f}/100."),
        "hi": (f"गंभीरता {severity} ({sev_val}/4) × आवृत्ति {freq_norm:.2f} (पिछले {cfg.window_days} दिनों में "
               f"{count} समान शिकायतें) × {aspect} महत्व {crit:.2f} = {score:.0f}/100."),
    }
    return {"severity": severity, "severity_value": sev_val, "frequency": count, "frequency_norm": round(freq_norm, 3),
            "criticality": crit, "score": score, "level": level, "why": why}
