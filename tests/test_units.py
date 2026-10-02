"""Quantities carry units: "30 days" is not "$500", and "three days" is "72 hours".

Found by the benchmark: the rules called a claim about a 30-day receipt deadline a collision with a $500
allowance, because both stated a figure the other didn't. Competition needs a comparable pair.
"""

from __future__ import annotations

import pytest

from palimpsest.consult import (
    DOMAIN_KINDS, Quantity, Relation, _comparable, _competing_values, _extract, _omits_value, _quantities, consult,
)
from palimpsest.memory_store import InMemoryStore
from palimpsest.models import DomainKind, Node, Origin, Scope


def q(text):
    return sorted((x.value, x.dim) for x in _extract(text))


@pytest.mark.parametrize("text, expected", [
    ("$10,000", [(10_000.0, "usd")]),
    ("$5M", [(5_000_000.0, "usd")]),
    ("5 million dollars", [(5_000_000.0, "usd")]),
    ("five hundred dollars annually", [(500.0, "usd")]),
    ("up to $500 per year", [(500.0, "usd")]),
    ("40% of budget", [(40.0, "pct")]),
    ("three days", [(259_200.0, "duration")]),
    ("72 hours", [(259_200.0, "duration")]),
    ("within 4 business hours", [(14_400.0, "duration")]),
    ("four business hours", [(14_400.0, "duration")]),
    ("twenty-one days", [(1_814_400.0, "duration")]),
    ("6:40 am", [(400.0, "clock")]),
    ("06:40", [(400.0, "clock")]),
    ("8 pm", [(1200.0, "clock")]),
    ("20:00", [(1200.0, "clock")]),
    ("12 am", [(0.0, "clock")]),
    ("12 pm", [(720.0, "clock")]),
    ("the 14th", [(14.0, "day")]),
    ("March 3", [(303.0, "date")]),
    ("0.4 mm", [(0.0004, "length")]),
    ("20 miles per hour", [(32_186.88, "length")]),
    ("minus 70 degrees", [(-70.0, "temp")]),
    ("-70 degrees Celsius", [(-70.0, "temp")]),
    ("at least 14 characters", [(14.0, "chars")]),
    ("PostgreSQL 16", [(16.0, None)]),
    ("two signatures", [(2.0, None)]),
    ("borrowed for one day", [(86_400.0, "duration")]),
    # not quantities
    ("Q3 limit", []),
    ("IPv6 and Q3", []),
    ("one project", []),                 # "one" alone is a pronoun
    ("a hundred reasons", []),           # a bare scale word is not a number
    ("no figures here", []),
])
def test_extraction(text, expected):
    assert q(text) == sorted(expected)


def test_a_clock_time_is_not_read_again_as_bare_numbers():
    assert q("Our flight leaves at 6:40 am on the 14th.") == [(14.0, "day"), (400.0, "clock")]


def test_quantities_keeps_its_plain_number_view_in_base_units():
    assert _quantities("$10,000 and 3 days") == {10_000.0, 259_200.0}


@pytest.mark.parametrize("a, b, expected", [
    (Quantity(1, "usd"), Quantity(2, "usd"), True),
    (Quantity(1, "usd"), Quantity(2, "duration"), False),
    (Quantity(400, "clock"), Quantity(2700, "duration"), False),
    (Quantity(1, None), Quantity(2, "usd"), True),    # unknown unit: assumed comparable, the conservative reading
    (Quantity(1, None), Quantity(2, None), True),
])
def test_comparable(a, b, expected):
    assert _comparable(a, b) is expected


@pytest.mark.parametrize("a, b, expected", [
    ("$10,000", "$5,000,000", ({10_000.0}, {5_000_000.0})),
    ("$5M", "5 million dollars", None),                                   # same figure, other form
    ("three days", "72 hours", None),                                     # same duration, other unit
    ("8 pm", "20:00", None),
    ("within 3 days", "within 5 days", ({259_200.0}, {432_000.0})),
    ("limit $10,000", "limit $10,000 and $2,500", None),                  # elaboration is not competition
    ("40% of budget", "25% of budget", ({40.0}, {25.0})),
    ("Q3 limit $10,000", "Q4 limit $10,000", None),
    # the benchmark's finding: figures of different kinds do not compete
    ("Receipts must be submitted within 30 days.", "Employees may expense up to $500 per year.", None),
    ("Check-in closes 45 minutes before departure.", "Our flight leaves at 6:40 am on the 14th.", None),
    ("Prints are removed after the bed cools below 30 degrees.", "The printer needs a 0.4 mm nozzle.", None),
    ("Raid signups close 24 hours before the start.", "The raid starts at 8 pm on Fridays.", None),
    # but the competing pair is still found among other figures
    ("Travel booked 14 days ahead; limit $5,000,000.", "Limit $10,000.", ({5_000_000.0}, {10_000.0})),
    # a bare number could be anything, so it competes as it always did
    ("PostgreSQL 16", "PostgreSQL 17", ({16.0}, {17.0})),
])
def test_competing_values(a, b, expected):
    assert _competing_values(a, b) == expected


