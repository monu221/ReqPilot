"""Reviewer: a separate call that checks the writer's stories (docs/method.md, section 2).

The reviewer gets the numbered notes and the writer's items, never the writer's prompt or
reasoning, so the writer does not grade its own work. It returns a pass or fail per rule per
story, measurability per non-functional item, and extra open questions.

`compare()` sets the reviewer's verdicts next to the Python checks, rule by rule, so the app
can show where the two agree and where only one of them found a problem.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from reqpilot import llm
from reqpilot.checks import Check, Finding
from reqpilot.config import Config
from reqpilot.models import OpenQuestion, Requirements, ReviewResult, Rule, RuleVerdict
from reqpilot.notes import Sentence, numbered

SCHEMA_NAME = "reqpilot_reviewer"

SYSTEM_PROMPT = """\
You are a strict reviewer of user stories. You did not write them. You get meeting notes as
numbered sentences, "[n] text", and the stories, criteria and other items written from them.

For every story, judge each rule, pass or fail. A failure needs a one-line reason that names
the words at fault; a pass has an empty reason.
- specific_role: the role is the most specific one the notes name ("As a user" fails when
  the notes name nurses).
- single_goal: the story has one goal ("... and also ..." joining two features fails).
- testable_criteria: every acceptance criterion can be tested; "fast" without a number and
  unit fails.
- no_vague_words: no "user-friendly", "etc.", "as appropriate" or similar in the story or its
  criteria.
- traceable: the cited source sentences exist and support the story.
- no_invented_facts: no number, rule or role that is not in the notes.

For every non-functional item, say whether it is measurable (has a number and unit).

