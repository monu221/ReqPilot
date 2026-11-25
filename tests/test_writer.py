"""Writer tests on FAKE responses (examples/demo, tests/data/fake). No live calls."""

import pytest

from reqpilot import llm, writer
from reqpilot.checks import Check, run_checks
from reqpilot.demo import demo_names, load_demo
from reqpilot.notes import split_notes
from tests.fakes import client, demo, fake


@pytest.mark.parametrize("name", demo_names())
def test_demo_writer_answers_parse(name):
    sentences = split_notes(load_demo(name).notes)
    c, transport = client(demo(name, "writer"))
    req = writer.write(sentences, c)
    assert req.stories and req.criteria
    assert all(s.status == "draft" for s in req.stories)
    assert all(q.origin == "writer" for q in req.open_questions)
    sent = transport.requests[0]
    assert sent["response_format"]["json_schema"]["name"] == writer.SCHEMA_NAME
    assert "[1] Workshop:" in sent["messages"][1]["content"]
    assert "Use only facts in the notes" in sent["messages"][0]["content"]


def test_writer_keeps_faults_for_the_checks():
    """The demo writer answer for set 01 has deliberate faults; nothing is repaired."""
    name = "01_maintenance"
    sentences = split_notes(load_demo(name).notes)
    c, _ = client(demo(name, "writer"))
    req = writer.write(sentences, c)
    found = {(f.check, f.item_id) for f in run_checks(req, sentences)}
    assert (Check.UNMEASURED_PERFORMANCE, "S4-AC1") in found
    assert (Check.TWO_GOALS, "S5") in found
    assert (Check.UNKNOWN_NUMBER, "S7") in found
    assert (Check.UNMEASURED_NON_FUNCTIONAL, "N1") in found
    assert req.stories[5].role == "user"  # caught by the reviewer, not by Python


def test_empty_notes_make_no_call():
    c, transport = client()
    with pytest.raises(llm.OutputError, match="empty"):
        writer.write([], c)
    assert transport.requests == []


def test_broken_reference_is_output_error():
    c, _ = client(fake("bad_reference"))
    with pytest.raises(llm.OutputError, match="unknown story"):
        writer.write(split_notes("- a"), c)


def test_no_stories_is_output_error():
    c, _ = client(fake("no_stories"))
    with pytest.raises(llm.OutputError, match="no user stories"):
        writer.write(split_notes("- a"), c)


def test_writer_schema_is_strict():
    schema = llm.strict_schema(writer.WriterOutput)
    story = schema["$defs"]["WStory"]
    assert story["additionalProperties"] is False
    assert set(story["required"]) == {"id", "role", "goal", "benefit", "source_sentences"}
