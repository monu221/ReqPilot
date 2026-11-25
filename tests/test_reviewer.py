"""Reviewer tests on FAKE responses (examples/demo). No live calls."""

import pytest

from reqpilot import reviewer, writer
from reqpilot.checks import run_checks
from reqpilot.demo import demo_names, load_demo
from reqpilot.models import Rule
from reqpilot.notes import split_notes
from tests.fakes import client, demo


def _written(name):
    sentences = split_notes(load_demo(name).notes)
    c, _ = client(demo(name, "writer"))
    return sentences, writer.write(sentences, c)


def _reviewed(name):
    sentences, req = _written(name)
    c, transport = client(demo(name, "reviewer"))
    return sentences, req, reviewer.review(sentences, req, c), transport


@pytest.mark.parametrize("name", demo_names())
def test_demo_reviews_cover_every_story(name):
    _, req, rev, _ = _reviewed(name)
    assert set(rev.results) == {s.id for s in req.stories}
    assert rev.warnings == []
    assert all(q.origin == "reviewer" for q in rev.open_questions)
    assert {n.id for n in req.non_functional} == set(rev.non_functional)


def test_reviewer_is_a_separate_call_without_the_writer_prompt():
    _, req, _, transport = _reviewed("01_maintenance")
    (body,) = transport.requests
    system, user = (m["content"] for m in body["messages"])
    assert body["response_format"]["json_schema"]["name"] == reviewer.SCHEMA_NAME
    assert system == reviewer.SYSTEM_PROMPT
    assert writer.SYSTEM_PROMPT not in user
    assert "[4] Anna: nurses report broken equipment" in user
    assert req.stories[0].text in user
    assert '"S1-AC1"' in user


def test_failed_rules_carry_reasons():
    _, _, rev, _ = _reviewed("01_maintenance")
    s6 = {v.rule: v for v in rev.results["S6"].verdicts}
    assert not s6[Rule.SPECIFIC_ROLE].passed
    assert "generic" in s6[Rule.SPECIFIC_ROLE].reason
    assert rev.results["S1"].passed


def _rows(name, story_id):
    sentences, req, rev, _ = _reviewed(name)
    rows = reviewer.compare(story_id, rev, run_checks(req, sentences))
    return {r.rule: r for r in rows}


def test_compare_python_only():
    """Set 01, S4: 'loads quickly' is missed by the (fake) reviewer, caught by Python."""
    row = _rows("01_maintenance", "S4")[Rule.TESTABLE_CRITERIA]
    assert row.agreement == "python only" and row.disagrees
    assert "quickly" in row.python_messages[0]


def test_compare_reviewer_only_where_python_passes():
    """Set 02, S6 cites sentence 16 instead of 17: only the reviewer can see that."""
    row = _rows("02_procurement", "S6")[Rule.TRACEABLE]
    assert row.python is True and row.reviewer is False
    assert row.agreement == "reviewer only" and row.disagrees


def test_compare_rule_without_python_check():
    row = _rows("01_maintenance", "S6")[Rule.SPECIFIC_ROLE]
    assert row.python is None
    assert row.agreement == "reviewer only*" and not row.disagrees


def test_compare_both_fail():
    rows = _rows("01_maintenance", "S5")
    assert rows[Rule.SINGLE_GOAL].agreement == "both fail"
    assert rows[Rule.SPECIFIC_ROLE].agreement == "both pass"


def test_unknown_and_skipped_stories_become_warnings():
    _, req = _written("03_lab_results")
    out = reviewer.ReviewOutput.model_validate(demo("03_lab_results", "reviewer")["content"])
    out.stories[0].story_id = "S99"
    out.stories[2].specific_role = reviewer.RVerdict(passed=False, reason=" ")
    rev = reviewer.to_review(out, req)
    assert "unknown story S99" in rev.warnings[0]
    assert "skipped S1" in rev.warnings[1]
    s3 = {v.rule: v for v in rev.results["S3"].verdicts}
    assert s3[Rule.SPECIFIC_ROLE].reason == "no reason given"


def test_not_reviewed_story():
    sentences, req = _written("03_lab_results")
    rows = reviewer.compare("S1", reviewer.Review(), run_checks(req, sentences))
    assert {r.agreement for r in rows} == {"not reviewed"}
