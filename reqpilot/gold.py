"""Read gold files (data/README.md, "Layout").

A gold file has, in this order:

    STORY n: As a <role>, I want <goal>, so that <benefit>.   ("As the <role>" keeps "the")
    ACn: Given <...>, when <...>, then <...>.
    NON-FUNCTIONAL:            (bullets, or "NON-FUNCTIONAL: none stated")
    OUT OF SCOPE (<reason>):   (bullets, or "OUT OF SCOPE: none stated")
    OPEN QUESTIONS:            (bullets)

Lines wrap freely; a bullet's wrapped lines are indented or start a new line without "- ".
Gold stories have no source sentences: the evaluation matches them to generated stories by
meaning (method section 5).

Ids: stories S1.., criteria S1-AC1.., non-functional N1.., out of scope X1.., questions Q1...
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from reqpilot.models import (
    AcceptanceCriterion,
    NonFunctional,
    OpenQuestion,
    OutOfScope,
    Requirements,
    Story,
)

_STORY_HEAD = re.compile(r"^STORY (\d+):\s*(.*)$")
_AC_HEAD = re.compile(r"^AC(\d+):\s*(.*)$")
_SECTION_HEAD = re.compile(
    r"^(?P<name>NON-FUNCTIONAL|OUT OF SCOPE|OPEN QUESTIONS)\s*"
    r"(?:\((?P<reason>[^)]*)\))?:\s*(?P<rest>.*)$"
)
_STORY = re.compile(
    r"^As (?:an? )?(?P<role>.+?), I want (?P<goal>.+?),? so that (?P<benefit>.+?)\.?$", re.S
)
_AC = re.compile(r"^Given (?P<given>.+?), when (?P<when>.+?), then (?P<then>.+?)\.?$", re.S)
_NONE = "none stated"
_SECTION_ORDER = ("NON-FUNCTIONAL", "OUT OF SCOPE", "OPEN QUESTIONS")


class GoldFormatError(ValueError):
    def __init__(self, path: str, line: int, message: str):
        super().__init__(f"{path}, line {line}: {message}")
        self.line = line


class GoldSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    requirements: Requirements


class _Block:
    """One STORY, AC or section bullet with its wrapped lines joined."""

    def __init__(self, kind: str, line: int, text: str, number: int = 0):
        self.kind = kind
        self.line = line
        self.text = text
        self.number = number


def _join(a: str, b: str) -> str:
    return f"{a} {b}".strip() if a else b


def parse_gold(text: str, name: str = "<gold>") -> GoldSet:
    req = _build(_blocks(text, name), name)
    return GoldSet(name=name, requirements=req)


def _blocks(text: str, name: str) -> list[_Block]:
    blocks: list[_Block] = []
    section: str | None = None
    seen_sections: list[str] = []
    reason = ""
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if m := _SECTION_HEAD.match(line):
            section = m["name"]
            if section in seen_sections:
                raise GoldFormatError(name, line_no, f"{section} appears twice")
            seen_sections.append(section)
            reason = (m["reason"] or "").strip()
            rest = m["rest"].strip()
            blocks.append(_Block("section", line_no, f"{section}|{reason}"))
            if rest and rest.lower() != _NONE:
                raise GoldFormatError(
                    name, line_no, f"expected bullets or '{_NONE}' after {section}:"
                )
            if rest.lower() == _NONE:
                blocks[-1].text += "|none"
            continue
        if section is None:
            if m := _STORY_HEAD.match(line):
                blocks.append(_Block("story", line_no, m[2], int(m[1])))
            elif m := _AC_HEAD.match(line):
                if not any(b.kind == "story" for b in blocks):
                    raise GoldFormatError(name, line_no, "AC before the first STORY")
                blocks.append(_Block("ac", line_no, m[2], int(m[1])))
            elif blocks:
                blocks[-1].text = _join(blocks[-1].text, line)
            else:
                raise GoldFormatError(name, line_no, "expected 'STORY 1:'")
            continue
        if line.startswith("- "):
            blocks.append(_Block("bullet", line_no, line[2:].strip()))
        elif blocks and blocks[-1].kind == "bullet":
            blocks[-1].text = _join(blocks[-1].text, line)
        else:
            raise GoldFormatError(name, line_no, f"expected '- ' bullet under {section}")
    if tuple(seen_sections) != _SECTION_ORDER:
        raise GoldFormatError(
            name,
            1,
            f"sections must be {', '.join(_SECTION_ORDER)} in this order; got {seen_sections}",
        )
    return blocks


def _build(blocks: list[_Block], name: str) -> Requirements:
    stories: list[Story] = []
    criteria: list[AcceptanceCriterion] = []
    nfr: list[NonFunctional] = []
    oos: list[OutOfScope] = []
    questions: list[OpenQuestion] = []
    section, reason, story_id = "", "", ""
    for b in blocks:
        if b.kind == "story":
            if b.number != len(stories) + 1:
                raise GoldFormatError(name, b.line, f"expected STORY {len(stories) + 1}")
            m = _STORY.match(b.text)
            if not m:
                raise GoldFormatError(
                    name, b.line, "story must read 'As a ..., I want ..., so that ...'"
                )
            story_id = f"S{b.number}"
            stories.append(Story(id=story_id, **m.groupdict()))
        elif b.kind == "ac":
            expected = len([c for c in criteria if c.story_id == story_id]) + 1
            if b.number != expected:
                raise GoldFormatError(name, b.line, f"expected AC{expected}")
            m = _AC.match(b.text)
            if not m:
                raise GoldFormatError(
                    name, b.line, "criterion must read 'Given ..., when ..., then ...'"
                )
            criteria.append(
                AcceptanceCriterion(
                    id=f"{story_id}-AC{b.number}", story_id=story_id, **m.groupdict()
                )
            )
        elif b.kind == "section":
            section, reason, *_ = b.text.split("|")
        elif section == "NON-FUNCTIONAL":
            category, _, statement = b.text.partition(":")
            if not statement:
                category, statement = "general", b.text
            nfr.append(
                NonFunctional(
                    id=f"N{len(nfr) + 1}", category=category.strip().lower(), statement=statement
                )
            )
        elif section == "OUT OF SCOPE":
            oos.append(OutOfScope(id=f"X{len(oos) + 1}", statement=b.text, reason=reason))
        else:
            questions.append(
                OpenQuestion(id=f"Q{len(questions) + 1}", question=b.text, origin="gold")
            )
    if not stories:
        raise GoldFormatError(name, 1, "no stories")
    return Requirements(
        stories=stories,
        criteria=criteria,
        open_questions=questions,
        non_functional=nfr,
        out_of_scope=oos,
    )


def load_gold(path: Path | str) -> GoldSet:
    path = Path(path)
    return parse_gold(path.read_text(encoding="utf-8"), name=path.stem)


def load_gold_dir(folder: Path | str) -> dict[str, GoldSet]:
    """All gold files in `folder`, keyed by file stem (for example "01_maintenance")."""
    return {p.stem: load_gold(p) for p in sorted(Path(folder).glob("*.txt"))}
