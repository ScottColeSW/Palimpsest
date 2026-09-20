"""These tests are the actual point of consult.py: proving that
having memory present changes the judgment, versus not having it --
not proving that storage works, which was never in question. Each
test that matters here is structured as an A/B: same candidate,
different mesh state, different (correct) relation returned.
"""

from __future__ import annotations

from palimpsest.consult import Relation, apply_consult, consult, domain_kind_for
from palimpsest.memory_store import InMemoryStore
from palimpsest.models import DomainKind, EdgeStatus, EdgeType, Node, Origin, Scope


def _n(id: str, text: str, domain: str, referent: str, scope: Scope, weight: float = 0.5) -> Node:
    return Node(id=id, text=text, domain=domain, referent=referent, scope=scope, origin=Origin.EPISODE, weight=weight)


def test_consult_is_new_with_an_empty_mesh():
    """No memory at all -- the honest baseline. Nothing to judge against."""
    store = InMemoryStore()
    candidate = _n("c1", "raven black hair", "appearance", "elena", Scope.GENERAL)
    result = consult(store, candidate)
    assert result.relation == Relation.NEW
    assert result.related_node is None


def test_memory_present_changes_the_outcome_for_the_same_candidate():
    """The actual claim from this turn's discussion, made concrete:
    identical candidate, two different mesh states, two different
    (both correct) judgments -- proof the mesh is doing something,
    not just storing."""
    candidate = _n("c1", "raven black hair caught the light", "appearance", "elena", Scope.GENERAL)

    empty_store = InMemoryStore()
    without_memory = consult(empty_store, candidate)

    populated_store = InMemoryStore()
    populated_store.add_node(_n("seed1", "raven black hair", "appearance", "elena", Scope.GENERAL))
    with_memory = consult(populated_store, candidate)

    assert without_memory.relation == Relation.NEW
    assert with_memory.relation == Relation.REINFORCES
    assert with_memory.related_node.id == "seed1"


def test_consult_reinforces_on_high_token_overlap_same_scope():
    store = InMemoryStore()
    store.add_node(_n("seed1", "raven black hair", "appearance", "elena", Scope.GENERAL))
    candidate = _n("c1", "her raven hair caught the light", "appearance", "elena", Scope.GENERAL)

    result = consult(store, candidate)
    assert result.relation == Relation.REINFORCES
    assert result.overlap >= 0.3


def test_consult_collides_on_low_token_overlap_same_scope():
    store = InMemoryStore()
    store.add_node(_n("seed1", "raven black hair", "appearance", "elena", Scope.GENERAL))
    candidate = _n("c1", "her golden curls", "appearance", "elena", Scope.GENERAL)

    result = consult(store, candidate)
    assert result.relation == Relation.COLLIDES
    assert result.overlap < 0.3


def test_scope_awareness_prevents_a_false_collision():
    """The dog/Rex case, run for real: a general trait and a
    contradicting instance-level observation about the SAME referent.
    A naive same-referent+domain check would see conflicting text and
    flag it. Scope-matching is what changes that outcome -- this is
    the mechanism actually being tested, not the token overlap."""
    store = InMemoryStore()
    store.add_node(_n("general1", "quick-tempered", "temperament", "marcus", Scope.GENERAL))
    candidate = _n(
        "c1", "uncharacteristically patient, waited without complaint",
        "temperament", "marcus", Scope.INSTANCE,
    )

    result = consult(store, candidate)
    assert result.relation == Relation.SCOPE_LINK
    assert result.relation != Relation.COLLIDES
    assert result.related_node.id == "general1"


def test_apply_consult_reinforces_bumps_weight_and_evidence_count():
    store = InMemoryStore()
    seed = _n("seed1", "raven black hair", "appearance", "elena", Scope.GENERAL, weight=0.3)
    store.add_node(seed)
    candidate = _n("c1", "her raven hair caught the light", "appearance", "elena", Scope.GENERAL)

    result = consult(store, candidate)
    apply_consult(store, candidate, result)

    assert store.get_node("c1") is not None  # candidate itself got stored
    assert seed.weight > 0.3
    assert seed.evidence_count == 1


