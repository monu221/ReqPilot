import pytest

from reqpilot.config import REPO_ROOT
from reqpilot.gold import GoldFormatError, load_gold_dir, parse_gold

GOLD = REPO_ROOT / "data" / "gold"

MINIMAL = """\
STORY 1: As a nurse, I want to report a fault,
so that it is fixed.
AC1: Given I am logged in, when I submit,
then the request is saved.

NON-FUNCTIONAL: none stated

OUT OF SCOPE: none stated

OPEN QUESTIONS:
- Who triages
  the request?
"""


def test_every_gold_file_parses_with_expected_counts():
    sets = load_gold_dir(GOLD)
    counts = {
        name: (
            len(g.requirements.stories),
            len(g.requirements.criteria),
            len(g.requirements.non_functional),
            len(g.requirements.out_of_scope),
            len(g.requirements.open_questions),
        )
        for name, g in sets.items()
    }
    assert counts == {
        "01_maintenance": (6, 8, 0, 0, 7),
        "02_procurement": (7, 12, 0, 0, 7),
        "03_lab_results": (6, 9, 2, 1, 8),
    }


def test_lab_results_sections():
    req = load_gold_dir(GOLD)["03_lab_results"].requirements
    assert [n.category for n in req.non_functional] == ["volume", "latency"]
    assert req.out_of_scope[0].reason == "unchanged process"
    assert req.out_of_scope[0].statement.startswith("Critical results are still phoned")
    assert req.stories[0].role == "treating clinician at another provider"


def test_minimal_gold_joins_wrapped_lines():
    req = parse_gold(MINIMAL).requirements
    s = req.stories[0]
    assert (s.id, s.role, s.goal, s.benefit) == ("S1", "nurse", "to report a fault", "it is fixed")
    c = req.criteria[0]
    assert (c.id, c.story_id, c.given, c.when, c.then) == (
        "S1-AC1",
        "S1",
        "I am logged in",
        "I submit",
        "the request is saved",
    )
    assert req.open_questions[0].question == "Who triages the request?"
    assert req.open_questions[0].origin == "gold"
    assert req.non_functional == [] and req.out_of_scope == []


def test_numbers_with_commas_do_not_split_criteria():
    text = MINIMAL.replace(
        "Given I am logged in, when I submit,\nthen the request is saved.",
        "Given a request between 5,000 and 50,000 EUR, when it is submitted, "
        "then finance approves.",
    )
    c = parse_gold(text).requirements.criteria[0]
    assert c.given == "a request between 5,000 and 50,000 EUR"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda t: t.replace("NON-FUNCTIONAL: none stated\n", ""), "sections must be"),
        (lambda t: t.replace("STORY 1: As a nurse", "STORY 2: As a nurse"), "expected STORY 1"),
        (lambda t: t.replace("AC1:", "AC2:"), "expected AC1"),
        (lambda t: t.replace("I want", "I need"), "As a ..., I want"),
        (lambda t: t.replace("when I submit", "and I submit"), "Given ..., when"),
        (lambda t: t.replace("- Who triages", "Who triages"), "bullet"),
        (lambda t: t.replace("OUT OF SCOPE: none stated", "OUT OF SCOPE: maybe"), "none stated"),
        (lambda t: t + "\nOPEN QUESTIONS:\n- again?\n", "appears twice"),
    ],
)
def test_format_errors_name_the_problem(change, message):
    with pytest.raises(GoldFormatError, match=message):
        parse_gold(change(MINIMAL))
