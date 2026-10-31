"""Analytics on stored feedback: duplicate / similar complaint detection, trending issues,
critical alerts and a deterministic local summary.

Everything here is a pure function over plain dicts (no database access), so it is easy to test
and never invents data: if there is not enough data the functions say so.

Row format (one per aspect mention) produced by database.db.fetch_rows():
    {feedback_id, timestamp(datetime), language, category, aspect, sentiment, severity, priority,
     score, clause, department}
"""
from collections import Counter, defaultdict
from datetime import timedelta

from .language_detection import primary_language
from .preprocessing import preprocess
from .priority import PriorityConfig, SEVERITY_VALUES, compute_priority
from .recommendations import ASPECT_I18N, recommend
from .categories import CATEGORY_I18N

LANG_BUCKETS = ["Tamil", "English", "Hindi", "Mixed"]
MIN_TREND_RECORDS = 3

# --------------------------------------------------------------------------- languages
def language_bucket(label: str) -> str:
    """Tamil / English / Hindi = single-script text; everything code-mixed (Tanglish, Hinglish,
    Tamil+English, Hindi+English, Mixed) is 'Mixed'."""
    if label == "English":
        return "English"
    if label == "Tamil":
        return "Tamil"
    if label == "Hindi":
        return "Hindi"
    return "Mixed"


# --------------------------------------------------------------------------- similarity
_SYNONYMS = {"internet": "wifi", "network": "wifi", "connection": "wifi", "connectivity": "wifi", "lan": "wifi",
             "broadband": "wifi", "signal": "wifi", "lag": "slow", "laggy": "slow", "speed": "slow",
             "delayed": "late", "delay": "late", "meal": "food", "meals": "food", "mess": "food",
             "teacher": "teaching", "teachers": "teaching", "faculty": "teaching", "lecturer": "teaching",
             "professor": "teaching", "explanation": "teaching", "teach": "teaching", "teaches": "teaching",
             "computers": "computer", "equipments": "equipment", "buses": "bus", "toilets": "toilet",
             "washroom": "toilet", "washrooms": "toilet", "bathroom": "toilet", "bathrooms": "toilet",
             "cut": "cut", "cuts": "cut"}
_DROP = {"very", "too", "so", "really", "is", "are", "was", "were", "the", "a", "an", "of", "in", "at", "to", "it",
         "this", "that", "and", "but", "bad", "poor", "terrible", "worst", "awful", "horrible", "good", "great",
         "ah", "iruku", "hai", "hain", "always", "all", "time", "some", "college", "our", "my", "we", "i", "very",
         "needs", "need", "improvement", "problem", "issue", "completely", "totally", "extremely", "less", "ok"}


def canonical_issue_text(clause: str) -> str:
    """Language-independent 'what is the complaint about' text: concept tokens, synonyms merged,
    filler / intensity words removed. 'Wifi romba slow ah iruku' and 'WiFi बहुत slow है' -> 'wifi slow'."""
    toks = []
    for t in preprocess(clause)["concept_tokens"]:
        t = _SYNONYMS.get(t, t)
        if len(t) < 2 or t in _DROP:
            continue
        toks.append(t)
    return " ".join(dict.fromkeys(toks))      # de-duplicate, keep order


def _components(n, pairs):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


def cluster_complaints(rows, cfg: PriorityConfig = None, min_size=1, max_rows=4000):
    """Group NEGATIVE aspect rows into recurring issues using TF-IDF cosine similarity on the
    canonical complaint text (rows are only compared inside the same aspect).
    Returns clusters sorted by priority score (highest first)."""
    cfg = cfg or PriorityConfig()
    neg = [r for r in rows if r["sentiment"] == "Negative"]
    neg.sort(key=lambda r: r["timestamp"], reverse=True)
    neg = neg[:max_rows]
    by_aspect = defaultdict(list)
    for r in neg:
        r = dict(r)
        r["canon"] = canonical_issue_text(r.get("clause", "")) or "__general__"
        by_aspect[r["aspect"]].append(r)

    clusters = []
    for aspect, items in by_aspect.items():
        pairs = []
        if len(items) > 1:
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
                vec = TfidfVectorizer(token_pattern=r"\S+", lowercase=False)
                X = vec.fit_transform([i["canon"] for i in items])
                sim = cosine_similarity(X)
                thr = cfg.similarity_threshold
                n = len(items)
                pairs = [(i, j) for i in range(n) for j in range(i + 1, n) if sim[i, j] >= thr]
            except Exception:       # e.g. empty vocabulary
                pairs = [(i, j) for i in range(len(items)) for j in range(i + 1, len(items))
                         if items[i]["canon"] == items[j]["canon"]]
        for comp in _components(len(items), pairs):
            members = [items[i] for i in comp]
            fids = sorted({m["feedback_id"] for m in members})
            if len(fids) < min_size:
                continue
            words = Counter(w for m in members for w in m["canon"].split() if w != "__general__")
            top_words = [w for w, _ in words.most_common(3)]
            sev = max((m["severity"] for m in members), key=lambda s: SEVERITY_VALUES.get(s, 1))
            pr = compute_priority(sev, len(fids), aspect, cfg)
            langs = Counter(language_bucket(m["language"]) for m in members)
            cats = Counter(m["category"] for m in members)
            latest = max(members, key=lambda m: m["timestamp"])
            category = cats.most_common(1)[0][0]
            rec = recommend(aspect, "Negative", pr["level"], len(fids), cfg.recurring_threshold)
            clusters.append({
                "key": f"{aspect}|{' '.join(top_words)}|{min(fids)}",
                "label": " ".join(top_words) if top_words else "general complaints",
                "aspect": aspect, "category": category, "count": len(fids),
                "languages": {b: langs.get(b, 0) for b in LANG_BUCKETS},
                "severity": sev, "priority": pr["level"], "score": pr["score"], "priority_why": pr["why"],
                "sample": latest.get("clause", ""), "first_seen": min(m["timestamp"] for m in members).isoformat(timespec="seconds"),
                "last_seen": latest["timestamp"].isoformat(timespec="seconds"),
                "feedback_ids": fids[:100], "recommendation": rec,
            })
    clusters.sort(key=lambda c: (-c["score"], -c["count"]))
    return clusters


def similar_feedback_ids(clusters, feedback_id, aspect=None):
    """Other feedback ids that belong to the same recurring issue(s) as `feedback_id`."""
    out = []
    for c in clusters:
        if feedback_id in c["feedback_ids"] and (aspect is None or c["aspect"] == aspect):
            out.append({"cluster": c, "others": [i for i in c["feedback_ids"] if i != feedback_id]})
    return out


# --------------------------------------------------------------------------- critical alerts
def critical_alerts(clusters, cfg: PriorityConfig = None):
    """Recurring issues whose priority score reaches the configured CRITICAL threshold."""
    cfg = cfg or PriorityConfig()
    return [c for c in clusters if c["score"] >= cfg.critical_min]


# --------------------------------------------------------------------------- trends
def trending_issues(rows, feedback_times, period_days, now, min_records=MIN_TREND_RECORDS, limit=8):
    """Compare negative complaints per aspect in the last `period_days` with the previous period.

    rows            negative/any aspect rows (see module doc)
    feedback_times  list of timestamps, one per feedback (to check that there is enough data)
    Returns {'status': 'ok'|'insufficient'|'no_changes', ...}. Never fabricates a percentage:
    when the previous count is 0 the entry is marked 'new' with change_pct None.
    """
    recent_start, prev_start = now - timedelta(days=period_days), now - timedelta(days=2 * period_days)
    n_recent = sum(1 for t in feedback_times if recent_start <= t <= now)
    n_prev = sum(1 for t in feedback_times if prev_start <= t < recent_start)
    base = {"period_days": period_days, "recent_total": n_recent, "previous_total": n_prev}
    if n_recent < min_records or n_prev < min_records:
        return {**base, "status": "insufficient", "items": [],
                "message": "Not enough historical data to calculate a trend."}
    recent, prev, cat = defaultdict(set), defaultdict(set), {}
    for r in rows:
        if r["sentiment"] != "Negative":
            continue
        t = r["timestamp"]
        if recent_start <= t <= now:
            recent[r["aspect"]].add(r["feedback_id"])
        elif prev_start <= t < recent_start:
            prev[r["aspect"]].add(r["feedback_id"])
        cat[r["aspect"]] = r["category"]
    items = []
    for a in set(recent) | set(prev):
        c, p = len(recent[a]), len(prev[a])
        if c + p < 2:
            continue
        if p == 0:
            direction, pct = "new", None
        else:
            pct = round(100.0 * (c - p) / p, 1)
            direction = "up" if c > p else "down" if c < p else "flat"
        items.append({"aspect": a, "category": cat.get(a, "Others"), "recent": c, "previous": p,
                      "change_pct": pct, "direction": direction})
    items.sort(key=lambda x: -abs(x["recent"] - x["previous"]))
    items = items[:limit]
    if not items:
        return {**base, "status": "no_changes", "items": [], "message": "No notable change in complaints between the two periods."}
    return {**base, "status": "ok", "items": items}


