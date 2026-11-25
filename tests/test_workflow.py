"""The app's steps without Streamlit. Demo sets use FAKE data; live paths use FakeTransport."""

import pytest

from reqpilot import llm, workflow
from reqpilot.config import get_config
from reqpilot.demo import load_demo
from reqpilot.models import StoryStatus
from tests.fakes import client, demo, fake


@pytest.fixture
def limiter(tmp_path):
    return llm.CallLimiter(get_config(), counter_file=tmp_path / "calls.json")


@pytest.fixture
def no_network(monkeypatch):
    def refuse():
        raise AssertionError("a demo must not create an API client")

    monkeypatch.setattr(workflow, "make_client", refuse)


def test_demo_runs_end_to_end_without_a_client(no_network, limiter):
    ws = workflow.start(load_demo("03_lab_results").notes, load_demo("03_lab_results"))
    session = llm.LlmSession()
    workflow.write_and_review(ws, limiter, session)
    assert ws.is_demo and len(ws.req.stories) == 6 and ws.review is not None
    for s in ws.req.stories[:3]:
        workflow.set_status(ws, s.id, StoryStatus.ACCEPTED)
    workflow.make_test_cases(ws, limiter, session)
    assert {t.criterion_id for t in ws.test_cases} == {"S1-AC1", "S1-AC2", "S2-AC1", "S3-AC1"}
    assert ws.warnings == []
    assert session.calls == 0 and limiter.used_today() == 0
    m = ws.matrix()
    assert m.stories_without_test_cases == []
    assert 13 in m.unused_sentences  # volume item not accepted yet


def _live(monkeypatch, *responses):
    c, transport = client(*responses)
    monkeypatch.setattr(workflow, "make_client", lambda: c)
    return transport


def test_live_path_counts_two_calls(monkeypatch, limiter):
    name = "01_maintenance"
    transport = _live(monkeypatch, demo(name, "writer"), demo(name, "reviewer"))
    ws, session = workflow.start(load_demo(name).notes), llm.LlmSession()
    workflow.write_and_review(ws, limiter, session)
    assert not ws.is_demo and len(transport.requests) == 2
    assert session.calls == 2 and limiter.used_today() == 2
    assert ws.review and set(ws.review.results) == {s.id for s in ws.req.stories}


def test_failed_review_keeps_the_stories(monkeypatch, limiter):
    name = "01_maintenance"
    _live(monkeypatch, demo(name, "writer"), fake("rate_limited"))
    ws = workflow.start(load_demo(name).notes)
    workflow.write_and_review(ws, limiter, llm.LlmSession())
    assert ws.req and ws.review is None
    assert "review could not run" in ws.warnings[0]


def test_live_test_cases_need_an_accepted_story(monkeypatch, limiter):
    name = "02_procurement"
    transport = _live(monkeypatch, demo(name, "writer"), demo(name, "reviewer"))
    ws, session = workflow.start(load_demo(name).notes), llm.LlmSession()
    workflow.write_and_review(ws, limiter, session)
    workflow.make_test_cases(ws, limiter, session)
    assert ws.test_cases == [] and len(transport.requests) == 2
    assert "no accepted story" in ws.warnings[-1]


def test_limit_reached_makes_no_call(monkeypatch, limiter):
    transport = _live(monkeypatch)
    session = llm.LlmSession(calls=get_config().llm.calls_per_session)
    ws = workflow.start("- a")
    with pytest.raises(llm.LimitReached):
        workflow.write_and_review(ws, limiter, session)
    assert transport.requests == []


def test_rejecting_a_story_drops_its_test_cases(no_network):
    ws = workflow.start(load_demo("02_procurement").notes, load_demo("02_procurement"))
    workflow.write_and_review(ws)
    for s in ws.req.stories:
        workflow.set_status(ws, s.id, StoryStatus.ACCEPTED)
    workflow.make_test_cases(ws)
    assert len(ws.test_cases) == 13
    workflow.set_status(ws, "S2", StoryStatus.REJECTED)
    assert len(ws.test_cases) == 10


def test_edit_marks_story_and_rejects_empty_text(no_network):
    ws = workflow.start(load_demo("01_maintenance").notes, load_demo("01_maintenance"))
    workflow.write_and_review(ws)
    s6 = ws.req.stories[5]
    assert workflow.edit_text(ws, s6, "role", "hospital staff member", "S6") is None
    assert s6.role == "hospital staff member" and "S6" in ws.edited
    assert "cannot be empty" in workflow.edit_text(ws, s6, "goal", "  ", "S6")
    assert s6.goal == "to sign in with my hospital login"


def test_overlong_notes_are_refused():
    with pytest.raises(ValueError, match="longer than"):
        workflow.start("x" * (workflow.MAX_NOTES_CHARS + 1))
