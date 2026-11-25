"""Test cases and traceability on hand-built data, plus the generator on FAKE responses."""

from reqpilot import testcases
from reqpilot.models import (
    AcceptanceCriterion,
    NonFunctional,
    OutOfScope,
    Requirements,
    Story,
    StoryStatus,
    TestCase,
)
from reqpilot.notes import split_notes
from reqpilot.traceability import build_matrix
from tests.fakes import client, demo

NOTES = split_notes(
    "Workshop: test\n- nurses report faults\n- photos wanted\n- volume 100 per day\n"
    "- phone calls stay\n- unrelated remark"
)
# 1 header, 2 report, 3 photos, 4 volume, 5 phone, 6 unrelated

A = StoryStatus.ACCEPTED


def _req(s2_status=A, s1_sources=(2, 3)):
    return Requirements(
        stories=[
            Story(id="S1", role="nurse", goal="to report", benefit="b",
                  source_sentences=list(s1_sources), status=A),
            Story(id="S2", role="nurse", goal="to attach", benefit="b",
                  source_sentences=[3], status=s2_status),
        ],
        criteria=[
            AcceptanceCriterion(id="S1-AC1", story_id="S1", given="g", when="w", then="t"),
            AcceptanceCriterion(id="S1-AC2", story_id="S1", given="g", when="w", then="t2"),
            AcceptanceCriterion(id="S2-AC1", story_id="S2", given="g", when="w", then="t"),
        ],
        non_functional=[NonFunctional(id="N1", category="volume", statement="100 per day",
                                      measure="100 per day", source_sentences=[4], status=A)],
        out_of_scope=[OutOfScope(id="X1", statement="phone calls stay", source_sentences=[5])],
    )  # fmt: skip


def _tc(id_, crit):
    return TestCase(id=id_, criterion_id=crit, title="t", steps=["s"], expected_result="r")


def test_matrix_rows_link_sentence_story_criterion_test():
    m = build_matrix(NOTES, _req(), [_tc("T1", "S1-AC1"), _tc("T2", "S2-AC1")])
    story_rows = [(r.sentence, r.item_id, r.criterion_id, r.test_case_id) for r in m.rows
                  if r.kind == "story"]  # fmt: skip
    assert story_rows == [
        (2, "S1", "S1-AC1", "T1"),
        (2, "S1", "S1-AC2", ""),
        (3, "S1", "S1-AC1", "T1"),
        (3, "S1", "S1-AC2", ""),
        (3, "S2", "S2-AC1", "T2"),
    ]
    assert m.criteria_without_test_cases == ["S1-AC2"]
    assert m.stories_without_test_cases == []


def test_matrix_lists_non_functional_and_skips_unaccepted_out_of_scope():
    m = build_matrix(NOTES, _req(), [])
    kinds = {(r.kind, r.item_id, r.sentence) for r in m.rows if r.kind != "story"}
    assert kinds == {("non-functional", "N1", 4)}
    assert m.unused_sentences == [5, 6]  # 1 is a header; X1 is not accepted


def test_rejected_story_is_left_out():
    m = build_matrix(NOTES, _req(s2_status=StoryStatus.REJECTED), [_tc("T1", "S1-AC1")])
    assert {r.item_id for r in m.rows if r.kind == "story"} == {"S1"}
    assert "S2-AC1" not in m.criteria_without_test_cases


def test_accepted_story_without_test_case_is_shown():
    m = build_matrix(NOTES, _req(), [_tc("T1", "S1-AC1")])
    assert m.stories_without_test_cases == ["S2"]
    assert not m.complete


def test_story_without_valid_source_is_shown_with_empty_sentence():
    m = build_matrix(NOTES, _req(s1_sources=(99,)), [])
    assert "S1" in m.items_without_source
    assert any(r.item_id == "S1" and r.sentence is None for r in m.rows)


def test_complete_matrix():
    req = _req()
    req.out_of_scope[0].status = A
    req.stories.append(Story(id="S3", role="r", goal="g", benefit="b", source_sentences=[6],
                             status=StoryStatus.ACCEPTED))  # fmt: skip
    req.criteria.append(AcceptanceCriterion(id="S3-AC1", story_id="S3", given="g", when="w",
                                            then="t"))  # fmt: skip
    tcs = [_tc(f"T{i}", c) for i, c in enumerate(["S1-AC1", "S1-AC2", "S2-AC1", "S3-AC1"])]
    assert build_matrix(NOTES, req, tcs).complete


# --- generator -------------------------------------------------------------------------


def test_only_accepted_criteria_are_sent():
    req = _req(s2_status=StoryStatus.DRAFT)
    msg = testcases.user_message(req)
    assert "S1-AC1" in msg and "S1-AC2" in msg and "S2-AC1" not in msg


def test_nothing_accepted_makes_no_call():
    req = _req()
    for s in req.stories:
        s.status = StoryStatus.DRAFT
    c, transport = client()
    result = testcases.generate(req, c)
    assert result.test_cases == [] and transport.requests == []


def test_generator_on_demo_answer_drops_unaccepted_and_renumbers():
    from reqpilot import writer
    from reqpilot.demo import load_demo

    sentences = split_notes(load_demo("02_procurement").notes)
    wc, _ = client(demo("02_procurement", "writer"))
    req = writer.write(sentences, wc)
    for s in req.stories:
        s.status = StoryStatus.ACCEPTED if s.id in ("S1", "S5") else StoryStatus.REJECTED
    c, transport = client(demo("02_procurement", "test_cases"))
    result = testcases.generate(req, c)
    assert [(t.id, t.criterion_id) for t in result.test_cases] == [
        ("T1", "S1-AC1"),
        ("T2", "S1-AC2"),
        ("T3", "S1-AC3"),
        ("T4", "S5-AC1"),
        ("T5", "S5-AC2"),
    ]
    assert len(result.warnings) == 13 - 5
    assert transport.requests[0]["response_format"]["json_schema"]["name"] == "reqpilot_test_cases"
