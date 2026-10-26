"""Token prices for cost-per-document tracking.

USD per million tokens. These change, so check your provider's pricing page; DOCFLOW_PRICE_IN and
DOCFLOW_PRICE_OUT override them. A local model costs nothing in API fees, but it still uses your machine.
"""
from __future__ import annotations

import os

# (input, output) USD per 1M tokens. Approximate; edit to match current pricing.
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    if os.getenv("DOCFLOW_PRICE_IN") and os.getenv("DOCFLOW_PRICE_OUT"):
        p_in, p_out = float(os.environ["DOCFLOW_PRICE_IN"]), float(os.environ["DOCFLOW_PRICE_OUT"])
    else:
        p_in, p_out = PRICES.get(model, (0.0, 0.0))  # local models (Ollama) cost nothing
    return round(input_tokens / 1e6 * p_in + output_tokens / 1e6 * p_out, 6)