@pytest.mark.parametrize("candidate, existing, expected", [
    ("The limit has been removed.", "The limit is $10,000.", {10_000.0}),
    ("Receipts are due within 30 days.", "Allowance is up to $500 per year.", {500.0}),   # a figure of another kind
    ("The limit is $5,000.", "The limit is $10,000.", None),                               # states a comparable value
    ("The limit is 5000.", "The limit is $10,000.", None),                                 # bare number: could be the value
    ("Anything goes.", "Anything goes.", None),                                            # nothing was dropped
])
def test_omits_value(candidate, existing, expected):
    assert _omits_value(candidate, existing) == expected


# -- through consult() -----------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def attribute_domain(monkeypatch):
    monkeypatch.setitem(DOMAIN_KINDS, "units_domain", DomainKind.ATTRIBUTE)


def _node(id, text):
    return Node(id=id, text=text, domain="units_domain", referent="r", scope=Scope.GENERAL, origin=Origin.EPISODE)


def _consult(held, claim):
    store = InMemoryStore()
    store.add_node(_node("held", held))
    return consult(store, _node("new", claim))


def test_a_deadline_beside_an_allowance_is_no_longer_a_collision():
    """Before units: "within 30 days" and "$500" each stated a figure the other didn't, so this was COLLIDES."""
    result = _consult("Remote employees may expense up to $500 per year for home office equipment.",
                      "Receipts for home office purchases must be submitted within 30 days.")
    assert result.relation == Relation.UNCONFIRMED and result.review_needed and result.competing_values is None


def test_a_different_figure_of_the_same_kind_still_collides():
    result = _consult("Remote employees may expense up to $500 per year for home office equipment.",
                      "Remote employees may expense up to $5,000 per year for home office equipment.")
    assert result.relation == Relation.COLLIDES and result.competing_values == ({5_000.0}, {500.0})


def test_the_same_duration_in_another_unit_still_reinforces():
    result = _consult("Support tickets must get a first response within 4 business hours.",
                      "Support tickets must get a first response within four business hours.")
    assert result.relation == Relation.REINFORCES


def test_a_changed_clock_time_collides():
    result = _consult("The guild raid starts at 8 pm server time on Fridays.",
                      "The guild raid starts at 9 pm server time on Fridays.")
    assert result.relation == Relation.COLLIDES


def test_a_time_beside_a_duration_does_not_collide():
    result = _consult("The guild raid starts at 8 pm server time on Fridays.",
                      "Raid signups close 24 hours before the guild raid starts.")
    assert result.relation != Relation.COLLIDES


@pytest.mark.parametrize("a, b, expected", [
    ("The backups run at 02:00 UTC.", "The database is PostgreSQL 16.", None),     # a bare number is not known to be a time
    ("PostgreSQL 16", "PostgreSQL 17", ({16.0}, {17.0})),                           # bare against bare still competes
    ("$10,000", "$5,000,000", ({10_000.0}, {5_000_000.0})),
    ("within 3 days", "$500 per year", None),
])
def test_strict_competition_needs_the_same_known_kind(a, b, expected):
    assert _competing_values(a, b, strict=True) == expected


def test_the_default_stays_conservative_about_bare_numbers():
    assert _competing_values("The backups run at 02:00 UTC.", "The database is PostgreSQL 16.") is not None


@pytest.mark.parametrize("a, b", [
    ("serviced every 500 running hours", "due at 500 hours of running time"),
    ("four operating hours", "4 hours"),
    ("within 4 business hours", "within four working hours"),
    ("a 3 day wait", "a wait of three days"),
])
def test_a_descriptive_word_before_the_unit_does_not_change_the_figure(a, b):
    assert _quantities(a) == _quantities(b) and _competing_values(a, b) is None


def test_a_word_after_a_bare_number_that_is_not_a_unit_leaves_it_bare():
    assert q("14 new employees") == [(14.0, None)]
    assert q("the 3 big blue boxes") == [(3.0, None)]
