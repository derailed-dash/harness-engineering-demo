"""Token usage and cost estimator for Gemini model runs.

Provides accurate tracking of prompt tokens, candidate tokens, and total costs in US Dollars.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TokenMetrics:
    """Holds accumulated token counters and pricing calculations."""
    prompt_tokens: int = 0
    candidate_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    history: list[dict[str, Any]] = field(default_factory=list)

    # Gemini 3.8 Flash pricing estimates ($ per 1M tokens)
    INPUT_RATE_PER_MILLION: float = 0.15
    OUTPUT_RATE_PER_MILLION: float = 0.60

    def add_usage(self, prompt: int, candidate: int, label: str = "") -> None:
        """Accumulate token counts and update dollar cost."""
        self.prompt_tokens += prompt
        self.candidate_tokens += candidate
        self.total_tokens = self.prompt_tokens + self.candidate_tokens
        
        cost_prompt = (prompt / 1_000_000) * self.INPUT_RATE_PER_MILLION
        cost_candidate = (candidate / 1_000_000) * self.OUTPUT_RATE_PER_MILLION
        turn_cost = cost_prompt + cost_candidate
        self.estimated_cost_usd += turn_cost

        self.history.append({
            "label": label,
            "prompt_tokens": prompt,
            "candidate_tokens": candidate,
            "turn_tokens": prompt + candidate,
            "turn_cost_usd": turn_cost,
            "cumulative_tokens": self.total_tokens,
            "cumulative_cost_usd": self.estimated_cost_usd,
        })

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for UI consumption."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "candidate_tokens": self.candidate_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "formatted_cost": f"${self.estimated_cost_usd:.4f}",
            "turn_count": len(self.history),
        }
