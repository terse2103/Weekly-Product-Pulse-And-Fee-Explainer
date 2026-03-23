# 📋 Weekly Product Pulse & Fee Explainer

> Turn **INDMoney Play Store reviews** into a **one-page weekly pulse** and a **ready-to-send email** — powered by Groq LLaMA 3.3 70B.

---

## What It Does

| Input | Output |
|-------|--------|
| Last 12 weeks of INDMoney Play Store reviews | ✅ Scannable weekly note (≤ 250 words) |
| | ✅ Professional HTML email with fee explanation appendix |
| | ✅ Combined JSON record appended to a Google Doc (via MCP) |

### The Weekly Note Contains

- **📊 Top Themes** — what users are talking about most (with review counts and one-liner descriptions)
- **💬 User Quotes** — verbatim, PII-free, complete (not truncated), one per top theme
- **💡 Action Ideas** — concrete next steps (key words highlighted in bold)

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
Ingest     Clean      PII        Theme     Group      Note       Web UI    Email +    Scheduler
Reviews    & Dedup    Filter     Generate  into       Generate   & Backend Fee +      (GitHub
                                           Themes                          GDoc       Actions)
```

| Phase | Name | What Happens |
|-------|------|--------------|
| **1** | Data Ingestion | Fetch Play Store reviews for `in.indwealth` (last 12 weeks, paginated, SHA-256 hashed IDs) |
| **2a** | Cleaning & Dedup | Normalize text, remove emojis, filter short (<5 words) & non-English reviews, Jaccard dedup (threshold 0.9) |
| **2b** | Privacy Filtering | Regex-based PII redaction (emails, UPI, phones, long numbers, @mentions) + second-pass validation |
| **3** | LLM Theme Generation | Discover 3–5 themes via Groq LLaMA 3.3 70B (batches of 50, cross-batch merge, max 5) |
| **4** | Grouping into Themes | Classify each review into exactly one theme (or "Other") via Groq LLaMA 3.3 70B (batches of 50) |
| **5** | Weekly Note Generation | Generate strictly < 250-word scannable one-pager via Groq LLaMA 3.3 70B (3 sections: Top Themes, User Quotes, Action Ideas) |
| **6** | Web UI & Backend | FastAPI REST API backend (`api_server.py`) + Vercel static frontend (HTML/CSS/JS) |
| **7a** | Email Draft & Delivery | Markdown → HTML email with fee explanation appendix, cascading delivery: Gmail API → SMTP → local `.eml` |
| **7b** | Combined JSON + Google Doc | Parse note into structured JSON, combine with fee data, append to Google Doc via MCP |
| **8** | Scheduler | Automated Sunday runs via GitHub Actions (`cron: 0 4 * * 0`) with Google OAuth token reconstruction |

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
# Required
GROQ_API_KEY=your_groq_api_key_here

# SMTP email (optional — for Phase 7a email delivery)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASS=your_app_password

# Gmail API (optional — alternative to SMTP)
# GMAIL_CREDENTIALS=/path/to/credentials.json

# Google Doc append via MCP (optional — for Phase 7b)
GDOC_ID=your_google_doc_id_here
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
# GOOGLE_REFRESH_TOKEN is used in CI to reconstruct token.pickle
```

### 3. Run the Full Pipeline

```bash
python main.py
```

This runs Phases 1–5, then Phase 7b (fee explanation + combined JSON + Google Doc append).

To also auto-send the email (Phase 7a):

```bash
RECIPIENT_NAME="Priya Sharma" RECIPIENT_EMAIL="priya@company.com" python main.py
```

**Pipeline execution order in `main.py`:**

1. Phase 1 — Fetch reviews → `data/raw_reviews.json`
2. Phase 2a — Clean & dedup → `data/normalized_reviews.json`
3. Phase 2b — PII filter → `data/clean_reviews.json`
4. Phase 3 — Generate themes → `data/themes.json`
5. Phase 4 — Classify reviews → `data/themed_reviews.json`
6. Phase 5 — Generate note → `output/weekly_note_{date}.md`
7. Phase 7a — Generate fee explanation
8. Phase 7b — Build combined JSON → `output/combined_pulse_{date}.json`
9. Phase 7b — Append to Google Doc via MCP (if `GDOC_ID` is set)
10. Phase 7a — Send email (if `RECIPIENT_NAME` and `RECIPIENT_EMAIL` are set)

