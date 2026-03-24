# 📋 Weekly Product Pulse & Fee Explainer

> Turn **INDMoney Play Store reviews** into a **one-page weekly pulse** and a **ready-to-send email** — powered by Groq LLaMA 3.3 70B.

<video src="https://raw.githubusercontent.com/terse2103/Weekly-Product-Pulse-And-Fee-Explainer/master/Demo%20video.mp4" width="100%" controls preload></video>

---

## What It Does

| Input | Output |
|-------|--------|
| Last 12 weeks of INDMoney Play Store reviews | ✅ Scannable weekly note (≤ 250 words) |
| | ✅ Professional HTML email with fee explanation appendix |
| | ✅ Combined JSON record appended to a Google Doc (via MCP) |

### The Weekly Note Contains

- **📊 Top 3 Themes** — what users are talking about most (with review counts and one-liner descriptions)
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
| **5** | Weekly Note Generation | Generate strictly ≤ 250-word scannable one-pager via Groq LLaMA 3.3 70B (3 sections: Top Themes, User Quotes, Action Ideas) |
| **6** | Web UI & Backend | Unified Streamlit Dashboard (`streamlit_app.py`) for pipeline orchestration and live viewing |
| **7a** | Email Draft & Delivery | Markdown → HTML email with fee explanation appendix, cascading delivery: Gmail API → SMTP → local `.eml` |
| **7b** | Combined JSON + Google Doc | Parse note into structured JSON, combine with fee data, append to Google Doc via MCP |
| **8** | Scheduler | Automated Sunday runs via GitHub Actions (`cron: 0 4 * * 0`) with Google OAuth token reconstruction |

See [Architecture.md](Architecture.md) for the full phase-wise breakdown, prompts, LLM configs, and data flow.

---

## Setup & Execution

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
# GOOGLE_REFRESH_TOKEN is used in CI and Streamlit Cloud to reconstruct token.pickle
```

Ensure `.streamlit/secrets.toml` is populated if deploying on Streamlit Cloud (copy values from `.streamlit/secrets.toml.example`).

### 3. Run the Full Pipeline

```bash
python main.py
```

This runs Phases 1–5, then Phase 7a (fee explanation), and Phase 7b (combined JSON + Google Doc append).

To also auto-send the email (Phase 7a):

```bash
RECIPIENT_NAME="Priya Sharma" RECIPIENT_EMAIL="priya@company.com" python main.py
```

### 4. Launch the Web UI Locally

**Streamlit UI (Primary Dashboard):**
```bash
streamlit run streamlit_app.py
```

### 5. Google Doc Integration (MCP)

To enable automatic Google Doc appends:

1. Set up a Google Cloud project and enable the Google Docs API.
2. Create OAuth2 credentials (Desktop application type).
3. Run `gdocs_mcp_server.py` locally once to complete the browser-based OAuth flow. This creates `token.pickle`.
4. Set `GDOC_ID` in your `.env` file (the document ID from the Google Doc URL).
5. For CI/CD and Streamlit Cloud, store `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` as secrets. The app/workflow reconstructs `token.pickle` from these before running the pipeline.

You can also manually test the MCP tool using:
```bash
python mcp_client_runner.py
```

---

## Deployment

### Architecture Setup

The project uses a **single unified dashboard**:
- **Primary UI & Orchestrator:** Streamlit app (`streamlit_app.py`) deployed on Streamlit Cloud. This handles full pipeline execution in background threads and serves the interactive UI, rendering the generated notes and sending emails natively.

### Streamlit Cloud Deployment
- Deploy `streamlit_app.py` on Streamlit Cloud.
- Add your secrets in the Streamlit Cloud dashboard (`Settings` → `Secrets`) using the `.streamlit/secrets.toml.example` structure.
- The app automatically reconstructs the Google Docs OAuth token in memory if `GOOGLE_REFRESH_TOKEN` is provided, enabling cloud-hosted MCP executions.

### Scheduler (GitHub Actions)
- The pipeline runs automatically every Sunday at 4:00 AM UTC (9:30 AM IST) via `.github/workflows/weekly_pulse.yml`.
- Reconstructs `token.pickle` from Google OAuth secrets.
- Fetches recent reviews, generates themes, updates docs, and auto-commits the markdown files back to the repo.

---

## Sample Q&A

**Q: Why was Groq LLaMA 3.3 70B chosen?**  
A: It offers extremely fast inference speeds for processing reviews, excellent instruction-following capabilities (crucial for our strict < 250 words limit), reliable JSON generation required for pipeline parsing, and an accessible free tier.

**Q: How does the system ensure no PII is included in the output?**  
A: Phase 2b runs a deterministic regex redaction process (stripping emails, Indian phone numbers, long digits, UPI IDs, and @mentions), followed by a second-pass validator. By addressing PII *before* LLM generation, we prevent leaks entirely.

**Q: Are the user quotes generated or hallucinated by the model?**  
A: No, the LLM is tightly prompted to extract verbatim excerpts from the provided reviews. We do not allow truncated quotes, ensuring what you read is exactly what the user wrote.

---

## Fee Explanation Details

The generated email and Google Doc payload contain a mandatory **Fee Explanation** section. 
This is implemented to ensure clear communication of financial policies.

**Source List:**
1. [Groww - Exit Load in Mutual Funds](https://groww.in/p/exit-load-in-mutual-funds)
2. [Nippon India MF - Financial Term of the Week: Exit Load](https://mf.nipponindiaim.com/investoreducation/financial-term-of-the-week-exit-load)

**Behavior:**
- The explainer is appended to the bottom of the Email (HTML) and the Google Doc JSON Payload.
- It strictly relies on facts from the sources, completely neutral, without opinions or recommendations.
- Hardcoded to provide precisely 3 bullet points with a "Last checked" date based on generation time.

---

## Disclaimer

This is a personal internal project for the Generative AI Bootcamp @ Next Leap. It uses public Play Store data and is not an official INDMoney repository. Financial fee explanations provided within the output are educational extracts automatically compiled from third-party sources. They do not constitute financial advice.

---
