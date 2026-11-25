"""Export tests. Golden files in tests/data/export are made from the FAKE demo sets.

To regenerate them after a deliberate format change: set UPDATE_GOLDEN=1 and run pytest.
"""

import csv
import io
import os

import pytest

from reqpilot import export, workflow
from reqpilot.config import REPO_ROOT
from reqpilot.demo import DEMO_LABEL, load_demo
from reqpilot.models import StoryStatus
from reqpilot.notes import split_notes

GOLDEN = REPO_ROOT / "tests" / "data" / "export"
A = StoryStatus.ACCEPTED


def _workspace(name, accept=all, demo=True):
    d = load_demo(name)
    ws = workflow.start(d.notes, d)
    workflow.write_and_review(ws)
    for item in [*ws.req.stories, *ws.req.non_functional, *ws.req.out_of_scope]:
        if accept is all or item.id in accept:
            workflow.set_status(ws, item.id, A)
    workflow.make_test_cases(ws)
    if not demo:
        ws.demo = None
    return ws


def _check_golden(name: str, text: str):
    path = GOLDEN / name
    if os.environ.get("UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    assert text == path.read_text(encoding="utf-8"), f"{name} changed; see module docstring"


@pytest.mark.parametrize("name", ["01_maintenance", "03_lab_results"])
def test_jira_csv_golden(name):
    ws = _workspace(name)
    _check_golden(
        f"{name}_jira.csv", export.to_jira_csv(ws.req, ws.test_cases, ws.sentences, demo=True)
    )


@pytest.mark.parametrize("name", ["01_maintenance", "03_lab_results"])
def test_markdown_golden(name):
    _check_golden(f"{name}.md", export.workspace_markdown(_workspace(name)))


def _rows(text):
    return list(csv.reader(io.StringIO(text)))


def test_csv_has_jira_columns_and_only_accepted_items():
    ws = _workspace("03_lab_results", accept={"S1", "S4", "N1"})
    rows = _rows(export.to_jira_csv(ws.req, ws.test_cases, ws.sentences, demo=True))
    assert rows[0] == export.JIRA_COLUMNS
    assert [r[3] for r in rows[1:]] == ["Story", "Story", "Task"]
    assert "S1-AC1: Given a lab result is validated" in rows[1][2]
    assert "T1:" in rows[1][1]
    assert rows[3][5] == "non-functional"


def test_demo_marking_in_csv_and_markdown():
    ws = _workspace("02_procurement", accept={"S1"})
    rows = _rows(export.to_jira_csv(ws.req, ws.test_cases, ws.sentences, demo=True))
    assert rows[1][1].startswith(DEMO_LABEL.upper())
    assert rows[1][5] == "demo-data"
    assert DEMO_LABEL in export.workspace_markdown(ws)


def test_live_export_is_not_marked_demo():
    ws = _workspace("02_procurement", accept={"S1"}, demo=False)
    text = export.to_jira_csv(ws.req, ws.test_cases, ws.sentences)
    assert "demo" not in text.lower()
    assert DEMO_LABEL not in export.workspace_markdown(ws)


def test_nothing_accepted_exports_header_only():
    ws = _workspace("02_procurement", accept=set())
    assert not export.has_accepted(ws.req)
    assert _rows(export.to_jira_csv(ws.req, [], ws.sentences)) == [export.JIRA_COLUMNS]
    md = export.workspace_markdown(ws)
    assert "None accepted." in md and "Open questions: 7" in md


def test_markdown_carries_quality_notes():
    md = export.workspace_markdown(_workspace("02_procurement"))
    assert "Reviewer, traceable: Sentence 16 is about the ERP export" in md
    assert "Python check (S4-AC1): number(s) not in the notes, possibly invented: 3" in md


def test_long_summary_is_cut_for_jira():
    ws = _workspace("02_procurement", accept={"S1"})
    ws.req.stories[0].goal = "x" * 400
    rows = _rows(export.to_jira_csv(ws.req, [], split_notes(ws.notes)))
    assert len(rows[1][0]) == export.JIRA_SUMMARY_MAX and rows[1][0].endswith("…")


def test_csv_quotes_commas_and_newlines():
    ws = _workspace("02_procurement", accept={"S2"})
    rows = _rows(export.to_jira_csv(ws.req, ws.test_cases, ws.sentences))
    assert rows[1][2].count("\n") == 2  # three criteria in one cell
    assert "5,000 EUR" in rows[1][2]
