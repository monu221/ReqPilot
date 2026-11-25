import pytest
from pydantic import ValidationError

from reqpilot.models import (
    AcceptanceCriterion,
    OpenQuestion,
    Requirements,
    ReviewResult,
    Rule,
    RuleVerdict,
    Story,
    TestCase,
)


def _story(id_="S1", **kw):
    return Story(id=id_, role="ward nurse", goal="to report faults", benefit="they are fixed", **kw)


def test_story_text():
    assert _story().text == "As a ward nurse, I want to report faults, so that they are fixed."
    s = Story(id="S2", role="approver", goal="g", benefit="b")
    assert s.text.startswith("As an approver,")
    s = Story(id="S3", role="the head of engineering", goal="g", benefit="b")
    assert s.text.startswith("As the head of engineering,")


def test_criterion_text():
    c = AcceptanceCriterion(id="S1-AC1", story_id="S1", given="g", when="w", then="t")
    assert c.text == "Given g, when w, then t."


def test_empty_role_is_rejected():
    with pytest.raises(ValidationError):
        Story(id="S1", role=" ", goal="g", benefit="b")


def test_criterion_must_refer_to_known_story():
    with pytest.raises(ValidationError, match="unknown story"):
        Requirements(
            stories=[_story()],
            criteria=[AcceptanceCriterion(id="C1", story_id="S9", given="g", when="w", then="t")],
        )


def test_open_question_must_refer_to_known_story():
    with pytest.raises(ValidationError, match="unknown story"):
        Requirements(
            stories=[_story()],
            open_questions=[OpenQuestion(id="Q1", question="?", related_story_ids=["S2"])],
        )


def test_ids_must_be_unique():
    with pytest.raises(ValidationError, match="duplicate ids: S1"):
        Requirements(stories=[_story(), _story()])


def test_source_numbers_collects_all_citations():
    r = Requirements(stories=[_story(source_sentences=[4, 5]), _story("S2", source_sentences=[5])])
    assert r.source_numbers() == {4, 5}


def _verdicts(failed: Rule | None = None, reason: str = "why"):
    return [
        RuleVerdict(rule=r, passed=r != failed, reason=reason if r == failed else "") for r in Rule
    ]


def test_review_needs_one_verdict_per_rule():
    assert ReviewResult(story_id="S1", verdicts=_verdicts()).passed
    with pytest.raises(ValidationError, match="one verdict per rule"):
        ReviewResult(story_id="S1", verdicts=_verdicts()[:-1])


def test_failed_rule_needs_reason():
    with pytest.raises(ValidationError, match="needs a reason"):
        _verdicts(Rule.SPECIFIC_ROLE, reason="")
    review = ReviewResult(story_id="S1", verdicts=_verdicts(Rule.SPECIFIC_ROLE))
    assert not review.passed


def test_test_case_needs_steps():
    with pytest.raises(ValidationError):
        TestCase(id="T1", criterion_id="S1-AC1", title="t", steps=[], expected_result="r")