### 4. Launch the Frontend & Backend Locally

```bash
# Start the FastAPI backend
uvicorn api_server:api --host 0.0.0.0 --port 8000 --reload
```

Then open `phase6_web_ui/static/index.html` in the browser. Ensure `window.__BACKEND_URL__` in `index.html` is set to `'http://localhost:8000'`.

The frontend provides:
- **🚀 Run Pipeline** — trigger Phases 1–5 + Phase 7b in the background (polls `/api/status` every 5s)
- **📄 Latest Note** — view the most recent weekly note (rendered from markdown via `marked.js`)
- **✉️ Send Email** — dispatch to any recipient (generates fee explanation and includes it in the email)
- **📊 Note Stats** — date, filename, word count

### 5. Check Outputs

- `output/weekly_note_{date}.md` — the weekly pulse note
- `output/combined_pulse_{date}.json` — combined JSON (weekly pulse + fee explanation)
- `output/email_draft_{date}.eml` — email draft (fallback when no email config)

### 6. Google Doc Integration (MCP)

To enable automatic Google Doc appends:

1. Set up a Google Cloud project and enable the Google Docs API.
2. Create OAuth2 credentials (Desktop application type).
3. Run `gdocs_mcp_server.py` locally once to complete the browser-based OAuth flow. This creates `token.pickle`.
4. Set `GDOC_ID` in your `.env` file (the document ID from the Google Doc URL).
5. For CI/CD (GitHub Actions), store `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` as repository secrets. The workflow reconstructs `token.pickle` from these before running the pipeline.

You can also manually test the MCP append using:
```bash
python mcp_client_runner.py
```

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
│  All requests routed   │        │   ├─ /api/send   (trigger email)  │
│  dynamically via API   │        │   └─ /api/health (health check)   │
└────────────────────────┘        └───────────────────────────────────┘
```

### Frontend — Vercel (Static)

The `phase6_web_ui/static/` directory is deployed as a static site via `vercel.json`.

The frontend communicates with the backend directly using CORS requests. Set `window.__BACKEND_URL__` in `index.html` to the URL of your deployed FastAPI backend.

### Backend — Streamlit Cloud (FastAPI)

`api_server.py` is the primary entry point. Deploy to Streamlit Cloud using their container ecosystem to run FastAPI via uvicorn.

**Required environment variables on the backend:**

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key for LLM calls |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS` | For email delivery |
| `GDOC_ID` | Google Document ID for combined JSON appends |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | For Google OAuth (if using Google Doc append) |

**REST API Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root health check |
| `/api/health` | GET | Health check |
| `/api/note` | GET | Latest weekly note (JSON with filename, date, markdown, word_count) |
| `/api/send` | POST | Send email (accepts `recipient_name` and `recipient_email`). Returns 502 if SMTP fails. |
| `/api/status` | GET | Pipeline status (`idle` / `running` / `error: <msg>`), last run, last note file, sent count |
| `/api/run` | POST | Trigger full pipeline in background (Phases 1–5 + Phase 7b). Returns 409 if already running. |

### Scheduler — GitHub Actions

The pipeline runs automatically every Sunday at 4:00 AM UTC (9:30 AM IST) via `.github/workflows/weekly_pulse.yml`.

**Key features:**
- Reconstructs `token.pickle` from Google OAuth secrets before running the pipeline
- Runs `python main.py` with all secrets injected as environment variables
- Uploads pipeline artifacts (notes, emails, logs)
- Auto-commits generated outputs back to the repo
- Can be manually triggered via `workflow_dispatch`

**Required GitHub Secrets:**

