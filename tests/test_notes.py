from reqpilot.config import REPO_ROOT
from reqpilot.notes import numbered, split_notes

NOTES = REPO_ROOT / "data" / "notes"


def _texts(text: str) -> list[str]:
    return [s.text for s in split_notes(text)]


def test_empty_input_gives_no_sentences():
    assert split_notes("") == []
    assert split_notes("\n  \n") == []


def test_bullets_are_numbered_and_markers_removed():
    s = split_notes("- first\n* second\n• third\n1. fourth\n2) fifth")
    assert [x.text for x in s] == ["first", "second", "third", "fourth", "fifth"]
    assert [x.number for x in s] == [1, 2, 3, 4, 5]
    assert [x.line for x in s] == [1, 2, 3, 4, 5]


def test_wrapped_lowercase_line_continues_the_item():
    text = "Attendees: lab manager (Priya), data protection\nofficer (Mrs. Weber)\n\n- a point"
    s = split_notes(text)
    assert s[0].text == "Attendees: lab manager (Priya), data protection officer (Mrs. Weber)"
    assert s[0].is_header
    assert s[1].text == "a point" and not s[1].is_header


def test_indented_wrapped_bullet_line_continues_the_bullet():
    assert _texts("- a long point that\n  Wraps here\n- next") == [
        "a long point that Wraps here",
        "next",
    ]


def test_sub_bullets_link_to_their_parent():
    s = split_notes(
        "- approval depends on amount\n  - under 5,000 EUR\n  - over 5,000 EUR\n- other"
    )
    assert [x.parent for x in s] == [None, 1, 1, None]


def test_nested_sub_bullets_link_to_nearest_parent():
    s = split_notes("- a\n  - b\n    - c\n  - d")
    assert [x.parent for x in s] == [None, 1, 2, 1]


def test_prose_is_split_at_sentence_ends_but_not_at_abbreviations():
    text = "Dr. Lin wants alerts. Mrs. Weber agreed, e.g. by email. Is it needed? Yes."
    assert _texts(text) == [
        "Dr. Lin wants alerts.",
        "Mrs. Weber agreed, e.g. by email.",
        "Is it needed?",
        "Yes.",
    ]


def test_capitalised_line_after_prose_starts_a_new_sentence():
    assert _texts("Meeting with finance\nThey want a report") == [
        "Meeting with finance",
        "They want a report",
    ]


def test_header_only_before_first_bullet():
    s = split_notes("Workshop: x\n- Lena: a point\nNote: later")
    assert [x.is_header for x in s] == [True, False, False]


def test_crlf_and_tabs_are_handled():
    s = split_notes("- a\r\n\t- b\r\n")
    assert [x.text for x in s] == ["a", "b"]
    assert s[1].parent == 1


def test_numbered_format():
    assert numbered(split_notes("- a\n- b")) == "[1] a\n[2] b"


def test_bundled_notes_split_as_expected():
    counts = {p.stem: len(split_notes(p.read_text(encoding="utf-8"))) for p in NOTES.glob("*.txt")}
    assert counts == {"01_maintenance": 12, "02_procurement": 17, "03_lab_results": 15}


def test_procurement_thresholds_keep_their_parent():
    s = split_notes((NOTES / "02_procurement.txt").read_text(encoding="utf-8"))
    by_number = {x.number: x for x in s}
    assert by_number[7].text == "Marc: approval depends on amount"
    assert [by_number[n].parent for n in (8, 9, 10)] == [7, 7, 7]
    assert by_number[3].text.endswith("department head of radiology (Dr. Okafor), IT (Tom)")
