"""route(): send a chat request to the right Nemotron model and log it."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from openai import OpenAI

from . import calllog
from .config import RouterSettings, load_settings
from .pricing import estimate_cost
from .routes import tier_for

log = logging.getLogger(__name__)

_clients: dict[tuple, OpenAI] = {}


def _client_for(settings: RouterSettings) -> OpenAI:
    if not settings.api_key:
        raise RuntimeError("TOKENFACTORY_API_KEY is not set")
    key = (settings.base_url, settings.api_key, settings.timeout_s)
    if key not in _clients:
        # max_retries=0 so each logged latency is one request, not hidden retries.
        _clients[key] = OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=settings.timeout_s,
            max_retries=0,
        )
    return _clients[key]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _safe_record(settings: RouterSettings, entry: calllog.CallRecord) -> None:
    # A broken log file must never take down the call it is logging.
    try:
        calllog.record(settings.db_path, entry)
    except Exception:
        log.exception("could not write router call log to %s", settings.db_path)


def route(task_type, messages, tools=None, *, settings=None, client=None, **params):
    """Send messages to the model for task_type and return the chat completion.

    Extra keyword arguments (max_tokens, temperature, tool_choice...) go
    straight to chat.completions.create.
    """
    settings = settings or load_settings()
    model = settings.models[tier_for(task_type)]
    client = client or _client_for(settings)

    request = {"model": model, "messages": messages, **params}
    if tools:
        request["tools"] = tools

    ts = _now()
    start = time.perf_counter()
    try:
        response = client.chat.completions.create(**request)
    except Exception as exc:
        _safe_record(settings, calllog.CallRecord(
            ts=ts, task_type=task_type, model=model, served_model=None,
            prompt_tokens=None, completion_tokens=None,
            latency_ms=round((time.perf_counter() - start) * 1000),
            cost_usd=None, status="error", error=f"{type(exc).__name__}: {exc}"[:500],
        ))
        raise
    latency_ms = round((time.perf_counter() - start) * 1000)

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    served_model = getattr(response, "model", None)
    if served_model and served_model.lower() != model.lower():
        log.warning("asked for %s but %s answered", model, served_model)

    # Price what actually answered; fall back to the requested model if the
    # served name isn't in the price table.
    cost = estimate_cost(served_model, prompt_tokens, completion_tokens) if served_model else None
    if cost is None:
        cost = estimate_cost(model, prompt_tokens, completion_tokens)

    _safe_record(settings, calllog.CallRecord(
        ts=ts, task_type=task_type, model=model, served_model=served_model,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        latency_ms=latency_ms, cost_usd=cost, status="ok",
    ))
    return response
