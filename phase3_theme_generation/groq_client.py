"""Groq API client wrapper for Phase 3 — LLM Theme Generation."""

import os
import json
import time
import logging
from groq import Groq
from dotenv import load_dotenv

# Load from the project root .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

logger = logging.getLogger(__name__)

MODEL = "llama-3.3-70b-versatile"
TEMPERATURE = 0.3
MAX_TOKENS = 2000


def get_client() -> Groq:
    """Initialises and returns a Groq client."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not found. Ensure it is set in the .env file at the project root."
        )
    return Groq(api_key=api_key)


def call_groq_json_mode(system_prompt: str, user_prompt: str, retries: int = 5) -> dict:
    """
    Sends a chat completion request to Groq (LLaMA 3.3 70B Versatile) with
    response_format={"type": "json_object"} to guarantee valid JSON output.

    Returns the parsed dict.
    """
    client = get_client()

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content.strip()

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # Strip markdown fences if present
                if raw.startswith("```json"):
                    raw = raw[7:]
                if raw.startswith("```"):
                    raw = raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                return json.loads(raw.strip())

        except Exception as e:
            if attempt < retries - 1:
                wait_time = 10 * (attempt + 1)
                logger.warning(f"Groq API error (attempt {attempt + 1}/{retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Groq API failed after {retries} attempts: {e}")
                raise
