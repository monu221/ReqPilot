"""Split meeting notes into numbered sentences (docs/method.md, section 1).

Notes are usually bullet lists with a few header lines, but pasted prose must work too.

Rules:
- A bullet (`-`, `*`, `•`, `1.`, `1)`) starts a new item. Its marker is removed.
- A line after a blank line starts a new item.
- Any other line continues the previous item if it starts in lower case or is indented
  (a wrapped line); otherwise it starts a new item.
- Each item is then split at sentence ends (`.`, `!`, `?` followed by a capital letter),
  except after common abbreviations such as "Dr." or "e.g.".
- A bullet indented deeper than the bullet above it gets that bullet as its `parent`, so
  "under 5,000 EUR: department head only" keeps its link to "approval depends on amount".
- `Key: value` lines before the first bullet (Workshop, Organisation, Attendees) are marked
  as headers. They can be cited, but are not reported as unused sentences.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

_BULLET = re.compile(r"^(?P<indent>[ \t]*)(?:[-*•]|\d{1,3}[.)])[ \t]+(?P<text>.*)$")
_HEADER = re.compile(r"^[A-Z][A-Za-z /&-]{0,30}:\s")
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]?\s+(?=[\"'(]?[A-Z0-9])")
_ABBREVIATIONS = (
    "dr.",
    "mr.",
    "mrs.",
    "ms.",
    "prof.",
    "e.g.",
    "i.e.",
    "etc.",
    "vs.",
    "no.",
    "approx.",
    "ca.",
    "incl.",
    "st.",
)


class Sentence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    number: int = Field(ge=1)
    text: str = Field(min_length=1)
    line: int = Field(ge=1, description="Line in the notes where the sentence starts")
    parent: int | None = Field(default=None, description="Number of the enclosing bullet")
    is_header: bool = False


class _Item:
    def __init__(self, text: str, line: int, indent: int, bullet: bool, header: bool):
        self.text = text
        self.line = line
        self.indent = indent
        self.bullet = bullet
        self.header = header
        self.parent_item: _Item | None = None
        self.first_number = 0


def _indent_width(s: str) -> int:
    return len(s.expandtabs(4)) - len(s.expandtabs(4).lstrip())


def _items(text: str) -> list[_Item]:
    items: list[_Item] = []
    after_blank = True
    seen_bullet = False
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            after_blank = True
            continue
        m = _BULLET.match(raw)
        if m:
            seen_bullet = True
            items.append(_Item(m["text"].strip(), line_no, _indent_width(m["indent"]), True, False))
        else:
            stripped = raw.strip()
            indented = _indent_width(raw) > 0
            continues = (
                items
                and not after_blank
                and (stripped[0].islower() or indented)
                and not (not seen_bullet and _HEADER.match(raw))
            )
            if continues:
                items[-1].text = f"{items[-1].text} {stripped}"
            else:
                header = not seen_bullet and bool(_HEADER.match(raw))
                items.append(_Item(stripped, line_no, 0, False, header))
        after_blank = False
    _link_parents(items)
    return items


def _link_parents(items: list[_Item]) -> None:
    stack: list[_Item] = []
    for item in items:
        if not item.bullet:
            stack.clear()
            continue
        while stack and stack[-1].indent >= item.indent:
            stack.pop()
        item.parent_item = stack[-1] if stack else None
        stack.append(item)


def _split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    for m in _SENTENCE_END.finditer(text):
        candidate = text[start : m.start()].rstrip()
        last_word = candidate.rsplit(None, 1)[-1].lower() if candidate else ""
        if last_word.endswith(_ABBREVIATIONS) or re.fullmatch(r"[a-z]\.", last_word):
            continue
        parts.append(text[start : m.end()].strip())
        start = m.end()
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


def split_notes(text: str) -> list[Sentence]:
    """Number the sentences in `text`, starting at 1."""
    sentences: list[Sentence] = []
    for item in _items(text):
        parent = item.parent_item.first_number if item.parent_item else None
        for i, part in enumerate(_split_sentences(item.text)):
            number = len(sentences) + 1
            if i == 0:
                item.first_number = number
            sentences.append(
                Sentence(
                    number=number, text=part, line=item.line, parent=parent, is_header=item.header
                )
            )
    return sentences


def numbered(sentences: list[Sentence]) -> str:
    """The sentences as `[n] text` lines, as given to the writer and reviewer."""
    return "\n".join(f"[{s.number}] {s.text}" for s in sentences)
