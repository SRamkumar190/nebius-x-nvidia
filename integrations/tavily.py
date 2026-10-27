"""Bounded Tavily Search API adapter."""
from __future__ import annotations

from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from keeper_core.adapters import (AdapterError, AuthenticationError, InvalidProviderResponse,
                                  ProviderUnavailable, RateLimited, SearchHit)

from .http_json import HttpFailure, post_json


class LiveTavily:
    def __init__(
        self, api_key: str, *, timeout: float = 8.0,
        transport: Callable[[str, dict, dict[str, str], float], dict] = post_json,
    ):
        if not api_key.strip() or timeout <= 0:
            raise ValueError("API key and positive timeout are required")
        self._key = api_key.strip()
        self._timeout = timeout
        self._transport = transport

    @classmethod
    def from_key_file(cls, key_file: Path, *, timeout: float = 8.0) -> "LiveTavily":
        return cls(Path(key_file).read_text(encoding="utf-8"), timeout=timeout)

    def search(self, query: str, *, limit: int = 5) -> tuple[SearchHit, ...]:
        if not query.strip() or not 1 <= limit <= 20:
            raise ValueError("query and limit between 1 and 20 are required")
        payload = {"query": query, "search_depth": "basic", "max_results": limit,
                   "include_answer": False, "include_raw_content": False,
                   "include_images": False}
        try:
            response = self._transport("https://api.tavily.com/search", payload,
                                       {"Authorization": f"Bearer {self._key}"}, self._timeout)
        except HttpFailure as exc:
            if exc.status in (401, 403):
                raise AuthenticationError("Tavily authorization failed") from None
            if exc.status == 429:
                raise RateLimited("Tavily rate limit reached", exc.retry_after) from None
            if exc.status >= 500:
                raise ProviderUnavailable("Tavily is unavailable") from None
            raise AdapterError(f"Tavily request failed (HTTP {exc.status})") from None
        except (TimeoutError, OSError) as exc:
            raise ProviderUnavailable("Tavily request timed out or transport failed") from exc
        if not isinstance(response, dict) or not isinstance(response.get("results"), list):
            raise InvalidProviderResponse("Tavily returned no valid results list")
        hits = []
        for item in response["results"][:limit]:
            if not isinstance(item, dict):
                raise InvalidProviderResponse("Tavily returned an invalid result")
            url, title, content = item.get("url"), item.get("title"), item.get("content")
            if not all(isinstance(value, str) for value in (url, title, content)):
                raise InvalidProviderResponse("Tavily result lacks URL, title, or content")
            try:
                parsed = urlsplit(url)
            except ValueError as exc:
                raise InvalidProviderResponse("Tavily result has an invalid URL") from exc
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise InvalidProviderResponse("Tavily result has an invalid URL")
            hits.append(SearchHit(url=url, title=title, snippet=content[:1000], source=parsed.hostname))
        return tuple(hits)
