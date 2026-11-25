"""The app's steps as plain functions, so they can be tested without Streamlit.

notes -> write and review (2 calls) -> human edits and decisions -> test cases (1 call)
-> traceability -> export.

A demo workspace uses the FAKE responses in examples/demo and never makes a call.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from reqpilot import llm, reviewer, testcases, writer
from reqpilot.checks import Finding, run_checks
from reqpilot.demo import DemoSet
from reqpilot.models import Requirements, StoryStatus, TestCase
from reqpilot.notes import Sentence, split_notes
from reqpilot.reviewer import Review
from reqpilot.traceability import Matrix, build_matrix

MAX_NOTES_CHARS = 20_000

# Replaced in tests; the app calls them, never llm directly.
make_client = llm.make_client
make_limiter = llm.CallLimiter

_ids = itertools.count(1)


@dataclass
class Workspace:
    notes: str
    sentences: list[Sentence]
    demo: DemoSet | None = None
    req: Requirements | None = None
    review: Review | None = None
    test_cases: list[TestCase] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    edited: set[str] = field(default_factory=set)  # items changed after the review
    uid: int = field(default_factory=lambda: next(_ids))  # widget key prefix

    @property
    def is_demo(self) -> bool:
        return self.demo is not None

    def findings(self) -> list[Finding]:
        return run_checks(self.req, self.sentences) if self.req else []

    def matrix(self) -> Matrix:
        return build_matrix(self.sentences, self.req or Requirements(), self.test_cases)


def start(notes: str, demo: DemoSet | None = None) -> Workspace:
    if len(notes) > MAX_NOTES_CHARS:
        raise ValueError(f"The notes are longer than {MAX_NOTES_CHARS:,} characters.")
    return Workspace(notes=notes, sentences=split_notes(notes), demo=demo)


def write_and_review(
    ws: Workspace, limiter: llm.CallLimiter | None = None, session: llm.LlmSession | None = None
) -> None:
    """Writer then reviewer. If the review fails, the stories are kept with a warning."""
    ws.req, ws.review, ws.test_cases, ws.warnings, ws.edited = None, None, [], [], set()
    if ws.demo:
        ws.req = writer.to_requirements(
            writer.WriterOutput.model_validate(ws.demo.content("writer"))
        )
        out = reviewer.ReviewOutput.model_validate(ws.demo.content("reviewer"))
        ws.review = reviewer.to_review(out, ws.req)
        ws.warnings.extend(ws.review.warnings)
        return
    if not ws.sentences:
        raise llm.OutputError(["the notes are empty"])
    limiter = limiter or make_limiter()
    session = session or llm.LlmSession()
    client = make_client()
    limiter.reserve(session)
    ws.req = writer.write(ws.sentences, client)
    try:
        limiter.reserve(session)
        ws.review = reviewer.review(ws.sentences, ws.req, client)
        ws.warnings.extend(ws.review.warnings)
    except llm.LlmError as e:
        ws.review = None
        ws.warnings.append(f"The review could not run: {e} The stories are shown unreviewed.")


def make_test_cases(
    ws: Workspace, limiter: llm.CallLimiter | None = None, session: llm.LlmSession | None = None
) -> None:
    if ws.req is None:
        return
    if ws.demo:
        accepted = {c.id for c in testcases.accepted_criteria(ws.req)}
        out = testcases.TestCaseOutput.model_validate(ws.demo.content("test_cases"))
        out.test_cases = [t for t in out.test_cases if t.criterion_id in accepted]
        generated = testcases.to_test_cases(out, ws.req)
    elif not testcases.accepted_criteria(ws.req):
        generated = testcases.Generated(warnings=["no accepted story has acceptance criteria"])
    else:
        limiter = limiter or make_limiter()
        session = session or llm.LlmSession()
        client = make_client()
        limiter.reserve(session)
        generated = testcases.generate(ws.req, client)
    ws.test_cases = generated.test_cases
    ws.warnings = [w for w in ws.warnings if not w.startswith("Test cases:")]
    ws.warnings.extend(f"Test cases: {w}" for w in generated.warnings)


def set_status(ws: Workspace, item_id: str, status: StoryStatus) -> None:
    if ws.req is None:
        return
    for item in [*ws.req.stories, *ws.req.non_functional, *ws.req.out_of_scope]:
        if item.id == item_id:
            if item.status != status:
                item.status = status
                # Test cases were made for the old decisions.
                ws.test_cases = [t for t in ws.test_cases if _story_of(ws, t) != item_id]
            return
    raise KeyError(item_id)


def _story_of(ws: Workspace, tc: TestCase) -> str | None:
    crit = next((c for c in ws.req.criteria if c.id == tc.criterion_id), None) if ws.req else None
    return crit.story_id if crit else None


def edit_text(ws: Workspace, obj, field_name: str, value: str, item_id: str) -> str | None:
    """Apply an edit from the form. Returns an error message, or None."""
    value = value.strip()
    if value == getattr(obj, field_name):
        return None
    if not value:
        return f"{item_id}: {field_name} cannot be empty; kept the previous text."
    setattr(obj, field_name, value)
    ws.edited.add(item_id)
    return None
