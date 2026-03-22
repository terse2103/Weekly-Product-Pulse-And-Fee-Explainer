# 📋 Weekly Product Pulse & Fee Explainer

> Turn **INDMoney Play Store reviews** into a **one-page weekly pulse** and a **ready-to-send email** — powered by Groq LLaMA 3.3 70B.

---

## What It Does

| Input | Output |
|-------|--------|
| Last 12 weeks of INDMoney Play Store reviews | ✅ Scannable weekly note (≤ 250 words) |
| | ✅ Professional HTML email, ready to send |

### The Weekly Note Contains

- **📊 Top 3 Themes** — what users are talking about most (with review counts)
- **💬 3 Real User Quotes** — verbatim, PII-free, complete (not truncated)
- **💡 3 Action Ideas** — concrete next steps (key words highlighted in bold)

---

## Who This Helps

| Team | Value |
|------|-------|
| **Product / Growth** | Understand what to fix next |
| **Support** | Know what users are saying |
| **Leadership** | Quick weekly health check |

---

## Architecture (8 Phases)

```
Phase 1 → Phase 2a → Phase 2b → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8
Ingest     Clean      PII        Theme     Group      Note       Web UI    Email      Scheduler
Reviews    & Dedup    Filter     Generate  into       Generate   & Backend  Draft     (GitHub
                                           Themes                          & Send     Actions)
```

| Phase | Name | What Happens |
|-------|------|--------------|
| **1** | Data Ingestion | Fetch Play Store reviews for `in.indwealth` (last 12 weeks, paginated, SHA-256 hashed IDs) |
| **2a** | Cleaning & Dedup | Normalize text, remove emojis, filter short (<5 words) & non-English reviews, Jaccard dedup |
| **2b** | Privacy Filtering | Regex-based PII redaction (emails, UPI, phones, long numbers, @mentions) + second-pass validation |
| **3** | LLM Theme Generation | Discover 3–5 themes via Groq LLaMA 3.3 70B (batches of 50, cross-batch merge) |
| **4** | Grouping into Themes | Classify each review into exactly one theme (or "Other") via Groq LLaMA 3.3 70B |
| **5** | Weekly Note Generation | Generate strictly < 250-word scannable one-pager (allowing slightly longer user quotes under constraint) via Groq LLaMA 3.3 70B |
| **6** | Web UI & Backend | FastAPI REST API backend + Vercel static frontend (HTML/CSS/JS) |
| **7** | Email Draft & Delivery | Markdown → HTML email, cascading delivery: Gmail API → SMTP → local .eml |
| **8** | Scheduler | Automated Sunday runs via GitHub Actions (`cron: 0 4 * * 0`) |

See [Architecture.md](Architecture.md) for the full phase-wise breakdown, prompts, LLM configs, and data flow.

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```bash
GROQ_API_KEY=your_groq_api_key_here

# SMTP email (optional — for Phase 7 email delivery)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASS=your_app_password

# Gmail API (optional — alternative to SMTP)
# GMAIL_CREDENTIALS=/path/to/credentials.json
```

### 3. Run the Full Pipeline

```bash
python main.py
```

This runs Phases 1–5 sequentially. To also auto-send the email:

```bash
RECIPIENT_NAME="Priya Sharma" RECIPIENT_EMAIL="priya@company.com" python main.py
```

### 4. Launch the Frontend & Backend locally

```bash
# Start the FastAPI backend
uvicorn api_server:api --host 0.0.0.0 --port 8000 --reload
```
You can now open `phase6_web_ui/static/index.html` in your browser. The frontend will communicate directly with the local FastAPI instance (provided `window.__BACKEND_URL__` is mapped accordingly).

The frontend provides:
- **🚀 Run Pipeline** — trigger Phases 1–5 in the background
- **📄 Latest Note** — view the most recent weekly note
- **✉️ Send Email** — dispatch to any recipient

### 5. Check Outputs

- `output/weekly_note_{date}.md` — the weekly pulse note
- `output/email_draft_{date}.eml` — email draft (fallback when no email config)

---

## Deployment

### Architecture

```
┌────────────────────────┐        ┌───────────────────────────────────┐
│  Public Frontend       │        │  Backend                          │
│  (Vercel Static)       │        │  (Streamlit Cloud)                │
│                        │        │                                   │
│  index.html            │        │  api_server.py (FastAPI)          │
│  style.css             │ CORS   │   ├─ /api/run    (trigger)        │
│  script.js             │ ─────▶ │   ├─ /api/status (poll status)    │
│                        │        │   ├─ /api/note   (fetch note)     │
│  All requests routed   │        │   └─ /api/send   (trigger email)  │
│  dynamically via API   │        │                                   │
└────────────────────────┘        └───────────────────────────────────┘
```

