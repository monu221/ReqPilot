import pytest

from reqpilot.checks import Check, has_measure, numbers_in, run_checks
from reqpilot.config import REPO_ROOT
from reqpilot.gold import load_gold_dir
from reqpilot.models import AcceptanceCriterion, NonFunctional, OutOfScope, Requirements, Story
from reqpilot.notes import split_notes

NOTES = split_notes("- nurses report faults\n- requests under 5,000 EUR need one approval")


def _story(goal="to report faults", benefit="they are fixed", sources=(1,), id_="S1"):
    return Story(
        id=id_, role="ward nurse", goal=goal, benefit=benefit, source_sentences=list(sources)
    )


def _ac(then="the request is saved", given="a fault", when="I submit"):
    return AcceptanceCriterion(id="S1-AC1", story_id="S1", given=given, when=when, then=then)


def _checks(req: Requirements, sentences=NOTES) -> list[tuple[Check, str]]:
    return [(f.check, f.item_id) for f in run_checks(req, sentences)]


def test_clean_story_passes():
    assert _checks(Requirements(stories=[_story()], criteria=[_ac()])) == []


# --- vague words -------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["a user-friendly form", "faults etc.", "as appropriate"])
def test_vague_words_in_stories_fail(text):
    assert _checks(Requirements(stories=[_story(benefit=text)])) == [(Check.VAGUE_WORD, "S1")]


def test_vague_words_in_criteria_fail():
    req = Requirements(stories=[_story()], criteria=[_ac(then="an easy form is shown")])
    assert _checks(req) == [(Check.VAGUE_WORD, "S1-AC1")]


def test_vague_word_must_be_a_whole_word():
    req = Requirements(stories=[_story(benefit="the uneasy feeling goes")])
    assert _checks(req) == []


# --- performance words without a measure -------------------------------------------------


def test_performance_word_without_measure_fails():
    req = Requirements(stories=[_story()], criteria=[_ac(then="results load quickly")])
    assert _checks(req) == [(Check.UNMEASURED_PERFORMANCE, "S1-AC1")]


def test_performance_word_with_measure_passes():
    notes = split_notes("- results load within 2 seconds")
    req = Requirements(stories=[_story()], criteria=[_ac(then="results load fast, within 2 s")])
    assert _checks(req, notes) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("within 2 s", True),
        ("under 200 ms", True),
        ("99.9%", True),
        ("3,000 results per day", True),
        ("10 per hour", True),
        ("5,000 EUR", True),
        ("near real time", False),
        ("3 approvers", False),
        ("version 2", False),
    ],
)
def test_has_measure(text, expected):
    assert has_measure(text) is expected


# --- two goals ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "goal",
    [
        "to report faults and see their status",
        "to report faults and to attach photos",
        "to report faults and also get reminders",
        "to report faults and then track them",
    ],
)
def test_goal_with_two_actions_fails(goal):
    assert _checks(Requirements(stories=[_story(goal=goal)])) == [(Check.TWO_GOALS, "S1")]


@pytest.mark.parametrize(
    "goal",
    [
        "to see open requests per team and how long each has been open",
        "messages kept and retried when the hub is down",
        "to report faults on wards and theatres",
    ],
)
def test_and_inside_one_goal_passes(goal):
    assert _checks(Requirements(stories=[_story(goal=goal)])) == []


# --- numbers not in the notes ------------------------------------------------------------


def test_number_in_notes_passes_even_if_formatted_differently():
    req = Requirements(stories=[_story()], criteria=[_ac(given="a request under 5000 EUR")])
    assert _checks(req) == []


def test_invented_number_fails():
    req = Requirements(stories=[_story()], criteria=[_ac(then="approval within 3 days")])
    findings = run_checks(req, NOTES)
    assert [(f.check, f.item_id) for f in findings] == [(Check.UNKNOWN_NUMBER, "S1-AC1")]
    assert "3" in findings[0].message


def test_numbers_in():
    assert numbers_in("5,000 EUR, 50,000 EUR, 2.50 h, S1 and 3") == {"5000", "50000", "2.5", "3"}


# --- sources -----------------------------------------------------------------------------


def test_story_without_source_fails():
    assert _checks(Requirements(stories=[_story(sources=())])) == [(Check.NO_SOURCE, "S1")]


def test_story_citing_missing_sentence_fails():
    findings = run_checks(Requirements(stories=[_story(sources=(1, 9))]), NOTES)
    assert [(f.check, f.message) for f in findings] == [
        (Check.NO_SOURCE, "story cites sentence(s) not in the notes: 9")
    ]


def test_without_notes_number_and_source_checks_are_skipped():
    req = Requirements(stories=[_story(sources=(), benefit="saves 7 hours")])
    assert _checks(req, sentences=None) == []


def test_out_of_scope_needs_source():
    req = Requirements(out_of_scope=[OutOfScope(id="X1", statement="phone calls stay")])
    assert _checks(req) == [(Check.NO_SOURCE, "X1")]


# --- non-functional items ----------------------------------------------------------------


def test_non_functional_without_measure_fails():
    nfr = NonFunctional(
        id="N1", category="latency", statement="near real time", source_sentences=[1]
    )
    assert _checks(Requirements(non_functional=[nfr])) == [(Check.UNMEASURED_NON_FUNCTIONAL, "N1")]


def test_non_functional_with_measure_passes():
    notes = split_notes("- about 3,000 results per day")
    nfr = NonFunctional(
        id="N1", category="volume", statement="3,000 results per day", source_sentences=[1]
    )
    assert _checks(Requirements(non_functional=[nfr]), notes) == []


# --- gold files --------------------------------------------------------------------------


def test_gold_stories_and_criteria_pass_all_checks():
    """Gold is the reference answer, so it must meet the rules (gold has no sources)."""
    for name, gold in load_gold_dir(REPO_ROOT / "data" / "gold").items():
        notes = split_notes((REPO_ROOT / "data" / "notes" / f"{name}.txt").read_text("utf-8"))
        story_and_criterion_ids = {s.id for s in gold.requirements.stories} | {
            c.id for c in gold.requirements.criteria
        }
        problems = [
            f
            for f in run_checks(gold.requirements, notes)
            if f.check != Check.NO_SOURCE and f.item_id in story_and_criterion_ids
        ]
        assert problems == [], name


def test_gold_lab_results_flags_unmeasured_latency_only():
    gold = load_gold_dir(REPO_ROOT / "data" / "gold")["03_lab_results"]
    notes = split_notes(
        (REPO_ROOT / "data" / "notes" / "03_lab_results.txt").read_text(encoding="utf-8")
    )
    flagged = [
        (f.check, f.item_id)
        for f in run_checks(gold.requirements, notes)
        if f.item_id.startswith("N")
    ]
    assert flagged == [
        (Check.NO_SOURCE, "N1"),
        (Check.UNMEASURED_NON_FUNCTIONAL, "N2"),
        (Check.NO_SOURCE, "N2"),
    ]
