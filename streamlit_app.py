import streamlit as st
import os
import glob
from pathlib import Path
from datetime import datetime
import json

# Pipeline Imports
from phase1_ingestion.fetch_reviews import fetch_reviews
from phase2_cleaning.deduplicator import run_phase2a
from phase2_cleaning.pii_filter import run_pii_filtering
from phase3_theme_generation.theme_generator import generate_themes
from phase4_grouping.theme_classifier import classify_reviews
from phase5_note_generation.note_generator import generate_note
from phase7_email.email_generator import send_email

st.set_page_config(page_title="Weekly Product Pulse Backend", page_icon="📡", layout="wide")

st.title("📡 Weekly Product Pulse — Backend Admin")
st.markdown("Manage and visualize your pulse generation backend pipeline from Streamlit.")

OUTPUT_DIR = Path("output")
DATA_DIR = Path("data")

def get_latest_note():
    pattern = str(OUTPUT_DIR / "weekly_note_*.md")
    files = sorted(glob.glob(pattern), reverse=True)
    return Path(files[0]) if files else None

def read_note(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# Sidebar config
st.sidebar.header("Pipeline Actions")

if st.sidebar.button("▶️ Run Entire Pipeline"):
    st.info("Running pipeline... Please wait.")
    with st.spinner("Executing Phase 1 (Data Ingest)"):
        raw = fetch_reviews()
    with st.spinner("Executing Phase 2a (Cleaning)"):
        normalized = run_phase2a()
    with st.spinner("Executing Phase 2b (PII Filtering)"):
        clean = run_pii_filtering()
    with st.spinner("Executing Phase 3 (Themes)"):
        themes = generate_themes()
    with st.spinner("Executing Phase 4 (Classification)"):
        classify_reviews()
        with open(DATA_DIR / "themed_reviews.json", "r", encoding="utf-8") as f:
            tagged = json.load(f)
    with st.spinner("Executing Phase 5 (Note Generation)"):
        note_res = generate_note(tagged, themes)
        # Note generated!
    st.success("✅ Pipeline execution successful!")
    st.rerun()

st.header("1. Latest Weekly Note")
latest_note = get_latest_note()

if latest_note:
    st.success(f"Loaded latest note: **{latest_note.name}**")
    note_content = read_note(latest_note)
    
    with st.expander("👀 View Generated Markdown Note (Phase 5/6)", expanded=True):
        st.markdown(note_content)
        
    st.header("2. Dispatch Note (Phase 7)")
    with st.form("dispatch_form"):
        st.write("Enter recipient details to send this note.")
        recip_name = st.text_input("Recipient Name", "Product Team")
        recip_email = st.text_input("Recipient Email", "product-team@company.com")
        
        if st.form_submit_button("Send Email Setup"):
            # Check env var for gmail
            if not os.environ.get("GMAIL_CREDENTIALS") and not os.environ.get("SMTP_HOST"):
                st.warning("No email credentials configured! A local Draft fallback will be created in output/")
            
            with st.spinner("Sending draft/email..."):
                try:
                    send_email(note_content, recip_name, recip_email)
                    st.success(f"Dispatched email sequence to {recip_name} <{recip_email}>")
                except Exception as e:
                    st.error(f"Failed: {e}")
else:
    st.warning("No weekly note generated yet. Run the pipeline first.")
