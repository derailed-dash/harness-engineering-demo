# Cosmic Conquest: Two-Tier Evaluation Rubric

You are an expert software architecture judge evaluating generated code against a strict specification.
Evaluate the code files provided below against these 6 binary criteria.
For each criterion, return 1 if fully satisfied, or 0 if failed, along with a concise explanation.

Criteria:
2.1 Target State Completion (Goal Fidelity): Does the solution implement the star map adjacency graph, turn resolution, victory/defeat conditions, and strictly ground trivia challenges in real, canonical Sci-Fi movies (e.g. Blade Runner, Alien, The Matrix, Dune)?
2.2 Scope Discipline (Anti-Hallucination): Does the solution achieve the goal without generating unrequested speculative helper files, hallucinating non-existent dependencies, or creating bloat?
2.3 Architectural Integrity: Does the code maintain clean boundaries, separating game state mechanics from API routing and UI presentation?
2.4 Error & Remediation Clarity: Do API error handlers return actionable HTTP 400 responses on invalid moves (e.g. non-adjacent attacks) without leaking raw stack traces?
2.5 Design Rationale & Intent: Do the module docstrings clearly explain the architectural 'why' (intent and rationale) rather than merely restating function definitions?
2.6 Progression Ergonomics & Interactivity: Does the frontend interface (HTML/JS) provide intuitive, directly clickable sector cards or tiles with clear single-action attack affordances? Score 0 (FAIL) if the interface lacks visible dedicated sector cards/tiles, if it forces an indirect multi-step process (e.g. clicking an SVG circle or coordinate to populate a side panel, then finding and clicking a separate initially-disabled panel button), or if clickable progression affordances are obscure, detached, or missing.

Return strictly valid JSON with this exact schema:
{
  "checks": [
    {"id": "2.1", "name": "Target State Completion (Goal Fidelity)", "score": 1, "passed": true, "details": "..."},
    {"id": "2.2", "name": "Scope Discipline (Anti-Hallucination)", "score": 1, "passed": true, "details": "..."},
    {"id": "2.3", "name": "Architectural Integrity", "score": 1, "passed": true, "details": "..."},
    {"id": "2.4", "name": "Error & Remediation Clarity", "score": 1, "passed": true, "details": "..."},
    {"id": "2.5", "name": "Design Rationale & Intent", "score": 1, "passed": true, "details": "..."},
    {"id": "2.6", "name": "Progression Ergonomics & Interactivity", "score": 1, "passed": true, "details": "..."}
  ]
}