# --------------------------------------------------------------------------- summary
_T = {
    "total": {
        "en": "{n} feedback item(s) received in the last {p} days; {neg} ({pct}%) negative.",
        "ta": "கடந்த {p} நாட்களில் {n} கருத்துகள் பெறப்பட்டன; {neg} ({pct}%) எதிர்மறை.",
        "hi": "पिछले {p} दिनों में {n} फीडबैक मिले; {neg} ({pct}%) नकारात्मक।"},
    "top_cat": {
        "en": "{cat} received the most complaints ({k}).",
        "ta": "{cat} பிரிவில் அதிக புகார்கள் ({k}) பெறப்பட்டன.",
        "hi": "{cat} श्रेणी में सबसे अधिक शिकायतें ({k}) मिलीं।"},
    "top_aspect": {
        "en": "{asp} was the most frequently discussed {cat} aspect ({m} mentions).",
        "ta": "{cat} பிரிவில் {asp} அதிகம் விவாதிக்கப்பட்ட அம்சம் ({m} குறிப்புகள்).",
        "hi": "{cat} में {asp} सबसे अधिक चर्चित पहलू रहा ({m} उल्लेख)।"},
    "trend_up": {
        "en": "{asp} complaints increased by {pct}% compared with the previous {p} days.",
        "ta": "முந்தைய {p} நாட்களுடன் ஒப்பிடும்போது {asp} புகார்கள் {pct}% அதிகரித்துள்ளன.",
        "hi": "पिछले {p} दिनों की तुलना में {asp} शिकायतें {pct}% बढ़ीं।"},
    "trend_new": {
        "en": "{asp} complaints are new this period ({c} vs 0 in the previous {p} days).",
        "ta": "{asp} புகார்கள் இந்த காலத்தில் புதியவை ({c}; முந்தைய {p} நாட்களில் 0).",
        "hi": "{asp} शिकायतें इस अवधि में नई हैं ({c}; पिछले {p} दिनों में 0)।"},
    "trend_down": {
        "en": "{asp} complaints decreased by {pct}% compared with the previous {p} days.",
        "ta": "முந்தைய {p} நாட்களுடன் ஒப்பிடும்போது {asp} புகார்கள் {pct}% குறைந்துள்ளன.",
        "hi": "पिछले {p} दिनों की तुलना में {asp} शिकायतें {pct}% घटीं।"},
    "cluster": {
        "en": "{label} ({asp}) is the highest-priority recurring issue: {c} similar complaints, priority {score}/100.",
        "ta": "{label} ({asp}) அதிக முன்னுரிமை கொண்ட தொடர்ச்சியான சிக்கல்: {c} ஒத்த புகார்கள், முன்னுரிமை {score}/100.",
        "hi": "{label} ({asp}) सर्वोच्च प्राथमिकता की बार-बार आने वाली समस्या है: {c} समान शिकायतें, प्राथमिकता {score}/100।"},
    "lang": {
        "en": "Most feedback was submitted in {lang} ({k} of {n}).",
        "ta": "பெரும்பாலான கருத்துகள் {lang} மொழியில் ({k}/{n}) சமர்ப்பிக்கப்பட்டன.",
        "hi": "अधिकांश फीडबैक {lang} भाषा में ({k}/{n}) दिए गए।"},
    "issues": {
        "en": "{o} issue(s) are open or in progress and {c} are critical.",
        "ta": "{o} சிக்கல்கள் திறந்த/செயலில் உள்ளன; {c} மிக முக்கியமானவை.",
        "hi": "{o} समस्याएँ खुली/प्रगति में हैं और {c} गंभीर हैं।"},
}


