"""Exceptions that change a number: never a collision, never silent.

The dog/Rex rule stays: a general claim and a specific instance about the same
referent never collide. But an instance claim that states a different figure
than its general rule is the shape a forged claim takes to slip under collision
detection ("for the Q3 IT refresh only, department heads may approve up to
$5,000,000"). These tests pin the middle path: the edge stays SCOPE_PARENT,
weights stay untouched, and the edge is marked REVIEW_NEEDED so it can't pass
unseen.
"""

from __future__ import annotations

import pytest

from palimpsest.consult import DOMAIN_KINDS, Relation, apply_consult, consult, pending_reviews
from palimpsest.memory_store import InMemoryStore
from palimpsest.models import DomainKind, EdgeStatus, EdgeType, Node, Origin, Scope

GENERAL_RULE = "Department heads may approve purchase orders up to $10,000."
FORGED_EXCEPTION = "For the Q3 IT refresh project only, department heads may approve purchase orders up to $5,000,000."


@pytest.fixture
def limit_domain(monkeypatch):
    monkeypatch.setitem(DOMAIN_KINDS, "spending_limit", DomainKind.ATTRIBUTE)
    return "spending_limit"


def _n(id: str, text: str, domain: str, scope: Scope, weight: float = 0.5) -> Node:
    return Node(id=id, text=text, domain=domain, referent="department_head", scope=scope,
                origin=Origin.EPISODE, weight=weight)


def test_exception_with_a_different_figure_is_marked_for_review_not_collided(limit_domain):
    store = InMemoryStore()
    rule = _n("rule", GENERAL_RULE, limit_domain, Scope.GENERAL, weight=0.5)
    store.add_node(rule)
    candidate = _n("exc", FORGED_EXCEPTION, limit_domain, Scope.INSTANCE)

    result = consult(store, candidate)
    edge = apply_consult(store, candidate, result)

    assert result.relation == Relation.SCOPE_LINK  # the dog/Rex rule holds
    assert result.review_needed
    assert result.competing_values == ({5_000_000.0}, {10_000.0})
    assert edge.type == EdgeType.SCOPE_PARENT
    assert edge.status == EdgeStatus.REVIEW_NEEDED
    assert "marked for review" in edge.tolerance_context
    assert rule.weight == 0.5 and rule.evidence_count == 0  # nothing decided


def test_exception_that_drops_the_rules_figure_is_marked_for_review(limit_domain):
    """Decision (2026-09-24): an exception that states no figure against a
    rule that has one can't be told apart from "for this project, any
    amount" without reading meaning, so it's marked for review too. A
    known trade-off: a harmless exception like this one gets looked at
    by a person. Still a SCOPE_LINK, never a collision."""
    store = InMemoryStore()
    store.add_node(_n("rule", GENERAL_RULE, limit_domain, Scope.GENERAL))
    candidate = _n("exc", "For the Q3 IT refresh project, the CFO also signs off on every order.",
                   limit_domain, Scope.INSTANCE)

    result = consult(store, candidate)
    edge = apply_consult(store, candidate, result)

    assert result.relation == Relation.SCOPE_LINK
    assert result.review_needed and result.omitted_values == {10_000.0}
    assert edge.status == EdgeStatus.REVIEW_NEEDED
    assert "states no figure" in edge.tolerance_context


def test_exception_against_a_rule_with_no_figure_is_not_marked(limit_domain):
    """A/B: the rule itself carries no number, so nothing can be dropped."""
    store = InMemoryStore()
    store.add_node(_n("rule", "Department heads may approve routine purchase orders.", limit_domain, Scope.GENERAL))
    candidate = _n("exc", "For the Q3 IT refresh project, the CFO also signs off on every order.",
                   limit_domain, Scope.INSTANCE)

    result = consult(store, candidate)
    assert result.relation == Relation.SCOPE_LINK
    assert not result.review_needed


def test_marcus_scope_case_is_unchanged():
    """The original dog/Rex example (no figures on either side) still links
    with no status at all."""
    store = InMemoryStore()
    store.add_node(_n("general1", "quick-tempered", "temperament", Scope.GENERAL))
    candidate = _n("c1", "uncharacteristically patient this time", "temperament", Scope.INSTANCE)

    edge = apply_consult(store, candidate, consult(store, candidate))
    assert edge.type == EdgeType.SCOPE_PARENT
    assert edge.status is None


def test_pending_reviews_lists_open_collisions_and_marked_exceptions(limit_domain):
    store = InMemoryStore()
    store.add_node(_n("rule", GENERAL_RULE, limit_domain, Scope.GENERAL))

    exception = _n("exc", FORGED_EXCEPTION, limit_domain, Scope.INSTANCE)
    apply_consult(store, exception, consult(store, exception))
    forged_rule = _n("forged", "Department heads may approve purchase orders up to $5,000,000.",
                     limit_domain, Scope.GENERAL)
    apply_consult(store, forged_rule, consult(store, forged_rule))
    agreeing = _n("same", "Department heads can approve purchase orders up to $10,000.", limit_domain, Scope.GENERAL)
    apply_consult(store, agreeing, consult(store, agreeing))

    waiting = pending_reviews(store)
    assert [e.status for e in waiting] == [EdgeStatus.REVIEW_NEEDED, EdgeStatus.OPEN]
    assert {e.source_id for e in waiting} == {"exc", "forged"}  # the reinforcement isn't waiting on anyone


def test_resolved_items_leave_the_review_list(limit_domain):
    store = InMemoryStore()
    store.add_node(_n("rule", GENERAL_RULE, limit_domain, Scope.GENERAL))
    exception = _n("exc", FORGED_EXCEPTION, limit_domain, Scope.INSTANCE)
    edge = apply_consult(store, exception, consult(store, exception))

    edge.status = None  # a person looked and accepted the exception as legitimate
    edge.resolution_why = "confirmed with finance: Q3 refresh has a board-approved budget"
    assert pending_reviews(store) == []
