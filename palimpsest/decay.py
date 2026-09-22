"""Weight decay -- letting standing confidence in a claim erode over
time when nothing reinforces it, instead of REINFORCES being the only
thing that ever moves weight (see consult.py: previously weight only
went up).

Deliberately narrow about what decays. Only ATTRIBUTE-domain EPISODE
nodes carry a weight that means "confidence in a competing claim" --
see models.DomainKind and consult.referent_prominence. EVENT-domain
nodes are ranked by mention count, not weight (weight barely moves for
them by design), so decaying it would be a silent no-op dressed up as
a real effect. DORMANT nodes were never judged significant in the
first place; decaying a weight nobody assigned on purpose doesn't mean
anything either.

Exponential decay toward a floor, not toward zero -- a claim that's
gone unreinforced for a long time should fade toward uncertainty, not
toward "never happened." Composable by construction: applying it twice
back-to-back over elapsed windows t1 then t2 gives the same result as
once over t1+t2, provided last_touched is advanced after each call
(which this module always does) -- see tests for the proof.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .consult import domain_kind_for
from .memory_store import InMemoryStore
from .models import DomainKind, Node, Origin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def apply_decay(
    node: Node, *, half_life_seconds: float, floor: float = 0.05, now: datetime | None = None
) -> None:
    """Decays `node.weight` toward `floor` based on elapsed time since
    `last_touched`, then advances `last_touched` to `now` -- so a
    second call immediately after is a no-op (nothing elapsed) rather
    than double-decaying. Doesn't check domain kind or origin; that
    judgment belongs to the caller (see decay_store), since a single
    node might legitimately be decayed outside the usual sweep."""
    now = now or _utcnow()
    elapsed = (now - node.last_touched).total_seconds()
    if elapsed <= 0:
        return
    if half_life_seconds <= 0:
        node.weight = floor
    else:
        decay_factor = 0.5 ** (elapsed / half_life_seconds)
        node.weight = floor + (node.weight - floor) * decay_factor
    node.last_touched = now


def decay_store(
    store: InMemoryStore, *, half_life_seconds: float, floor: float = 0.05, now: datetime | None = None
) -> int:
    """Sweeps every ATTRIBUTE-domain EPISODE node in the store and
    applies apply_decay to each. Returns how many nodes were touched.
    EVENT-domain and DORMANT nodes are skipped -- see module docstring
    for why decaying them wouldn't mean anything."""
    now = now or _utcnow()
    touched = 0
    for node in store.all_nodes():
        if node.origin != Origin.EPISODE:
            continue
        if domain_kind_for(node.domain) != DomainKind.ATTRIBUTE:
            continue
        apply_decay(node, half_life_seconds=half_life_seconds, floor=floor, now=now)
        touched += 1
    return touched
