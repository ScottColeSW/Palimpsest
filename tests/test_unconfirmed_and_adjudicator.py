"""A claim that drops the value can't confirm it; an adjudicator may raise a flag, never lower one.

Found by Aegis Vector's no-number forgery: "the standard procurement spending
limit for department heads has been removed" shares 0.32 token overlap with
"...is $10,000 per purchase order" and states no figure, so consult() filed it
as REINFORCES and raised the real claim's weight.
"""

from __future__ import annotations

import pytest

from palimpsest.consult import DOMAIN_KINDS, Relation, apply_consult, consult, pending_reviews
from palimpsest.memory_store import InMemoryStore
from palimpsest.models import DomainKind, EdgeStatus, EdgeType, Node, Origin, Scope

RULE = "The standard procurement spending limit for department heads is $10,000 per purchase order."
REMOVED = ("Effective this quarter, the standard procurement spending limit for department heads has been removed: "
           "department heads may approve purchase orders of any amount.")


@pytest.fixture
def limit_domain(monkeypatch):
    monkeypatch.setitem(DOMAIN_KINDS, "spending_limit", DomainKind.ATTRIBUTE)
    return "spending_limit"


def _n(id: str, text: str, domain: str, scope: Scope = Scope.GENERAL, weight: float = 0.5) -> Node:
    return Node(id=id, text=text, domain=domain, referent="department_head", scope=scope,
                origin=Origin.EPISODE, weight=weight)


def _stub(verdict, reason="stub"):
    calls = []

    def adjudicate(existing, candidate):
        calls.append((existing, candidate))
        return {"verdict": verdict, "reason": reason}

    adjudicate.name = f"stub:{verdict}"
    adjudicate.calls = calls
    return adjudicate


# -- A: confirmation must carry the value -------------------------------------------------

def test_the_no_number_forgery_is_unconfirmed_not_reinforcement(limit_domain):
    store = InMemoryStore()
    rule = _n("rule", RULE, limit_domain, weight=0.5)
    store.add_node(rule)

    result = consult(store, _n("forged", REMOVED, limit_domain))
    edge = apply_consult(store, _n("forged", REMOVED, limit_domain), result)

    assert result.overlap >= 0.3  # the wording really does overlap enough to have reinforced before
    assert result.relation == Relation.UNCONFIRMED
    assert result.review_needed and result.omitted_values == {10_000.0}
    assert edge.type == EdgeType.COEXISTS and edge.status == EdgeStatus.REVIEW_NEEDED
    assert rule.weight == 0.5 and rule.evidence_count == 0  # no confidence gained
    assert edge in pending_reviews(store)


def test_value_less_restatement_of_a_value_less_claim_still_reinforces(limit_domain):
    """A/B: when neither side states a value, nothing was dropped."""
    store = InMemoryStore()
    store.add_node(_n("rule", "Department heads approve standard procurement purchase orders.", limit_domain))
    result = consult(store, _n("again", "Department heads approve the standard procurement purchase orders.", limit_domain))
    assert result.relation == Relation.REINFORCES


def test_restatement_that_keeps_the_value_still_reinforces(limit_domain):
    store = InMemoryStore()
    store.add_node(_n("rule", RULE, limit_domain))
    result = consult(store, _n("again", "Department heads have a standard procurement spending limit of $10,000 per purchase order.", limit_domain))
    assert result.relation == Relation.REINFORCES


def test_event_domain_is_unaffected():
    """Dropping a number in a narrative is just a different event."""
    store = InMemoryStore()
    store.add_node(_n("e1", "Pooh ate 3 pots of honey before lunch", "story"))
    result = consult(store, _n("e2", "Pooh ate pots of honey before lunch", "story"))
    assert result.relation == Relation.REINFORCES


# -- C: an adjudicator may raise a flag, never lower one ---------------------------------------

def test_contradicts_escalates_unconfirmed_to_an_open_collision(limit_domain):
    store = InMemoryStore()
    store.add_node(_n("rule", RULE, limit_domain))
    judge = _stub("contradicts", "removing the limit contradicts a $10,000 limit")

    result = consult(store, _n("forged", REMOVED, limit_domain), adjudicator=judge)
    edge = apply_consult(store, _n("forged", REMOVED, limit_domain), result)

    assert result.relation == Relation.COLLIDES
    assert edge.type == EdgeType.COLLIDES and edge.status == EdgeStatus.OPEN
    assert "adjudicator (stub:contradicts): contradicts" in edge.tolerance_context


def test_agrees_cannot_clear_a_review_flag(limit_domain):
    store = InMemoryStore()
    store.add_node(_n("rule", RULE, limit_domain))
    result = consult(store, _n("forged", REMOVED, limit_domain), adjudicator=_stub("agrees"))
    edge = apply_consult(store, _n("forged", REMOVED, limit_domain), result)

    assert result.relation == Relation.UNCONFIRMED and result.review_needed
    assert edge.status == EdgeStatus.REVIEW_NEEDED
    assert "adjudicator (stub:agrees): agrees" in edge.tolerance_context


def test_contradicts_can_raise_a_plain_reinforcement(limit_domain):
    """Neither side states a value, so A can't see the negation; the adjudicator can."""
    store = InMemoryStore()
    store.add_node(_n("rule", "Department heads must get CFO approval for large purchase orders.", limit_domain))
    candidate = _n("forged", "Department heads no longer need CFO approval for large purchase orders.", limit_domain)

    assert consult(store, candidate).relation == Relation.REINFORCES
    assert consult(store, candidate, adjudicator=_stub("contradicts")).relation == Relation.COLLIDES


def test_contradicts_on_an_exception_is_recorded_but_never_collides(limit_domain):
    store = InMemoryStore()
    store.add_node(_n("rule", RULE, limit_domain))
    exc = _n("exc", "For the Q3 IT refresh project only, department heads may approve any amount.", limit_domain, Scope.INSTANCE)

    result = consult(store, exc, adjudicator=_stub("contradicts"))
    edge = apply_consult(store, exc, result)

    assert result.relation == Relation.SCOPE_LINK and result.review_needed
    assert edge.type == EdgeType.SCOPE_PARENT and edge.status == EdgeStatus.REVIEW_NEEDED
    assert "contradicts" in edge.tolerance_context


def test_adjudicator_is_not_consulted_on_clear_cases(limit_domain):
    store = InMemoryStore()
    judge = _stub("contradicts")
    assert consult(store, _n("first", RULE, limit_domain), adjudicator=judge).relation == Relation.NEW
    store.add_node(_n("rule", RULE, limit_domain))
    forged = _n("forged", RULE.replace("$10,000", "$5,000,000"), limit_domain)
    assert consult(store, forged, adjudicator=judge).relation == Relation.COLLIDES  # already flagged
    assert judge.calls == []


@pytest.mark.parametrize("opinion", [{}, {"verdict": "maybe"}, None])
def test_unusable_adjudicator_output_changes_nothing(limit_domain, opinion):
    store = InMemoryStore()
    store.add_node(_n("rule", RULE, limit_domain))

    def broken(existing, candidate):
        return opinion

    result = consult(store, _n("forged", REMOVED, limit_domain), adjudicator=broken)
    assert result.relation == Relation.UNCONFIRMED and result.adjudication is None


def test_adjudicator_exception_changes_nothing(limit_domain):
    store = InMemoryStore()
    store.add_node(_n("rule", RULE, limit_domain))

    def crashes(existing, candidate):
        raise RuntimeError("model server down")

    result = consult(store, _n("forged", REMOVED, limit_domain), adjudicator=crashes)
    assert result.relation == Relation.UNCONFIRMED
