"""Proving decay does what it claims: weight erodes toward the floor
over elapsed time, composes correctly across repeated calls, and only
touches the node kind it's supposed to (ATTRIBUTE-domain EPISODE) --
not EVENT-domain narrative nodes or DORMANT material, and not by
skipping the "why" (see decay.py's module docstring).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from palimpsest.decay import apply_decay, decay_store
from palimpsest.memory_store import InMemoryStore
from palimpsest.models import Node, Origin, Scope


def _attr_node(id: str, weight: float, last_touched: datetime) -> Node:
    return Node(
        id=id, text="raven black hair", domain="appearance", referent="elena",
        scope=Scope.GENERAL, origin=Origin.EPISODE, weight=weight, last_touched=last_touched,
    )


def test_apply_decay_erodes_weight_toward_floor_over_one_half_life():
    now = datetime.now(timezone.utc)
    node = _attr_node("n1", weight=1.0, last_touched=now - timedelta(seconds=100))

    apply_decay(node, half_life_seconds=100, floor=0.0, now=now)

    assert abs(node.weight - 0.5) < 1e-9


def test_apply_decay_respects_a_nonzero_floor():
    now = datetime.now(timezone.utc)
    node = _attr_node("n1", weight=1.0, last_touched=now - timedelta(seconds=1_000_000))

    apply_decay(node, half_life_seconds=100, floor=0.2, now=now)

    # Effectively fully decayed after that many half-lives -- should
    # land on the floor, never below it.
    assert abs(node.weight - 0.2) < 1e-6


def test_apply_decay_advances_last_touched_so_immediate_replay_is_a_noop():
    now = datetime.now(timezone.utc)
    node = _attr_node("n1", weight=1.0, last_touched=now - timedelta(seconds=100))

    apply_decay(node, half_life_seconds=100, floor=0.0, now=now)
    weight_after_first = node.weight
    apply_decay(node, half_life_seconds=100, floor=0.0, now=now)  # no time elapsed

    assert node.weight == weight_after_first
    assert node.last_touched == now


def test_repeated_decay_over_split_windows_matches_one_call_over_the_combined_window():
    """The composability claim from the module docstring, checked
    directly: decaying over t1 then t2 should equal decaying once over
    t1+t2, as long as last_touched advances between calls (which
    apply_decay always does)."""
    start = datetime.now(timezone.utc)
    mid = start + timedelta(seconds=40)
    end = start + timedelta(seconds=100)

    split = _attr_node("split", weight=1.0, last_touched=start)
    apply_decay(split, half_life_seconds=100, floor=0.1, now=mid)
    apply_decay(split, half_life_seconds=100, floor=0.1, now=end)

    combined = _attr_node("combined", weight=1.0, last_touched=start)
    apply_decay(combined, half_life_seconds=100, floor=0.1, now=end)

    assert abs(split.weight - combined.weight) < 1e-9


def test_apply_decay_ignores_negative_or_zero_elapsed_time():
    now = datetime.now(timezone.utc)
    node = _attr_node("n1", weight=0.7, last_touched=now + timedelta(seconds=5))  # future touch

    apply_decay(node, half_life_seconds=100, floor=0.0, now=now)

    assert node.weight == 0.7  # untouched -- nothing has elapsed yet


def test_decay_store_only_touches_attribute_domain_episode_nodes():
    now = datetime.now(timezone.utc)
    old = now - timedelta(seconds=1000)
    store = InMemoryStore()

    attribute_node = _attr_node("attr1", weight=1.0, last_touched=old)
    event_node = Node(
        id="evt1", text="Pooh climbed a tree", domain="story", referent="pooh",
        scope=Scope.GENERAL, origin=Origin.EPISODE, weight=1.0, last_touched=old,
    )
    dormant_node = Node(
        id="dorm1", text="a passing detail", domain="appearance", referent="elena",
        scope=Scope.GENERAL, origin=Origin.DORMANT, weight=1.0, last_touched=old,
    )
    for n in (attribute_node, event_node, dormant_node):
        store.add_node(n)

    touched = decay_store(store, half_life_seconds=100, floor=0.0, now=now)

    assert touched == 1
    assert attribute_node.weight < 1.0
    assert event_node.weight == 1.0  # EVENT domain: prominence is mention count, not weight
    assert dormant_node.weight == 1.0  # never judged significant, nothing to erode
