import os
from functools import lru_cache

from groq import Groq


class AIServiceConfigurationError(RuntimeError):
    """Raised when the server has no usable AI provider configuration."""


@lru_cache(maxsize=1)
def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise AIServiceConfigurationError("GROQ_API_KEY is not configured")
    return Groq(api_key=api_key)


def get_ai_model() -> str:
    return os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant"


def public_ai_error(exc: Exception) -> str:
    """Return actionable provider guidance without exposing credentials or internals."""
    if isinstance(exc, AIServiceConfigurationError):
        return "AI service is not configured. Add GROQ_API_KEY to the backend environment and redeploy."

    status_code = getattr(exc, "status_code", None)
    message = str(exc).lower()

    if status_code in (401, 403) or "api key" in message or "authentication" in message:
        return "AI service authentication failed. Replace GROQ_API_KEY in Vercel and redeploy the backend."
    if status_code == 429 or "rate limit" in message or "quota" in message:
        return "AI service quota or rate limit was reached. Check the Groq console and try again later."
    if status_code == 404 or ("model" in message and ("not found" in message or "decommission" in message)):
        return "The configured AI model is unavailable. Check the backend model setting and Groq model availability."

    return "AI provider request failed. Check the backend logs in Vercel for the provider error."
