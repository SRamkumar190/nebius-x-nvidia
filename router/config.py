"""Router settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

DEFAULT_BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/"

# Ids as GET /v1/models lists them. They are case sensitive.
DEFAULT_MODELS = {
    "nano": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "super": "nvidia/nemotron-3-super-120b-a12b",
    "ultra": "nvidia/Nemotron-3-Ultra-550b-a55b",
}


@dataclass(frozen=True)
class RouterSettings:
    base_url: str
    api_key: str
    db_path: Path
    timeout_s: float
    models: dict = field(default_factory=dict)


def load_settings(env: Mapping[str, str] = os.environ) -> RouterSettings:
    data_dir = Path(env.get("KEEPER_DATA_DIR", "./data"))
    models = {
        tier: env.get(f"KEEPER_MODEL_{tier.upper()}", default).strip() or default
        for tier, default in DEFAULT_MODELS.items()
    }
    return RouterSettings(
        base_url=env.get("TOKENFACTORY_BASE_URL", DEFAULT_BASE_URL),
        api_key=env.get("TOKENFACTORY_API_KEY", "").strip(),
        db_path=Path(env.get("KEEPER_ROUTER_DB", str(data_dir / "router.db"))),
        timeout_s=float(env.get("KEEPER_TIMEOUT_S", "120")),
        models=models,
    )