| Secret | Purpose |
|--------|---------|
| `GROQ_API_KEY` | LLM inference |
| `RECIPIENT_NAME` / `RECIPIENT_EMAIL` | Auto-send email target |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS` | Email delivery |
| `GMAIL_CREDENTIALS` | Gmail API (optional) |
| `GDOC_ID` | Target Google Doc for combined JSON |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REFRESH_TOKEN` | Google OAuth for MCP |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Play Store Data | `google-play-scraper` |
| Language Detection | `langdetect` |
| LLM | Groq — **`llama-3.3-70b-versatile`** |
| PII Filtering | Regex (5 ordered patterns) |
| REST API Backend | FastAPI (`api_server.py`) |
| Web Frontend | Vanilla HTML / CSS / JS + `marked.js` |
| Frontend Hosting | Vercel (Static) |
| Backend Hosting | Streamlit Cloud (FastAPI via uvicorn) |
| Email | Gmail API / SMTP / Local `.eml` |
| Google Doc Sync | MCP (Model Context Protocol) via local Python MCP server |
| Scheduler | GitHub Actions (every Sunday, `cron: 0 4 * * 0`) |
| Config | `python-dotenv` (`.env` file) |
| Testing | `pytest` + `httpx` |

---

## Constraints

- ✅ **Public reviews only** — no scraping behind logins
- ✅ **≤ 5 themes** — focused, not noisy (hard cap in code + prompt)
- ✅ **< 250 words** — strictly enforced limit for the scannable one-pager (validated by `word_counter.py`)
- ✅ **No truncated quotes** — real user quotes are verbatim and fully complete
- ✅ **No PII** — emails, phones, UPI IDs, @mentions are stripped via regex + second-pass validation
- ✅ **English only** — non-English reviews filtered via `langdetect`
- ✅ **Anonymized IDs** — review IDs hashed with SHA-256 (first 10 chars)
- ✅ **Minimum review length** — reviews with <5 words are discarded
- ✅ **Fee explanation: neutral** — facts only, no recommendations, 3 bullets, 2 approved sources
- ✅ **Google Doc: MCP only** — combined JSON appended via local Python MCP server + Google Docs API

---

## Project Structure

```
├── main.py                       # Pipeline orchestrator (Phases 1–5 + Phase 7a/7b)
├── api_server.py                 # FastAPI REST API (6 endpoints, background pipeline runner)
├── gdocs_mcp_server.py           # Python MCP server for Google Docs (FastMCP)
├── mcp_client_runner.py          # Standalone MCP client for manual testing
├── vercel.json                   # Vercel static deployment config
├── requirements.txt              # Python dependencies
├── packages.txt                  # System packages for Streamlit Cloud
├── openapi.json                  # Generated OpenAPI 3.1.0 spec
├── pytest.ini                    # pytest config
├── token.pickle                  # Cached Google OAuth2 credentials
├── .env                          # API keys & credentials (gitignored)
│
├── phase1_ingestion/             # Fetch Play Store reviews (google-play-scraper)
├── phase2_cleaning/              # 2a: Clean, filter, dedup | 2b: PII redaction & validation
├── phase3_theme_generation/      # Groq LLM theme discovery (batch + merge)
├── phase4_grouping/              # Assign each review to a theme via Groq LLM
├── phase5_note_generation/       # Generate ≤250-word weekly note via Groq LLM
├── phase6_web_ui/                # Static frontend (HTML/CSS/JS for Vercel)
├── phase7_email/                 # Email draft + delivery, fee explanation, combined JSON,
│                                 #   Google Doc append via MCP
├── phase8_scheduler/             # GitHub Actions docs & setup guide
│
├── .github/workflows/
│   └── weekly_pulse.yml          # Automated Sunday pipeline runs (with Google OAuth token reconstruction)
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
├── output/                       # Final outputs (gitignored, except latest_note.json)
│   ├── weekly_note_{date}.md     # Phase 5 output
│   ├── combined_pulse_{date}.json # Phase 7b output (combined JSON backup)
│   └── email_draft_{date}.eml    # Phase 7a fallback output
│
└── docs/
    ├── Architecture.md           # Full phase-wise architecture documentation
    └── README.md                 # This file
```

---

## License

Internal project — Generative AI Bootcamp @ Next Leap.
