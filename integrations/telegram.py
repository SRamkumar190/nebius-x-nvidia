"""Telegram Bot API sendMessage with durable delivery identity and logging."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from keeper_core.adapters import (AdapterError, AuthenticationError, IdempotencyConflict,
                                  InvalidProviderResponse, ProviderUnavailable, RateLimited)
from keeper_core.time import to_storage

from .http_json import HttpFailure, post_json


def _record_id(key: str, recipient: str, message: str) -> str:
    payload = json.dumps([key, recipient, message], ensure_ascii=False, separators=(",", ":"))
    return "notification:telegram:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _retry_delay(body: dict, header_delay: float | None) -> float:
    parameter = body.get("parameters", {})
    value = parameter.get("retry_after") if isinstance(parameter, dict) else None
    try:
        return min(max(float(value), 0), 60) if value is not None else (header_delay or 1.0)
    except (ValueError, TypeError):
        return header_delay or 1.0


class LiveTelegram:
    def __init__(
        self, bot_token: str, db_path: Path, *,
        transport: Callable[[str, dict, dict[str, str], float], dict] = post_json,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        timeout: float = 10.0, max_attempts: int = 3,
    ):
        if not bot_token or timeout <= 0 or max_attempts < 1:
            raise ValueError("bot token, positive timeout and attempts are required")
        self._token = bot_token.strip()
        self._db_path = Path(db_path)
        self._transport = transport
        self._sleep = sleep
        self._now = now
        self._timeout = timeout
        self._max_attempts = max_attempts

    @classmethod
    def from_token_file(cls, token_file: Path, db_path: Path) -> "LiveTelegram":
        return cls(Path(token_file).read_text(encoding="utf-8").strip(), db_path)

    def _claim(self, key: str, recipient: str, message: str) -> tuple[str, str | None]:
        record_id = _record_id(key, recipient, message)
        with sqlite3.connect(self._db_path, timeout=10) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT id, status, provider_message_id FROM notification_records WHERE idempotency_key = ?",
                               (key,)).fetchone()
            if row is not None:
                if row[0] != record_id:
                    raise IdempotencyConflict("Telegram delivery key reused for different content")
                if row[1] == "delivered":
                    if not row[2]:
                        raise InvalidProviderResponse("delivered notification has no message ID")
                    return record_id, row[2]
                if row[1] == "pending":
                    raise ProviderUnavailable("Telegram delivery is pending or uncertain; reconcile before retry")
                conn.execute("UPDATE notification_records SET status = 'pending', error = NULL WHERE id = ?",
                             (record_id,))
            else:
                conn.execute("""INSERT INTO notification_records
                    (id, channel, recipient_reference, purpose, idempotency_key, status, created_at)
                    VALUES (?, 'telegram', ?, 'sendMessage', ?, 'pending', ?)""",
                             (record_id, recipient, key, to_storage(self._now())))
        return record_id, None

    def _log(self, record_id: str, status: str, *, message_id: str | None = None,
             error: str | None = None) -> None:
        with sqlite3.connect(self._db_path, timeout=10) as conn:
            conn.execute("""UPDATE notification_records SET status = ?, provider_message_id = ?,
                delivered_at = ?, error = ? WHERE id = ?""",
                (status, message_id, to_storage(self._now()) if status == "delivered" else None,
                 error, record_id))

    def send_message(self, recipient_reference: str, text: str, *, idempotency_key: str) -> str:
        if not recipient_reference.strip() or not text.strip() or not idempotency_key:
            raise ValueError("recipient, text, and idempotency key are required")
        if len(text) > 4096:
            raise ValueError("Telegram text exceeds 4096 characters")
        record_id, delivered_id = self._claim(idempotency_key, recipient_reference, text)
        if delivered_id is not None:
            return delivered_id
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {"chat_id": recipient_reference, "text": text, "disable_notification": False}
        for attempt in range(self._max_attempts):
            try:
                response = self._transport(url, payload, {}, self._timeout)
            except HttpFailure as exc:
                response = {**exc.body, "ok": False, "error_code": exc.status}
                header_delay = exc.retry_after
            except InvalidProviderResponse:
                self._log(record_id, "pending", error="delivery outcome unknown after invalid response")
                raise
            except (ProviderUnavailable, TimeoutError, OSError) as exc:
                self._log(record_id, "pending", error="delivery outcome unknown after transport failure")
                raise ProviderUnavailable("Telegram delivery outcome is unknown") from exc
            else:
                header_delay = None
            if not isinstance(response, dict):
                self._log(record_id, "pending", error="delivery outcome unknown after invalid response")
                raise InvalidProviderResponse("Telegram response is not an object")
            if response.get("ok") is True:
                result = response.get("result")
                message_id = result.get("message_id") if isinstance(result, dict) else None
                if not isinstance(message_id, int) or isinstance(message_id, bool):
                    self._log(record_id, "pending", error="delivery outcome unknown after invalid response")
                    raise InvalidProviderResponse("Telegram success has no message ID")
                self._log(record_id, "delivered", message_id=str(message_id))
                return str(message_id)
            code = response.get("error_code")
            if code == 429:
                delay = _retry_delay(response, header_delay)
                if attempt + 1 < self._max_attempts:
                    self._sleep(delay)
                    continue
                self._log(record_id, "failed", error="Telegram rate limited delivery")
                raise RateLimited("Telegram rate limit reached", delay)
            if code in (401, 403):
                self._log(record_id, "failed", error=f"Telegram HTTP {code}")
                raise AuthenticationError("Telegram bot is unauthorized for this chat")
            if code == 400:
                self._log(record_id, "failed", error="Telegram rejected message or chat")
                raise AdapterError("Telegram rejected message or chat")
            self._log(record_id, "pending", error="delivery outcome unknown after provider error")
            raise ProviderUnavailable("Telegram delivery outcome is unknown")
        raise AssertionError("unreachable retry state")
