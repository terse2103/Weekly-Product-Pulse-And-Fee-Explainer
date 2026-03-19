# 📋 Weekly Product Pulse & Fee Explainer

> Turn **INDMoney Play Store reviews** into a **one-page weekly pulse** and a **ready-to-send draft email** — powered by LLMs.

---

## What It Does

| Input | Output |
|-------|--------|
| Last 8–12 weeks of INDMoney Play Store reviews | ✅ Scannable weekly note (≤ 250 words) |
| | ✅ Draft email ready to send |

### The Weekly Note Contains

- **📊 Top 3 Themes** — what users are talking about most
- **💬 3 Real User Quotes** — verbatim, PII-free
- **💡 3 Action Ideas** — concrete next steps

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
Reviews               Filter     Generate  into       Generate   & Backend  Draft     (GitHub
                                           Themes                                     Actions)
```

| Phase | Name | Description |
|-------|------|-------------|
| **1** | Data Ingestion | Fetch Play Store reviews |
| **2a** | Cleaning | Normalize text, deduplicate |
| **2b** | Privacy Filtering | Strip PII (emails, phones, usernames) |
| **3** | LLM Theme Generation | Discover 3–5 themes via LLM |
| **4** | Grouping into Themes | Assign each review to a theme |
| **5** | Weekly Note Generation | Create ≤250-word one-pager |
| **6** | Web UI & Backend | Collect recipient name/email, preview note |
| **7** | Email Draft & Delivery | Send email to specified recipient |
| **8** | Scheduler | Automated Sunday run via GitHub Actions |

See [Architecture.md](Architecture.md) for the full phase-wise breakdown.

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
# Add your Groq API key (GROQ_API_KEY) and SMTP credentials
```

### 3. Run the Pipeline

```bash
python main.py
```

### 4. Launch the Admin Panel / REST Bridge

```bash
# To run Streamlit Admin dashboard (spawns FastAPI background threads)
streamlit run streamlit_app.py

# To test standalone FastAPI server
uvicorn api_server:api --host 0.0.0.0 --port 8502
```

### 5. Check Outputs

- `output/weekly_note_{date}.md` — the weekly pulse
- `output/email_draft_{date}.eml` — the draft email

---

## Deployment

### Architecture

```
Browser (Vercel)              Docker Container
──────────────────            ────────────────────────────────────────
index.html / script.js   ──▶  PORT (Streamlit UI)    ← admin panel
                         ──▶  PORT+1/8081 (FastAPI)  ← REST API used by frontend
```

### Backend — Streamlit inside Docker

`streamlit_app.py` is the entry point. It:
1. Renders the **Streamlit admin panel** (run pipeline, preview note, send email).
2. Starts `api_server.py` (FastAPI) in a **daemon thread** on `API_PORT` (default 8081).

**Environment variables (set in your Docker host / platform):**

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | Streamlit UI port (set by hosting platform) |
| `API_PORT` | `8081` | FastAPI REST API port |
| `GROQ_API_KEY` | — | Groq/LLM API key |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | — | SMTP username |
| `SMTP_PASS` | — | SMTP password / app password |

**Build & run locally:**
```bash
docker build -t weekly-pulse .
docker run -p 8080:8080 -p 8081:8081 \
  -e GROQ_API_KEY=your_key \
  -e SMTP_USER=you@gmail.com \
  -e SMTP_PASS=app_password \
  weekly-pulse
```

### Frontend — Vercel (Static)

The `phase6_web_ui/static/` directory is deployed as a static site via `vercel.json`.

**After deploying the Docker backend**, update `index.html`:
```js
// phase6_web_ui/static/index.html
window.__BACKEND_URL__ = 'https://your-docker-host.example.com:8081';
```

Then redeploy to Vercel (`vercel --prod`).

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Play Store Data | `google-play-scraper` |
| LLM | Groq (**`llama-3.3-70b-versatile`**) |
| PII Filtering | Regex + heuristics |
| Web Backend | Streamlit & FastAPI |
| Web Frontend | Vanilla HTML / CSS / JS |
| Email | Gmail API / SMTP |
| Scheduler | GitHub Actions (every Sunday) |
| Testing | `pytest` |

---

## Constraints

- ✅ **Public reviews only** — no scraping behind logins
- ✅ **≤ 5 themes** — focused, not noisy
- ✅ **≤ 250 words** — scannable one-pager
- ✅ **No PII** — usernames, emails, IDs are stripped

---

## Project Structure

```
├── api_server.py                 # FastAPI REST bridge orchestrator
├── streamlit_app.py              # Streamlit Backend Admin app
├── main.py                       # Pipeline orchestrator
├── vercel.json                    # Static Frontend Deployment Config
├── phase1_ingestion/             # Fetch Play Store reviews
├── phase2_cleaning/              # 2a: Clean text | 2b: Strip PII
├── phase3_theme_generation/      # Groq LLM theme discovery
├── phase4_grouping/              # Assign reviews to themes
├── phase5_note_generation/       # Generate weekly one-pager
├── phase6_web_ui/                # static UI + FastAPI static holder placeholder
├── phase7_email/                 # Email draft & delivery
├── phase8_scheduler/             # GitHub Actions docs
├── .github/workflows/            # Automated Sunday runs
├── data/                         # Intermediate data files
├── output/                       # Final outputs
└── logs/                         # Run logs
```

---

## License

Internal project — Generative AI Bootcamp @ Next Leap.