def _fmt(key, **kw):
    return {lg: _T[key][lg].format(**kw) for lg in ("en", "ta", "hi")}


def build_summary(items, rows, clusters, trend, issue_counts, period_days, now, cfg: PriorityConfig = None):
    """Deterministic summary of the last `period_days` of stored feedback. No external AI is used;
    every statement is computed from the data and omitted when it cannot be supported."""
    cfg = cfg or PriorityConfig()
    start = now - timedelta(days=period_days)
    win = [i for i in items if start <= i["_dt"] <= now]
    out = {"period_days": period_days, "generated_by": "local statistics (no external AI)", "bullets": [], "empty": False}
    if not win:
        out["empty"] = True
        out["message"] = "No feedback available for this period."
        return out
    neg_items = [i for i in win if i["sentiment"] == "Negative"]
    pct = round(100.0 * len(neg_items) / len(win), 1)
    out["bullets"].append(_fmt("total", n=len(win), p=period_days, neg=len(neg_items), pct=pct))

    cats = Counter(i["category"] for i in neg_items)
    if cats:
        cat, k = cats.most_common(1)[0]
        cl = {lg: CATEGORY_I18N[cat][lg] for lg in ("en", "ta", "hi")}
        out["bullets"].append({lg: _T["top_cat"][lg].format(cat=cl[lg], k=k) for lg in ("en", "ta", "hi")})
        win_ids = {i["id"] for i in win}
        mentions = Counter(r["aspect"] for r in rows if r["feedback_id"] in win_ids and r["category"] == cat)
        if mentions:
            asp, m = mentions.most_common(1)[0]
            al = ASPECT_I18N.get(asp, {"en": asp, "ta": asp, "hi": asp})
            out["bullets"].append({lg: _T["top_aspect"][lg].format(asp=al[lg], cat=cl[lg], m=m) for lg in ("en", "ta", "hi")})

    if trend and trend.get("status") == "ok":
        best = max((t for t in trend["items"] if t["direction"] in ("up", "new")),
                   key=lambda t: (t["recent"] - t["previous"]), default=None)
        if best:
            al = ASPECT_I18N.get(best["aspect"], {"en": best["aspect"], "ta": best["aspect"], "hi": best["aspect"]})
            if best["direction"] == "up":
                out["bullets"].append({lg: _T["trend_up"][lg].format(asp=al[lg], pct=best["change_pct"], p=period_days)
                                       for lg in ("en", "ta", "hi")})
            else:
                out["bullets"].append({lg: _T["trend_new"][lg].format(asp=al[lg], c=best["recent"], p=period_days)
                                       for lg in ("en", "ta", "hi")})
        else:
            worst_down = min(trend["items"], key=lambda t: (t["change_pct"] if t["change_pct"] is not None else 0), default=None)
            if worst_down and worst_down["direction"] == "down":
                al = ASPECT_I18N.get(worst_down["aspect"], {"en": worst_down["aspect"], "ta": worst_down["aspect"], "hi": worst_down["aspect"]})
                out["bullets"].append({lg: _T["trend_down"][lg].format(asp=al[lg], pct=abs(worst_down["change_pct"]), p=period_days)
                                       for lg in ("en", "ta", "hi")})

    rec = [c for c in clusters if c["count"] >= 2]
    if rec:
        c = rec[0]
        al = ASPECT_I18N.get(c["aspect"], {"en": c["aspect"], "ta": c["aspect"], "hi": c["aspect"]})
        out["bullets"].append({lg: _T["cluster"][lg].format(label=c["label"], asp=al[lg], c=c["count"], score=round(c["score"]))
                               for lg in ("en", "ta", "hi")})

    langs = Counter(i["language"] for i in win)
    lang, k = langs.most_common(1)[0]
    out["bullets"].append({lg: _T["lang"][lg].format(lang=lang, k=k, n=len(win)) for lg in ("en", "ta", "hi")})

    if issue_counts:
        out["bullets"].append(_fmt("issues", o=issue_counts.get("open", 0) + issue_counts.get("in_progress", 0),
                                   c=issue_counts.get("critical", 0)))
    return out
