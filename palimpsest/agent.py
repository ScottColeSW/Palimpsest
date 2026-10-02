"""Agent-driven memory: the agent judges, the library keeps the record honest.

consult() decides with fixed rules (token overlap, quantities, a negation cue
list). That is a useful floor but it is scripting, and a memory that is
supposed to be shaped by an agent's own judgment shouldn't be run by it. Here
the agent decides what a new claim is to what is already held (new, a
reinforcement, a coexisting claim, a collision, an exception, a replacement),
how much it weighs, and why, and the library records that as a dated,
attributed, revisable entry.

What the library still enforces, whatever the agent says:

- Every decision carries a reason and an author. Nothing is silent.
- Nothing is erased. A superseded or released claim stays in the store with
  its provenance; it just stops counting as a live belief.
- The injection boundary. A claim whose source is "external" (content the
  agent read and doesn't vouch for) can't supersede anything, and if the
  rules floor would hold it, or the agent itself judges it in conflict with a held
  claim, or as an exception to one, it is held for the user: a model can be talked
  into agreeing with a well-written forgery, so a flag from either side is never
  cleared by the other.
  Claims from the agent's own experience or the user are the agent's to judge.

The floor is itself a policy: pass floor=False to commit() to turn it off.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .embed import cosine
from .consult import ConsultResult, Relation, _overlap, _utcnow, consult, live_nodes, pending_reviews, scan_other_domains
from .memory_store import InMemoryStore
from .models import Edge, EdgeStatus, EdgeType, Node, Origin

AGENT_RELATIONS = ("new", "reinforces", "coexists", "collides", "exception_of", "supersedes")
SOURCES = ("agent", "external")
REINFORCE_BUMP = 0.15  # default; commit(bump=...) lets the agent choose


@dataclass
class Neighbor:
    node: Node
    overlap: float  # wording overlap
    same_fact: bool  # same referent+domain as the candidate
    similarity: float | None = None  # cosine, when both claims have an embedding


@dataclass
class Proposal:
    """Read-only: what the memory holds near a candidate, for the agent to judge."""
    neighbors: list[Neighbor]
    # What the fixed rules would say. Advisory only: shown so the agent can weigh it, never applied.
    rules_opinion: dict


@dataclass
class Commit:
    node: Node
    edge: Edge | None
    held: bool = False
    held_because: str = ""


def propose(store: InMemoryStore, candidate: Node, limit: int = 6) -> Proposal:
    """The live claims closest to `candidate` by wording, same-fact ones first, plus the fixed rules'
    opinion as one input among others."""
    scored = []
    for node in live_nodes(store):
        if node.id == candidate.id or node.origin == Origin.DORMANT:
            continue
        same = node.referent == candidate.referent and node.domain == candidate.domain
        score = _overlap(candidate.text, node.text)
        sim = cosine(candidate.embedding, node.embedding) if candidate.embedding and node.embedding else None
        if same or score > 0 or sim is not None:
            scored.append(Neighbor(node=node, overlap=score, same_fact=same, similarity=sim))
    # Meaning when there is an embedding on both sides, so a claim in other words is still found (and a
    # misfiled one is too); otherwise wording, with same-fact claims first as before.
    scored.sort(key=lambda n: (n.similarity is not None, n.similarity or 0.0, n.same_fact, n.overlap), reverse=True)
    result = consult(store, candidate)
    opinion = {"relation": result.relation.value, "review_needed": result.review_needed,
               "related_id": result.related_node.id if result.related_node else None,
               "overlap": result.overlap, "polarity_flip": result.polarity_flip}
    cross = scan_other_domains(store, candidate)
    if cross is not None:
        opinion["cross_fact_conflict"] = {"related_id": cross.related_node.id, "relation": cross.relation.value}
    return Proposal(neighbors=scored[:limit], rules_opinion=opinion)


def _floor_hold(store: InMemoryStore, candidate: Node):
    """The rules' view of an external claim: (ConsultResult that holds it, why) or None."""
    result = consult(store, candidate)
    if result.relation == Relation.COLLIDES or result.review_needed:
        return result, f"rules judged it {result.relation.value}" + (", marked for review" if result.review_needed else "")
    cross = scan_other_domains(store, candidate)
    if cross is not None:
        return cross, "it restates another claim with a different figure"
    return None


