import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

class GeminiClient:
    def __init__(self):
        # Initialize Google GenAI client
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in environment variables")
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.0-flash"

    def generate_content(self, system_prompt: str, user_prompt: str, max_tokens: int = 2000, temperature: float = 0.4) -> str:
        """
        Generates content using Gemini 2.0 Flash model.
        """
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=config
        )
        return response.text
