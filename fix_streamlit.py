import sys

def fix_streamlit():
    with open('streamlit_app.py', 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    
    # We want to replace everything between line 41 and line 70
    # based on the broken content that repeats start_api_bridge or uvicorn.run
    fixed_lines = lines[:40] # lines up to 40 inclusive (0-indexed 39)
    
    # insert the clean code
    fixed_lines.append("\ndef _start_api_bridge():\n")
    fixed_lines.append("    \"\"\"Starts the FastAPI server in a background subprocess.\"\"\"\n")
    fixed_lines.append("    import subprocess\n")
    fixed_lines.append("    subprocess.Popen(\n")
    fixed_lines.append("        [\"uvicorn\", \"api_server:api\", \"--host\", \"0.0.0.0\", \"--port\", \"8502\", \"--log-level\", \"warning\"]\n")
    fixed_lines.append("    )\n\n")
    fixed_lines.append("# Start the REST bridge once per process\n")
    fixed_lines.append("if \"api_started\" not in st.session_state:\n")
    fixed_lines.append("    _start_api_bridge()\n")
    fixed_lines.append("    st.session_state[\"api_started\"] = True\n")
    
    # skip the glitched duplicate stuff, pick back up at line 70 (0-indexed 69)
    # let's look for '# ── Streamlit UI' to safely stitch it back
    for i, line in enumerate(lines):
        if '# ── Streamlit UI' in line:
            fixed_lines.extend(lines[i:])
            break
            
    with open('streamlit_app.py', 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)
    print("Streamlit app fixed!")

if __name__ == '__main__':
    fix_streamlit()