def commit(store: InMemoryStore, candidate: Node, *, relation: str, reason: str, related_id: str | None = None,
           by: str = "agent", floor: bool = True, bump: float = REINFORCE_BUMP) -> Commit:
    """Records the agent's judgment of `candidate`. `relation` is one of AGENT_RELATIONS; everything but
    "new" names the live claim it is judged against in `related_id`."""
    if relation not in AGENT_RELATIONS:
        raise ValueError(f"relation must be one of {list(AGENT_RELATIONS)}, got {relation!r}")
    if not reason.strip():
        raise ValueError("a judgment needs a reason")
    if candidate.source not in SOURCES:
        raise ValueError(f"source must be one of {list(SOURCES)}, got {candidate.source!r}")
    if store.get_node(candidate.id) is not None:
        raise ValueError(f"node {candidate.id} already exists")
    related = None
    if relation != "new":
        if not related_id:
            raise ValueError(f"relation {relation!r} needs related_id")
        related = next((n for n in live_nodes(store) if n.id == related_id), None)
        if related is None:
            raise ValueError(f"no live claim {related_id!r} (released or superseded claims can't be judged against)")
    if candidate.source == "external" and relation == "supersedes":
        raise ValueError("external content can't supersede a claim. Record it as 'collides' and let the user resolve it")

    candidate.author = by
    note = f"{by}: {reason.strip()}"

    if candidate.source == "external" and floor:
        held = _floor_hold(store, candidate)
        if held is None and relation == "collides":
            # The fixed rules found nothing (a reversal with no figures and no cue words reads to them as a
            # confirmation), but the agent itself judged the claim in conflict with a held one. A flag only ever
            # goes up, so external content in conflict is held, not admitted as a live belief beside the one it disputes.
            held = (ConsultResult(relation=Relation.COLLIDES, related_node=related), "the agent judged it in conflict with a held claim")
        if held is None and relation == "exception_of":
            # "For this one case, the rule doesn't apply" is the shape a forgery takes when it can't just contradict a
            # rule. An exception to a held claim from content nobody vouched for waits for the user, like a conflict.
            held = (ConsultResult(relation=Relation.SCOPE_LINK, related_node=related, review_needed=True),
                    "the agent judged it an exception to a held claim, and an exception from unvouched content is held")
        if held is not None:
            result, why = held
            candidate.weight = min(candidate.weight, 0.05)
            candidate.why = f"HELD (external): {candidate.why}".strip()
            store.add_node(candidate)
            collides = result.relation == Relation.COLLIDES
            edge = Edge(
                id=f"{candidate.id}-held-{result.related_node.id}", source_id=candidate.id,
                target_id=result.related_node.id,
                type=EdgeType.COLLIDES if collides else EdgeType.COEXISTS,
                status=EdgeStatus.OPEN if collides else EdgeStatus.REVIEW_NEEDED,
                tolerance_context=(f"external claim held: {why}. Agent judged '{relation}' ({note}); an agent "
                                   f"can't clear a flag on external content, only the user can"),
                decided_by=by, floor=True,
            )
            store.add_edge(edge)
            return Commit(node=candidate, edge=edge, held=True, held_because=why)

    store.add_node(candidate)
    if relation == "new":
        return Commit(node=candidate, edge=None)

    edge_type, status = {
        "reinforces": (EdgeType.REINFORCES, None),
        "coexists": (EdgeType.COEXISTS, None),
        "collides": (EdgeType.COLLIDES, EdgeStatus.OPEN),
        "exception_of": (EdgeType.SCOPE_PARENT, None),
        "supersedes": (EdgeType.SUPERSEDES, None),
    }[relation]
    edge = Edge(id=f"{candidate.id}-{relation}-{related.id}", source_id=candidate.id, target_id=related.id,
                type=edge_type, status=status, tolerance_context=note, decided_by=by)
    if relation == "reinforces":
        related.weight = min(1.0, related.weight + bump)
        related.evidence_count += 1
        related.last_touched = _utcnow()
    elif relation == "supersedes":
        edge.resolution_why, edge.resolved_at = reason.strip(), _utcnow()
    store.add_edge(edge)
    return Commit(node=candidate, edge=edge)


# -- reading it back -------------------------------------------------------------------

