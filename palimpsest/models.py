"""Node and edge shapes for the Palimpsest mesh.

Field-level reasoning lives in CLAUDE.md, not here -- this is just the
schema that came out of it. A few fields are enums rather than free
strings on purpose: domain, scope, origin, edge type, and edge status
are all load-bearing identities that collision detection, tolerance
lookups, and rendering key off of, not labels a caller can typo past.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Scope(str, Enum):
    """General (a category-level claim) vs. instance (a named referent).

    Two entries only ever collide if their scope AND referent both
    match -- see traversal/collision notes in CLAUDE.md's "dog/Rex"
    discussion. A GENERAL claim about "dogs" and an INSTANCE claim
    about "Rex" are not in tension just because they share a topic.
    """

    GENERAL = "general"
    INSTANCE = "instance"


class Origin(str, Enum):
    """Where a node came from. Permanent -- never overwritten, even as
    weight and evidence_count evolve with real interactions. Losing
    this fact would be exactly the silent-erasure failure mode this
    project exists to avoid."""

    EPISODE = "episode"
    REFLECTION = "reflection"
    SEED = "seed"


class EdgeType(str, Enum):
    REINFORCES = "reinforces"
    COLLIDES = "collides"
    SUPERSEDES = "supersedes"
    SCOPE_PARENT = "scope_parent"
    RECONCILED_WITH = "reconciled_with"


class EdgeStatus(str, Enum):
    """Only meaningful on COLLIDES edges. Resolution status lives on
    the edge, not on either node -- it's a property of a specific
    disagreement between two claims, not a property either claim owns
    alone."""

    OPEN = "open"
    VINDICATED = "vindicated"
    MOOTED = "mooted"
    WRONG = "wrong"
    RECONCILED_TOGETHER = "reconciled_together"


@dataclass
class Node:
    id: str
    text: str
    domain: str
    referent: str
    scope: Scope
    origin: Origin
    why: str = ""
    weight: float = 0.5
    evidence_count: int = 0
    embedding: list[float] | None = None
    origin_date: datetime = field(default_factory=_utcnow)
    last_touched: datetime = field(default_factory=_utcnow)


@dataclass
class Edge:
    id: str
    source_id: str
    target_id: str
    type: EdgeType
    date: datetime = field(default_factory=_utcnow)
    status: EdgeStatus | None = None
    tolerance_context: str = ""
    resolution_why: str = ""
    resolved_at: datetime | None = None
