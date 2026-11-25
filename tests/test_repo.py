"""Repository hygiene: the key stays out of git, and the data folders line up."""

import subprocess

from reqpilot.config import REPO_ROOT

GOLD_SECTIONS = ("NON-FUNCTIONAL:", "OUT OF SCOPE", "OPEN QUESTIONS:")


def test_env_file_is_git_ignored():
    result = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=REPO_ROOT, check=False)
    assert result.returncode == 0, ".env must be listed in .gitignore"


def test_every_note_set_has_a_gold_file_and_vice_versa():
    notes = {p.name for p in (REPO_ROOT / "data" / "notes").glob("*.txt")}
    gold = {p.name for p in (REPO_ROOT / "data" / "gold").glob("*.txt")}
    assert notes, "no note sets found"
    assert notes == gold


def test_note_files_are_not_empty():
    for path in (REPO_ROOT / "data" / "notes").glob("*.txt"):
        assert path.read_text(encoding="utf-8").strip(), f"{path.name} is empty"


def test_every_gold_file_has_all_sections():
    for path in (REPO_ROOT / "data" / "gold").glob("*.txt"):
        text = path.read_text(encoding="utf-8")
        assert "STORY 1:" in text, path.name
        for section in GOLD_SECTIONS:
            assert section in text, f"{path.name} lacks {section}"
