"""
streamlit_app.py — Weekly Product Pulse · Full Streamlit UI
============================================================
Single-app deployment for Streamlit Cloud.

Features:
  • View the latest weekly note (rendered markdown)
  • Run the full pipeline (Phases 1–5 + Phase 7b) in a background thread
  • Send the note via email to any recipient
  • Pipeline status with live refresh
  • Note stats (date, filename, word count)

Secrets required (Streamlit Cloud → Settings → Secrets):
  GROQ_API_KEY, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
  GDOC_ID, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
"""

import glob
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# ── 1. Bootstrap: secrets → os.environ ──────────────────────────────────────
load_dotenv()
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass

# ── 2. Directories ────────────────────────────────────────────────────────────
for _d in ("data", "output", "logs"):
    os.makedirs(_d, exist_ok=True)

OUTPUT_DIR = Path("output")
DATA_DIR   = Path("data")

# ── 3. Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="INDMoney Weekly Product Pulse",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 4. Premium CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 0 !important; padding-bottom: 0 !important; }
div[data-testid="stDecoration"] { display: none; }

:root {
  --bg:       #0a0d18;
  --surface:  #111527;
  --border:   rgba(99,102,241,.18);
  --border-h: rgba(99,102,241,.42);
  --p1:       #6366f1;
  --p2:       #818cf8;
  --a1:       #06b6d4;
  --a2:       #22d3ee;
  --vio:      #a78bfa;
  --text:     #e2e8f0;
  --muted:    #64748b;
  --subtle:   #94a3b8;
  --ok:       #10b981;
  --err:      #f87171;
  --warn:     #fbbf24;
  --glass:    rgba(17,21,39,.72);
  --font:     'Inter', system-ui, sans-serif;
  --mono:     'JetBrains Mono', monospace;
  --r:        14px;
}

.stApp {
  background: var(--bg) !important;
  font-family: var(--font) !important;
  color: var(--text) !important;
}

/* Ambient blobs */
.blob { position: fixed; border-radius: 50%; filter: blur(100px);
        opacity: .24; pointer-events: none; z-index: 0; }
.b1 { width:520px;height:520px;
  background: radial-gradient(circle,#6366f1 0%,transparent 70%);
  top:-160px; left:-160px; }
.b2 { width:480px;height:480px;
  background: radial-gradient(circle,#06b6d4 0%,transparent 70%);
  bottom:-140px; right:-140px; }

/* — Top header banner — */
.pulse-header {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 12px;
  padding: 22px 32px 20px;
  background: var(--glass);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  margin-bottom: 4px;
  position: relative; z-index: 10;
}
.logo-row { display: flex; align-items: center; gap: 14px; }
.logo-em  { font-size: 2rem; filter: drop-shadow(0 0 10px rgba(99,102,241,.6)); }
.pulse-title {
  font-size: 1.4rem; font-weight: 800; letter-spacing: -.4px;
  background: linear-gradient(135deg, var(--p2) 0%, var(--a2) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.pulse-sub { font-size: .72rem; color: var(--muted); letter-spacing: .07em;
             text-transform: uppercase; }
.badge-date {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 14px; border-radius: 999px;
  font-size: .74rem; font-weight: 600; letter-spacing: .03em;
  background: rgba(99,102,241,.15); color: var(--p2);
  border: 1px solid rgba(99,102,241,.35);
}

/* — Glass card — */
.gcard {
  background: var(--glass);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 20px 22px;
  transition: border-color .3s, box-shadow .3s;
  position: relative; z-index: 1;
}
.gcard:hover { border-color: var(--border-h); box-shadow: 0 6px 32px rgba(99,102,241,.1); }
.card-hdr {
  font-size: .78rem; font-weight: 700; color: var(--subtle);
  text-transform: uppercase; letter-spacing: .08em;
  margin-bottom: 14px; display: flex; align-items: center; gap: 8px;
}

/* — Note panel — */
.note-panel {
  background: var(--glass);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 26px 30px;
  min-height: 540px;
  position: relative; z-index: 1;
  transition: border-color .3s;
}
.note-panel:hover { border-color: var(--border-h); }
.note-panel-hdr {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 24px; padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
}
.note-panel-icon { font-size: 1.25rem; }
.note-panel-title {
  font-size: 1rem; font-weight: 700;
  background: linear-gradient(90deg, var(--p2), var(--vio));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* — Note markdown styles — */
.note-md { font-size: .93rem; line-height: 1.78; color: var(--text);
           animation: fadeUp .45s cubic-bezier(.22,1,.36,1); }
@keyframes fadeUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
.note-md h1 {
  font-size: 1.4rem; font-weight: 700; margin: 20px 0 8px;
  background: linear-gradient(135deg, var(--p2), var(--a2));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.note-md h2 { font-size: 1.05rem; font-weight: 700; color: var(--a2); margin: 18px 0 8px; }
.note-md h3 { font-size: .95rem; font-weight: 700; color: var(--vio); margin: 14px 0 6px; }
.note-md ul, .note-md ol { padding-left: 22px; margin: 6px 0 12px; }
.note-md li  { margin-bottom: 6px; }
.note-md strong { color: var(--p2); font-weight: 600; }
.note-md em     { color: var(--a2); font-style: normal; font-weight: 500; }
.note-md blockquote {
  border-left: 3px solid var(--vio); margin: 10px 0; padding: 9px 16px;
  background: rgba(167,139,250,.07); border-radius: 0 8px 8px 0;
  font-style: italic; color: var(--subtle);
}
.note-md hr { border: none; height: 1px; background: var(--border); margin: 16px 0; }
.note-md p  { margin-bottom: 10px; }

/* — Status dot — */
.sdot {
  display: inline-block; width: 9px; height: 9px;
  border-radius: 50%; margin-right: 7px; vertical-align: middle;
}
.sdot-idle    { background: var(--muted); }
.sdot-running { background: var(--warn); animation: pulse 1.2s infinite; }
.sdot-ok      { background: var(--ok); }
.sdot-err     { background: var(--err); }
@keyframes pulse {
  0%  { box-shadow: 0 0 0 0   rgba(251,191,36,.5); }
  70% { box-shadow: 0 0 0 8px rgba(251,191,36,0);  }
  100%{ box-shadow: 0 0 0 0   rgba(251,191,36,0);  }
}
.slabel { font-size: .86rem; font-weight: 600; }
.sdetail { font-size: .72rem; color: var(--muted); font-family: var(--mono); margin-top: 3px; }

/* — Stat row — */
.srow {
  display: flex; justify-content: space-between; align-items: center;
  font-size: .82rem; padding: 7px 10px;
  background: rgba(99,102,241,.06); border-radius: 8px;
  border: 1px solid rgba(99,102,241,.10); margin-bottom: 6px;
}
.sk { color: var(--muted); font-weight: 500; }
.sv { color: var(--text); font-weight: 700; font-variant-numeric: tabular-nums; }

/* — Empty state — */
.empty {
  display: flex; flex-direction: column; align-items: center; text-align: center;
  padding: 60px 24px; gap: 12px;
}
.empty-icon  { font-size: 2.4rem; }
.empty-title { font-size: 1.05rem; font-weight: 700; }
.empty-desc  { font-size: .82rem; color: var(--muted); }

/* — Footer — */
.pfooter {
  text-align: center; font-size: .72rem; color: var(--muted);
  padding: 20px 0 8px; border-top: 1px solid var(--border); margin-top: 32px;
  position: relative; z-index: 1;
}

/* Streamlit button override */
div[data-testid="stButton"] > button {
  border-radius: 12px !important;
  font-family: var(--font) !important;
  font-weight: 700 !important;
  font-size: .88rem !important;
  transition: transform .15s, box-shadow .2s !important;
  border: 1px solid rgba(99,102,241,.35) !important;
  background: rgba(99,102,241,.14) !important;
  color: var(--p2) !important;
}
div[data-testid="stButton"] > button:hover {
  background: rgba(99,102,241,.26) !important;
  color: #fff !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 6px 20px rgba(99,102,241,.3) !important;
}
div[data-testid="stButton"] > button:active { transform: translateY(1px) !important; }

/* form submit button */
div[data-testid="stFormSubmitButton"] > button {
  width: 100% !important;
  border-radius: 12px !important;
  font-family: var(--font) !important;
  font-weight: 700 !important;
  background: linear-gradient(135deg, var(--p1) 0%, var(--a1) 100%) !important;
  color: #fff !important;
  border: none !important;
  box-shadow: 0 4px 20px rgba(99,102,241,.35) !important;
  transition: transform .15s, box-shadow .2s !important;
  font-size: .9rem !important;
}
div[data-testid="stFormSubmitButton"] > button:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 8px 28px rgba(99,102,241,.45) !important;
}

/* Streamlit text inputs */
div[data-testid="stTextInput"] > div > div > input {
  background: rgba(255,255,255,.04) !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
  border-radius: 8px !important;
  font-family: var(--font) !important;
}
div[data-testid="stTextInput"] > div > div > input:focus {
  border-color: var(--p1) !important;
  box-shadow: 0 0 0 3px rgba(99,102,241,.22) !important;
}
div[data-testid="stTextInput"] label {
  color: var(--subtle) !important;
  font-size: .75rem !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: .05em !important;
}

/* Streamlit success/error/info banners */
div[data-testid="stAlert"] {
  border-radius: 10px !important;
  font-family: var(--font) !important;
}
</style>

<div class="blob b1"></div>
<div class="blob b2"></div>
""", unsafe_allow_html=True)

# ── 5. Session state ──────────────────────────────────────────────────────────
defaults = {
    "pipeline_status": "idle",   # idle | running | done | error
    "pipeline_error":  "",
    "pipeline_last_run": None,
    "send_result": None,          # None | ("success"|"error"|"info", msg)
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── 6. Helpers ────────────────────────────────────────────────────────────────

def get_latest_note() -> Path | None:
    files = sorted(glob.glob(str(OUTPUT_DIR / "weekly_note_*.md")), reverse=True)
    return Path(files[0]) if files else None


def read_note(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def format_date(s: str) -> str:
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
        return d.strftime("%d %b %Y").lstrip("0")
    except Exception:
        return s


def md_to_html(md: str) -> str:
    """Lightweight markdown → HTML converter (no third-party deps)."""
    import html as _h

    def inline(t: str) -> str:
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"\*(.+?)\*",     r"<em>\1</em>", t)
        t = re.sub(r"`(.+?)`",       r"<code>\1</code>", t)
        return t

    def norm_heading(t: str) -> str:
        """Strips leading numbers from canonical headings (e.g. 'Top 3 themes' -> 'Top Themes')"""
        # Remove any surrounding markdown bold/italic asterisks first
        clean = re.sub(r"^\*+|\*+$", "", t.strip())
        
        # Apply the substitutions on the cleaned string
        clean = re.sub(r"(?i)^top\s+\d+\s+themes?", "Top Themes", clean)
        clean = re.sub(r"(?i)^\d+\s+user\s+quotes?", "User Quotes", clean)
        clean = re.sub(r"(?i)^\d+\s+action\s+(?:ideas|items|recommendations)?", "Action Ideas", clean)
        
        return clean

    lines = md.split("\n")
    out   = []
    in_ul = False
    in_ol = False
    in_themes_section = False

    def close_list():
        nonlocal in_ul, in_ol
        if in_ul: out.append("</ul>"); in_ul = False
        if in_ol: out.append("</ol>"); in_ol = False

    _THEME_PAT_A = re.compile(r"^([^:]+):\s*(\d+)\s+reviews?\.\s*(?:Description:\s*)?(.*)$", re.I)
    _THEME_PAT_B = re.compile(r"^\*{0,2}([^*(]+?)\*{0,2}\s*\((\d+)\s+reviews?\):\s*(.*)$", re.I)

    for line in lines:
        safe    = _h.escape(line)
        stripped = safe.strip()

        # ATX headings
        if stripped.startswith("### "):
            close_list()
            norm = norm_heading(stripped[4:])
            in_themes_section = bool(re.search(r"Top Themes", norm, re.I))
            out.append(f"<h3>{inline(norm)}</h3>")
        elif stripped.startswith("## "):
            close_list()
            norm = norm_heading(stripped[3:])
            in_themes_section = bool(re.search(r"Top Themes", norm, re.I))
            out.append(f"<h2>{inline(norm)}</h2>")
        elif stripped.startswith("# "):
            close_list()
            norm = norm_heading(stripped[2:])
            in_themes_section = bool(re.search(r"Top Themes", norm, re.I))
            out.append(f"<h1>{inline(norm)}</h1>")
        # Standalone bold line  →  treat as h2 (LLM pattern: **Top 3 themes**)
        elif re.fullmatch(r"\*\*[^*]+\*\*", stripped):
            close_list()
            inner = _h.escape(line.strip()[2:-2])
            norm = norm_heading(inner)
            in_themes_section = bool(re.search(r"Top Themes", norm, re.I))
            out.append(f"<h2>{norm}</h2>")
        # Unordered list
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if in_ol: close_list()
            if not in_ul: out.append("<ul>"); in_ul = True
            
            content = stripped[2:]
            
            # Apply theme enhancement if we are in the themes section
            if in_themes_section:
                m = _THEME_PAT_A.match(content) or _THEME_PAT_B.match(content)
                if m:
                    theme_name   = m.group(1).strip().strip("*")
                    review_count = m.group(2).strip()
                    description  = m.group(3).strip()
                    
                    badge = (f'<span style="display:inline-block;font-size:0.75rem;font-weight:600;'
                             f'color:var(--p2);background:rgba(99,102,241,0.15);'
                             f'border:1px solid rgba(99,102,241,0.3);'
                             f'border-radius:4px;padding:1px 7px;margin-left:8px;'
                             f'vertical-align:middle;">[{review_count} reviews]</span>')
                    desc_html = (f'<span style="display:block;margin-top:6px;font-size:0.85rem;'
                                 f'color:var(--subtle);font-style:italic;">{inline(description)}</span>') if description else ""
                    
                    out.append(f"<li><strong>{theme_name}</strong>{badge}{desc_html}</li>")
                    continue

            out.append(f"<li>{inline(content)}</li>")

        # Ordered list
        elif re.match(r"^\d+\.\s", stripped):
            if in_ul: close_list()
            if not in_ol: out.append("<ol>"); in_ol = True
            out.append(f"<li>{inline(re.sub(r'^\\d+\\.\\s', '', stripped))}</li>")
        # HR
        elif stripped in ("---", "***", "___"):
            close_list()
            out.append("<hr>")
        # Blockquote
        elif stripped.startswith("&gt; "):
            close_list()
            out.append(f"<blockquote>{inline(stripped[5:])}</blockquote>")
        # Blank
        elif stripped == "":
            close_list()
        # Paragraph
        else:
            close_list()
            out.append(f"<p>{inline(safe)}</p>")

    close_list()
    return "\n".join(out)


# ── 7. Background pipeline runner ─────────────────────────────────────────────

def _run_pipeline():
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
        note_md, _ = generate_note(tagged, themes)

        from phase7_email import generate_fee_explanation, build_combined_json, append_to_gdoc
        fee_data = generate_fee_explanation()
        combined = build_combined_json(note_md, fee_data)
        append_to_gdoc(combined)

        st.session_state.pipeline_status   = "done"
        st.session_state.pipeline_last_run = datetime.now().isoformat()

    except Exception as exc:
        st.session_state.pipeline_status = "error"
        st.session_state.pipeline_error  = str(exc)


# ── 8. Data ───────────────────────────────────────────────────────────────────
note_path    = get_latest_note()
note_content = read_note(note_path) if note_path else None
note_date    = note_path.name.replace("weekly_note_", "").replace(".md", "") if note_path else ""
word_count   = len(note_content.split()) if note_content else 0
status       = st.session_state.pipeline_status
last_run     = st.session_state.pipeline_last_run

# ── 9. Header ─────────────────────────────────────────────────────────────────
badge = f'<span class="badge-date">📅 {format_date(note_date)}</span>' if note_date else ""
st.markdown(f"""
<div class="pulse-header">
  <div class="logo-row">
    <span class="logo-em">📋</span>
    <div>
      <div class="pulse-title">INDMoney Weekly Pulse</div>
      <div class="pulse-sub">Play Store · Voice of the Customer</div>
    </div>
  </div>
  <div>{badge}</div>
</div>
""", unsafe_allow_html=True)

# ── 10. Two-column layout using st.columns ────────────────────────────────────
col_note, col_actions = st.columns([2.8, 1], gap="medium")

# ── LEFT COLUMN: Note viewer ───────────────────────────────────────────────────
with col_note:
    html_out = [
        '<div class="note-panel">',
        '  <div class="note-panel-hdr">',
        '    <span class="note-panel-icon">📄</span>',
        '    <span class="note-panel-title">This Week\'s Note</span>',
        '  </div>'
    ]

    if note_content:
        html_out.append(f'<div class="note-md">{md_to_html(note_content)}</div>')
    else:
        html_out.append('''
        <div class="empty">
          <span class="empty-icon">⚠️</span>
          <p class="empty-title">Note not available</p>
          <p class="empty-desc">Run the pipeline using the button on the right to generate this week's note.</p>
        </div>
        ''')

    html_out.append('</div>')
    st.markdown('\n'.join(html_out), unsafe_allow_html=True)

# ── RIGHT COLUMN: Action cards ────────────────────────────────────────────────
with col_actions:

    # ── Pipeline Status ──────────────────────────────────────────────────────
    if status == "running":
        dot_cls, slabel = "sdot-running", "Pipeline running…"
    elif status == "done":
        dot_cls, slabel = "sdot-ok",      "Pipeline complete ✅"
    elif status == "error":
        dot_cls, slabel = "sdot-err",     "Pipeline error ❌"
    elif note_content:
        dot_cls, slabel = "sdot-ok",      "Note ready"
    else:
        dot_cls, slabel = "sdot-idle",    "Pipeline idle"

    detail = ""
    if last_run:
        detail = f'<div class="sdetail">Last run: {last_run[:19].replace("T"," ")}</div>'
    elif note_path:
        detail = f'<div class="sdetail">File: {note_path.name}</div>'

    st.markdown(f"""
    <div class="gcard">
      <div class="card-hdr">⚙️ Pipeline Status</div>
      <div style="display:flex;align-items:center;">
        <span class="sdot {dot_cls}"></span>
        <span class="slabel">{slabel}</span>
      </div>
      {detail}
    </div>
    """, unsafe_allow_html=True)

    if status == "error":
        st.error(f"Error: {st.session_state.pipeline_error}")

    # ── Run Pipeline button ──────────────────────────────────────────────────
    run_label = "⏳ Running…" if status == "running" else "🚀 Run Pipeline"
    if st.button(run_label, key="btn_run", disabled=(status == "running"), use_container_width=True):
        st.session_state.pipeline_status = "running"
        st.session_state.pipeline_error  = ""
        threading.Thread(target=_run_pipeline, daemon=True).start()
        st.rerun()

    if status == "running":
        st.info("⏳ Pipeline started — refresh this page in a few minutes to see the new note.")

    # ── Note Stats ────────────────────────────────────────────────────────────
    if note_content:
        fname_short = note_path.name if note_path else "—"
        st.markdown(f"""
        <div class="gcard" style="margin-top:10px;">
          <div class="card-hdr">📊 Note Stats</div>
          <div class="srow"><span class="sk">Note date</span><span class="sv">{format_date(note_date)}</span></div>
          <div class="srow"><span class="sk">File</span><span class="sv" style="font-size:.7rem;">{fname_short}</span></div>
          <div class="srow"><span class="sk">Words</span><span class="sv">{word_count}</span></div>
        </div>
        """, unsafe_allow_html=True)

    # ── Send Email ────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="gcard" style="margin-top:10px;">
      <div class="card-hdr">✉️ Send This Pulse</div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("send_form", clear_on_submit=True):
        rec_name  = st.text_input("Recipient Name",  placeholder="e.g. Priya Sharma")
        rec_email = st.text_input("Recipient Email", placeholder="e.g. priya@company.com")
        submitted = st.form_submit_button("Send Weekly Pulse ✉️", use_container_width=True)

    if submitted:
        if not rec_name.strip():
            st.session_state.send_result = ("error", "Recipient name is required.")
        elif "@" not in rec_email or "." not in rec_email:
            st.session_state.send_result = ("error", "Please enter a valid email address.")
        elif not note_content:
            st.session_state.send_result = ("error", "No weekly note available. Run the pipeline first.")
        else:
            with st.spinner("Sending email…"):
                try:
                    from phase7_email import send_email, generate_fee_explanation
                    fee_data = generate_fee_explanation()
                    delivery, detail_msg = send_email(
                        note_content, rec_name.strip(), rec_email.strip(), fee_data=fee_data
                    )
                    if delivery in ("email", "smtp", "gmail", "sent"):
                        st.session_state.send_result = ("success", f"✅ Email delivered to {rec_email}")
                    elif delivery == "fallback":
                        st.session_state.send_result = ("error", f"⚠️ Fallback mode: {detail_msg}")
                    else:
                        st.session_state.send_result = ("info", f"ℹ️ Queued ({delivery}): {detail_msg}")
                except Exception as exc:
                    st.session_state.send_result = ("error", f"❌ Failed: {exc}")
            st.rerun()

    # Show send notification
    if st.session_state.send_result:
        kind, msg = st.session_state.send_result
        if kind == "success":
            st.success(msg)
        elif kind == "error":
            st.error(msg)
        else:
            st.info(msg)
        st.session_state.send_result = None

# ── 11. Footer ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="pfooter">
  Powered by <strong>Groq LLaMA&nbsp;3.3&nbsp;70B</strong>
  &nbsp;·&nbsp; Play Store data
  &nbsp;·&nbsp; Hosted on <strong>Streamlit Cloud</strong>
</div>
""", unsafe_allow_html=True)
