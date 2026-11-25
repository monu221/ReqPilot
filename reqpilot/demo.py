"""Bundled examples: note sets in data/notes with FAKE responses in examples/demo.

The responses are hand-written demo data, not real model output (examples/demo/README.md).
Loading them makes no AI call and needs no API key.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reqpilot.config import REPO_ROOT
from reqpilot.llm import FAKE_LABEL, load_fake

DEMO_DIR = REPO_ROOT / "examples" / "demo"
NOTES_DIR = REPO_ROOT / "data" / "notes"
DEMO_LABEL = "Demo data, not real model output"
KINDS = ("writer", "reviewer", "test_cases")

TITLES = {
    "01_maintenance": "Equipment maintenance requests",
    "02_procurement": "Purchase request approvals",
    "03_lab_results": "Lab results to a national health record",
}


@dataclass(frozen=True)
class DemoSet:
    name: str
    title: str
    notes: str
    responses: dict[str, dict[str, Any]]  # kind -> fake file (with "content")
    label: str = DEMO_LABEL

    def content(self, kind: str) -> dict[str, Any]:
        return self.responses[kind]["content"]


def demo_names() -> list[str]:
    return sorted(p.name for p in DEMO_DIR.iterdir() if p.is_dir())


def load_demo(name: str, demo_dir: Path = DEMO_DIR, notes_dir: Path = NOTES_DIR) -> DemoSet:
    responses = {kind: load_fake(demo_dir / name / f"{kind}.json") for kind in KINDS}
    for kind, data in responses.items():
        if data.get("set") != name or data.get("kind") != kind:
            raise ValueError(f"{name}/{kind}.json names the wrong set or kind")
    return DemoSet(
        name=name,
        title=TITLES.get(name, name),
        notes=(notes_dir / f"{name}.txt").read_text(encoding="utf-8"),
        responses=responses,
    )


__all__ = ["DEMO_LABEL", "FAKE_LABEL", "DemoSet", "demo_names", "load_demo"]
