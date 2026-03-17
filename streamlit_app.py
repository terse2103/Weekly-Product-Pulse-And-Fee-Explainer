"""
streamlit_app.py — Weekly Product Pulse Backend Admin
======================================================
Deployed on Streamlit Cloud.

Manages pipeline execution, note viewing, and email dispatch.
Also exposes a lightweight REST API via a background thread so the
Vercel-hosted static frontend can call /api/note, /api/send, /api/status.
"""

import streamlit as st
import os
import glob
import json
import threading
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

load_dotenv()

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Weekly Product Pulse — Backend",
    page_icon="📡",
    layout="wide",
)

# ── Directories ─────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("output")
DATA_DIR   = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


def get_latest_note() -> Path | None:
    """Return the Path to the most-recently generated weekly note, or None."""
    pattern = str(OUTPUT_DIR / "weekly_note_*.md")
    files = sorted(glob.glob(pattern), reverse=True)
    return Path(files[0]) if files else None


def read_note(path: Path) -> str:
    """Read and return the note contents as a string."""
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _start_api_bridge():
    """Starts the FastAPI server in a background subprocess."""
    import subprocess
    subprocess.Popen(
        ["uvicorn", "api_server:api", "--host", "0.0.0.0", "--port", "8502", "--log-level", "warning"]
    )

# Start the REST bridge once per process
if "api_started" not in st.session_state:
    _start_api_bridge()
    st.session_state["api_started"] = True
# ── Streamlit UI ─────────────────────────────────────────────────────────────
st.title("📡 Weekly Product Pulse — Backend Admin")
st.markdown(
    "Use this panel to run the pipeline, view the generated note, and dispatch emails. "
    "The **public frontend** is served via Vercel and calls this backend's REST API."
)

st.divider()

# ── Sidebar: Pipeline Actions ────────────────────────────────────────────────
st.sidebar.header("⚙️ Pipeline Actions")

if st.sidebar.button("▶️ Run Entire Pipeline", use_container_width=True):
    st.info("Running pipeline… this may take a minute.")

    try:
        from phase1_ingestion.fetch_reviews import fetch_reviews
        with st.spinner("Phase 1 — Fetching reviews…"):
            raw = fetch_reviews()
        st.sidebar.success(f"Phase 1 ✅  {len(raw)} reviews fetched")

        from phase2_cleaning.deduplicator import run_phase2a
        with st.spinner("Phase 2a — Deduplication & normalisation…"):
            normalized = run_phase2a()
        st.sidebar.success(f"Phase 2a ✅  {len(normalized)} reviews normalised")

        from phase2_cleaning.pii_filter import run_pii_filtering
        with st.spinner("Phase 2b — PII filtering…"):
            clean = run_pii_filtering()
        st.sidebar.success(f"Phase 2b ✅  {len(clean)} clean reviews")

        from phase3_theme_generation.theme_generator import generate_themes
        with st.spinner("Phase 3 — Generating themes…"):
            themes = generate_themes()
        st.sidebar.success(f"Phase 3 ✅  {len(themes)} themes")

        from phase4_grouping.theme_classifier import classify_reviews
        with st.spinner("Phase 4 — Classifying reviews…"):
            classify_reviews()
        with open(DATA_DIR / "themed_reviews.json", "r", encoding="utf-8") as f:
            tagged = json.load(f)
        st.sidebar.success("Phase 4 ✅  Reviews classified")

        from phase5_note_generation.note_generator import generate_note
        with st.spinner("Phase 5 — Generating weekly note…"):
            note_res = generate_note(tagged, themes)
        st.sidebar.success("Phase 5 ✅  Note generated")

        st.success("✅ Pipeline completed successfully! Refresh to see the latest note.")
        st.rerun()

    except Exception as exc:
        st.error(f"Pipeline failed: {exc}")

st.sidebar.divider()
st.sidebar.caption("Logs and output files are stored in `output/` and `data/`.")

# ── Main: Latest Note ────────────────────────────────────────────────────────
st.header("📄 Latest Weekly Note")

latest_note = get_latest_note()

if latest_note:
    st.success(f"**{latest_note.name}**  — loaded from `output/`")
    note_content = read_note(latest_note)

    with st.expander("👀 View Generated Note", expanded=True):
        st.markdown(note_content)

    # ── Email Dispatch ───────────────────────────────────────────────────────
    st.header("✉️ Dispatch Note (Phase 7)")
    with st.form("dispatch_form"):
        col1, col2 = st.columns(2)
        recip_name  = col1.text_input("Recipient Name",  placeholder="e.g. Priya Sharma")
        recip_email = col2.text_input("Recipient Email", placeholder="e.g. priya@company.com")

        submitted = st.form_submit_button("📤 Send Email")
        if submitted:
            if not recip_name or not recip_email:
                st.warning("Please fill in both recipient name and email.")
            else:
                if not os.environ.get("GMAIL_CREDENTIALS") and not os.environ.get("SMTP_HOST"):
                    st.warning(
                        "No email credentials configured. "
                        "A local `.eml` draft will be saved in `output/`."
                    )
                with st.spinner("Dispatching email…"):
                    try:
                        from phase7_email.email_generator import send_email  # type: ignore
                        send_email(note_content, recip_name, recip_email)
                        st.success(f"✅ Email dispatched to **{recip_name}** `<{recip_email}>`")
                    except Exception as exc:
                        st.error(f"❌ Failed: {exc}")

else:
    st.warning("No weekly note found. Use the **Run Entire Pipeline** button in the sidebar to generate one.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Powered by **Groq LLaMA 3.3 70B** · Google Play Store data · "
    "Backend admin via Streamlit Cloud · Public UI via Vercel"
)