### Frontend — Vercel (Static)

The `phase6_web_ui/static/` directory is deployed as a static site via `vercel.json`.

The frontend communicates with the backend directly using CORS requests. Ensure `window.__BACKEND_URL__` in `index.html` is set to the URL of your deployed FastAPI backend.

### Backend — Streamlit Cloud (FastAPI)

`api_server.py` is the primary entry point. Deploy to Streamlit Cloud using their container ecosystem to run FastAPI.

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key for LLM calls |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS` | For email delivery |

REST API Endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/api/health` | GET | Health check |
| `/api/note` | GET | Latest weekly note (JSON) |
| `/api/send` | POST | Send email. Returns 502 if Network blocks SMTP. |
| `/api/status` | GET | Pipeline status |
| `/api/run` | POST | Trigger pipeline (background task) |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Play Store Data | `google-play-scraper` |
| Language Detection | `langdetect` |
| LLM | Groq — **`llama-3.3-70b-versatile`** |
| PII Filtering | Regex (5 ordered patterns) |
| REST API Backend | FastAPI |
| Web Frontend | Vanilla HTML / CSS / JS + `marked.js` |
| Frontend Hosting | Vercel (Static) |
| Email | Gmail API / SMTP / Local `.eml` |
| Scheduler | GitHub Actions (every Sunday, `cron: 0 4 * * 0`) |
| Config | `python-dotenv` (`.env` file) |
| Testing | `pytest` + `httpx` |

---

## Constraints

- ✅ **Public reviews only** — no scraping behind logins
- ✅ **≤ 5 themes** — focused, not noisy (hard cap in code + prompt)
- ✅ **< 250 words** — strictly enforced limit for the scannable one-pager (allowing slightly longer quotes while staying under the limit, validated by `word_counter.py`)
- ✅ **No truncated quotes** — real user quotes are verbatim and fully complete
- ✅ **No PII** — emails, phones, UPI IDs, @mentions are stripped via regex
- ✅ **English only** — non-English reviews filtered via `langdetect`
- ✅ **Anonymized IDs** — review IDs hashed with SHA-256
- ✅ **Minimum review length** — reviews with <5 words are discarded

---

## Project Structure

```
├── main.py                       # Pipeline orchestrator (Phases 1–5 + optional Phase 7)
├── api_server.py                 # FastAPI REST API (6 endpoints, backend orchestrator)
├── vercel.json                   # Vercel static deployment config
├── requirements.txt              # Python dependencies
├── packages.txt                  # System packages for Streamlit Cloud
├── openapi.json                  # Generated OpenAPI 3.1.0 spec
├── pytest.ini                    # pytest config
├── .env                          # API keys & SMTP credentials (gitignored)
│
├── phase1_ingestion/             # Fetch Play Store reviews (google-play-scraper)
├── phase2_cleaning/              # 2a: Clean, filter, dedup | 2b: PII redaction & validation
├── phase3_theme_generation/      # Groq LLM theme discovery (batch + merge)
├── phase4_grouping/              # Assign each review to a theme via Groq LLM
├── phase5_note_generation/       # Generate ≤250-word weekly note via Groq LLM
├── phase6_web_ui/                # Static frontend (HTML/CSS/JS)
├── phase7_email/                 # Email: markdown→HTML, Gmail API / SMTP / .eml fallback
├── phase8_scheduler/             # GitHub Actions docs & setup guide
│
├── .github/workflows/
│   └── weekly_pulse.yml          # Automated Sunday pipeline runs
│
├── .devcontainer/
│   └── devcontainer.json         # VS Code Dev Container config
│
├── data/                         # Intermediate data files (gitignored)
│   ├── raw_reviews.json          # Phase 1 output
│   ├── normalized_reviews.json   # Phase 2a output
│   ├── clean_reviews.json        # Phase 2b output
│   ├── themes.json               # Phase 3 output
│   └── themed_reviews.json       # Phase 4 output
│
├── output/                       # Final outputs (gitignored)
│   ├── weekly_note_{date}.md     # Phase 5 output
│   └── email_draft_{date}.eml    # Phase 7 fallback output
│
├── docs/                         # Contains README.md and Architecture.md
```

---

## License

Internal project — Generative AI Bootcamp @ Next Leap.
