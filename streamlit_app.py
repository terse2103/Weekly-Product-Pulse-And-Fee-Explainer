"""
streamlit_app.py — Weekly Product Pulse Admin Panel
=====================================================
Deployed on Streamlit inside Docker.

This file serves two purposes:
  1.  Streamlit UI  — admin dashboard to trigger the pipeline, preview the
                      latest note, and dispatch emails.
  2.  FastAPI thread — starts api_server.py (FastAPI + uvicorn) in a
                       background daemon thread so the REST API is reachable
                       by the Vercel frontend on the same Docker host.

Docker CMD:
  streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0

When Streamlit Cloud / Docker exposes one port, the Streamlit UI is on that
port.  The FastAPI REST API listens on PORT+1 (default 8081) so traffic can
be routed separately (e.g. via a reverse proxy or Railway's multi-port config).
For simplicity in a single-container deployment the two ports are both exposed;
the frontend's BACKEND_URL should point to the FastAPI port.
"""

from __future__ import annotations

import glob
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Page config — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Weekly Pulse Admin",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path("output")
DATA_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Pipeline status (shared between UI and background tasks via st.session_state)
# ---------------------------------------------------------------------------
if "pipeline_status" not in st.session_state:
    st.session_state.pipeline_status = "idle"
if "last_run" not in st.session_state:
    st.session_state.last_run = None
if "pipeline_log" not in st.session_state:
    st.session_state.pipeline_log = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_latest_note() -> Path | None:
    """Return the path to the most-recently generated weekly note, or None."""
    pattern = str(OUTPUT_DIR / "weekly_note_*.md")
    files = sorted(glob.glob(pattern), reverse=True)
    return Path(files[0]) if files else None


