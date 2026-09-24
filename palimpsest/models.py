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
    project exists to avoid.

    DORMANT (added for ingestion): a chunk of real raw material that
    digestion looked at and didn't judge significant *yet* -- kept,
    not discarded, so "wasn't interesting on first pass" never quietly
    becomes "gone." Distinct from SEED (authored, never observed) and
    EPISODE (an evaluated conclusion) -- dormant material is real and
    unevaluated, sitting below the weight threshold that would make it
    an active node, eligible for promotion if a later chunk makes its
    relevance clear."""

    EPISODE = "episode"
    REFLECTION = "reflection"
    SEED = "seed"
    DORMANT = "dormant"


class EdgeType(str, Enum):
    REINFORCES = "reinforces"
    COLLIDES = "collides"
    SUPERSEDES = "supersedes"
    SCOPE_PARENT = "scope_parent"
    RECONCILED_WITH = "reconciled_with"
    COEXISTS = "coexists"  # same referent+domain+scope, no claimed tension -- see DomainKind.EVENT


class DomainKind(str, Enum):
    """What kind of thing a domain's claims compete over -- decides
    what "low text overlap between two same-referent claims" means.

    ATTRIBUTE: the domain has one true value at a time (a character's
    hair color, a person's general temperament). Two different-content
    claims at the same scope really are in tension -- low overlap is
    real signal, COLLIDES is the right call.

    EVENT: the domain is a stream of things that happened, where many
    different, unrelated claims can all be true at once (a character's
    narrative -- "came downstairs", "ate honey", "climbed a tree").
    Low overlap here just means "a different event", not disagreement
    -- flagging it as COLLIDES is confidently wrong, not cautious.

    Found the hard way: consult() originally treated every domain as
    ATTRIBUTE, and real Winnie-the-Pooh ingestion produced 44 false
    "collisions" between ordinary, compatible sentences about Pooh
    that simply didn't share vocabulary -- see CLAUDE.md."""

    ATTRIBUTE = "attribute"
    EVENT = "event"


class EdgeStatus(str, Enum):
    """Resolution status lives on the edge, not on either node -- it's a
    property of a specific relationship between two claims, not a
    property either claim owns alone.

    On COLLIDES edges: OPEN until something real resolves it
    (VINDICATED / MOOTED / WRONG / RECONCILED_TOGETHER).

    REVIEW_NEEDED: kept visible until someone looks, never silently
    accepted or rejected. Two places it appears:

    - SCOPE_PARENT edges whose instance claim changes or drops its general
      rule's figure ("department heads may approve up to $10,000" vs "for
      this one project, up to $5,000,000", or "...this one project needs
      no limit"). Still an exception, not a collision -- the dog/Rex rule
      holds -- but it's exactly the shape a forged claim takes to slip under
      collision detection. A SCOPE_PARENT edge whose rule states no figure,
      or whose exception keeps it, has no status.
    - COEXISTS edges from an UNCONFIRMED consult: a same-scope claim that
      shares the rule's wording but omits the value it would have to
      carry to confirm it ("the limit has been removed" vs "the limit is
      $10,000"). Not evidence, not a collision.
    """

    OPEN = "open"
    VINDICATED = "vindicated"
    MOOTED = "mooted"
    WRONG = "wrong"
    RECONCILED_TOGETHER = "reconciled_together"
    REVIEW_NEEDED = "review_needed"


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
