"""Google GenAI Client Factory.

Provides a unified client instantiator that prioritises Google Cloud Application
Default Credentials (ADC) with Vertex AI, falling back to GEMINI_API_KEY when ADC
is unavailable.
"""

import os
from typing import Tuple

import google.auth
from google import genai

from app.config import GEMINI_API_KEY


def get_genai_client() -> Tuple[genai.Client | None, str]:
    """Retrieve an authenticated Google Gen AI client.
    
    Priority:
    1. Google Cloud Application Default Credentials (ADC) via Vertex AI ('global' location).
    2. GEMINI_API_KEY / GOOGLE_API_KEY via Gemini Developer API.
    3. None (triggers offline / synthetic fallback).
    
    Returns:
        tuple[Client | None, str]: (Client instance, Auth Mode Description)
    """
    # 1. Attempt Application Default Credentials (ADC)
    try:
        credentials, project_id = google.auth.default()
        proj = project_id or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
        if proj:
            client = genai.Client(
                vertexai=True,
                project=proj,
                location=location,
                credentials=credentials,
            )
            return client, f"ADC ({proj})"
    except Exception:
        pass

    # 2. Fall back to GEMINI_API_KEY
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            return client, "GEMINI_API_KEY"
        except Exception:
            pass

    return None, "NONE"
