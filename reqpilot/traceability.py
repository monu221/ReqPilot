"""Traceability matrix: note sentence -> story -> criterion -> test case (method section 4).

Only accepted items appear. The gaps show what a BA still has to look at: accepted stories
or criteria without a test case, accepted items without a source sentence, and note sentences
that no accepted item uses (header lines such as the attendee list are not counted).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from reqpilot.models import Requirements, StoryStatus, TestCase
from reqpilot.notes import Sentence

ItemKind = Literal["story", "non-functional", "out of scope"]


@dataclass(frozen=True)
class TraceRow:
    sentence: int | None
    sentence_text: str
    kind: ItemKind
    item_id: str
    item_text: str
    criterion_id: str = ""
    test_case_id: str = ""


@dataclass
class Matrix:
    rows: list[TraceRow] = field(default_factory=list)
    stories_without_test_cases: list[str] = field(default_factory=list)
    criteria_without_test_cases: list[str] = field(default_factory=list)
    items_without_source: list[str] = field(default_factory=list)
    unused_sentences: list[int] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not (
            self.stories_without_test_cases
            or self.criteria_without_test_cases
            or self.items_without_source
            or self.unused_sentences
        )


def build_matrix(
    sentences: list[Sentence], req: Requirements, test_cases: list[TestCase]
) -> Matrix:
    text_of = {s.number: s.text for s in sentences}
    tests_for: dict[str, list[str]] = {}
    for tc in test_cases:
        tests_for.setdefault(tc.criterion_id, []).append(tc.id)

    m = Matrix()
    used: set[int] = set()

    def sources(cited: list[int]) -> list[int | None]:
        known = [n for n in dict.fromkeys(cited) if n in text_of]
        used.update(known)
        return list(known) or [None]

    for story in req.stories:
        if story.status != StoryStatus.ACCEPTED:
            continue
        criteria = req.criteria_for(story.id)
        if not any(n in text_of for n in story.source_sentences):
            m.items_without_source.append(story.id)
        story_tested = False
        for number in sources(story.source_sentences):
            base = dict(
                sentence=number,
                sentence_text=text_of.get(number, "") if number else "",
                kind="story",
                item_id=story.id,
                item_text=story.text,
            )
            if not criteria:
                m.rows.append(TraceRow(**base))
            for c in criteria:
                tests = tests_for.get(c.id, [])
                story_tested = story_tested or bool(tests)
                for t in tests or [""]:
                    m.rows.append(TraceRow(**base, criterion_id=c.id, test_case_id=t))
        m.criteria_without_test_cases.extend(c.id for c in criteria if c.id not in tests_for)
        if not story_tested:
            m.stories_without_test_cases.append(story.id)

    others = [("non-functional", n, n.statement) for n in req.non_functional] + [
        ("out of scope", o, o.statement) for o in req.out_of_scope
    ]
    for kind, item, text in others:
        if item.status != StoryStatus.ACCEPTED:
            continue
        if not any(n in text_of for n in item.source_sentences):
            m.items_without_source.append(item.id)
        for number in sources(item.source_sentences):
            m.rows.append(
                TraceRow(
                    sentence=number,
                    sentence_text=text_of.get(number, "") if number else "",
                    kind=kind,
                    item_id=item.id,
                    item_text=text,
                )
            )

    m.unused_sentences = [s.number for s in sentences if not s.is_header and s.number not in used]
    return m
