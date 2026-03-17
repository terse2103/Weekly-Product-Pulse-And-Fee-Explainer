from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from pathlib import Path
import glob
from datetime import datetime
import json
import os

api = FastAPI(title="Weekly Pulse REST Bridge")

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

# ── Pipeline status (shared memory pseudo-state) ─────────────────────────
_status = {
    "status": "idle",
    "last_run": None,
    "last_note_file": None,
    "sent_count": 0,
}

def get_latest_note() -> Path | None:
    pattern = str(OUTPUT_DIR / "weekly_note_*.md")
    files = sorted(glob.glob(pattern), reverse=True)
    return Path(files[0]) if files else None

def read_note(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@api.get("/api/note")
def api_note():
    note_path = get_latest_note()
    if not note_path:
        raise HTTPException(
            status_code=404,
            detail="No weekly note found. Run Phase 5 first to generate a note.",
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
            detail="No weekly note available to send. Generate it first.",
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
