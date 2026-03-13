# main.py — Weekly Pulse Pipeline Orchestrator
import os
import sys

# Importing from specific modules to avoid __init__.py issues
from phase1_ingestion.fetch_reviews import fetch_reviews
from phase2_cleaning import clean_text, filter_pii
from phase3_theme_generation.theme_generator import generate_themes
from phase4_grouping.theme_classifier import classify_reviews
from phase5_note_generation.note_generator import generate_note
from phase7_email.email_generator import generate_email_draft
from phase7_email.gmail_client import send_via_gmail
from phase7_email.smtp_client import send_via_smtp

def send_email(note, recipient_name, recipient_email):
    # Retrieve configuration and method
    email_method = os.environ.get("EMAIL_METHOD", "local")
    
    html_body = generate_email_draft(note)
    subject = "📋 INDMoney Weekly Product Pulse"
    
    if email_method == "gmail":
        send_via_gmail(recipient_name, recipient_email, subject, html_body)
    elif email_method == "smtp":
        send_via_smtp(recipient_name, recipient_email, subject, html_body)
    else:
        # Fallback to local .eml is handled within the phase7 logic usually, 
        # but here we just pass if local
        print("Draft generated locally.")

def run_pipeline(recipient_name=None, recipient_email=None):
    print("Starting Weekly Pulse Pipeline...")
    raw = fetch_reviews()                  # Phase 1
    print(f"Phase 1: Fetched {len(raw)} reviews.")
    
    normalized = clean_text(raw)           # Phase 2a
    print(f"Phase 2a: Normalized to {len(normalized)} reviews.")
    
    clean = filter_pii(normalized)         # Phase 2b
    print(f"Phase 2b: PII filtered. Remaining: {len(clean)} reviews.")
    
    themes = generate_themes(clean)        # Phase 3
    print(f"Phase 3: Generated {len(themes)} themes.")
    
    tagged = classify_reviews(clean, themes)  # Phase 4
    print("Phase 4: Classified reviews into themes.")
    
    note = generate_note(tagged, themes)   # Phase 5
    print("Phase 5: Generated weekly note.")
    
    # Phase 6 (Web UI) runs separately as a FastAPI server
    
    if recipient_name and recipient_email:
        print(f"Phase 7: Sending email to {recipient_name} <{recipient_email}>")
        send_email(note, recipient_name, recipient_email)  # Phase 7
    
    print("Pipeline execution completed successfully.")

if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs("data", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # Read from env if running in CI/CD action
    recip_name = os.environ.get("RECIPIENT_NAME")
    recip_email = os.environ.get("RECIPIENT_EMAIL")
    
    try:
        run_pipeline(recipient_name=recip_name, recipient_email=recip_email)
    except Exception as e:
        print(f"Pipeline failed: {e}")
        sys.exit(1)
