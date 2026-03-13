import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()


class GroqClient:
    """
    Groq API client wrapper for Phase 5 note generation.
    Uses llama-3.3-70b-versatile model via the Groq SDK.
    """

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in environment variables")
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"

    def generate_content(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.4,
    ) -> str:
        """
        Generates content using Groq LLaMA 3.3 70B Versatile model.

        Args:
            system_prompt: The system instruction for the LLM.
            user_prompt: The user-facing prompt with review data.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature (0.0–1.0).

        Returns:
            The generated text string.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content
