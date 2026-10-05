---
name: gemini-api-dev
description: Best practices for integrating the Google GenAI SDK (google-genai), structured outputs, and grounding.
---

# Gemini API Development Skill

## Overview

Guidance on using the modern Google GenAI SDK (`google-genai`) for structured output generation, dynamic reasoning, and grounded trivia or content creation.

## Core Practices

1. **Modern SDK Usage**:
   - Always import and use `from google import genai` and `from google.genai import types`.
   - Initialise the client via `client = genai.Client()`.
   - Never use the deprecated `google-generativeai` package.

2. **Model Selection**:
   - Default to current generally available (GA) models (e.g. `gemini-2.5-flash` or `gemini-2.5-pro`).
   - Never downgrade models or introduce obsolete versions.

3. **Structured Outputs**:
   - When generating complex structured domain data (such as questions, options, answers, or state evaluations), leverage Pydantic models as `response_schema` within `types.GenerateContentConfig`.
   - Set `response_mime_type="application/json"` to ensure machine-parsable responses.

4. **Domain Grounding & Fallbacks**:
   - Provide explicit, bounded prompts and system instructions referencing canonical sources or domain requirements.
   - Implement graceful error handling and deterministic local fallbacks in case of quota exhaustion, network disruption, or malformed API responses.
