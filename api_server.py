"""
api_server.py — Weekly Pulse REST API (FastAPI)
================================================
Runs as a background thread inside the Streamlit Docker container.
Streamlit is the primary entry point (streamlit_app.py); this module is
imported and started via uvicorn in a daemon thread on API_PORT (default 8081).

Endpoints:
  GET  /           → Health check (used by Railway)
  GET  /api/note   → Returns the latest generated weekly note
  POST /api/send   → Dispatches the note to a recipient via email
  GET  /api/status → Pipeline run status
  GET  /api/health → Health check
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

api = FastAPI(title="Weekly Pulse REST API")

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path("output")
DATA_DIR   = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ── Pipeline status (in-memory) ───────────────────────────────────────────────
_status = {
    "status": "idle",
    "last_run": None,
    "last_note_file": None,
    "sent_count": 0,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_latest_note() -> Path | None:
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
        generate_note(tagged, themes)

        _status["status"] = "idle"
        _status["last_run"] = datetime.now().isoformat()

    except Exception as exc:
        _status["status"] = f"error: {exc}"


# ── Routes ────────────────────────────────────────────────────────────────────

@api.get("/")
def root():
    """Root endpoint — used by Railway health checks."""
    return {"status": "ok", "service": "Weekly Pulse API"}


@api.get("/api/health")
def api_health():
    return {"status": "ok"}


@api.get("/api/note")
def api_note():
    note_path = get_latest_note()
    if not note_path:
        raise HTTPException(
            status_code=404,
            detail="No weekly note found. Run the pipeline first via POST /api/run.",
        )
    content  = read_note(note_path)
    filename = note_path.name
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
    note_path = get_latest_note()
    if not note_path:
        raise HTTPException(
            status_code=404,
            detail="No weekly note available to send. Run the pipeline first.",
        )
    try:
        from phase7_email.email_generator import send_email  # type: ignore
        note_content = read_note(note_path)
        send_email(note_content, body.recipient_name, body.recipient_email)
        delivery = "email"
    except ImportError:
        delivery = "stub"
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Email delivery failed: {exc}")

    _status["sent_count"] += 1
    _status["last_run"] = datetime.now().isoformat()
    date_part = note_path.name.replace("weekly_note_", "").replace(".md", "")
    message = (
        f"Email {'delivered' if delivery == 'email' else 'queued (stub)'} "
        f"to {body.recipient_email} — Weekly Pulse for {date_part}"
    )
    return {"status": "sent", "message": message}


@api.get("/api/status")
def api_status():
    note_path = get_latest_note()
    _status["last_note_file"] = note_path.name if note_path else None
    return JSONResponse(_status)


@api.post("/api/run")
def api_run(background_tasks: BackgroundTasks):
    """
    Trigger the full data pipeline (Phases 1–5) asynchronously.
    Poll GET /api/status to check when it completes.
    """
    if _status["status"] == "running":
        raise HTTPException(status_code=409, detail="Pipeline is already running.")
    background_tasks.add_task(_run_pipeline_task)
    return {"status": "started", "message": "Pipeline triggered. Poll /api/status for progress."}
