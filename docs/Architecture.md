# Weekly Product Pulse & Fee Explainer — Phase-Wise Architecture

> **Goal:** Turn the last 12 weeks of INDMoney Play Store reviews into a scannable one-page weekly pulse (≤ 250 words), a ready-to-send draft email with a **Fee Explanation** appendix, and a **combined JSON record** appended to a Google Doc via MCP.

---

## High-Level System Flow

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐  ┌───────────────────────────────────────────┐  ┌──────────┐
│ Phase 1  │─▶│ Phase 2  │─▶│ Phase 3  │─▶│ Phase 4  │─▶│ Phase 5  │─▶│ Phase 6               │─▶│ Phase 7                                   │─▶│ Phase 8  │
│  Data    │  │ Cleaning │  │LLM Theme │  │ Grouping │  │  Weekly  │  │ Unified UI Dashboard  │  │ ┌──────────────────┐ ┌──────────────────┐ │  │Scheduler │
│ Ingest   │  │  & PII   │  │Generation│  │  into    │  │  Note    │  │ (Streamlit Cloud)     │  │ │  7a: Email Draft  │ │  7b: Combined    │ │  │ (GitHub  │
│(PlayStore│  │ Filtering│  │          │  │ Themes   │  │Generation│  │                       │  │ │  & Delivery +    │ │  JSON → Google   │ │  │ Actions) │
│ Reviews) │  │ (2a, 2b) │  │          │  │          │  │(One-Pager│  │                       │  │ │  Fee Explanation  │ │  Doc (via MCP)   │ │  │          │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └───────────────────────┘  │ └──────────────────┘ └──────────────────┘ │  └──────────┘
                                                                                                 └───────────────────────────────────────────┘
```

---

## Phase 1 — Data Ingestion (Play Store Reviews)

### Objective
Fetch the **last 12 weeks** of public Play Store reviews for the **INDMoney** app (`in.indwealth`).

### Approach
| Option | Library / API | Notes |
|--------|--------------|-------|
| **Primary** | `google-play-scraper` (Python) | Public API wrapper; no login required |

### Implementation Details

- **App ID:** `in.indwealth` (configured in `config.py`)
- **Review window:** Last 12 weeks (configurable via `REVIEW_WEEKS`)
- **Sort order:** `Sort.NEWEST` — fetches most recent reviews first
- **Batch fetching:** Iteratively fetches up to 1000 reviews per batch using `continuation_token` pagination until the 12-week cutoff date is reached
- **ID anonymization:** Review IDs are hashed using SHA-256 and truncated to 10 characters for pseudo-anonymization
- **Language & country:** `en` (English), `in` (India)

### Data Schema (per review)

| Field | Type | Example |
|-------|------|---------|
| `rating` | int (1–5) | `3` |
| `text` | str | `I like the UI but the fee structure...` |
| `date` | ISO 8601 | `2026-01-15T12:30:00` |
| `review_id` | str (SHA-256 hash, first 10 chars) | `a8f3c2b1d0` |

### Constraints
- **Public reviews only** — no scraping behind authentication walls.
- Reviews older than ~12 weeks are discarded at fetch time.
- No PII is stored (usernames, emails, device IDs are stripped at this stage — only rating, text, date, and hashed review_id are kept).

### Output
`data/raw_reviews.json` — array of review objects.

---

## Phase 2 — Cleaning & Privacy Filtering

Phase 2 is split into two sub-phases to keep responsibilities clearly separated.

### Phase 2a — Cleaning & Deduplication

#### Objective
Normalize, filter, and deduplicate raw review text before privacy filtering.

#### Pipeline Steps

1. **Validate schema** — ensure each review contains `rating`, `text`, `date`, `review_id` (all non-null).
2. **Remove emojis** — strip all emoji characters (emoticons, symbols, pictographs, transport/map symbols, flags, dingbats) using comprehensive Unicode regex.
3. **Normalize text** — lowercase the text and collapse multiple whitespace characters into a single space.
4. **Filter short reviews** — discard any review with **fewer than 5 words** post-normalization (too brief to extract meaningful themes).
5. **Filter non-English** — use `langdetect` library to keep only English-language reviews.
6. **Deduplication** — remove exact-match duplicates (via set lookup) and near-duplicate reviews (Jaccard similarity > 0.9 on word tokens).

#### Output
`data/normalized_reviews.json` — deduplicated, normalized review objects.

---

### Phase 2b — Privacy Filtering

#### Objective
**Strip any residual PII** from normalized reviews before they reach the LLM.

#### PII Redaction Rules (applied in order)

| # | PII Type | Regex Pattern | Replacement |
|---|----------|---------------|-------------|
| 1 | Email addresses | `user@domain.com` | `[EMAIL]` |
| 2 | UPI IDs | `username@bankname` | `[REDACTED]` |
| 3 | Phone numbers (Indian) | `+91-XXXXXXXXXX` or 10 digits starting with 6–9 | `[PHONE]` |
| 4 | Bank account / long numbers | 9–18 digit numbers | `[REDACTED]` |
| 5 | @mentions / usernames | `@username` | `[USER]` |

#### Pipeline Steps

1. **Regex scan & redact** — iterate through all reviews and apply each PII pattern/replacement sequentially.
2. **Validate** — second-pass check (`pii_validator.py`) runs the same regex patterns over the output to assert no PII tokens remain.

#### Output
`data/clean_reviews.json` — deduplicated, PII-free review objects.

---

## Phase 3 — LLM Theme Generation

### Objective
Use **Groq** (LLM inference provider) to identify **3–5 recurring themes** across the cleaned reviews.

### LLM Configuration

| Setting | Value |
|---------|-------|
| **Provider** | Groq |
| **Model** | `llama-3.3-70b-versatile` |
| **Temperature** | `0.3` |
| **Max tokens** | `2000` |
| **Response format** | `json_object` (forced JSON mode) |
| **Retry logic** | Up to 5 retries with exponential backoff (10s × attempt#) |

### Approach

- Reviews are sent in **batches of 50** (`BATCH_SIZE`) to stay within context limits.
- A **5-second delay** between batches (`BATCH_DELAY_SECS`) to respect rate limits.
- If only one batch: use extracted themes directly (capped at 5).
- If multiple batches: merge themes across batches via a second LLM call.
- **Hard cap at 5 themes** (`MAX_THEMES`).
- Each theme is validated: must have `theme` (string, non-empty) and `description` (string, non-empty) keys. Theme labels > 5 words trigger a warning.

### Output
`data/themes.json` — list of theme objects (`[{"theme": "...", "description": "..."}, ...]`).

---

## Phase 4 — Grouping into Themes

### Objective
Assign **each cleaned review to exactly one of the themes** discovered in Phase 3, or to `"Other"`.

### Approach

- Reviews are sent in **batches of 50** (`BATCH_SIZE`).
- A **2-second delay** between batches.
- The available themes list includes all Phase 3 themes plus `"Other"`.
- Classifications are merged back to reviews: if a review's assigned theme is not in the valid theme list, it is reassigned to `"Other"`.
- Reviews missing `review_id` or `id` fields are assigned synthetic IDs (`rev_{index}`).

### Validation (`validator.py`)
- All reviews must have a `theme` field.
- Theme distribution is logged.
- **Warning** if any single theme has > 60% of reviews (overly broad categorization).
- **Warning** if `"Other"` has > 30% of reviews (themes may need to be broader — suggests re-running Phase 3).

### Output
`data/themed_reviews.json` — each review now has a `theme` field added.

---

## Phase 5 — Weekly Note Generation (One-Pager)

### Objective
Generate a **≤ 250-word, scannable weekly note** containing:

| Section | Content |
|---------|---------|
| **📊 Top Themes** | Theme label + 1-line description + review count (strictly Top 3) |
| **💬 User Quotes** | Verbatim (PII-free) complete quotes, one per theme |
| **💡 Action Ideas** | Concrete next-step suggestions tied to themes |

### Implementation Details

1. **Summarize reviews** (`summarize_reviews()`):
   - Count reviews per theme.
   - Sort themes by count (descending), pick top 3.
   - Collect up to 5 sample user quotes per top theme (allowing quotes up to 40 words while under 250 words total constraint).
   - Format into a structured text block for the LLM prompt.

2. **Generate note** (`generate_note()`):
   - Build user prompt with the date and themed review summary.
   - Call Groq LLaMA 3.3 70B with system prompt instructing ≤ 250-word scannable note format.
   - Restrict headers to: `#### Top 3 Themes`, `#### User Quotes`, `#### Action Ideas`.
   - Validate word count via `word_counter.py`.
   - Save output to `output/weekly_note_{date}.md`.

### Output
`output/weekly_note_{date}.md` — the formatted weekly note.

---

## Phase 6 — Web UI Dashboard (Streamlit)

### Objective
Provide a unified **Streamlit web interface** for users and internal staff to trigger the pipeline dynamically, view the generated weekly note (with the Fee Explanation embedded natively), and dispatch updates via email natively from the app window. 

### Architecture

The system operates strictly as a **monolith dashboard** using Streamlit Cloud.
- **Primary Unified App (`streamlit_app.py`):** 
   - A single-screen interactive view of the pipeline status and settings.
   - Orchestrates the full Phase 1-5 + Phase 7a/7b steps natively by executing operations globally as Background Threads so the user UI loop does not freeze.
   - Tracks metrics, renders Streamlit-native markdown based on newly generated text arrays, and binds email submission inputs natively.
   - **Fee Explanation embedded in UI**: Dynamically computes and presents the fixed fee logic next to the generated weekly note to serve as a complete visualization.
   
- **Config & Secrets:**
   - Handled via `.streamlit/secrets.toml`.
   - Google Auth logic allows Headless operations using `GOOGLE_REFRESH_TOKEN` to rebuild local tokens dynamically on Cloud hosts perfectly without launching an OAuth browser prompt.

---

## Phase 7 — Email Draft Generation, Delivery & Fee Explanation + Google Doc Sync

### Phase 7a — Email Draft Generation & Delivery (with Fee Explanation)

#### Objective
Wrap the weekly note into a **professional HTML email**, append a **"Fee Explanation: Mutual Fund Exit Load"** section, and deliver it to the **recipient specified via the Web UI** (Phase 6) or environment variables.

#### Fee Explanation Appendix
Appended **after** the weekly note body inside the same email.

**Constraints:**
- **Neutral, facts-only tone** — no recommendations, no comparisons, no opinions.
- **Exactly 3 bullet points** summarizing what a mutual fund exit load is.
- **Only** the two approved sources listed above may be referenced (Groww and Nippon India).
- The `Last checked` date is the pipeline run date.

#### Delivery Priority (Cascading Fallback)

| Priority | Method | Trigger Condition | Library |
|----------|--------|-------------------|---------|
| 1 | **Gmail API** | `GMAIL_CREDENTIALS` env var is set | `google-api-python-client`, `google-auth-oauthlib` |
| 2 | **SMTP** | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS` env vars are set | `smtplib` (Python stdlib) |
| 3 | **Local .eml** | Fallback — always succeeds | `email.mime` (Python stdlib) |

### Phase 7b — Combined JSON → Google Doc (via MCP)

#### Objective
After generating the weekly note and fee explanation, create a **combined JSON record** (`json_assembler.py`) and append it to a **Google Doc** using **MCP**.

#### Integration Strategy

- **MCP Appender (`gdoc_mcp_appender.py`)**: Spawns a child process for the local Python server (`gdocs_mcp_server.py`) using `stdio` transport. Dispatches the `append_to_google_doc(doc_id, text)` tool command.
- Handles synchronous and async nested event loops appropriately.
- **Format**: JSON block fenced in a markdown code block, preceded by the run `date`. Appends without modifying historical iterations inside the targeted Google Doc.

---

## Phase 8 — Scheduler (GitHub Actions)

### Objective
Automate the **entire pipeline to run every Sunday** using GitHub Actions (`weekly_pulse.yml`).

### Workflow Details
- **Schedule:** `0 4 * * 0` (4:00 AM UTC = 9:30 AM IST).
- **Google OAuth token reconstruction:** Reconstructs `token.pickle` from `GOOGLE_REFRESH_TOKEN`, `GOOGLE_CLIENT_ID`, and `GOOGLE_CLIENT_SECRET` secrets.
- Runs `python main.py` with embedded secrets.
- **Artifacts & Delivery:** Uploads notes, email drafts, and logs. It forces local check-ins of the `output/` artifacts using a headless git-bot user.

---

## Pipeline Orchestrator (`main.py`)

The standalone entry point synchronizing operations execution:
- Phase 1-5 runs sequentially inside `run_pipeline()`.
- Phase 7a (Fee Explainer generation and Email wrapping) computes facts.
- Phase 7b (Google Doc append and combine JSON export) runs automatically regardless of the selected delivery parameters.
- Dispatches Email correctly if CI environments populate recipient vars.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Play Store Scraping | `google-play-scraper` |
| LLM | Groq (`llama-3.3-70b-versatile`) |
| Primary App UI | Streamlit Cloud (`streamlit_app.py`) |
| Config & Secrets | `python-dotenv`, `secrets.toml` |
| Google Doc Sync | MCP (Model Context Protocol) via `FastMCP` |
| Scheduler | GitHub Actions |

---

## Constraints Checklist

| # | Constraint | How It's Enforced |
|---|-----------|-------------------|
| 1 | Public review exports only | `google-play-scraper` uses public API; no auth required |
| 2 | Maximum 5 themes | `MAX_THEMES = 5` in `theme_generator.py` |
| 3 | Weekly note ≤ 250 words | `word_counter.py` validates; prompt instructs ≤ 250 words |
| 4 | No truncated quotes | Explicitly stated in Prompts "do not truncate". |
| 5 | No PII in outputs | `pii_filter.py` in Phase 2b + second-pass check |
| 6 | Fee explanation: neutral tone | Hardcoded generation based strictly on 2 approved sources; 3 bullets only. |
| 7 | Google Doc sync: MCP only | `gdoc_mcp_appender.py` spawns `gdocs_mcp_server.py` |
| 8 | Scheduler tokenization | GitHub Actions pipeline dynamically creates memory tokens to execute headless flows. |
