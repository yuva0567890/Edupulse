# EduPulse — Multilingual Aspect-Based Sentiment & Priority Analysis for Student Feedback

EduPulse turns free-text student feedback written in **English, Tamil (தமிழ்), Hindi (हिन्दी), Tanglish and code-mixed text**
into structured insight: sentiment, aspect-level sentiment, severity, a 0-100 priority score, a plain-language
"why" explanation and a recommended action — all shown in a live admin dashboard.

> **Honest status.** The Academics / Hostel / Others rules, the similarity, trend and summary logic are covered by automated tests that run offline. The database, route and login tests need `pip install -r requirements.txt` (SQLAlchemy, pytest) and were written but **could not be executed in the sandbox where this project was generated** — run `pytest -v` after installing and report any failure.
>
> **Training data note.** The bundled training data is **synthetic** (generated from phrase templates, see `data/README.md`),
> so the evaluation numbers on the *Model Performance* page are optimistic and only show that the pipeline works.
> No metric in the UI is hard-coded: every number comes from real predictions on a held-out test split.
> Train on real, labelled feedback before drawing conclusions about a real college.

## What's new in this version
1. **Proper authentication** — Sign Up, Login (email or username), Logout and protected admin pages backed by a `users` table (see *Admin accounts* below).
2. **Academics / Hostel / Others** categories with automatic category detection (Category → Aspect → Sentiment → Severity → Priority).
3. **All Feedback** management table with filters, search, sorting, pagination and CSV export, and a detail page per feedback.
4. **Issue tracking** — negative feedback becomes an issue `EDU-YYYY-NNNN` (Open / In Progress / Resolved / Closed) with status history.
5. **Admin responses** — stored in the database and shown to the student on their result page.
6. **Duplicate / similar complaint detection** (TF-IDF cosine similarity, configurable threshold) across Tamil, English, Hindi and mixed text.
7. **Trending issues** (7 / 30 / 90 days vs the previous period; shows "not enough data" instead of inventing numbers).
8. **Critical issue alerts** (recurring issues whose priority reaches the configured critical threshold).
9. **Category and department analytics**, plus a deterministic **AI / NLP summary** computed from stored data (no external AI).
10. Multilingual NLP unchanged: Tamil, English, Hindi, Tanglish, code-mixed.
11. Dashboard cards for Total / Academics / Hostel / Others / Positive / Neutral / Negative / High / Critical / Open / Resolved and charts for Category × Sentiment, Category × Priority, Department × Category and Language × Category.

