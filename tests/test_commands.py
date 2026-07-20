import pytest

from fantasy_draft.draft.commands import bulk_pick_queries, pick_query


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("someone got Gibbs", "Gibbs"),
        ("Gibbs picked", "Gibbs"),
        ("Gibbs got picked", "Gibbs"),
        ("they took Ja'Marr Chase", "Ja'Marr Chase"),
        ("draft Puka Nacua", "Puka Nacua"),
        ("Brock Bowers is gone.", "Brock Bowers"),
    ],
)
def test_pick_query_recognizes_conservative_selection_phrases(text, expected):
    assert pick_query(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Who should I take?",
        "Who picked Gibbs?",
        "Compare Gibbs and Bijan",
        "Gibbs",
    ],
)
def test_pick_query_does_not_turn_questions_or_bare_names_into_mutations(text):
    assert pick_query(text) is None


def test_bulk_pick_queries_accept_common_catch_up_formats():
    assert bulk_pick_queries("Gibbs, Chase picked; they took Bowers") == [
        "Gibbs",
        "Chase",
        "Bowers",
    ]
    assert bulk_pick_queries("1. Gibbs\n2) Bijan\n- Puka") == [
        "Gibbs",
        "Bijan",
        "Puka",
    ]
