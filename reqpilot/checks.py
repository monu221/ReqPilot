"""Plain-Python quality checks, independent of the AI (docs/method.md, section 3).

Each check returns findings; an empty list means the item passed. The word lists come from
config.yaml (`checks`). The checks are deliberately simple and explainable: they catch the
obvious cases cheaply and give the AI reviewer's verdict a second, deterministic opinion.
"""

from __future__ import annotations

import re
from enum import StrEnum
from functools import cache

from pydantic import BaseModel, ConfigDict

from reqpilot.config import Checks, get_config
from reqpilot.models import Requirements
from reqpilot.notes import Sentence


class Check(StrEnum):
    VAGUE_WORD = "vague_word"
    UNMEASURED_PERFORMANCE = "unmeasured_performance"
    TWO_GOALS = "two_goals"
    UNKNOWN_NUMBER = "unknown_number"
    NO_SOURCE = "no_source"
    UNMEASURED_NON_FUNCTIONAL = "unmeasured_non_functional"


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check: Check
    item_id: str
    story_id: str | None
    message: str


# A number followed by a unit, or a number with a "per <x>" rate.
_UNIT = (
    r"%|ms|milliseconds?|s|secs?|seconds?|mins?|minutes?|h|hrs?|hours?|"
    r"(?:working |business |calendar )?days?|weeks?|months?|years?|"
    r"kb|mb|gb|tb|eur|usd|chf|gbp|€|\$|"
    r"users?|requests?|results?|messages?|records?|transactions?|items?|pages?|files?|"
    r"calls?|orders?|patients?|times?"
)
_MEASURE = re.compile(
    rf"(?:[€$]\s*\d|\d[\d,.]*\s*(?:{_UNIT})(?![a-z])|\d[\d,.]*\s+(?:\w+\s+)?per\s+\w+|\d+\s*/\s*\w+)",
    re.I,
)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[,.]\d+)*(?![\w])")


def _normalise_number(raw: str) -> str:
    # "5,000" and "5000" are the same; "2.5" keeps its decimal point.
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", raw):
        raw = raw.replace(",", "")
    return raw.rstrip(".").rstrip("0").rstrip(".") if "." in raw else raw


def numbers_in(text: str) -> set[str]:
    return {_normalise_number(m) for m in _NUMBER.findall(text)}


def has_measure(text: str) -> bool:
    return bool(_MEASURE.search(text))


@cache
def _word_pattern(words: tuple[str, ...]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", re.I)


def _found(words: tuple[str, ...], text: str) -> list[str]:
    seen: list[str] = []
    for m in _word_pattern(words).finditer(text):
        word = m.group(0).lower()
        if word not in seen:
            seen.append(word)
    return seen


def _quote(words: list[str]) -> str:
    return ", ".join(f'"{w}"' for w in words)


def _two_goals(goal: str, verbs: tuple[str, ...]) -> str | None:
    """The joined part if `goal` holds two goals ("... and also ...", "... and to ...")."""
    lowered = goal.lower()
    if re.search(r"\band also\b", lowered):
        return "and also"
    for m in re.finditer(r"\band\s+(?:then\s+)?(\w+)", lowered):
        word = m.group(1)
        if word == "to" or word in verbs:
            return m.group(0)
    return None


def run_checks(
    req: Requirements,
    sentences: list[Sentence] | None = None,
    checks: Checks | None = None,
) -> list[Finding]:
    """All method section 3 checks on `req`.

    `sentences` are the notes the items were written from. Without them the number and
    source checks are skipped (there is nothing to compare against).
    """
    cfg = checks or get_config().checks
    findings: list[Finding] = []

    def add(check: Check, item_id: str, story_id: str | None, message: str) -> None:
        findings.append(Finding(check=check, item_id=item_id, story_id=story_id, message=message))

    note_numbers: set[str] | None = None
    if sentences is not None:
        note_numbers = set().union(*(numbers_in(s.text) for s in sentences))
    valid_sources = {s.number for s in sentences} if sentences is not None else set()

    def number_check(item_id: str, story_id: str | None, text: str) -> None:
        if note_numbers is None:
            return
        unknown = sorted(numbers_in(text) - note_numbers, key=lambda n: (len(n), n))
        if unknown:
            add(
                Check.UNKNOWN_NUMBER,
                item_id,
                story_id,
                f"number(s) not in the notes, possibly invented: {', '.join(unknown)}",
            )

    def source_check(item_id: str, story_id: str | None, kind: str, cited: list[int]) -> None:
        if sentences is None:
            return
        if not cited:
            add(Check.NO_SOURCE, item_id, story_id, f"{kind} cites no source sentence")
            return
        missing = sorted(n for n in set(cited) if n not in valid_sources)
        if missing:
            add(
                Check.NO_SOURCE,
                item_id,
                story_id,
                f"{kind} cites sentence(s) not in the notes: {', '.join(map(str, missing))}",
            )

    for story in req.stories:
        text = f"{story.role} {story.goal} {story.benefit}"
        if vague := _found(cfg.vague_words, text):
            add(Check.VAGUE_WORD, story.id, story.id, f"vague word(s): {_quote(vague)}")
        if joined := _two_goals(story.goal, cfg.action_verbs):
            add(
                Check.TWO_GOALS,
                story.id,
                story.id,
                f'goal joins two actions ("{joined}"); split it into two stories',
            )
        number_check(story.id, story.id, text)
        source_check(story.id, story.id, "story", story.source_sentences)

    for c in req.criteria:
        text = f"{c.given} {c.when} {c.then}"
        if vague := _found(cfg.vague_words, text):
            add(Check.VAGUE_WORD, c.id, c.story_id, f"vague word(s): {_quote(vague)}")
        if (perf := _found(cfg.performance_words, text)) and not has_measure(text):
            add(
                Check.UNMEASURED_PERFORMANCE,
                c.id,
                c.story_id,
                f"{_quote(perf)} without a number and unit; not testable",
            )
        number_check(c.id, c.story_id, text)

    for n in req.non_functional:
        text = f"{n.statement} {n.measure}"
        if vague := _found(cfg.vague_words, text):
            add(Check.VAGUE_WORD, n.id, None, f"vague word(s): {_quote(vague)}")
        if not n.measure.strip() and not has_measure(n.statement):
            add(
                Check.UNMEASURED_NON_FUNCTIONAL,
                n.id,
                None,
                f"{n.category}: no number and unit; needs an open question for the target",
            )
        number_check(n.id, None, text)
        source_check(n.id, None, "non-functional item", n.source_sentences)

    for o in req.out_of_scope:
        source_check(o.id, None, "out-of-scope item", o.source_sentences)

    return findings


def findings_by_item(findings: list[Finding]) -> dict[str, list[Finding]]:
    grouped: dict[str, list[Finding]] = {}
    for f in findings:
        grouped.setdefault(f.item_id, []).append(f)
    return grouped
