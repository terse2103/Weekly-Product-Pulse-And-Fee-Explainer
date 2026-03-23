"""
gdocs_mcp_server.py
===================
A custom Python-based MCP Server for Google Docs.
Exposes a tool 'append_to_google_doc' to append text to a given document ID.

Requires:
  - mcp
  - google-api-python-client
  - google-auth-oauthlib
  - python-dotenv
"""

import os
import json
import logging
import pickle
from typing import Any
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Google API imports
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gdocs_mcp_server")

# ── Google API Scopes ────────────────────────────────────────────────────────
SCOPES = ['https://www.googleapis.com/auth/documents']

# Initialize FastMCP Server
mcp = FastMCP("GoogleDocsServer")

def get_gdocs_service():
    """Authenticates and returns the Google Docs service object."""
    creds = None
    token_path = Path("token.pickle")
    
    # Use existing token if available
    if token_path.exists():
        with open(token_path, "rb") as token:
            creds = pickle.load(token)
            
    # If no valid credentials, run the auth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # We expect GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env
            client_config = {
                "installed": {
                    "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                    "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
            if not client_config["installed"]["client_id"]:
                raise ValueError("GOOGLE_CLIENT_ID missing from .env")
                
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save credentials for future use
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)
            
    return build('docs', 'v1', credentials=creds)

@mcp.tool()
def append_to_google_doc(doc_id: str, text: str) -> str:
    """
    Appends text to the end of a Google Document.
    
    Args:
        doc_id: The ID of the Google Document (from the URL).
        text: The text string to append.
    """
    try:
        service = get_gdocs_service()
        
        # Get the current document length to append at the end
        doc = service.documents().get(documentId=doc_id).execute()
        end_index = doc.get('body').get('content')[-1].get('endIndex') - 1
        
        # Execute the append request
        requests = [
            {
                'insertText': {
                    'location': {'index': end_index},
                    'text': text
                }
            }
        ]
        
        service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        
        return f"✅ Successfully appended text to document ID: {doc_id}"
        
    except Exception as e:
        logger.error(f"Error appending to doc: {e}")
        return f"❌ Failed to append: {str(e)}"

if __name__ == "__main__":
    # Start the MCP server using standard I/O
    mcp.run()
