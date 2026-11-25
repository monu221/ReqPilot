"""Test cases from accepted acceptance criteria (docs/method.md, section 4).

One call for all accepted criteria. Criteria of draft or rejected stories are never sent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, ValidationError

from reqpilot import llm
from reqpilot.config import Config
from reqpilot.models import AcceptanceCriterion, Requirements, StoryStatus, TestCase

SCHEMA_NAME = "reqpilot_test_cases"

SYSTEM_PROMPT = """\
You are a test analyst. For each acceptance criterion you get, write one or more test cases
that a tester can run by hand: a short title, preconditions, numbered steps and the expected
result. Use concrete values only where the criterion or story gives them; otherwise describe
the value ("an amount under the lowest threshold"). Do not invent rules.

Ids: T1, T2, ... in order. Every test case names the criterion id it tests. Write in English.
"""


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TCase(_Out):
    id: str
    criterion_id: str
    title: str
    preconditions: list[str]
    steps: list[str]
    expected_result: str


class TestCaseOutput(_Out):
    __test__ = False

    test_cases: list[TCase]


@dataclass
class Generated:
    test_cases: list[TestCase] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def accepted_criteria(req: Requirements) -> list[AcceptanceCriterion]:
    accepted = {s.id for s in req.stories if s.status == StoryStatus.ACCEPTED}
    return [c for c in req.criteria if c.story_id in accepted]


def user_message(req: Requirements) -> str:
    lines = []
    criteria = accepted_criteria(req)
    for story in req.stories:
        own = [c for c in criteria if c.story_id == story.id]
        if not own:
            continue
        lines.append(f"Story {story.id}: {story.text}")
        lines.extend(f"  {c.id}: {c.text}" for c in own)
    return "Accepted criteria:\n\n" + "\n".join(lines)


def to_test_cases(out: TestCaseOutput, req: Requirements) -> Generated:
    """Keep test cases for accepted criteria; renumber T1.. so ids stay unique."""
    allowed = {c.id for c in accepted_criteria(req)}
    result = Generated()
    for tc in out.test_cases:
        if tc.criterion_id not in allowed:
            result.warnings.append(
                f"dropped test case {tc.id}: criterion {tc.criterion_id} is not accepted"
            )
            continue
        data = tc.model_dump() | {"id": f"T{len(result.test_cases) + 1}"}
        try:
            result.test_cases.append(TestCase(**data))
        except ValidationError as e:
            result.warnings.append(f"dropped test case {tc.id}: {e.errors()[0]['msg']}")
    return result


def generate(req: Requirements, client: llm.GroqClient, cfg: Config | None = None) -> Generated:
    """One call for all accepted criteria. No call if nothing is accepted."""
    if not accepted_criteria(req):
        return Generated(warnings=["no accepted story has acceptance criteria"])
    out = llm.complete(
        client,
        name=SCHEMA_NAME,
        system=SYSTEM_PROMPT,
        user=user_message(req),
        schema=TestCaseOutput,
        cfg=cfg,
    )
    return to_test_cases(out, req)
