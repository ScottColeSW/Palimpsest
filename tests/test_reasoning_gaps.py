"""Gaps found by reading Aegis Vector's memory-gate results.

Low word overlap isn't evidence of conflict without a value to compare; a
reversal isn't a restatement; a reviewer needs a way to close what the gate
holds; and a claim the filing step misplaced still has to be checked.
"""

from __future__ import annotations

import pytest

from palimpsest.consult import (
    DOMAIN_KINDS, Relation, apply_consult, consult, pending_reviews, resolve, scan_other_domains,
)
from palimpsest.memory_store import InMemoryStore
from palimpsest.models import DomainKind, EdgeStatus, Node, Origin, Scope

RULE = "The standard procurement spending limit for department heads is $10,000 per purchase order."
CFO = "Purchase orders above the department limit must be approved by the CFO and logged in the procurement system."


@pytest.fixture(autouse=True)
def domains(monkeypatch):
    for d in ("limit", "card", "other_fact"):
        monkeypatch.setitem(DOMAIN_KINDS, d, DomainKind.ATTRIBUTE)


def _n(id, text, domain="limit", referent="dept", scope=Scope.GENERAL):
    return Node(id=id, text=text, domain=domain, referent=referent, scope=scope, origin=Origin.EPISODE)


def _store(*nodes):
    store = InMemoryStore()
    for n in nodes:
        store.add_node(n)
    return store


# -- low overlap is not conflict ------------------------------------------------------

def test_a_different_aspect_with_a_figure_added_is_not_a_collision():
    """The real $10,000 rule arriving next to the CFO-approval rule (Aegis hand labels held both)."""
    assert consult(_store(_n("cfo", CFO)), _n("rule", RULE)).relation == Relation.COEXISTS


def test_a_figure_dropped_at_low_overlap_is_unconfirmed_not_a_collision():
    result = consult(_store(_n("rule", RULE)), _n("cfo", CFO))
    assert result.relation == Relation.UNCONFIRMED and result.review_needed
    assert result.omitted_values == {10_000.0}


def test_same_figure_in_different_words_is_not_a_collision():
    result = consult(_store(_n("rule", RULE)), _n("again", "Department heads can sign off on anything up to $10,000."))
    assert result.relation == Relation.COEXISTS


def test_a_different_figure_still_collides_at_any_overlap():
    result = consult(_store(_n("rule", RULE)), _n("other", "Spending cap of $5,000,000 applies."))
    assert result.relation == Relation.COLLIDES and result.competing_values


def test_qualitative_attributes_still_collide_on_low_overlap():
    """No figures anywhere: wording is all there is to go on (hair color)."""
    store = _store(_n("hair", "her long dark hair", "appearance", "elena"))
    assert consult(store, _n("gold", "golden curls", "appearance", "elena")).relation == Relation.COLLIDES


# -- a reversal is not a restatement --------------------------------------------------

@pytest.mark.parametrize("flipped", [
    "Department heads no longer need CFO approval for large purchase orders.",
    "Department heads don't need CFO approval for large purchase orders.",
    "Department heads may approve large purchase orders of any amount without CFO approval.",
])
def test_a_reversal_cannot_reinforce(flipped):
    rule = _n("rule", "Department heads must get CFO approval for large purchase orders.")
    store = _store(rule)
    result = consult(store, _n("flip", flipped))
    assert result.relation == Relation.UNCONFIRMED and result.polarity_flip and result.review_needed
    edge = apply_consult(store, _n("flip", flipped), result)
    assert edge.status == EdgeStatus.REVIEW_NEEDED and rule.evidence_count == 0 and rule.weight == 0.5


def test_a_genuine_restatement_still_reinforces():
    rule = _n("rule", "Department heads must get CFO approval for large purchase orders.")
    result = consult(_store(rule), _n("again", "Large purchase orders need CFO approval from department heads."))
    assert result.relation == Relation.REINFORCES


def test_agreeing_negatives_still_reinforce():
    rule = _n("rule", "Visitors may not enter the lab without an escort.")
    result = consult(_store(rule), _n("again", "Visitors may not enter the lab unescorted, without an escort."))
    assert result.relation == Relation.REINFORCES