## Features
- Language identification (Unicode script analysis + Romanized Tamil/Hindi lexicons) · Unicode normalisation · Tanglish/Hinglish spelling normalisation · code-mixed handling
- Sentiment (Positive / Neutral / Negative) with model probability as confidence
- ABSA for four aspects: **Teaching, Lab/Infrastructure, Course Content, Wi-Fi** (multiple aspects per feedback)
- Priority = **Severity × Frequency × Aspect criticality**, normalised to 0-100, configurable, frequency from stored feedback
- TF-IDF explainability (tf-idf × coefficient, shown with the student's original words)
- Rule-based recommendations in English / Tamil / Hindi with escalation for recurring HIGH/CRITICAL issues
- Admin dashboard (8 charts, 8 KPI cards, filters, search, sorting, pagination, CSV export), feedback explorer, detail page, model performance page, settings
- UI language selector (English / தமிழ் / हिन्दी) — independent from NLP language support
- Database-backed admin accounts (sign up / login / logout, hashed passwords, sessions, CSRF, login lock-out), SQLite → PostgreSQL via SQLAlchemy

## Technology stack
Python 3.10-3.12 · Flask · SQLAlchemy 2 · scikit-learn · pandas · Chart.js · gunicorn · (optional) PyTorch + Transformers (XLM-RoBERTa)

## Architecture
```
Student feedback
  → Language detection            nlp/language_detection.py
  → Preprocessing + Tanglish /    nlp/preprocessing.py, nlp/multilingual_utils.py
    code-mixed normalisation
  → Sentiment                     nlp/sentiment.py   (Transformer → TF-IDF+LogReg → lexicon)
  → ABSA (clauses + aspects)      nlp/absa.py
  → Severity + Priority           nlp/priority.py
  → TF-IDF explainability         nlp/explainability.py
  → Recommendation                nlp/recommendations.py
  → Database (SQLAlchemy)         database/models.py, database/db.py
  → Admin dashboard               routes/admin.py, routes/api.py, templates/, static/
```
`nlp/pipeline.py` wires everything together and is database-free (frequency counts are injected).

## NLP pipeline in detail
1. **Cleaning**: Unicode NFC, zero-width/control characters removed, emoji → sentiment words, `Wi-Fi/wi fi/वाई-फाई` → `wifi`, `isn't` → `is not`.
2. **Tokenisation**: script-aware regex (Tamil block, Devanagari block without the danda, Latin, digits) so Indic words with combining marks stay whole.
3. **Normalisation**: Romanized spelling variants (`romba/rombha`, `bahut/bohot`), elongations (`sooo`), phrase rules (`nalla illa → not good`, `अच्छा नहीं → not good`, `வேலை செய்யவில்லை → not working`).
4. **Shared concept space**: Tamil, Hindi and Romanized words are mapped to English concept tokens (`மெதுவாக`, `धीमा`, `slow` → `slow`) so one model serves every language. Tamil suffixes are stripped for lexicon lookup.
5. **Sentiment**: TF-IDF (word 1-2 grams) + Logistic Regression. If `models/saved/transformer/` exists and `torch`/`transformers` import, a fine-tuned XLM-R is used instead. If no model exists the lexicon scorer is used — the app never crashes.
6. **ABSA**: clause splitting at connectors (`but / ஆனால் / लेकिन / aana / lekin …`), keyword lexicon per aspect (applied to concept tokens), ML aspect classifier as fallback, per-clause sentiment.
7. **Severity**: rules on concept tokens → Low / Medium / High / Critical (`not working`, `completely`, `worst` → Critical).
8. **Priority**: `score = 100 × (severity/4) × frequency_norm × criticality`, where `frequency_norm = max(min_frequency, min(count, cap)/cap)` and `count` = negative feedback for that aspect in the last N days (from the DB). Levels: LOW < 25 ≤ MEDIUM < 50 ≤ HIGH < 85 ≤ CRITICAL. All values editable under **Admin → Settings**.
9. **Explainability + recommendation** as described above.

**NLP mode** (shown in the UI): `Multilingual Transformer` when a fine-tuned transformer is loaded, otherwise `Fallback / Demo` (TF-IDF + Logistic Regression + rules).

## Installation (Windows + Visual Studio Code)
1. Install **Python 3.10 – 3.12** from python.org (tick *Add python.exe to PATH*) and **VS Code** with the *Python* extension.
2. Unzip `EduPulse_Project.zip`, then in VS Code: **File → Open Folder…** → choose the `EduPulse_Project` folder.
3. Open a terminal in VS Code (**Terminal → New Terminal**, PowerShell) and run:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # optional: a ready-made .env is already included (it holds no admin password)
python app.py
```
If PowerShell blocks activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again.

4. Open **http://127.0.0.1:5000**. In VS Code pick the interpreter with *Ctrl+Shift+P → Python: Select Interpreter → .\venv\Scripts\python.exe*. You can also press **F5** (a launch configuration is included).

macOS / Linux: `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && cp .env.example .env && python app.py`

On the first start the app trains the TF-IDF model from `data/training_data.csv` (a few seconds) and writes it, plus real evaluation metrics, to `models/saved/`.

## Admin accounts: Sign Up and Login (database based)

There is **no built-in or hard-coded admin account** and nothing about the login lives in `.env`. Accounts are rows in the `users` table (`id, username, email, password_hash, role, created_at, is_active`); passwords are stored only as salted hashes (`werkzeug.security`, scrypt, PBKDF2 fallback).

1. Start the app: `python app.py`
2. Open **http://127.0.0.1:5000/admin/signup**, enter *username, email, password, confirm password* (password ≥ 8 characters) and press **Sign Up** → "Account created successfully. Please login."
3. On **/admin/login** sign in with your **email or username** + password → you land on **/admin/dashboard**.
4. **Logout** (sidebar button or `/admin/logout`) clears the session and returns to the login page. Every admin page and `/api/dashboard/*`, `/api/feedback*`, `/api/issues` endpoint requires a valid login.

*Optional helpers* (you do not need them): `python scripts/create_admin.py --username demo --email demo@example.com --password "Demo@12345"` creates/resets an account (also `--prompt`, `--list`); `python scripts/check_auth.py` runs a self-test of signup/login/logout on a throw-away database and prints exactly which step fails, with library versions.

**Who may sign up?** Locally sign-up is open. In production (Render) only the **first** account can be created; after that `/admin/signup` is closed unless you set `ALLOW_SIGNUP=true`. Set `ADMIN_SIGNUP_CODE=<secret>` to require an invitation code for every additional account. (Open sign-up means anyone who can reach the site can become an admin, so do not leave it open on a public server.)

**Upgrading from an older version:** accounts from the old `admin_users` table are copied into `users` automatically on start (their e-mail becomes `<username>@edupulse.local`; they keep their old password). The old `ADMIN_USERNAME` / `ADMIN_PASSWORD` settings are no longer used. Existing feedback is untouched.

**Security notes:** passwords are never stored or logged in plain text; login uses CSRF-protected forms, an HttpOnly session cookie, a 5-failure / 10-minute lock-out per IP, and a constant-time-style check for unknown users; usernames/emails are unique case-insensitively; open redirects after login are blocked. The server log records *why* a login failed (no such user / wrong password) but never the password.

## Demo data
`AUTO_SEED=true` (default in `.env.example`) loads ~260 synthetic demo submissions into an empty database so the charts are populated. Or run:
```powershell
python scripts/seed_database.py --reset
```
Regenerate the synthetic datasets with `python scripts/generate_dataset.py`.

## Training and evaluation
```powershell
python training/train.py                     # CSV → preprocessing → 70/15/15 split → train → evaluate → save
python training/evaluate.py                  # re-evaluate the saved model on the saved test split
python training/train.py --data my_data.csv  # your own data
pip install -r requirements-transformer.txt
python training/train.py --transformer       # OPTIONAL: fine-tune xlm-roberta-base (GPU recommended)
```
CSV columns: `text, language, sentiment, aspect, severity` (+ optional `level` = `clause` | `full`; multi-aspect rows use `Teaching|Wi-Fi`).
Reported: accuracy, macro precision/recall/F1, weighted F1, confusion matrix, per-language (Tamil / English / Hindi / Mixed / Overall), per-aspect, severity-rule accuracy.
> The transformer path (`--transformer`) is provided but was **not executed** while building this project (no GPU/internet there) — treat it as untested.

## Testing
```powershell
pytest -v
```
The suite includes the exact flow *sign up → login → dashboard → submit feedback → logout → login → feedback still visible*, also with CSRF enforcement as in production (`tests/test_auth.py`, `tests/test_browser_flow.py`).
Covers language detection, preprocessing, Tamil / English / Hindi / Tanglish / mixed input, sentiment, ABSA, priority, recommendations, fallback mode, database, API, admin authentication, CSV export.

## Categories and aspects
| Category | Aspects |
|---|---|
| **Academics** | Teaching, Lab/Infrastructure, Course Content, Wi-Fi (campus), Exams, Assignments, Academic Support |
| **Hostel** | Food, Room, Cleanliness, Water, Electricity, Security, Maintenance, Hostel Facilities, Wi-Fi (when the text talks about the hostel) |
| **Others** | Transport, Library, Sports, Events, Administration, Campus Facilities, General |

The student may pick a category or leave **Auto Detect**. The rule-based detector (aspect keyword lexicon in `nlp/absa.py` + category rules in `nlp/categories.py`) always runs; if the student's choice differs from what was detected, the student's choice is kept and the detected category is stored and shown. To extend the rules without touching code, edit `data/category_rules.json` (`aspect_category`, `aspect_keywords`, `hostel_context`) and restart.

## Issues, responses, similarity, trends, alerts, summary
* **Issues** — every negative feedback gets an issue id `EDU-<year>-<seq>`; admins change the status on *Issues* or the feedback detail page; every change is stored in `issue_history`. Admin responses are stored in `admin_responses` and shown to the student on their result page.
* **Similar complaints** — the complaint text is reduced to a language-independent form (e.g. *"WiFi is very slow"*, *"Wifi romba slow ah iruku"*, *"Internet speed is poor"*, *"WiFi बहुत slow है"* → `wifi slow`) and compared with TF-IDF cosine similarity inside the same aspect. Threshold: **Settings → Similar-complaint threshold** (default 0.45). The dashboard shows count, language split (Tamil / English / Hindi / Mixed) and priority per recurring issue.
* **Trending** — negative complaints per aspect in the last 7/30/90 days vs the previous equal period. If either period has fewer than 3 feedback items the page says *"Not enough historical data to calculate a trend."*; a previous count of 0 is shown as **NEW**, never as a made-up percentage.
* **Critical alerts** — recurring issues whose priority score ≥ the critical threshold (Settings, default 85). With no such issue the panel says so.
* **AI / NLP summary** — bullets built from the stored statistics only (totals, top category, top aspect, trend, top recurring issue, main language, open issues); no external AI or API key is used.

## Database changes and migration
New columns on `feedback` (`category`, `category_selected`, `category_detected`, `status`, `admin_response`, `issue_id`, `updated_at`) and `analysis_results` (`category`), and new tables `issues`, `issue_history`, `admin_responses`. On start `database/db.py` adds missing columns with `ALTER TABLE … ADD COLUMN` and back-fills the category / issues for older rows — **no data is dropped**, so you can keep using your existing `instance/edupulse.db`.

## Pages and API
Pages: `/`, `/feedback`, `/result/<id>`, `/admin/login`, `/admin/dashboard`, `/admin/feedback` (All Feedback), `/admin/feedback/<id>`, `/admin/issues`, `/admin/analytics`, `/admin/model-performance`, `/admin/settings`, `/healthz`.

| Method | Endpoint | Access |
|---|---|---|
| POST | `/api/analyze` `{"text": "...", "language": "Auto Detect"}` | public (not stored) |
| POST | `/api/feedback` | public (stored, 201) |
| GET | `/api/feedback`, `/api/feedback/<id>` | admin session |
| GET | `/api/dashboard/stats \| trends \| aspects \| languages` | admin session (filters as query params) |
| GET | `/api/dashboard/trending?period=7\|30\|90`, `/critical`, `/similar`, `/summary?period=`, `/recent` | admin session |
| GET | `/api/issues` | admin session |
| POST | `/api/feedback/<id>/status` `{status, note}`, `/api/feedback/<id>/response` `{response, status?}` | admin session |
| GET | `/api/categories` | public |
| GET | `/api/model/performance` | admin session |

## Render deployment
1. Push the project to a GitHub repository (`.env` and `instance/` are git-ignored).
2. On https://render.com choose **New → Blueprint**, select the repo; Render reads `render.yaml`.
3. `SECRET_KEY` is generated automatically. Open `https://<your-service>.onrender.com/admin/signup` **immediately after the first deploy** to create the first admin account (sign-up closes afterwards because `ALLOW_SIGNUP=false`; use a PostgreSQL `DATABASE_URL` so the account survives restarts).
4. Build runs `pip install -r requirements.txt && python training/train.py`; start command is `gunicorn app:app …` (same as `Procfile`).
5. **Data persistence:** Render's free disk is ephemeral, so SQLite data is lost on redeploy/restart. For real use create a Render **PostgreSQL** database and set `DATABASE_URL` to its internal URL (the app converts `postgres://` automatically). With `AUTO_SEED=true` demo data is re-created only when the database is empty — set it to `false` for production.

Environment variables: `SECRET_KEY`, `DATABASE_URL`, `AUTO_SEED`, `ALLOW_SIGNUP`, `ADMIN_SIGNUP_CODE`, `FLASK_DEBUG`, `PORT`.

## Limitations
- Synthetic seed data; real feedback is noisier. Metrics on it are optimistic.
- Lexicon-based normalisation covers common Tamil / Hindi / Tanglish words only; unseen spellings and vocabulary can be misclassified (e.g. unfamiliar negative words), sarcasm and long-range negation are not handled.
- Clause splitting is heuristic; very long, run-on feedback may attach an opinion to the wrong aspect.
- Priority depends on stored volume: a single complaint scores low by design (frequency factor).
- Chart.js and Google Fonts load from CDNs, so the dashboard charts need internet access.
- Rate limiting / login lock-out are in-memory (per process).

## Future enhancements
Fine-tuned XLM-R / IndicBERT trained on real labelled data · more aspects (hostel, canteen, administration) · CSV upload for bulk analysis · email alerts for CRITICAL items · per-department dashboards · Alembic migrations · transliteration of Tanglish to Tamil script.
