"""Groq client, call limits and structured output (docs/plan.md, "Settings", M3).

The writer, reviewer and test-case generator each make one call through `complete()`. Each
call asks for a strict JSON schema, so the answer is parsed straight into a Pydantic model.

Failures fall into these kinds, each with its own exception:
- `OutputError`: the model answered, but the answer is unusable (wrong shape, cut off,
  declined). The reasons say why.
- `LimitReached`: the per-session or daily call limit is used up. No call was made.
- `LlmUnavailable`: no API key, or the API could not be reached or refused the request.
  `RateLimited` is the free-tier case of this.

Tests never reach the network: `FakeTransport` answers with hand-written responses that are
marked as fake (see examples/demo/README.md), and `ReplayTransport` answers with recordings.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2
from pydantic import BaseModel, ValidationError

from reqpilot.config import REPO_ROOT, Config, get_config

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_TIMEOUT_S = 120.0
API_KEY_NAME = "GROQ_API_KEY"
FAKE_LABEL = "FAKE: hand-written demo data, not real model output"


class LlmError(Exception):
    """Base class; `str(e)` is a message for the user."""


class OutputError(LlmError):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("The model's answer could not be used: " + "; ".join(reasons))


class LimitReached(LlmError):
    pass


class LlmUnavailable(LlmError):
    pass


class RateLimited(LlmUnavailable):
    def __init__(self, message: str, wait_s: float | None = None, daily: bool = False):
        super().__init__(message)
        self.wait_s = wait_s
        self.daily = daily


# --------------------------------------------------------------------------- limits


@dataclass
class LlmSession:
    """Per-user state; the app keeps one per browser session."""

    calls: int = 0


class CallLimiter:
    """Per-session and daily call limits. The daily count lives in a JSON file keyed by the
    UTC date; it is not shared between servers."""

    _lock = threading.Lock()

    def __init__(self, cfg: Config | None = None, counter_file: Path | None = None, now=None):
        cfg = cfg or get_config()
        self.per_session = cfg.llm.calls_per_session
        self.per_day = cfg.llm.calls_per_day
        path = counter_file or cfg.llm.counter_file
        self.path = path if path.is_absolute() else REPO_ROOT / path
        self._now = now or (lambda: datetime.now(UTC))

    def _today(self) -> str:
        return self._now().date().isoformat()

    def used_today(self) -> int:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return 0
        return int(data.get("calls", 0)) if data.get("date") == self._today() else 0

    def left(self, session: LlmSession) -> tuple[int, int]:
        """Calls left in this session and today."""
        return (
            max(0, self.per_session - session.calls),
            max(0, self.per_day - self.used_today()),
        )

    def reserve(self, session: LlmSession, calls: int = 1) -> None:
        """Count `calls` calls before they are made, or raise LimitReached (counting none)."""
        if session.calls + calls > self.per_session:
            raise LimitReached(
                f"This session has used its {self.per_session} AI calls. Reload the page for a "
                "new session, or work on with what you have."
            )
        with self._lock:
            used = self.used_today()
            if used + calls > self.per_day:
                raise LimitReached(
                    f"The daily limit of {self.per_day} AI calls is used up. Try again tomorrow, "
                    "or open a bundled example."
                )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"date": self._today(), "calls": used + calls}), "utf-8")
            tmp.replace(self.path)
        session.calls += calls


# --------------------------------------------------------------------------- client


def api_key() -> str | None:
    """Streamlit secrets first (deployment), then the environment and .env (local)."""
    try:
        import streamlit as st

        key = st.secrets.get(API_KEY_NAME)
        if key:
            return str(key)
    except Exception:  # no secrets file, or not running in an app
        pass
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env", override=False)
    return os.environ.get(API_KEY_NAME) or None


class GroqClient:
    """Minimal client for Groq's OpenAI-compatible chat completions endpoint."""

    def __init__(
        self, key: str, transport: httpx2.BaseTransport | None = None, max_retries: int = 2
    ):
        self.max_retries = max_retries
        self._http = httpx2.Client(
            base_url=GROQ_BASE_URL,
            headers={"Authorization": f"Bearer {key}"},
            timeout=GROQ_TIMEOUT_S,
            transport=transport,
        )

    def post_chat(self, body: dict[str, Any]) -> httpx2.Response:
        """POST with retries on transient server errors. A 429 is never retried: the wait
        can be long, so the user is told instead."""
        for attempt in range(self.max_retries + 1):
            last = attempt == self.max_retries
            try:
                response = self._http.post("/chat/completions", json=body)
            except httpx2.TransportError as e:
                if last:
                    raise LlmUnavailable("Could not reach Groq. Check the connection.") from e
            else:
                if response.status_code not in (500, 502, 503) or last:
                    return response
            time.sleep(0.5 * 2**attempt)
        raise AssertionError("unreachable")


def make_client(
    key: str | None = None, transport: httpx2.BaseTransport | None = None, max_retries: int = 2
) -> GroqClient:
    """A Groq client. `transport` replaces the network (tests, recording)."""
    key = key or api_key()
    if not key:
        raise LlmUnavailable(
            f"No API key: set {API_KEY_NAME} in .env or the Streamlit secrets. The bundled "
            "examples work without one."
        )
    return GroqClient(key, transport=transport, max_retries=max_retries)