def _stamp(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def node_view(store: InMemoryStore, node: Node) -> dict:
    """One claim as the agent reads it: the text, its visible weight and the judgment behind it, and
    whatever disputes are still open against it."""
    disputes = [{"edge": e.id, "type": e.type.value, "status": e.status.value, "with": e.target_id if e.source_id == node.id else e.source_id,
                 "note": e.tolerance_context, "held_for_user": e.floor}
                for e in store.get_edges_for_node(node.id) if e.status in (EdgeStatus.OPEN, EdgeStatus.REVIEW_NEEDED)]
    return {"id": node.id, "text": node.text, "domain": node.domain, "referent": node.referent,
            "scope": node.scope.value, "weight": round(node.weight, 3), "evidence_count": node.evidence_count,
            "origin": node.origin.value, "source": node.source, "author": node.author, "why": node.why,
            "recorded": _stamp(node.origin_date), "last_touched": _stamp(node.last_touched), "disputes": disputes}


def recall(store: InMemoryStore, *, query: str | None = None, referent: str | None = None,
           domain: str | None = None, include_history: bool = False, limit: int = 10) -> dict:
    """What the memory currently believes, strongest first, with its disputes visible. With `query`,
    ranked by wording overlap then weight. include_history adds superseded and released claims.

    A claim held for the user (external content in conflict, see commit) is not a belief: it is listed under
    "held_for_user", visible and waiting, until the user resolves it."""
    held_ids = {e.source_id for e in store.all_edges()
                if e.floor and e.status in (EdgeStatus.OPEN, EdgeStatus.REVIEW_NEEDED)}
    wanted = lambda n: (referent is None or n.referent == referent) and (domain is None or n.domain == domain)  # noqa: E731
    held = [n for n in live_nodes(store) if n.id in held_ids and wanted(n)]
    live = [n for n in live_nodes(store) if n.origin != Origin.DORMANT and n.id not in held_ids and wanted(n)]
    if query:
        live.sort(key=lambda n: (_overlap(query, n.text), n.weight), reverse=True)
        live = [n for n in live if _overlap(query, n.text) > 0]
    else:
        live.sort(key=lambda n: n.weight, reverse=True)
    out = {"beliefs": [node_view(store, n) for n in live[:limit]], "total_matching": len(live),
           "held_for_user": [node_view(store, n) for n in held], "pending_reviews": len(pending_reviews(store))}
    if include_history:
        live_ids = {n.id for n in live_nodes(store)}
        superseded_by = {e.target_id: (e.source_id, e.resolution_why) for e in store.all_edges() if e.type == EdgeType.SUPERSEDES}
        history = []
        for n in store.all_nodes():
            if n.id in live_ids or n.origin == Origin.DORMANT:
                continue
            if (referent and n.referent != referent) or (domain and n.domain != domain):
                continue
            entry = node_view(store, n)
            if n.id in superseded_by:
                entry["superseded_by"], entry["superseded_why"] = superseded_by[n.id]
            if n.released_at:
                entry["released"], entry["released_why"] = _stamp(n.released_at), n.release_why
            history.append(entry)
        out["history"] = history
    return out


def release(store: InMemoryStore, node_id: str, reason: str, by: str = "agent") -> Node:
    """Deliberate, examined release of a claim that is no longer load-bearing. Kept, never deleted."""
    node = next((n for n in live_nodes(store) if n.id == node_id), None)
    if node is None:
        raise ValueError(f"no live claim {node_id!r}")
    if not reason.strip():
        raise ValueError("a release needs a reason")
    if any(e.status in (EdgeStatus.OPEN, EdgeStatus.REVIEW_NEEDED) for e in store.get_edges_for_node(node_id)):
        raise ValueError(f"{node_id} is part of an unresolved dispute: resolve it first")
    node.released_at, node.release_why = _utcnow(), f"{by}: {reason.strip()}"
    return node


def reflect(store: InMemoryStore, *, stale_days: float = 30, low_weight: float = 0.15,
            now: datetime | None = None) -> dict:
    """The material for a reflective pass, for the agent to act on (release, reinforce, resolve). Changes
    nothing: deciding what is still load-bearing is the agent's job, not a timer's."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=stale_days)
    live = [n for n in live_nodes(store) if n.origin != Origin.DORMANT]
    return {
        "stale": [node_view(store, n) for n in live if n.last_touched < cutoff],
        "low_weight": [node_view(store, n) for n in live if n.weight <= low_weight],
        "pending_reviews": [{"edge": e.id, "type": e.type.value, "status": e.status.value, "from": e.source_id,
                             "to": e.target_id, "note": e.tolerance_context, "held_for_user": e.floor}
                            for e in pending_reviews(store)],
    }