Then list open questions a business analyst must still ask that are not already in the
existing open questions. Do not repeat them. Write in English.
"""


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RVerdict(_Out):
    passed: bool
    reason: str


class RStory(_Out):
    story_id: str
    specific_role: RVerdict
    single_goal: RVerdict
    testable_criteria: RVerdict
    no_vague_words: RVerdict
    traceable: RVerdict
    no_invented_facts: RVerdict


class RNonFunctional(_Out):
    id: str
    measurable: bool
    reason: str


class RQuestion(_Out):
    topic: str
    question: str
    related_story_ids: list[str]


class ReviewOutput(_Out):
    stories: list[RStory]
    non_functional: list[RNonFunctional]
    open_questions: list[RQuestion]


class NonFunctionalVerdict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    measurable: bool
    reason: str = ""


@dataclass
class Review:
    results: dict[str, ReviewResult] = field(default_factory=dict)
    non_functional: dict[str, NonFunctionalVerdict] = field(default_factory=dict)
    open_questions: list[OpenQuestion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def user_message(sentences: list[Sentence], req: Requirements) -> str:
    items = {
        "stories": [
            {
                "id": s.id,
                "story": s.text,
                "source_sentences": s.source_sentences,
                "criteria": [{"id": c.id, "text": c.text} for c in req.criteria_for(s.id)],
            }
            for s in req.stories
        ],
        "non_functional": [
            {"id": n.id, "category": n.category, "statement": n.statement, "measure": n.measure}
            for n in req.non_functional
        ],
        "out_of_scope": [{"id": o.id, "statement": o.statement} for o in req.out_of_scope],
        "existing_open_questions": [q.question for q in req.open_questions],
    }
    return (
        "Meeting notes:\n\n"
        + numbered(sentences)
        + "\n\nItems to review:\n\n"
        + json.dumps(items, indent=1, ensure_ascii=False)
    )


def to_review(out: ReviewOutput, req: Requirements) -> Review:
    """Keep what refers to known items; note anything skipped or unknown as a warning."""
    review = Review()
    story_ids = {s.id for s in req.stories}
    for rs in out.stories:
        if rs.story_id not in story_ids:
            review.warnings.append(f"the reviewer judged an unknown story {rs.story_id}")
            continue
        if rs.story_id in review.results:
            review.warnings.append(f"the reviewer judged story {rs.story_id} twice; kept the first")
            continue
        verdicts = []
        for rule in Rule:
            v: RVerdict = getattr(rs, rule.value)
            reason = v.reason.strip() or ("" if v.passed else "no reason given")
            verdicts.append(RuleVerdict(rule=rule, passed=v.passed, reason=reason))
        review.results[rs.story_id] = ReviewResult(story_id=rs.story_id, verdicts=verdicts)
    if missing := [i for i in story_ids if i not in review.results]:
        review.warnings.append(f"the reviewer skipped {', '.join(sorted(missing))}")
    nfr_ids = {n.id for n in req.non_functional}
    for rn in out.non_functional:
        if rn.id in nfr_ids and rn.id not in review.non_functional:
            review.non_functional[rn.id] = NonFunctionalVerdict(
                id=rn.id, measurable=rn.measurable, reason=rn.reason.strip()
            )
    for i, q in enumerate(out.open_questions, start=1):
        related = [s for s in q.related_story_ids if s in story_ids]
        review.open_questions.append(
            OpenQuestion(
                id=f"R{i}",
                topic=q.topic,
                question=q.question,
                related_story_ids=related,
                origin="reviewer",
            )
        )
    return review


def review(
    sentences: list[Sentence],
    req: Requirements,
    client: llm.GroqClient,
    cfg: Config | None = None,
) -> Review:
    """One reviewer call, separate from the writer's. Call limits are the caller's job."""
    out = llm.complete(
        client,
        name=SCHEMA_NAME,
        system=SYSTEM_PROMPT,
        user=user_message(sentences, req),
        schema=ReviewOutput,
        cfg=cfg,
    )
    return to_review(out, req)


# --------------------------------------------------------------------------- comparison

# Which Python check covers which reviewer rule. specific_role has no Python check.
CHECK_RULE: dict[Check, Rule] = {
    Check.VAGUE_WORD: Rule.NO_VAGUE_WORDS,
    Check.UNMEASURED_PERFORMANCE: Rule.TESTABLE_CRITERIA,
    Check.TWO_GOALS: Rule.SINGLE_GOAL,
    Check.UNKNOWN_NUMBER: Rule.NO_INVENTED_FACTS,
    Check.NO_SOURCE: Rule.TRACEABLE,
}


@dataclass(frozen=True)
class RuleRow:
    rule: Rule
    reviewer: bool | None  # True = pass, None = not reviewed
    reviewer_reason: str
    python: bool | None  # True = pass, None = no Python check for this rule
    python_messages: tuple[str, ...]

    @property
    def agreement(self) -> str:
        if self.reviewer is None:
            return "not reviewed"
        if self.python is None:
            return "reviewer only*" if not self.reviewer else "both pass"
        if self.reviewer == self.python:
            return "both pass" if self.reviewer else "both fail"
        return "python only" if self.reviewer else "reviewer only"

    @property
    def disagrees(self) -> bool:
        return self.agreement in ("python only", "reviewer only")


def compare(story_id: str, review: Review, findings: list[Finding]) -> list[RuleRow]:
    """One row per rule for `story_id`: the reviewer's verdict next to the Python checks.

    Findings on the story's criteria count for the story. "reviewer only*" means the rule
    has no Python check (specific_role), so there is nothing to disagree with.
    """
    result = review.results.get(story_id)
    by_rule: dict[Rule, list[str]] = {}
    for f in findings:
        if f.story_id == story_id and f.check in CHECK_RULE:
            by_rule.setdefault(CHECK_RULE[f.check], []).append(f.message)
    covered = set(CHECK_RULE.values())
    rows = []
    for rule in Rule:
        verdict = next((v for v in result.verdicts if v.rule == rule), None) if result else None
        messages = tuple(by_rule.get(rule, []))
        rows.append(
            RuleRow(
                rule=rule,
                reviewer=verdict.passed if verdict else None,
                reviewer_reason=verdict.reason if verdict else "",
                python=(not messages) if rule in covered else None,
                python_messages=messages,
            )
        )
    return rows
