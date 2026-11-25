import json
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ConfigDict, Field

from reqpilot import llm
from reqpilot.config import get_config
from tests.fakes import all_fake_files, client, fake


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, description="a name")
    tags: list[str]


# --- fake data is marked ---------------------------------------------------------------


def test_every_fake_file_is_marked_fake():
    files = all_fake_files()
    assert len(files) >= 9 + 7
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["fake"] is True, path
        assert data["label"] == llm.FAKE_LABEL, path


def test_load_fake_refuses_unmarked_file(tmp_path):
    path = tmp_path / "x.json"
    path.write_text(json.dumps({"content": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="not marked as fake"):
        llm.load_fake(path)


# --- schema and request ----------------------------------------------------------------


def test_strict_schema_requires_all_and_forbids_extra():
    schema = llm.strict_schema(Answer)
    assert schema["required"] == ["name", "tags"]
    assert schema["additionalProperties"] is False
    assert "minLength" not in json.dumps(schema)
    assert schema["properties"]["name"]["description"] == "a name"


def test_request_uses_configured_model_and_strict_mode():
    c, transport = client({"content": {"name": "x", "tags": []}})
    llm.complete(c, name="t", system="sys", user="hello", schema=Answer)
    body = transport.requests[0]
    assert body["model"] == get_config().llm.groq.model
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
    ]
    assert body["temperature"] == 0


def test_answer_is_parsed():
    c, _ = client({"content": {"name": "x", "tags": ["a"]}})
    assert llm.complete(c, name="t", system="s", user="u", schema=Answer) == Answer(
        name="x", tags=["a"]
    )


# --- errors ----------------------------------------------------------------------------


def test_wrong_shape_is_output_error():
    c, _ = client({"content": {"name": "", "tags": []}})
    with pytest.raises(llm.OutputError, match="name"):
        llm.complete(c, name="t", system="s", user="u", schema=Answer)


def test_cut_off_answer_is_output_error():
    c, _ = client(fake("cut_off"))
    with pytest.raises(llm.OutputError, match="cut off"):
        llm.complete(c, name="t", system="s", user="u", schema=Answer)


def test_schema_failure_is_output_error():
    c, _ = client(fake("schema_failed"))
    with pytest.raises(llm.OutputError):
        llm.complete(c, name="t", system="s", user="u", schema=Answer)


def test_rate_limit_reports_wait():
    c, _ = client(fake("rate_limited"))
    with pytest.raises(llm.RateLimited) as e:
        llm.complete(c, name="t", system="s", user="u", schema=Answer)
    assert e.value.wait_s == 42 and not e.value.daily
    assert "42 s" in str(e.value)


def test_daily_quota_is_flagged():
    c, _ = client(fake("daily_quota"))
    with pytest.raises(llm.RateLimited) as e:
        llm.complete(c, name="t", system="s", user="u", schema=Answer)
    assert e.value.daily and "2 h" in str(e.value)


def test_wrong_key_is_unavailable():
    c, _ = client(fake("auth_error"))
    with pytest.raises(llm.LlmUnavailable, match="rejected"):
        llm.complete(c, name="t", system="s", user="u", schema=Answer)


def test_server_error_is_retried():
    transport = llm.FakeTransport(
        {"http": {"status": 503, "body": {}}}, {"content": {"name": "x", "tags": []}}
    )
    c = llm.make_client(key="k", transport=transport, max_retries=1)
    assert llm.complete(c, name="t", system="s", user="u", schema=Answer).name == "x"
    assert len(transport.requests) == 2


def test_missing_key_is_unavailable(monkeypatch):
    monkeypatch.setattr(llm, "api_key", lambda: None)
    with pytest.raises(llm.LlmUnavailable, match="No API key"):
        llm.make_client()


# --- call limits -----------------------------------------------------------------------


def _limiter(tmp_path, day="2026-11-25"):
    now = datetime.fromisoformat(f"{day}T12:00:00").replace(tzinfo=UTC)
    return llm.CallLimiter(get_config(), counter_file=tmp_path / "calls.json", now=lambda: now)


def test_session_limit(tmp_path):
    limiter, session = _limiter(tmp_path), llm.LlmSession()
    limiter.reserve(session, calls=19)
    limiter.reserve(session)
    assert limiter.left(session) == (0, 80)
    with pytest.raises(llm.LimitReached, match="session"):
        limiter.reserve(session)


def test_daily_limit_counts_across_sessions_and_resets_next_day(tmp_path):
    limiter = _limiter(tmp_path)
    for _ in range(5):
        limiter.reserve(llm.LlmSession(), calls=20)
    with pytest.raises(llm.LimitReached, match="daily"):
        limiter.reserve(llm.LlmSession())
    assert _limiter(tmp_path, day="2026-11-26").used_today() == 0


def test_reservation_that_does_not_fit_counts_nothing(tmp_path):
    limiter, session = _limiter(tmp_path), llm.LlmSession()
    limiter.reserve(session, calls=19)
    with pytest.raises(llm.LimitReached):
        limiter.reserve(session, calls=2)
    assert session.calls == 19 and limiter.used_today() == 19
