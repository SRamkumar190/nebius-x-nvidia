"""OpenAI-compatible client pointed at Token Factory."""
from openai import OpenAI

from .config import Settings


def make_client(settings: Settings) -> OpenAI:
    # max_retries=0 so latency numbers reflect one request, not hidden retries.
    return OpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout=settings.timeout_s,
        max_retries=0,
    )
