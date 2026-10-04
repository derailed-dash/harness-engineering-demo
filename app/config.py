"""Configuration settings for Harness Demo Workbench.

Reads environment variables from .env with fallback defaults for local and Cloud Run execution.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Base workspace path
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
load_dotenv(BASE_DIR / ".env")

# Model configuration
DEFAULT_MODEL = "gemini-3.8-flash"
MODEL_NAME = os.getenv("MODEL_NAME", DEFAULT_MODEL)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "32768"))

# Server configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# Execution thresholds
MAX_ITERATIONS = int(os.getenv("DEFAULT_MAX_ITERATIONS", "5"))
PLATEAU_LIMIT = int(os.getenv("DEFAULT_PLATEAU_LIMIT", "3"))

# Workspaces directory
WORKSPACES_DIR = BASE_DIR / "workspaces"
UNHARNESSED_DIR = WORKSPACES_DIR / "unharnessed"
HARNESSED_DIR = WORKSPACES_DIR / "harnessed"
SPECS_DIR = BASE_DIR / "specs"
COSMIC_CONQUEST_SPEC_PATH = SPECS_DIR / "cosmic_conquest_spec.md"
HARNESS_CONTEXT_PATH = SPECS_DIR / "harness_context.md"
GOLDEN_TESTS_DIR = BASE_DIR / "golden_tests"
REPLAY_DATA_PATH = BASE_DIR / "app" / "replay" / "replay_data.json"
REPLAY_SNAPSHOTS_DIR = BASE_DIR / "snapshots"


def load_cosmic_conquest_spec() -> str:
    """Load canonical goal specification from specs/cosmic_conquest_spec.md."""
    if COSMIC_CONQUEST_SPEC_PATH.is_file():
        return COSMIC_CONQUEST_SPEC_PATH.read_text(encoding="utf-8")
    return ""


def load_harness_context() -> str:
    """Load harness context and engineering guardrails from specs/harness_context.md."""
    if HARNESS_CONTEXT_PATH.is_file():
        return HARNESS_CONTEXT_PATH.read_text(encoding="utf-8")
    return ""

