"""Check requested model ids against the live /v1/models list."""
import difflib
from dataclasses import dataclass

from openai import OpenAI


@dataclass
class Resolution:
    requested: str
    resolved: str | None
    note: str


def list_model_ids(client: OpenAI) -> list[str]:
    return sorted(m.id for m in client.models.list())


def resolve(requested: str, available: list[str]) -> Resolution:
    if requested in available:
        return Resolution(requested, requested, "ok")
    by_lower = {a.lower(): a for a in available}
    if requested.lower() in by_lower:
        actual = by_lower[requested.lower()]
        return Resolution(requested, actual, f"case differs, using {actual}")
    close = difflib.get_close_matches(requested.lower(), list(by_lower), n=3, cutoff=0.6)
    hint = ", ".join(by_lower[c] for c in close) or "none"
    return Resolution(requested, None, f"not in catalog (closest: {hint})")


def nemotron_ids(available: list[str]) -> list[str]:
    return [a for a in available if "nemotron" in a.lower()]
