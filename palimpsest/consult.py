"""consult() -- the step that makes this a memory system instead of a
labeled pile of context. Everything built before this (ingest.py,
memory_store.py, traversal.py) only put material somewhere and let it
sit. consult() is what actually reads the mesh back and lets a new
claim be judged against what's already there -- the one behavior
CLAUDE.md's opening paragraph says separates memory from "more tokens
to read before answering."

Deliberately narrow about what it's honest to claim. No real
contradiction detection -- that's a hard, unsolved NLU problem, same
policy as ingest.py's placeholder classifier: don't fake
sophistication that isn't there. What IS real and not a placeholder:
scope matching. A general claim and an instance claim about the same
referent are never treated as colliding, full stop, regardless of
content -- that's structural logic, not a guess (see CLAUDE.md's
dog/Rex discussion, and demo_scenario.py's Marcus example, which this
module's tests deliberately reuse rather than inventing new data).
For same-scope claims about the same referent+domain, token overlap
(Jaccard -- the same pattern Evolution2Civ's TribeMemory uses, cited
in CLAUDE.md's grounding section) decides reinforcement vs. everything
else -- and what "everything else" means depends on DomainKind
(models.py): an ATTRIBUTE domain has one true value at a time, so low
overlap really is tension and becomes an OPEN collision needing real
resolution. An EVENT domain doesn't -- many different, unrelated
things can be true about the same referent (a narrative), so low
overlap there just means "a different event", not disagreement, and
becomes COEXISTS instead. Getting this wrong isn't hypothetical: an
earlier version treated every domain as ATTRIBUTE and real
Winnie-the-Pooh ingestion produced 44 false collisions between
perfectly ordinary, compatible sentences about Pooh.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .memory_store import InMemoryStore
from .models import DomainKind, Edge, EdgeStatus, EdgeType, Node

# A domain has to be explicitly declared attribute-like (one true value
# competes at a time) to get collision detection at all. Unregistered
# domains default to EVENT -- see DomainKind's docstring for why an
# unsafe default here produced real false positives against real text.
# A plain dict on purpose, not a generated registry -- easy to read,
# easy to extend, same call Dominion's model catalog makes.
DOMAIN_KINDS: dict[str, DomainKind] = {
    "appearance": DomainKind.ATTRIBUTE,
    "temperament": DomainKind.ATTRIBUTE,
}


def domain_kind_for(domain: str) -> DomainKind:
    return DOMAIN_KINDS.get(domain, DomainKind.EVENT)


_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "and", "or", "of", "to",
    "in", "on", "at", "with", "her", "his", "its", "it", "he", "she", "for",
})

# Same first-cut number TribeMemory's reflection-reinforcement check uses
# (see CLAUDE.md's grounding section) -- no real data behind this one
# either yet, worth revisiting once some exists.
REINFORCEMENT_OVERLAP_THRESHOLD = 0.3


def _tokenize(text: str) -> set[str]:
    return set(_WORD.findall(text.lower())) - _STOPWORDS


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class Relation(str, Enum):
    NEW = "new"  # nothing related exists yet
    SCOPE_LINK = "scope_link"  # different scope, same referent+domain -- never a collision
    REINFORCES = "reinforces"  # same scope+referent+domain, high overlap
    COLLIDES = "collides"  # ATTRIBUTE domain, low overlap -- real, structural divergence
    COEXISTS = "coexists"  # EVENT domain, low overlap -- a different event, not a conflict


@dataclass
class ConsultResult:
    relation: Relation
    related_node: Node | None
    overlap: float | None = None


def consult(store: InMemoryStore, candidate: Node) -> ConsultResult:
    """Judges `candidate` (not yet stored) against what already exists
    for its referent+domain. Doesn't mutate the store or decide
    anything by itself -- see apply_consult for the version that acts
    on the judgment. Kept pure and side-effect-free specifically so
    the judgment can be inspected and tested before anything is
    written, the same discipline as everywhere else in this project:
    nothing gets silently acted on."""
    same_referent = [
        n for n in store.all_nodes() if n.referent == candidate.referent and n.domain == candidate.domain
    ]
    if not same_referent:
        return ConsultResult(relation=Relation.NEW, related_node=None)

    same_scope = [n for n in same_referent if n.scope == candidate.scope]
    if not same_scope:
        # Different scope, same referent+domain -- structural non-collision
        # regardless of content. This is the actual, checkable claim: a
        # naive same-referent+domain check alone would see conflicting
        # text here; scope-awareness is what changes the outcome.
        return ConsultResult(relation=Relation.SCOPE_LINK, related_node=same_referent[0])

    best = max(same_scope, key=lambda n: _overlap(candidate.text, n.text))
    score = _overlap(candidate.text, best.text)
    if score >= REINFORCEMENT_OVERLAP_THRESHOLD:
        return ConsultResult(relation=Relation.REINFORCES, related_node=best, overlap=score)

    # Below the threshold means "doesn't obviously restate the same
    # claim" -- what that implies depends entirely on what kind of
    # domain this is. An ATTRIBUTE domain has one true value, so this
    # really is tension. An EVENT domain doesn't -- a different,
    # unrelated thing happening is the normal case, not a conflict.
    if domain_kind_for(candidate.domain) == DomainKind.ATTRIBUTE:
        return ConsultResult(relation=Relation.COLLIDES, related_node=best, overlap=score)
    return ConsultResult(relation=Relation.COEXISTS, related_node=best, overlap=score)


def apply_consult(store: InMemoryStore, candidate: Node, result: ConsultResult) -> Edge | None:
    """Actually stores candidate and, if warranted, the edge consult()
    judged. Separate from consult() on purpose -- decide, then act,
    never both in one step."""
    store.add_node(candidate)

    if result.relation == Relation.NEW:
        return None

    if result.relation == Relation.SCOPE_LINK:
        edge = Edge(
            id=f"{candidate.id}-scope-{result.related_node.id}",
            source_id=candidate.id,
            target_id=result.related_node.id,
            type=EdgeType.SCOPE_PARENT,
        )
    elif result.relation == Relation.REINFORCES:
        edge = Edge(
            id=f"{candidate.id}-reinforce-{result.related_node.id}",
            source_id=candidate.id,
            target_id=result.related_node.id,
            type=EdgeType.REINFORCES,
        )
        result.related_node.weight = min(1.0, result.related_node.weight + 0.15)
        result.related_node.evidence_count += 1
    elif result.relation == Relation.COEXISTS:
        # Linked for traversal (e.g. "everything that's happened
        # involving Pooh"), but deliberately doesn't touch weight or
        # evidence_count -- a new, unrelated event isn't confirmation
        # of the one it's linked to, and treating it as such would
        # inflate confidence for no real reason.
        edge = Edge(
            id=f"{candidate.id}-coexists-{result.related_node.id}",
            source_id=candidate.id,
            target_id=result.related_node.id,
            type=EdgeType.COEXISTS,
        )
    else:  # COLLIDES
        edge = Edge(
            id=f"{candidate.id}-collide-{result.related_node.id}",
            source_id=candidate.id,
            target_id=result.related_node.id,
            type=EdgeType.COLLIDES,
            status=EdgeStatus.OPEN,
            tolerance_context=(
                f"overlap={result.overlap:.2f}, below reinforcement threshold "
                f"{REINFORCEMENT_OVERLAP_THRESHOLD} -- not a claim either side is wrong"
            ),
        )

    store.add_edge(edge)
    return edge