def test_apply_consult_collides_creates_open_edge_not_a_verdict():
    store = InMemoryStore()
    store.add_node(_n("seed1", "raven black hair", "appearance", "elena", Scope.GENERAL))
    candidate = _n("c1", "her golden curls", "appearance", "elena", Scope.GENERAL)

    result = consult(store, candidate)
    edge = apply_consult(store, candidate, result)

    assert edge.type == EdgeType.COLLIDES
    assert edge.status == EdgeStatus.OPEN  # never silently resolved to a winner
    assert "not a claim either side is wrong" in edge.tolerance_context


def test_apply_consult_scope_link_creates_scope_parent_edge():
    store = InMemoryStore()
    store.add_node(_n("general1", "quick-tempered", "temperament", "marcus", Scope.GENERAL))
    candidate = _n("c1", "uncharacteristically patient this time", "temperament", "marcus", Scope.INSTANCE)

    result = consult(store, candidate)
    edge = apply_consult(store, candidate, result)

    assert edge.type == EdgeType.SCOPE_PARENT
    assert edge.status is None  # not a collision, nothing to resolve


def test_apply_consult_new_stores_candidate_but_creates_no_edge():
    store = InMemoryStore()
    candidate = _n("c1", "raven black hair", "appearance", "elena", Scope.GENERAL)

    result = consult(store, candidate)
    edge = apply_consult(store, candidate, result)

    assert edge is None
    assert store.get_node("c1") is not None
    assert store.all_edges() == []


# -- domain-kind: attribute vs. event ---------------------------------

def test_unregistered_domain_defaults_to_event_not_attribute():
    """The safe default matters -- an unknown domain should not
    silently get collision detection turned on for it."""
    assert domain_kind_for("story") == DomainKind.EVENT
    assert domain_kind_for("some_domain_nobody_registered") == DomainKind.EVENT
    assert domain_kind_for("appearance") == DomainKind.ATTRIBUTE


def test_the_actual_pooh_bug_two_unrelated_events_do_not_collide():
    """The real failure this was built to fix: two ordinary, compatible
    narrative sentences about the same character, low text overlap,
    domain="story" (unregistered -> EVENT). Previously this produced
    Relation.COLLIDES -- a false alarm. It must not anymore."""
    store = InMemoryStore()
    store.add_node(_n("e1", "Pooh came downstairs bump bump bump", "story", "pooh", Scope.GENERAL))
    candidate = _n("e2", "Pooh sat by the fire and listened to a story", "story", "pooh", Scope.GENERAL)

    result = consult(store, candidate)

    assert result.relation == Relation.COEXISTS
    assert result.relation != Relation.COLLIDES


def test_event_domain_still_reinforces_on_genuine_near_duplicate():
    """Low overlap becoming COEXISTS instead of COLLIDES shouldn't
    swallow real reinforcement -- an actual near-duplicate description
    of the same event in an EVENT domain should still reinforce."""
    store = InMemoryStore()
    store.add_node(_n("e1", "Pooh climbed the tree looking for honey", "story", "pooh", Scope.GENERAL))
    candidate = _n("e2", "Pooh climbed a tree looking for some honey", "story", "pooh", Scope.GENERAL)

    result = consult(store, candidate)
    assert result.relation == Relation.REINFORCES


def test_attribute_domain_unchanged_still_collides():
    """Confirms the fix is additive, not a regression -- a real
    ATTRIBUTE domain (hair color) still gets real collision detection,
    unaffected by the new EVENT branch."""
    store = InMemoryStore()
    store.add_node(_n("seed1", "raven black hair", "appearance", "elena", Scope.GENERAL))
    candidate = _n("c1", "her golden curls", "appearance", "elena", Scope.GENERAL)

    result = consult(store, candidate)
    assert result.relation == Relation.COLLIDES


def test_apply_consult_coexists_links_but_does_not_touch_weight():
    store = InMemoryStore()
    seed = _n("e1", "Pooh came downstairs bump bump bump", "story", "pooh", Scope.GENERAL, weight=0.5)
    store.add_node(seed)
    candidate = _n("e2", "Pooh sat by the fire and listened to a story", "story", "pooh", Scope.GENERAL)

    result = consult(store, candidate)
    edge = apply_consult(store, candidate, result)

    assert edge.type == EdgeType.COEXISTS
    assert edge.status is None
    assert seed.weight == 0.5  # untouched -- a new event isn't confirmation
    assert seed.evidence_count == 0
