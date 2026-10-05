---
name: api-and-interface-design
description: Guides stable API and interface design. Use when designing APIs, module boundaries, Pydantic schemas, or public interfaces.
---

# API and Interface Design Skill

## Overview

Design clean, robust, and strongly typed interfaces. Well-designed APIs establish unambiguous boundaries between layers (such as frontend clients, FastAPI backend endpoints, and domain logic), reject invalid states deterministically, and simplify testing.

## Key Principles

1. **Explicit Request & Response Schemas**:
   - Always define explicit Pydantic models for incoming payload validation and outgoing responses.
   - Forbid arbitrary dictionary parsing or unvalidated JSON objects in route handlers.

2. **Strict Validation & Rejection Contracts**:
   - Reject malformed requests, missing fields, out-of-range values, or unparsable bodies with `HTTP 400 Bad Request` or `HTTP 422 Unprocessable Entity`.
   - Never let unvalidated client input crash the server with an unhandled `500 Internal Server Error`.


3. **Domain Layer Independence**:
   - Keep API routes and route handlers thin: handle request decoding, validation, domain service delegation, and HTTP status code mapping.
   - Core domain business logic and state machines should reside in dedicated modules independent of HTTP transport details.

4. **RESTful Resource Consistency**:
   - Use standard HTTP methods (`GET` for retrieval, `POST` for actions or state transitions, `DELETE` for removals).
   - Ensure predictable, structured error response envelopes (e.g. `{"detail": "Error description"}`).