# --------------------------------------------------------------------------- schema


# Keywords that strict structured-output modes reject or ignore. Pydantic still enforces
# them when the answer is parsed.
_UNSUPPORTED = {"title", "default", "minLength", "maxLength", "pattern", "minimum", "maximum",
                "exclusiveMinimum", "exclusiveMaximum", "minItems", "maxItems",
                "format"}  # fmt: skip


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema for strict mode: every property required, no extra properties."""

    def clean(node: Any) -> Any:
        if isinstance(node, dict):
            out = {k: clean(v) for k, v in node.items() if k not in _UNSUPPORTED}
            if out.get("type") == "object" and "properties" in out:
                out["required"] = list(out["properties"])
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [clean(v) for v in node]
        return node

    return clean(model.model_json_schema())


def chat_request(
    name: str, system: str, user: str, schema: type[BaseModel], cfg: Config
) -> dict[str, Any]:
    return {
        "model": cfg.llm.groq.model,
        "max_completion_tokens": cfg.llm.groq.max_tokens,
        "temperature": 0,
        "reasoning_effort": cfg.llm.groq.reasoning_effort,
        "include_reasoning": False,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": name, "strict": True, "schema": strict_schema(schema)},
        },
    }


def _wait_text(retry_after: str | None) -> str:
    try:
        seconds = float(retry_after)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "Try again in a minute."
    if seconds < 90:
        return f"Try again in about {max(1, round(seconds))} s."
    if seconds < 5400:
        return f"Try again in about {round(seconds / 60)} min."
    return f"Try again in about {round(seconds / 3600)} h."


def _groq_error(response: httpx2.Response) -> LlmError:
    status = response.status_code
    try:
        error = response.json().get("error") or {}
    except (ValueError, AttributeError):
        error = {}
    if status == 429:
        retry_after = response.headers.get("retry-after")
        try:
            wait_s = float(retry_after)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            wait_s = None
        daily = "per day" in str(error.get("message", "")).lower()
        return RateLimited(
            ("The free Groq tier's daily quota is used up. " if daily else "")
            + "The free Groq tier's rate limit is reached. "
            + _wait_text(retry_after)
            + " The bundled examples still work without an API call.",
            wait_s=wait_s,
            daily=daily,
        )
    if status == 401:
        return LlmUnavailable("The API key was rejected.")
    if status == 403:
        return LlmUnavailable("The API key may not use this model.")
    if status == 400 and error.get("code") == "json_validate_failed":
        return OutputError(["the answer did not match the required format"])
    if status in (400, 404, 413, 422):
        return LlmUnavailable(f"The API rejected the request ({status}).")
    return LlmUnavailable(f"The API returned an error ({status}). Try again.")


def _messages(e: ValidationError) -> list[str]:
    out = []
    for err in e.errors()[:5]:
        where = ".".join(str(p) for p in err["loc"]) or "answer"
        out.append(f"{where}: {err['msg']}")
    return out


def complete[T: BaseModel](
    client: GroqClient,
    *,
    name: str,
    system: str,
    user: str,
    schema: type[T],
    cfg: Config | None = None,
) -> T:
    """One structured-output call. No limits are checked here; see `CallLimiter`."""
    cfg = cfg or get_config()
    response = client.post_chat(chat_request(name, system, user, schema, cfg))
    if response.status_code != 200:
        raise _groq_error(response)
    try:
        choice = response.json()["choices"][0]
        message = choice["message"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise LlmUnavailable("The API returned an unreadable response. Try again.") from e
    if message.get("refusal"):
        raise OutputError(["the model declined to process this text"])
    if choice.get("finish_reason") == "length":
        raise OutputError(["the answer was cut off (max_tokens in config.yaml)"])
    content = message.get("content")
    if not content:
        raise OutputError(["the model gave no answer"])
    try:
        return schema.model_validate_json(content)
    except ValidationError as e:
        raise OutputError(_messages(e)) from e


# --------------------------------------------------------------------------- fakes


def load_fake(path: Path) -> dict[str, Any]:
    """A hand-written fake response. Refuses files that are not marked as fake."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("fake") is not True or data.get("label") != FAKE_LABEL:
        raise ValueError(f"{path} is not marked as fake data")
    return data


def groq_body(content: dict[str, Any] | str, finish_reason: str = "stop") -> dict[str, Any]:
    """A Groq chat completion body around `content`, as the API would return it."""
    text = content if isinstance(content, str) else json.dumps(content)
    return {
        "id": "fake",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": finish_reason,
            }
        ],
    }


class FakeTransport(httpx2.BaseTransport):
    """Answers requests in order with canned responses; keeps the requests it saw.

    Each response is either a fake file's dict (its "content" becomes the model answer, or
    its "http" gives a raw status, body and headers) or such a dict built in a test.
    """

    def __init__(self, *responses: dict[str, Any]):
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.read()))
        if not self.responses:
            raise AssertionError("FakeTransport has no response left")
        r = self.responses.pop(0)
        if "http" in r:
            http = r["http"]
            return httpx2.Response(http["status"], json=http["body"], headers=http.get("headers"))
        return httpx2.Response(200, json=groq_body(r["content"], r.get("finish_reason", "stop")))
