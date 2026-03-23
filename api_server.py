"""
api_server.py — Weekly Pulse REST API (FastAPI)
================================================
This is the primary backend for the Weekly Product Pulse project.
Deployed on Streamlit Cloud by running:
  uvicorn api_server:api --host 0.0.0.0 --port 8000

The Vercel frontend communicates directly with this backend via CORS.

Endpoints:
  GET  /           → Root health check
  GET  /api/health → Health check
  GET  /api/note   → Returns the latest generated weekly note (markdown + metadata)
  POST /api/send   → Dispatches the note to a recipient via email (Phase 7)
  GET  /api/status → Pipeline run status (idle | running | error)
  POST /api/run    → Triggers the full pipeline (Phases 1–5) in the background
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from pathlib import Path
import glob
from datetime import datetime
import json
import os
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Explicitly load .env file so SMTP credentials are in os.environ
load_dotenv()

api = FastAPI(
    title="Weekly Pulse REST API",
    description="Backend for the INDMoney Weekly Product Pulse. Deployed on Streamlit Cloud.",
    version="2.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Vercel frontend (and localhost for local dev) to call this API.
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten to your Vercel domain in production if desired
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path("output")
DATA_DIR   = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ── Pipeline status (in-memory) ───────────────────────────────────────────────
_status = {
    "status": "idle",          # idle | running | error: <message>
    "last_run": None,
    "last_note_file": None,
    "sent_count": 0,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_latest_note() -> Path | None:
    """Return the most-recently generated weekly note path, or None."""
    pattern = str(OUTPUT_DIR / "weekly_note_*.md")
    files = sorted(glob.glob(pattern), reverse=True)
    return Path(files[0]) if files else None


def read_note(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _run_pipeline_task():
    """Runs the full pipeline (Phases 1–5) synchronously in a background thread."""
    _status["status"] = "running"
    try:
        from phase1_ingestion.fetch_reviews import fetch_reviews
        fetch_reviews()

        from phase2_cleaning.deduplicator import run_phase2a
        run_phase2a()

        from phase2_cleaning.pii_filter import run_pii_filtering
        run_pii_filtering()

        from phase3_theme_generation.theme_generator import generate_themes
        themes = generate_themes()

        from phase4_grouping.theme_classifier import classify_reviews
        classify_reviews()

        with open(DATA_DIR / "themed_reviews.json", "r", encoding="utf-8") as f:
            tagged = json.load(f)

        from phase5_note_generation.note_generator import generate_note
        note, word_count = generate_note(tagged, themes)

        from phase7_email import generate_fee_explanation, build_combined_json, append_to_gdoc
        
        fee_data = generate_fee_explanation()
        combined = build_combined_json(note, fee_data)
        append_to_gdoc(combined)

        _status["status"]    = "idle"
        _status["last_run"]  = datetime.now().isoformat()

    except Exception as exc:
        _status["status"] = f"error: {exc}"


# ── Routes ────────────────────────────────────────────────────────────────────

@api.get("/")
def root():
    """Root endpoint — health check."""
    return {"status": "ok", "service": "Weekly Pulse API"}


@api.get("/api/health")
def api_health():
    return {"status": "ok"}


@api.get("/api/note")
def api_note():
    """
    Returns the latest weekly note.

    Response:
      {
        "filename":   "weekly_note_2026-03-20.md",
        "date":       "2026-03-20",
        "markdown":   "<full note content>",
        "word_count": 198
      }
    """
    note_path = get_latest_note()
    if not note_path:
        raise HTTPException(
            status_code=404,
            detail="No weekly note found. Use POST /api/run to generate one.",
        )
    content   = read_note(note_path)
    filename  = note_path.name
    date_part = filename.replace("weekly_note_", "").replace(".md", "")
    _status["last_note_file"] = filename
    return JSONResponse({
        "filename":   filename,
        "date":       date_part,
        "markdown":   content,
        "word_count": len(content.split()),
    })


class SendRequest(BaseModel):
    recipient_name:  str
    recipient_email: EmailStr


@api.post("/api/send")
def api_send(body: SendRequest):
    """
    Accepts recipient details and dispatches the latest weekly note via email (Phase 7).
    """
    note_path = get_latest_note()
    if not note_path:
        raise HTTPException(
            status_code=404,
            detail="No weekly note available to send. Run the pipeline first.",
        )
    try:
        from phase7_email import send_email, generate_fee_explanation
        note_content = read_note(note_path)
        fee_data = generate_fee_explanation()
        delivery, detail_msg = send_email(note_content, body.recipient_name, body.recipient_email, fee_data=fee_data)
    except ImportError:
        delivery = "stub"
        detail_msg = "Stub delivery"
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Email delivery failed: {exc}")

    if delivery == "fallback":
        raise HTTPException(status_code=502, detail=detail_msg)

    _status["sent_count"] += 1
    _status["last_run"]    = datetime.now().isoformat()
    date_part = note_path.name.replace("weekly_note_", "").replace(".md", "")
    message = (
        f"Email {'delivered' if delivery in ('email', 'smtp', 'gmail') else 'queued (stub)'} "
        f"to {body.recipient_email} — Weekly Pulse for {date_part}"
    )
    return {"status": "sent", "message": message}


@api.get("/api/status")
def api_status():
    """
    Returns the current pipeline run status.

    Response:
      {
        "status":         "idle" | "running" | "error: <msg>",
        "last_run":       "2026-03-20T10:00:00" | null,
        "last_note_file": "weekly_note_2026-03-20.md" | null,
        "sent_count":     3
      }
    """
    note_path = get_latest_note()
    _status["last_note_file"] = note_path.name if note_path else None
    return JSONResponse(_status)


@api.post("/api/run")
def api_run(background_tasks: BackgroundTasks):
    """
    Trigger the full data pipeline (Phases 1–5) asynchronously.
    Poll GET /api/status to track progress. Status returns to "idle" when done.
    """
    if _status["status"] == "running":
        raise HTTPException(status_code=409, detail="Pipeline is already running.")
    background_tasks.add_task(_run_pipeline_task)
    return {"status": "started", "message": "Pipeline triggered. Poll /api/status for progress."}
