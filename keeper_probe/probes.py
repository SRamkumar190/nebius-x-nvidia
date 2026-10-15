"""One plain chat call and one tool-calling call per model."""
import json
import time
from dataclasses import dataclass, field

from openai import OpenAI

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
}

PLAIN_PROMPT = "Reply with one short sentence: what is Nebius Token Factory?"
TOOL_PROMPT = "What is the weather in Paris right now? Use the get_weather tool."

# Markers some chat templates emit when the server's tool parser is off,
# so the call lands in content as plain text instead of tool_calls.
TEXT_TOOL_MARKERS = ("<tool_call>", "<toolcall>", '"name": "get_weather"', "get_weather(")


@dataclass
class ProbeResult:
    kind: str
    ok: bool = False
    latency_s: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None
    detail: str = ""
    error: str | None = None
    extra: dict = field(default_factory=dict)


def _timed_call(client: OpenAI, **kwargs):
    start = time.perf_counter()
    resp = client.chat.completions.create(**kwargs)
    return resp, time.perf_counter() - start


def _fill_usage(result: ProbeResult, resp) -> None:
    usage = getattr(resp, "usage", None)
    if usage is not None:
        result.prompt_tokens = usage.prompt_tokens
        result.completion_tokens = usage.completion_tokens
    result.finish_reason = resp.choices[0].finish_reason


def plain_chat(client: OpenAI, model: str, max_tokens: int) -> ProbeResult:
    result = ProbeResult(kind="plain")
    try:
        resp, result.latency_s = _timed_call(
            client,
            model=model,
            messages=[{"role": "user", "content": PLAIN_PROMPT}],
            max_tokens=max_tokens,
        )
    except Exception as exc:  # report every API failure, keep probing other models
        result.error = f"{type(exc).__name__}: {exc}"
        return result
    _fill_usage(result, resp)
    text = (resp.choices[0].message.content or "").strip()
    result.ok = bool(text)
    result.detail = text[:120].replace("\n", " ") if text else "empty content"
    return result


def tool_call(client: OpenAI, model: str, max_tokens: int) -> ProbeResult:
    result = ProbeResult(kind="tool")
    try:
        resp, result.latency_s = _timed_call(
            client,
            model=model,
            messages=[{"role": "user", "content": TOOL_PROMPT}],
            tools=[WEATHER_TOOL],
            tool_choice="auto",
            max_tokens=max_tokens,
        )
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        return result
    _fill_usage(result, resp)
    msg = resp.choices[0].message
    calls = msg.tool_calls or []
    if calls:
        call = calls[0]
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            result.detail = f"tool_call with unparseable args: {call.function.arguments!r}"
            return result
        result.ok = call.function.name == "get_weather" and "city" in args
        result.detail = f"{call.function.name}({json.dumps(args)})"
        result.extra["tool_calls"] = len(calls)
        return result
    content = msg.content or ""
    if any(marker in content for marker in TEXT_TOOL_MARKERS):
        result.detail = "tool call came back as TEXT in content, not tool_calls (parser off?)"
    else:
        result.detail = "no tool_call; content: " + (content[:100].replace("\n", " ") or "empty")
    return result
