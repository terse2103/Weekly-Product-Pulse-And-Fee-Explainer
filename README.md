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
cp .env.example .env
# Add your LLM API key (OpenAI / Gemini)
```

### 3. Run the Pipeline

```bash
python main.py
```

### 4. Launch the Web UI

```bash
python phase6_web_ui/app.py
# Open http://localhost:5000
```

### 5. Check Outputs

- `output/weekly_note_{date}.md` — the weekly pulse
- `output/email_draft_{date}.eml` — the draft email

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Play Store Data | `google-play-scraper` |
| LLM | Google Gemini (`gemini-2.0-flash`) |
| PII Filtering | Regex + heuristics |
| Web Backend | Flask |
| Web Frontend | HTML / CSS / JS |
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
├── main.py                       # Pipeline orchestrator
├── config/settings.yaml          # Configuration
├── phase1_ingestion/             # Fetch Play Store reviews
├── phase2_cleaning/              # 2a: Clean text | 2b: Strip PII
├── phase3_theme_generation/      # LLM theme discovery
├── phase4_grouping/              # Assign reviews to themes
├── phase5_note_generation/       # Generate weekly one-pager
├── phase6_web_ui/                # Web UI + Flask backend
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
