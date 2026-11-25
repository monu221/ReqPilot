"""Writer: numbered notes to stories, criteria and questions (docs/method.md, section 1).

One call. The model fills `WriterOutput`, a strict schema; `to_requirements()` turns it into
`Requirements`. Faults the method's checks are meant to catch (a missing source, a vague
word) are kept, not repaired, so that the reviewer and the Python checks can show them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from reqpilot import llm
from reqpilot.config import Config
from reqpilot.models import (
    AcceptanceCriterion,
    NonFunctional,
    OpenQuestion,
    OutOfScope,
    Requirements,
    Story,
)
from reqpilot.notes import Sentence, numbered

SCHEMA_NAME = "reqpilot_writer"

SYSTEM_PROMPT = """\
You are a senior business analyst. You turn meeting notes into a product backlog.

The notes come as numbered sentences, "[n] text". Return JSON in the given schema with
user stories, acceptance criteria, open questions, non-functional items and out-of-scope items.

Rules:
1. Use only facts in the notes. If a needed fact (a number, a rule, a role, a format) is
   missing, write an open question instead of inventing it.
2. Use the most specific role the notes name, for example "ward nurse", not "user". The
   attendee list says who holds which role.
3. One goal per story. If a sentence asks for two things, write two stories.
4. Every story, non-functional item and out-of-scope item cites the sentence numbers it comes
   from, in source_sentences. Cite only numbers that appear in the notes.
5. Each story has 2 to 5 acceptance criteria in Given/When/Then form. Each criterion must be
   testable: no vague words ("user-friendly", "etc.", "as appropriate", "fast") and no
   measures that the notes do not give.
6. Quality requirements for the whole system (volume, speed, availability, security,
   retention) are non-functional items, not stories. Put the number and unit in "measure"; if
   the notes give none, leave "measure" empty and add an open question asking for it.
7. Things the notes say stay as they are, or that the system will not do, are out-of-scope
   items, not stories.
8. Open questions name the gap precisely, say who could answer if the notes say so, and list
   the related story ids.

Ids: stories S1, S2, ...; criteria S1-AC1, S1-AC2, ...; open questions Q1, ...;
non-functional items N1, ...; out-of-scope items X1, .... Write in English.
"""


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WStory(_Out):
    id: str
    role: str = Field(description="The most specific role named in the notes")
    goal: str = Field(description="One goal: what follows 'I want', e.g. 'to report ...'")
    benefit: str = Field(description="Why, without 'so that'")
    source_sentences: list[int]


class WCriterion(_Out):
    id: str
    story_id: str
    given: str = Field(description="Without the word 'Given'")
    when: str = Field(description="Without the word 'when'")
    then: str = Field(description="Without the word 'then'")


class WQuestion(_Out):
    id: str
    topic: str = Field(description="Two to four words")
    question: str
    related_story_ids: list[str]


class WNonFunctional(_Out):
    id: str
    category: str = Field(description="volume, latency, availability, security, retention, ...")
    statement: str
    measure: str = Field(description="Number and unit from the notes, or empty")
    source_sentences: list[int]


class WOutOfScope(_Out):
    id: str
    statement: str
    reason: str = Field(description="For example 'unchanged process' or 'later release'")
    source_sentences: list[int]


class WriterOutput(_Out):
    stories: list[WStory]
    criteria: list[WCriterion]
    open_questions: list[WQuestion]
    non_functional: list[WNonFunctional]
    out_of_scope: list[WOutOfScope]


def user_message(sentences: list[Sentence]) -> str:
    return "Meeting notes:\n\n" + numbered(sentences)


def to_requirements(out: WriterOutput) -> Requirements:
    """Raise `llm.OutputError` if ids clash or references do not resolve."""
    try:
        return Requirements(
            stories=[Story(**s.model_dump()) for s in out.stories],
            criteria=[AcceptanceCriterion(**c.model_dump()) for c in out.criteria],
            open_questions=[
                OpenQuestion(**q.model_dump(), origin="writer") for q in out.open_questions
            ],
            non_functional=[NonFunctional(**n.model_dump()) for n in out.non_functional],
            out_of_scope=[OutOfScope(**o.model_dump()) for o in out.out_of_scope],
        )
    except ValidationError as e:
        raise llm.OutputError([err["msg"] for err in e.errors()[:5]]) from e


def write(
    sentences: list[Sentence], client: llm.GroqClient, cfg: Config | None = None
) -> Requirements:
    """One writer call. Call limits are the caller's job (see `workflow`)."""
    if not sentences:
        raise llm.OutputError(["the notes are empty"])
    out = llm.complete(
        client,
        name=SCHEMA_NAME,
        system=SYSTEM_PROMPT,
        user=user_message(sentences),
        schema=WriterOutput,
        cfg=cfg,
    )
    if not out.stories:
        raise llm.OutputError(["the model found no user stories in the notes"])
    return to_requirements(out)
