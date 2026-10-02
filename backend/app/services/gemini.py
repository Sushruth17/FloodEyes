"""Single place that constructs the Gemini client (AI Studio locally, Vertex AI on Cloud Run)."""

from functools import lru_cache

from google import genai

from app.config import get_settings


@lru_cache
def get_client() -> genai.Client:
    s = get_settings()
    if s.gemini_backend == "vertex":
        return genai.Client(
            vertexai=True, project=s.google_cloud_project, location=s.google_cloud_location
        )
    return genai.Client(api_key=s.gemini_api_key)
