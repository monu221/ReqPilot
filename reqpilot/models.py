"""Requirement objects (docs/method.md, sections 1, 2 and 4; docs/plan.md, "Data model").

Source sentence lists may be empty here. A story without a source is a finding of the
Python checks (method section 3), not a parse error, so gold files and faulty writer output
can still be loaded and shown.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_Id = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
_Text = Field(min_length=1)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StoryStatus(StrEnum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Story(_Model):
    id: str = _Id
    role: str = _Text
    goal: str = _Text
    benefit: str = _Text
    source_sentences: list[int] = Field(default_factory=list)
    status: StoryStatus = StoryStatus.DRAFT

    @property
    def text(self) -> str:
        if self.role.lower().startswith("the "):
            who = self.role
        else:
            who = f"{'an' if self.role[:1].lower() in 'aeiou' else 'a'} {self.role}"
        return f"As {who}, I want {self.goal}, so that {self.benefit}."


class AcceptanceCriterion(_Model):
    id: str = _Id
    story_id: str = _Id
    given: str = _Text
    when: str = _Text
    then: str = _Text

    @property
    def text(self) -> str:
        return f"Given {self.given}, when {self.when}, then {self.then}."


class OpenQuestion(_Model):
    id: str = _Id
    topic: str = ""
    question: str = _Text
    related_story_ids: list[str] = Field(default_factory=list)
    origin: Literal["writer", "reviewer", "gold"] = "writer"


class NonFunctional(_Model):
    id: str = _Id
    category: str = _Text
    statement: str = _Text
    measure: str = Field(default="", description="Number and unit; empty if the notes give none")
    source_sentences: list[int] = Field(default_factory=list)


class OutOfScope(_Model):
    id: str = _Id
    statement: str = _Text
    reason: str = ""
    source_sentences: list[int] = Field(default_factory=list)


class Rule(StrEnum):
    """Reviewer rules, method section 2."""

    SPECIFIC_ROLE = "specific_role"
    SINGLE_GOAL = "single_goal"
    TESTABLE_CRITERIA = "testable_criteria"
    NO_VAGUE_WORDS = "no_vague_words"
    TRACEABLE = "traceable"
    NO_INVENTED_FACTS = "no_invented_facts"


class RuleVerdict(_Model):
    rule: Rule
    passed: bool
    reason: str = ""

    @model_validator(mode="after")
    def _failure_needs_reason(self) -> RuleVerdict:
        if not self.passed and not self.reason:
            raise ValueError(f"a failed rule needs a reason ({self.rule})")
        return self


class ReviewResult(_Model):
    story_id: str = _Id
    verdicts: list[RuleVerdict]

    @model_validator(mode="after")
    def _one_verdict_per_rule(self) -> ReviewResult:
        rules = [v.rule for v in self.verdicts]
        if sorted(rules) != sorted(Rule):
            raise ValueError(f"story {self.story_id}: need exactly one verdict per rule")
        return self

    @property
    def passed(self) -> bool:
        return all(v.passed for v in self.verdicts)


class TestCase(_Model):
    __test__ = False  # not a pytest class

    id: str = _Id
    criterion_id: str = _Id
    title: str = _Text
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(min_length=1)
    expected_result: str = _Text


def _duplicates(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    return sorted({i for i in ids if i in seen or seen.add(i)})


class Requirements(_Model):
    """Everything the writer returns for one note set, or one gold file."""

    stories: list[Story] = Field(default_factory=list)
    criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    non_functional: list[NonFunctional] = Field(default_factory=list)
    out_of_scope: list[OutOfScope] = Field(default_factory=list)

    @model_validator(mode="after")
    def _references_resolve(self) -> Requirements:
        all_ids = (
            [s.id for s in self.stories]
            + [c.id for c in self.criteria]
            + [q.id for q in self.open_questions]
            + [n.id for n in self.non_functional]
            + [o.id for o in self.out_of_scope]
        )
        if dupes := _duplicates(all_ids):
            raise ValueError(f"duplicate ids: {', '.join(dupes)}")
        story_ids = {s.id for s in self.stories}
        for c in self.criteria:
            if c.story_id not in story_ids:
                raise ValueError(f"criterion {c.id} refers to unknown story {c.story_id}")
        for q in self.open_questions:
            unknown = [i for i in q.related_story_ids if i not in story_ids]
            if unknown:
                raise ValueError(f"open question {q.id} refers to unknown story {unknown[0]}")
        return self

    def criteria_for(self, story_id: str) -> list[AcceptanceCriterion]:
        return [c for c in self.criteria if c.story_id == story_id]

    def source_numbers(self) -> set[int]:
        """Every sentence number cited anywhere."""
        cited: set[int] = set()
        for item in [*self.stories, *self.non_functional, *self.out_of_scope]:
            cited.update(item.source_sentences)
        return cited
