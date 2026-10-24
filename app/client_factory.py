"""Google GenAI and ADK Model Factory.

Provides a unified client and ADK model instantiator that prioritises Google Cloud
Application Default Credentials (ADC) with Vertex AI, falling back to GEMINI_API_KEY
when ADC is unavailable.
"""

import os
import ssl
from typing import Any

import certifi
import google.auth
import httpx
from google import genai
from google.adk.models import Gemini
from google.genai import types

from app.config import DEFAULT_MODEL, GEMINI_API_KEY, MODEL_NAME

_CACHED_ADC: tuple[Any, str | None] | None = None


def _get_cached_adc() -> tuple[Any, str | None]:
    """Load and cache Google Cloud ADC credentials so token refreshes persist across calls."""
    global _CACHED_ADC
    if _CACHED_ADC is None:
        credentials, project_id = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        _CACHED_ADC = (credentials, project_id)
    return _CACHED_ADC


def _build_ipv4_http_options(timeout_ms: int = 20_000) -> types.HttpOptions:
    """Bind httpx sync and async transports to IPv4 (0.0.0.0) with a bounded timeout and single-attempt fail-fast.

    In WSL2, dual-stack DNS resolution for `*.googleapis.com` often attempts an IPv6 (`AAAA`)
    connection first, which silently blackholes until the OS TCP SYN timeout (~130s).
    Binding `local_address="0.0.0.0"` forces immediate IPv4 routing, while passing explicit
    `certifi` SSL verification and `httpx.Timeout` on the transports prevents infinite hangs.
    """
    timeout_sec = max(timeout_ms / 1000.0, 5.0)
    httpx_timeout = httpx.Timeout(timeout_sec, connect=5.0)
    ssl_ctx = ssl.create_default_context(
        cafile=os.environ.get("SSL_CERT_FILE", certifi.where()),
        capath=os.environ.get("SSL_CERT_DIR"),
    )
    return types.HttpOptions(
        timeout=timeout_ms,
        retry_options=types.HttpRetryOptions(attempts=1),
        client_args={
            "transport": httpx.HTTPTransport(local_address="0.0.0.0", verify=ssl_ctx),
            "timeout": httpx_timeout,
        },
        async_client_args={
            "transport": httpx.AsyncHTTPTransport(local_address="0.0.0.0", verify=ssl_ctx),
            "timeout": httpx_timeout,
        },
    )


def get_genai_client() -> tuple[genai.Client | None, str]:
    """Retrieve an authenticated Google Gen AI client.

    Priority:
    1. Google Cloud Application Default Credentials (ADC) via Vertex AI ('global' location).
    2. GEMINI_API_KEY / GOOGLE_API_KEY via Gemini Developer API.
    3. None (triggers offline / deterministic fallback).

    Returns:
        tuple[genai.Client | None, str]: (Client instance, Auth Mode Description)
    """
    # 1. Attempt Application Default Credentials (ADC)
    try:
        credentials, project_id = _get_cached_adc()
        proj = project_id or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
        if proj:
            client = genai.Client(
                vertexai=True,
                project=proj,
                location=location,
                credentials=credentials,
                http_options=_build_ipv4_http_options(),
            )
            return client, f"ADC ({proj})"
    except Exception:
        pass

    # 2. Fall back to GEMINI_API_KEY
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            client = genai.Client(
                api_key=api_key,
                http_options=_build_ipv4_http_options(),
            )
            return client, "GEMINI_API_KEY"
        except Exception:
            pass

    return None, "NONE"


def get_adk_gemini_model(model_name: str | None = None) -> tuple[Gemini | None, str]:
    """Retrieve a configured Google ADK Gemini model bound to the active GenAI client.

    Args:
        model_name: Optional override for the Gemini model identifier.

    Returns:
        tuple[Gemini | None, str]: (ADK Gemini model wrapper or None if offline, Auth Mode Description)
    """
    client, auth_mode = get_genai_client()
    if client is None:
        return None, auth_mode
    resolved_model = model_name or MODEL_NAME or DEFAULT_MODEL
    # Inject the pre-authenticated genai.Client directly into ADK's Gemini wrapper so
    # Vertex AI ADC ('global' endpoint) and API-key fallback work without mutating os.environ.
    return Gemini(model=resolved_model, client=client), auth_mode
