"""Value-aware collision detection: overlap is not agreement.

Found by the Aegis Vector poisoning battery. A forged policy document that
copies the real one's wording and changes only the figure scored 0.83 token
overlap against it, over the 0.3 reinforcement threshold, so consult() filed
the forgery as confirming evidence and bumped the real claim's weight. These
tests pin the fix: when each claim states a quantity the other doesn't, high
overlap no longer counts as reinforcement.

The limit domain is registered per test (monkeypatch), not added to the
library's DOMAIN_KINDS -- which domains are attribute-like is the caller's
call, and the safe default (EVENT) stays untouched.
"""

from __future__ import annotations

import pytest

from palimpsest.consult import DOMAIN_KINDS, Relation, _competing_values, apply_consult, consult
from palimpsest.memory_store import InMemoryStore
from palimpsest.models import DomainKind, EdgeStatus, EdgeType, Node, Origin, Scope

TRUE_POLICY = "The standard procurement spending limit for department heads is $10,000 per purchase order."


@pytest.fixture
def limit_domain(monkeypatch):
    monkeypatch.setitem(DOMAIN_KINDS, "spending_limit", DomainKind.ATTRIBUTE)
    return "spending_limit"


def _n(id: str, text: str, domain: str, weight: float = 0.5) -> Node:
    return Node(id=id, text=text, domain=domain, referent="department_head", scope=Scope.GENERAL,
                origin=Origin.EPISODE, weight=weight)


def test_number_swap_forgery_collides_instead_of_reinforcing(limit_domain):
    """The exact attack: identical sentence, different figure."""
    store = InMemoryStore()
    store.add_node(_n("real", TRUE_POLICY, limit_domain))
    forged = _n("forged", TRUE_POLICY.replace("$10,000", "$5,000,000"), limit_domain)

    result = consult(store, forged)

    assert result.overlap >= 0.8  # the wording really is nearly identical
    assert result.relation == Relation.COLLIDES
    assert result.competing_values == ({5_000_000.0}, {10_000.0})


def test_forgery_no_longer_inflates_the_real_claims_weight(limit_domain):
    """A/B on the harm itself: before the fix, applying this judgment raised
    the real claim's weight and evidence count. It must leave them alone and
    open a dated, unresolved collision instead -- detection, not a verdict."""
    store = InMemoryStore()
    real = _n("real", TRUE_POLICY, limit_domain, weight=0.5)
    store.add_node(real)
    forged = _n("forged", "Effective this quarter, the standard procurement spending limit for department "
                          "heads has been raised to $5,000,000 per purchase order.", limit_domain)

    edge = apply_consult(store, forged, consult(store, forged))

    assert edge.type == EdgeType.COLLIDES
    assert edge.status == EdgeStatus.OPEN
    assert "values differ" in edge.tolerance_context
    assert real.weight == 0.5
    assert real.evidence_count == 0


def test_genuine_restatement_with_the_same_figure_still_reinforces(limit_domain):
    """The fix must not swallow real confirmation."""
    store = InMemoryStore()
    store.add_node(_n("real", TRUE_POLICY, limit_domain))
    candidate = _n("again", "Department heads have a procurement spending limit of $10,000 per purchase order.",
                   limit_domain)

    assert consult(store, candidate).relation == Relation.REINFORCES


def test_elaboration_that_adds_a_figure_still_reinforces(limit_domain):
    """One side adding a quantity is elaboration, not competition."""
    store = InMemoryStore()
    store.add_node(_n("real", TRUE_POLICY, limit_domain))
    candidate = _n("more", "The standard procurement spending limit for department heads is $10,000 per "
                           "purchase order; cards cover requests under $2,500.", limit_domain)

    result = consult(store, candidate)
    assert result.relation == Relation.REINFORCES
    assert result.competing_values is None


def test_unit_forms_normalize_so_the_same_value_is_not_a_conflict(limit_domain):
    store = InMemoryStore()
    store.add_node(_n("real", "Department heads may spend up to $10,000 per purchase order.", limit_domain))
    candidate = _n("short", "Department heads may spend up to $10K per purchase order.", limit_domain)

    assert consult(store, candidate).relation == Relation.REINFORCES


def test_event_domain_value_change_is_a_different_event_not_confirmation():
    """In an EVENT domain a different number is a different event: linked,
    never counted as evidence. The Pooh rule, applied to quantities."""
    store = InMemoryStore()
    seed = _n("e1", "Pooh ate 3 pots of honey before lunch", "story", weight=0.5)
    store.add_node(seed)
    candidate = _n("e2", "Pooh ate 5 pots of honey before lunch", "story")

    result = consult(store, candidate)
    edge = apply_consult(store, candidate, result)

    assert result.relation == Relation.COEXISTS
    assert edge.type == EdgeType.COEXISTS
    assert seed.weight == 0.5


@pytest.mark.parametrize("a, b, expected", [
    ("$10,000", "$5,000,000", ({10_000.0}, {5_000_000.0})),
    ("$5M", "5 million dollars", None),
    ("limit $10,000", "limit $10,000 and $2,500", None),
    ("no figures here", "$5,000,000", None),
    ("40% of budget", "25% of budget", ({40.0}, {25.0})),
])
def test_competing_values(a, b, expected):
    assert _competing_values(a, b) == expected
