"""
phase6_web_ui/app.py
====================
FastAPI backend for the Weekly Product Pulse Web UI.

Endpoints:
  GET  /             → Serves the static HTML UI page
  GET  /api/note     → Returns the latest weekly note (markdown + metadata)
  POST /api/send     → Accepts { recipient_name, recipient_email }, triggers email delivery
  GET  /api/status   → Returns pipeline run status

Run with:
  uvicorn phase6_web_ui.app:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import glob
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv

# Load environment variables (e.g., SMTP credentials)
load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("phase6_web_ui")

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = Path("output")  # relative to project root

app = FastAPI(
    title="Weekly Product Pulse — Web UI",
    description="View and send the INDMoney Weekly Product Pulse note.",
    version="1.0.0",
)

# Mount the static directory so CSS/JS/images are served at /static/...
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# In-memory pipeline status (lightweight; replace with DB for production)
# ---------------------------------------------------------------------------
_pipeline_status = {
    "last_run": None,
    "status": "idle",          # idle | running | completed | failed
    "last_note_file": None,
    "sent_count": 0,
}


# ---------------------------------------------------------------------------
# Helper — find the latest weekly note file
# ---------------------------------------------------------------------------
def _get_latest_note() -> Optional[Path]:
    """Return the Path to the most-recently generated weekly note, or None."""
    pattern = str(OUTPUT_DIR / "weekly_note_*.md")
    files = sorted(glob.glob(pattern), reverse=True)
    return Path(files[0]) if files else None


def _read_note(path: Path) -> str:
    """Read and return the note contents as a string."""
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------
class SendRequest(BaseModel):
    recipient_name: str
    recipient_email: EmailStr  # Pydantic validates e-mail format


class SendResponse(BaseModel):
    status: str
    message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_ui():
    """Serve the main HTML UI page."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="UI not found. Check static/index.html.")
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


@app.get("/api/note")
async def get_note():
    """
    Returns the latest weekly note.

    Response:
      {
        "filename": "weekly_note_2026-03-12.md",
        "date":     "2026-03-12",
        "markdown": "<full note content>",
        "word_count": 198
      }
    """
    note_path = _get_latest_note()
    if note_path is None:
        raise HTTPException(
            status_code=404,
            detail="No weekly note found. Run Phase 5 first to generate a note.",
        )

    content = _read_note(note_path)
    word_count = len(content.split())
    filename = note_path.name
    # Extract date from filename like weekly_note_2026-03-12.md
    date_part = filename.replace("weekly_note_", "").replace(".md", "")

    _pipeline_status["last_note_file"] = filename
    logger.info(f"Serving note: {filename} ({word_count} words)")

    return JSONResponse(content={
        "filename": filename,
        "date": date_part,
        "markdown": content,
        "word_count": word_count,
    })


@app.post("/api/send", response_model=SendResponse)
async def send_note(body: SendRequest):
    """
    Accepts recipient details and triggers email delivery (Phase 7 hook).

    For Phase 6, the endpoint validates input and stubs the send operation.
    Phase 7 will replace the stub with genuine Gmail / SMTP delivery.
    """
    logger.info(f"Send requested → {body.recipient_name} <{body.recipient_email}>")

    note_path = _get_latest_note()
    if note_path is None:
        raise HTTPException(
            status_code=404,
            detail="No weekly note available to send. Generate it first.",
        )

    # -----------------------------------------------------------------------
    # Phase 7 hook — replace this block with actual email dispatch
    # -----------------------------------------------------------------------
    try:
        # Attempt to import Phase 7 email sender if it exists
        from phase7_email.email_generator import send_email  # type: ignore
        note_content = _read_note(note_path)
        send_email(note_content, body.recipient_name, body.recipient_email)
        delivery_method = "email"
    except ImportError:
        # Phase 7 not yet implemented — log and stub
        logger.warning(
            "Phase 7 email module not found. Stubbing send. "
            "Implement phase7_email.email_generator.send_email() to enable real delivery."
        )
        delivery_method = "stub"
    except Exception as exc:
        logger.error(f"Email delivery failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Email delivery failed: {exc}")
    # -----------------------------------------------------------------------

    _pipeline_status["sent_count"] += 1
    _pipeline_status["last_run"] = datetime.now().isoformat()

    note_file = note_path.name
    date_part = note_file.replace("weekly_note_", "").replace(".md", "")

    message = (
        f"Email {'delivered' if delivery_method == 'email' else 'queued (stub)'} "
        f"to {body.recipient_email} — Weekly Pulse for {date_part}"
    )
    logger.info(message)

    return SendResponse(status="sent", message=message)


@app.get("/api/status")
async def get_status():
    """
    Returns the current pipeline run status.

    Response:
      {
        "status":        "idle" | "running" | "completed" | "failed",
        "last_run":      "2026-03-12T10:00:00" | null,
        "last_note_file": "weekly_note_2026-03-12.md" | null,
        "sent_count":    3
      }
    """
    note_path = _get_latest_note()
    _pipeline_status["last_note_file"] = note_path.name if note_path else None

    return JSONResponse(content=_pipeline_status)
