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
from datetime import datetime, timezone
from enum import Enum

from .memory_store import InMemoryStore
from .models import DomainKind, Edge, EdgeStatus, EdgeType, Node, Origin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

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


# Quantities: "$10,000", "$5M", "5 million", "3.5", "40%". Found the hard way
# by the Aegis Vector poisoning battery: token overlap measures shared
# vocabulary, not agreement, so a forged claim that copies the real one's
# wording and changes only the figure scored 0.83 overlap against it --
# far over the reinforcement threshold -- and would have been filed as
# confirming evidence, bumping the real claim's weight.
# A number glued to a letter in front ("Q3", "IPv6") is a label, not a quantity
_QUANTITY = re.compile(r"(?<![A-Za-z\d.])(\d[\d,]*(?:\.\d+)?)\s*(million|thousand|billion|[mkb]\b|%)?", re.IGNORECASE)
_SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "billion": 1e9, "b": 1e9}


def _quantities(text: str) -> set[float]:
    values = set()
    for number, unit in _QUANTITY.findall(text):
        try:
            value = float(number.replace(",", ""))
        except ValueError:
            continue
        values.add(round(value * _SCALE.get(unit.lower(), 1), 6))
    return values


def _competing_values(a: str, b: str) -> tuple[set[float], set[float]] | None:
    """Two claims compete on value when EACH states a quantity the other
    doesn't -- "$10,000" vs "$5,000,000". One side merely adding a figure
    ("$10,000 per order, CFO approval above that") is elaboration, not
    competition, so a superset still reinforces. Returns the two unshared
    sets when they compete, None otherwise."""
    qa, qb = _quantities(a), _quantities(b)
    only_a, only_b = qa - qb, qb - qa
    if only_a and only_b:
        return only_a, only_b
    return None


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
    # Set when the judgment turned on differing quantities rather than
    # overlap: (candidate's unshared values, related node's unshared values).
    competing_values: tuple[set[float], set[float]] | None = None
    # SCOPE_LINK only: the exception states a different figure than its
    # general rule. Not a collision; marked so it can't pass unseen.
    review_needed: bool = False


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
        # Still not a collision when the figures differ, but an exception
        # that changes a number gets marked for review (see EdgeStatus).
        for node in same_referent:
            competing = _competing_values(candidate.text, node.text)
            if competing is not None:
                return ConsultResult(relation=Relation.SCOPE_LINK, related_node=node,
                                     competing_values=competing, review_needed=True)
        return ConsultResult(relation=Relation.SCOPE_LINK, related_node=same_referent[0])

    best = max(same_scope, key=lambda n: _overlap(candidate.text, n.text))
    score = _overlap(candidate.text, best.text)
    competing = _competing_values(candidate.text, best.text)
    if score >= REINFORCEMENT_OVERLAP_THRESHOLD and competing is None:
        return ConsultResult(relation=Relation.REINFORCES, related_node=best, overlap=score)

    # High overlap with a different figure is never confirmation. In an
    # ATTRIBUTE domain it's the sharpest kind of collision (same claim,
    # different value); in an EVENT domain it's a different event
    # ("ate 3 pots" vs "ate 5 pots"), linked but not counted as evidence.
    if competing is not None and score >= REINFORCEMENT_OVERLAP_THRESHOLD:
        relation = (Relation.COLLIDES if domain_kind_for(candidate.domain) == DomainKind.ATTRIBUTE
                    else Relation.COEXISTS)
        return ConsultResult(relation=relation, related_node=best, overlap=score, competing_values=competing)

    # Below the threshold means "doesn't obviously restate the same
    # claim" -- what that implies depends entirely on what kind of
    # domain this is. An ATTRIBUTE domain has one true value, so this
    # really is tension. An EVENT domain doesn't -- a different,
    # unrelated thing happening is the normal case, not a conflict.
    if domain_kind_for(candidate.domain) == DomainKind.ATTRIBUTE:
        return ConsultResult(relation=Relation.COLLIDES, related_node=best, overlap=score, competing_values=competing)
    return ConsultResult(relation=Relation.COEXISTS, related_node=best, overlap=score, competing_values=competing)


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
        if result.review_needed:
            # Weights untouched and nothing decided -- just made visible
            mine, theirs = (", ".join(f"{v:g}" for v in sorted(s)) for s in result.competing_values)
            edge.status = EdgeStatus.REVIEW_NEEDED
            edge.tolerance_context = (
                f"exception states {mine} where its general rule states {theirs} -- "
                f"not a collision (different scope), marked for review"
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
        # Fresh evidence resets the decay clock (see decay.py) -- a
        # claim that was just reinforced hasn't gone stale.
        result.related_node.last_touched = _utcnow()
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
            tolerance_context=_collision_context(result),
        )

    store.add_edge(edge)
    return edge


def pending_reviews(store: InMemoryStore) -> list[Edge]:
    """Everything waiting on a person: open collisions and exceptions
    marked REVIEW_NEEDED, oldest first. Reading this list is how
    "never silent" is kept -- nothing in it resolves itself."""
    waiting = [e for e in store.all_edges() if e.status in (EdgeStatus.OPEN, EdgeStatus.REVIEW_NEEDED)]
    return sorted(waiting, key=lambda e: e.date)


def _collision_context(result: ConsultResult) -> str:
    if result.competing_values is not None:
        mine, theirs = (", ".join(f"{v:g}" for v in sorted(s)) for s in result.competing_values)
        return (f"values differ ({mine} vs {theirs}) despite overlap={result.overlap:.2f} -- "
                f"same wording, different figure; not a claim either side is wrong")
    return (f"overlap={result.overlap:.2f}, below reinforcement threshold "
            f"{REINFORCEMENT_OVERLAP_THRESHOLD} -- not a claim either side is wrong")


def referent_prominence(store: InMemoryStore, domain: str) -> list[tuple[str, float]]:
    """Ranks referents within a domain by whichever signal is actually
    meaningful for that domain's kind -- not one number pretending to
    mean the same thing everywhere.

    ATTRIBUTE domains: ranked by the highest weight any single claim
    about that referent has reached. Weight legitimately means
    confidence there, since low overlap really does mean competing
    claims -- see consult().

    EVENT domains: ranked by how many distinct episodes mention that
    referent. Weight barely moves in an EVENT domain by design
    (COEXISTS never touches it, REINFORCES only fires on near-literal
    repeats, which narrative text rarely produces) -- using it to rank
    "how central is this referent" was the actual bug. Raw mention
    count is what really reflects how much the mesh has accumulated
    about something, and it's what caught the difference between Pooh
    (14 mentions in three real chapters) and a one-off name.

    Dormant nodes are excluded from both -- they were never judged
    significant, so they shouldn't count toward prominence any more
    than they get individually rendered.

    Returns (referent, score) pairs, highest first. Scores from an
    ATTRIBUTE domain and an EVENT domain are not the same currency --
    a weight and a count -- and should never be compared to each
    other, which is the same "domains don't share a currency" rule
    tolerance already follows.
    """
    episodes = [n for n in store.all_nodes() if n.domain == domain and n.origin == Origin.EPISODE]
    if not episodes:
        return []

    if domain_kind_for(domain) == DomainKind.ATTRIBUTE:
        best_weight: dict[str, float] = {}
        for n in episodes:
            best_weight[n.referent] = max(best_weight.get(n.referent, 0.0), n.weight)
        return sorted(best_weight.items(), key=lambda kv: kv[1], reverse=True)

    counts: dict[str, int] = {}
    for n in episodes:
        counts[n.referent] = counts.get(n.referent, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
