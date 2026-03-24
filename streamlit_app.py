"""
streamlit_app.py — Streamlit Cloud entrypoint for the Weekly Pulse FastAPI backend
====================================================================================
Streamlit Cloud requires a streamlit_app.py as its entrypoint.
Since our real backend is a FastAPI app (api_server.py), this file:
  1. Launches api_server:api with uvicorn in a background thread on port 8000.
  2. Shows a minimal Streamlit status page so the Streamlit Cloud slot stays alive.

Deploy steps (Streamlit Cloud):
  - Main file: streamlit_app.py
  - Python version: 3.10+
  - All dependencies must be in requirements.txt (streamlit, fastapi, uvicorn[standard], …)
"""

import threading
import os
import streamlit as st
import uvicorn

# ── Sync Streamlit secrets → os.environ ─────────────────────────────────────
# Streamlit Cloud stores secrets in st.secrets (not a physical .env file).
# The FastAPI backend reads env vars via python-dotenv / os.environ.
# This block bridges the two systems at startup.
try:
    for _key, _val in st.secrets.items():
        if isinstance(_val, str):
            os.environ.setdefault(_key, _val)
except Exception:
    pass  # st.secrets is empty locally (use .env file instead)

# ── Config ──────────────────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 8000))

def _start_fastapi():
    """Run the FastAPI app in a daemon thread so it doesn't block Streamlit."""
    uvicorn.run(
        "api_server:api",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )

# Start FastAPI exactly once (Streamlit re-runs this script on every interaction)
if "fastapi_started" not in st.session_state:
    thread = threading.Thread(target=_start_fastapi, daemon=True)
    thread.start()
    st.session_state["fastapi_started"] = True

# ── Streamlit status page ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Weekly Pulse — Backend",
    page_icon="📋",
)

st.title("📋 Weekly Product Pulse — Backend")
st.success(f"✅ FastAPI backend is running on port **{PORT}**.")
st.markdown(
    """
    This Streamlit app hosts the **FastAPI REST API** for the Weekly Product Pulse project.

    | Endpoint | Description |
    |---|---|
    | `GET  /api/health` | Health check |
    | `GET  /api/note` | Latest weekly note (markdown + metadata) |
    | `POST /api/send` | Send note via email |
    | `GET  /api/status` | Pipeline run status |
    | `POST /api/run` | Trigger full pipeline (Phases 1–5) |
    | `GET  /docs` | Swagger UI (interactive API docs) |

    > **Frontend** is deployed separately on **Vercel** and communicates with this backend via CORS.
    """
)

st.info("ℹ️ The Streamlit UI above is a status page only. All real traffic goes through the FastAPI endpoints listed above.")
