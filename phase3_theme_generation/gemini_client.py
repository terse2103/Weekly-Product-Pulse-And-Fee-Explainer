"""Gemini API client wrapper for Phase 3."""

import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load from the project root .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

MODEL = "gemini-2.0-flash"
TEMPERATURE = 0.3


def get_client() -> genai.Client:
    """Initialises and returns a Gemini client."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not found. Ensure it is set in the .env file at the project root."
        )
    return genai.Client(api_key=api_key)


import time

def call_gemini_json_mode(system_prompt: str, user_prompt: str, retries: int = 5) -> dict:
    """
    Sends a request with response_mime_type="application/json" to guarantee
    structurally valid JSON output. The system prompt must instruct the model
    to return a JSON object.
    Returns the parsed dict.
    """
    client = get_client()
    
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=TEMPERATURE,
                    response_mime_type="application/json"
                )
            )
            
            raw = response.text.strip()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # Fences might be present even with mime_type set depending on the prompt
                if raw.startswith("```json"):
                    raw = raw[7:]
                if raw.startswith("```"):
                    raw = raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                return json.loads(raw.strip())
        except Exception as e:
            if attempt < retries - 1:
                wait_time = 60 * (attempt + 1)
                print(f"Gemini API error: {e}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise
