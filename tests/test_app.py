"""Smoke tests of the Streamlit app with AppTest. No live calls: demo sets use FAKE data and
the own-notes path gets a FakeTransport client."""

import pytest
from streamlit.testing.v1 import AppTest

from reqpilot import llm, workflow
from reqpilot.config import REPO_ROOT, get_config
from reqpilot.demo import DEMO_LABEL
from tests.fakes import client, demo

APP = str(REPO_ROOT / "app" / "streamlit_app.py")


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(
        workflow,
        "make_limiter",
        lambda: llm.CallLimiter(get_config(), counter_file=tmp_path / "calls.json"),
    )

    def refuse():
        raise AssertionError("no client expected")

    monkeypatch.setattr(workflow, "make_client", refuse)


def _button(at, prefix):
    return next(b for b in at.button if b.label.startswith(prefix))


def _texts(elements):
    return " ".join(e.value for e in elements)


def test_demo_set_walkthrough():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert DEMO_LABEL in _texts(at.warning)
    _button(at, "Load demo stories").click().run()
    assert not at.exception
    assert "S6" in " ".join(e.label for e in at.expander)
    _button(at, "Accept all stories").click().run()
    _button(at, "Make test cases").click().run()
    assert not at.exception
    assert any("Traceability" in h.value for h in at.header)
    downloads = [d.proto.label for d in at.get("download_button")]
    assert downloads == ["Download Jira CSV", "Download Markdown"]
    assert "calls left: **20** this session" in _texts(at.sidebar.caption)


@pytest.mark.parametrize("index", [1, 2])
def test_other_demo_sets_load(index):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[index]).run()
    _button(at, "Load demo stories").click().run()
    assert not at.exception


def test_own_notes_use_the_client(monkeypatch):
    name = "02_procurement"
    c, transport = client(demo(name, "writer"), demo(name, "reviewer"))
    monkeypatch.setattr(workflow, "make_client", lambda: c)
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.radio[0].set_value("My own notes").run()
    notes = (REPO_ROOT / "data" / "notes" / f"{name}.txt").read_text(encoding="utf-8")
    at.text_area[0].input(notes).run()
    _button(at, "Write and review stories").click().run()
    assert not at.exception
    assert len(transport.requests) == 2
    assert DEMO_LABEL not in _texts(at.warning)
    assert "calls left: **18** this session" in _texts(at.sidebar.caption)
