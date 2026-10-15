"""Settings for the Token Factory probe, read from environment variables."""
import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/"

# Ultra id taken from the Nebius token-factory-cookbook (note the capital N).
# The catalog check in catalog.py fixes casing if Nebius lists it differently.
DEFAULT_MODELS = (
    "nvidia/nemotron-3-nano-30b-a3b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/Nemotron-3-Ultra-550b-a55b",
)


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    models: tuple
    timeout_s: float
    max_tokens: int


def load_settings() -> Settings:
    api_key = os.environ.get("TOKENFACTORY_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "TOKENFACTORY_API_KEY is not set. In PowerShell:\n"
            '  $env:TOKENFACTORY_API_KEY = "your-key"'
        )
    models_env = os.environ.get("KEEPER_MODELS", "").strip()
    models = tuple(m.strip() for m in models_env.split(",") if m.strip()) or DEFAULT_MODELS
    return Settings(
        api_key=api_key,
        base_url=os.environ.get("TOKENFACTORY_BASE_URL", DEFAULT_BASE_URL),
        models=models,
        timeout_s=float(os.environ.get("KEEPER_TIMEOUT_S", "120")),
        max_tokens=int(os.environ.get("KEEPER_MAX_TOKENS", "1024")),
    )