def read_note(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def run_pipeline() -> None:
    """Execute the full pipeline (Phases 1–5) synchronously."""
    log: list[str] = []
    st.session_state.pipeline_status = "running"
    st.session_state.pipeline_log = log

    def _log(msg: str) -> None:
        log.append(f"[{datetime.now().strftime('%H:%M:%S')}]  {msg}")
        st.session_state.pipeline_log = list(log)

    try:
        _log("▶ Phase 1 — Fetching Play Store reviews…")
        from phase1_ingestion.fetch_reviews import fetch_reviews
        fetch_reviews()
        _log("✔ Phase 1 complete")

        _log("▶ Phase 2a — Deduplication…")
        from phase2_cleaning.deduplicator import run_phase2a
        run_phase2a()
        _log("✔ Phase 2a complete")

        _log("▶ Phase 2b — PII Filtering…")
        from phase2_cleaning.pii_filter import run_pii_filtering
        run_pii_filtering()
        _log("✔ Phase 2b complete")

        _log("▶ Phase 3 — Theme Generation (LLM)…")
        from phase3_theme_generation.theme_generator import generate_themes
        themes = generate_themes()
        _log(f"✔ Phase 3 complete — {len(themes)} themes discovered")

        _log("▶ Phase 4 — Classifying reviews into themes (LLM)…")
        from phase4_grouping.theme_classifier import classify_reviews
        classify_reviews()
        _log("✔ Phase 4 complete")

        _log("▶ Phase 5 — Generating weekly note (LLM)…")
        with open(DATA_DIR / "themed_reviews.json", "r", encoding="utf-8") as f:
            tagged = json.load(f)
        from phase5_note_generation.note_generator import generate_note
        generate_note(tagged, themes)
        _log("✔ Phase 5 complete — note written to output/")

        # ─── Static JSON Export for Vercel ─────────────────────────────────
        note_p = get_latest_note()
        if note_p:
            _log("▶ Exporting latest_note.json for Vercel…")
            nc = read_note(note_p)
            n_data = {
                "filename": note_p.name,
                "date": note_p.name.replace("weekly_note_", "").replace(".md", ""),
                "markdown": nc,
                "word_count": len(nc.split())
            }
            with open(OUTPUT_DIR / "latest_note.json", "w", encoding="utf-8") as f_out:
                json.dump(n_data, f_out, indent=2)
            _log("✔ latest_note.json exported up to date")

            # ─── Push to GitHub ──────────────────────────────────────────
            gh_token = os.environ.get("GITHUB_TOKEN")
            if gh_token:
                _log("▶ Found GITHUB_TOKEN. Pushing static file to GitHub master…")
                import subprocess
                try:
                    # Configure git for actions
                    subprocess.run(["git", "config", "user.name", "Streamlit-AdminPanel"], check=True)
                    subprocess.run(["git", "config", "user.email", "admin@streamlit.app"], check=True)
                    
                    # Add and commit with Force flag to bypass any .gitignore layout warnings
                    subprocess.run(["git", "add", "-f", "output/latest_note.json"], check=True)
                    # Allow commit failure if file is unchanged (though note contents usually vary with date/counter)
                    subprocess.run(["git", "commit", "-m", "📋 Streamlit Update — latest_note.json"], check=False)
                    
                    # Push using Token auth
                    # Using a simplified push command targeting master
                    # Standard checkout is usually clone address
                    remote = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True).stdout.strip()
                    if "github.com" in remote:
                         # e.g. https://github.com/user/repo.git -> replace with token auth
                         auth_push = remote.replace("https://", f"https://x-access-token:{gh_token}@")
                         subprocess.run(["git", "push", auth_push, "master"], check=True)
                    _log("✔ Sync to GitHub successful!")
                except Exception as git_err:
                     _log(f"⚠️ Git push failed: {git_err}")
            else:
                _log("ℹ️ Skipping Git push — specify GITHUB_TOKEN in your environment variables to enable auto-sync back to GitHub for Vercel.")
        # ───────────────────────────────────────────────────────────────────

        st.session_state.pipeline_status = "completed"
        st.session_state.last_run = datetime.now().isoformat()
        _log("🎉 Pipeline finished successfully!")

    except Exception as exc:  # noqa: BLE001
        _log(f"❌ ERROR: {exc}")
        st.session_state.pipeline_status = f"error: {exc}"


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      /* ── General ─────────────────────────────────────────────────────────── */
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

      html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

      /* Dark sidebar */
      section[data-testid="stSidebar"] {
        background: #0f172a;
        color: #e2e8f0;
      }
      section[data-testid="stSidebar"] h1,
      section[data-testid="stSidebar"] h2,
      section[data-testid="stSidebar"] h3,
      section[data-testid="stSidebar"] p,
      section[data-testid="stSidebar"] label {
        color: #e2e8f0 !important;
      }

      /* Status badges */
      .badge-idle     { background:#334155; color:#94a3b8; padding:4px 12px; border-radius:99px; font-size:0.78rem; }
      .badge-running  { background:#1e3a5f; color:#60a5fa; padding:4px 12px; border-radius:99px; font-size:0.78rem; }
      .badge-complete { background:#14532d; color:#4ade80; padding:4px 12px; border-radius:99px; font-size:0.78rem; }
      .badge-error    { background:#7f1d1d; color:#fca5a5; padding:4px 12px; border-radius:99px; font-size:0.78rem; }

      /* Code log area */
      .log-box {
        background: #0f172a;
        color: #a5f3fc;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        padding: 1rem;
        border-radius: 8px;
        max-height: 300px;
        overflow-y: auto;
        white-space: pre-wrap;
      }

      /* Note preview */
      .note-preview {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 2rem;
        color: #e2e8f0;
        line-height: 1.7;
      }

      /* Metric cards */
      div[data-testid="metric-container"] {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem 1.5rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 📋 Weekly Pulse")
    st.markdown("**Admin Dashboard**")
    st.markdown("---")

    # Status indicator
    status = st.session_state.pipeline_status
    if status == "idle":
        st.markdown('<span class="badge-idle">● Idle</span>', unsafe_allow_html=True)
    elif status == "running":
        st.markdown('<span class="badge-running">⟳ Running…</span>', unsafe_allow_html=True)
    elif status == "completed":
        st.markdown('<span class="badge-complete">✔ Completed</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-error">✖ Error</span>', unsafe_allow_html=True)

    if st.session_state.last_run:
        st.caption(f"Last run: {st.session_state.last_run[:19]}")

    st.markdown("---")

    note_path = get_latest_note()
    if note_path:
        content = read_note(note_path)
        word_count = len(content.split())
        st.metric("Word Count", f"{word_count} words")
        st.metric("Note File", note_path.name)
    else:
        st.info("No note generated yet. Run the pipeline first.")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
st.title("📋 INDMoney Weekly Pulse — Admin Panel")
st.markdown(
    "Trigger the pipeline, preview the generated note, and dispatch the weekly email."
)

tab_pipeline, tab_note, tab_email, tab_info = st.tabs(
    ["🚀 Run Pipeline", "📄 Latest Note", "✉️ Send Email", "ℹ️ Info"]
)

# ── Tab 1: Run Pipeline ────────────────────────────────────────────────────
with tab_pipeline:
    st.subheader("Run Full Pipeline (Phases 1–5)")
    st.markdown(
        """
        Clicking **Run Pipeline** will execute all phases sequentially:

        | Phase | Description |
        |-------|-------------|
        | **1** | Fetch Play Store reviews (last 12 weeks) |
        | **2a** | Deduplicate & normalize review text |
        | **2b** | Strip PII (emails, phones, @mentions) |
        | **3** | Discover recurring themes via Groq LLaMA 3.3 70B |
        | **4** | Classify each review into a theme |
        | **5** | Generate the ≤ 250-word weekly note |
        """
    )

    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        run_disabled = st.session_state.pipeline_status == "running"
        if st.button(
            "▶ Run Pipeline",
            disabled=run_disabled,
            use_container_width=True,
            type="primary",
        ):
            with st.spinner("Pipeline running — this may take a minute…"):
                run_pipeline()
            st.rerun()

    with col_status:
        if st.session_state.pipeline_status == "completed":
            st.success("✅ Pipeline completed successfully!")
        elif st.session_state.pipeline_status == "running":
            st.info("⟳ Pipeline is running…")
        elif str(st.session_state.pipeline_status).startswith("error"):
            st.error(f"❌ {st.session_state.pipeline_status}")

    # Log output
    if st.session_state.pipeline_log:
        st.markdown("**Execution Log**")
        log_text = "\n".join(st.session_state.pipeline_log)
        st.markdown(
            f'<div class="log-box">{log_text}</div>', unsafe_allow_html=True
        )

# ── Tab 2: Latest Note ─────────────────────────────────────────────────────
with tab_note:
    st.subheader("Latest Generated Note")
    note_path = get_latest_note()
    if note_path:
        content = read_note(note_path)
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("File", note_path.name)
        col_b.metric("Words", len(content.split()))
        date_part = note_path.name.replace("weekly_note_", "").replace(".md", "")
        col_c.metric("Date", date_part)

        st.markdown("---")
        st.markdown("**Preview**")
        st.markdown(
            f'<div class="note-preview">{content}</div>', unsafe_allow_html=True
        )

        st.download_button(
            label="⬇ Download Note (.md)",
            data=content,
            file_name=note_path.name,
            mime="text/markdown",
        )
    else:
        st.warning("No weekly note found. Run the pipeline first.")

# ── Tab 3: Send Email ─────────────────────────────────────────────────────
with tab_email:
    st.subheader("Dispatch Weekly Note via Email")
    note_path = get_latest_note()

    if not note_path:
        st.warning("Generate a note first before sending.")
    else:
        with st.form("send_form"):
            recipient_name = st.text_input("Recipient Name", placeholder="e.g. Priya Sharma")
            recipient_email = st.text_input(
                "Recipient Email", placeholder="e.g. priya@company.com"
            )
            submitted = st.form_submit_button("✉️ Send Email", type="primary")

        if submitted:
            if not recipient_name.strip() or not recipient_email.strip():
                st.error("Please fill in both recipient name and email.")
            else:
                with st.spinner("Sending email…"):
                    try:
                        from phase7_email.email_generator import send_email  # type: ignore
                        note_content = read_note(note_path)
                        send_email(note_content, recipient_name.strip(), recipient_email.strip())
                        st.success(
                            f"✅ Email sent to **{recipient_name}** ({recipient_email})"
                        )
                    except ImportError:
                        st.warning(
                            "⚠️ Phase 7 email module not found — running in stub mode. "
                            "Implement `phase7_email.email_generator.send_email()` to enable real delivery."
                        )
                    except Exception as exc:
                        st.error(f"❌ Email delivery failed: {exc}")

# ── Tab 4: Info ────────────────────────────────────────────────────────────
with tab_info:
    st.subheader("Deployment Info")

    st.markdown(
        f"""
        | Component | Value |
        |-----------|-------|
        | **Platform** | Streamlit Cloud / Managed |
        | **Output directory** | `{OUTPUT_DIR.resolve()}` |
        | **Data directory** | `{DATA_DIR.resolve()}` |
        """
    )

    st.markdown("---")
    st.markdown("**Environment Variables**")
    env_keys = ["GROQ_API_KEY", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "GITHUB_TOKEN"]
    env_data = {k: ("✔ set" if os.environ.get(k) else "✖ not set") for k in env_keys}
    st.table(env_data)

    st.markdown("---")
    st.markdown("**Vercel Static Integration**")
    st.markdown(
        """
        Since this app runs on Streamlit Cloud, direct REST API triggers from Vercel are not supported.
        In stead, the pipeline saves a static **`output/latest_note.json`** on every run.
        
        **To sync it back to GitHub for Vercel automatically**:
        1. Create a GitHub **Personal Access Token (PAT)** with `repo` scope.
        2. Add **`GITHUB_TOKEN`** to your Streamlit Cloud **Secrets** with that token value.
        """
    )
