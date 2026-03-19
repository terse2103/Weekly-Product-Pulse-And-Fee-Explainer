from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import os
import sys

# Add project root to sys path so phase7_email is importable on Vercel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI()

class SendRequest(BaseModel):
    recipient_name: str
    recipient_email: EmailStr

@app.post("/api/send")
def api_send(body: SendRequest):
    import json
    import urllib.request
    
    try:
        # Fetch the latest generated note statically from Github Raw rather than via local disk
        # because Vercel severless operates immutably
        url = 'https://raw.githubusercontent.com/terse2103/Weekly-Product-Pulse-And-Fee-Explainer/master/output/latest_note.json'
        with urllib.request.urlopen(url) as response:
            note_data = json.loads(response.read().decode())
            markdown_content = note_data.get('markdown', '')
            
        from phase7_email.email_generator import send_email
        send_email(markdown_content, body.recipient_name, body.recipient_email)
        
        return {"status": "sent", "message": f"Weekly Pulse safely shipped to {body.recipient_email}!"}
    
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