def test_a_reversal_in_an_event_domain_is_another_event_not_evidence():
    store = _store(_n("e1", "Pooh ate the honey before lunch", "story", "pooh"))
    result = consult(store, _n("e2", "Pooh never ate the honey before lunch", "story", "pooh"))
    assert result.relation == Relation.COEXISTS and result.polarity_flip


# -- a person can close what the gate holds -------------------------------------------

def _held():
    store = _store(_n("rule", RULE))
    cand = _n("cfo", CFO)
    edge = apply_consult(store, cand, consult(store, cand))
    return store, edge


def test_resolving_records_what_and_when_and_clears_the_queue():
    store, edge = _held()
    assert edge in pending_reviews(store)
    resolve(store, edge.id, EdgeStatus.RECONCILED_TOGETHER, "Approval routing, not the limit: both stand.")
    assert edge.status == EdgeStatus.RECONCILED_TOGETHER
    assert edge.resolution_why.startswith("Approval routing") and edge.resolved_at is not None
    assert pending_reviews(store) == []


def test_resolving_touches_no_weights():
    store, edge = _held()
    before = {n.id: (n.weight, n.evidence_count) for n in store.all_nodes()}
    resolve(store, edge.id, EdgeStatus.WRONG, "Forged.")
    assert before == {n.id: (n.weight, n.evidence_count) for n in store.all_nodes()}


def test_a_resolution_needs_a_reason():
    store, edge = _held()
    with pytest.raises(ValueError):
        resolve(store, edge.id, EdgeStatus.MOOTED, "  ")
    assert edge.status == EdgeStatus.REVIEW_NEEDED


def test_a_resolved_edge_cannot_be_quietly_resolved_again():
    store, edge = _held()
    resolve(store, edge.id, EdgeStatus.MOOTED, "Superseded.")
    with pytest.raises(ValueError):
        resolve(store, edge.id, EdgeStatus.WRONG, "Changed my mind.")
    assert edge.status == EdgeStatus.MOOTED


@pytest.mark.parametrize("status", [EdgeStatus.OPEN, EdgeStatus.REVIEW_NEEDED])
def test_resolve_refuses_non_resolutions(status):
    store, edge = _held()
    with pytest.raises(ValueError):
        resolve(store, edge.id, status, "no")


def test_resolve_unknown_edge():
    with pytest.raises(KeyError):
        resolve(InMemoryStore(), "nope", EdgeStatus.MOOTED, "x")


# -- a misfiled claim is still checked ------------------------------------------------

def test_a_misfiled_forgery_is_caught_by_scanning_other_domains():
    store = _store(_n("rule", RULE))
    forged = _n("forged", RULE.replace("$10,000", "$5,000,000"), domain="other_fact", referent="other")
    assert consult(store, forged).relation == Relation.NEW  # filed elsewhere: consult() sees nothing
    found = scan_other_domains(store, forged)
    assert found.relation == Relation.COLLIDES and found.related_node.id == "rule"
    assert found.competing_values == ({5_000_000.0}, {10_000.0})


def test_scan_ignores_unrelated_topics_with_different_figures():
    store = _store(_n("card", "Corporate credit card limits are capped at $25,000 for executive leadership.", "card", "exec"))
    assert scan_other_domains(store, _n("new", RULE, "other_fact", "other")) is None


def test_scan_ignores_same_figure_and_figureless_claims():
    store = _store(_n("rule", RULE))
    assert scan_other_domains(store, _n("same", RULE, "other_fact", "other")) is None
    figureless = _n("none", "The limit has been removed for department heads.", "other_fact", "other")
    assert scan_other_domains(store, figureless) is None


def test_scan_skips_event_domains():
    store = _store(_n("e1", "Pooh ate 3 pots of honey before lunch", "story", "pooh"))
    assert scan_other_domains(store, _n("e2", "Pooh ate 5 pots of honey before lunch", "other_fact", "x")) is None


def test_scan_treats_a_different_scope_as_review_not_collision():
    store = _store(_n("rule", RULE))
    exc = _n("exc", "For this one project the department heads' standard procurement spending limit is $5,000,000.",
             "other_fact", "x", Scope.INSTANCE)
    found = scan_other_domains(store, exc)
    assert found.relation == Relation.SCOPE_LINK and found.review_needed
