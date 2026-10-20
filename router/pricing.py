"""Estimated cost from Nebius Token Factory list prices.

USD per 1M tokens (input, output), checked 2026-10-20 against the Token
Factory model catalog and pricing pages. Update here if Nebius changes them.
"""
from __future__ import annotations

PRICES_PER_M = {
    "nvidia/nvidia-nemotron-3-nano-30b-a3b": (0.06, 0.24),
    "nvidia/nemotron-3-super-120b-a12b": (0.30, 0.90),
    "nvidia/nemotron-3-ultra-550b-a55b": (1.00, 3.00),
}


def estimate_cost(model: str, prompt_tokens: int | None, completion_tokens: int | None) -> float | None:
    """Return the estimated USD cost, or None if the model or usage is unknown."""
    prices = PRICES_PER_M.get(model.lower())
    if prices is None or prompt_tokens is None or completion_tokens is None:
        return None
    price_in, price_out = prices
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000
