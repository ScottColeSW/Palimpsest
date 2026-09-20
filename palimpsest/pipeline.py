"""Composes ingest.py and consult.py into the thing the demo actually
needs: one fixed-size chunk, classified, and -- if judged significant
-- checked against the mesh before being added, instead of dropped in
as an isolated node. Kept separate from both modules on purpose:
ingest.py doesn't need to know memory judgment exists, consult.py
doesn't need to know chunking exists. This is just the wiring.

Dormant material skips consult() entirely -- it was never judged
significant, so there's nothing to check it against; it still gets
stored, same as ingest.py always did, just via this one entry point
instead of two.
"""

from __future__ import annotations

from dataclasses import dataclass

from .consult import ConsultResult, Relation, apply_consult, consult
from .ingest import ClassifyFn, Intake, naive_placeholder_classifier
from .memory_store import InMemoryStore
from .models import Edge, Node, Origin


@dataclass
class PipelineResult:
    node: Node
    relation: Relation | None  # None for dormant material -- never consulted
    edge: Edge | None
    done: bool


def digest_and_consult(
    intake: Intake,
    store: InMemoryStore,
    classify: ClassifyFn = naive_placeholder_classifier,
) -> PipelineResult | None:
    """Advances digestion by one chunk, same as ingest.digest_next_chunk,
    but routes significant material through consult() instead of
    storing it blind. Returns None once the intake is fully digested."""
    if intake.fully_digested:
        return None

    end = min(intake.cursor + intake.chunk_size, len(intake.raw_text))
    chunk = intake.raw_text[intake.cursor : end]
    intake.cursor = end

    result = classify(chunk)
    node_id = f"{intake.id}-chunk-{len(intake.spawned_node_ids)}"

    if not result.significant:
        node = Node(
            id=node_id, text=result.text[:160], domain=intake.domain,
            referent=result.referent, scope=result.scope,
            origin=Origin.DORMANT, weight=0.05,
        )
        store.add_node(node)
        intake.spawned_node_ids.append(node.id)
        return PipelineResult(node=node, relation=None, edge=None, done=intake.fully_digested)

    candidate = Node(
        id=node_id, text=result.text[:160], domain=intake.domain,
        referent=result.referent, scope=result.scope,
        origin=Origin.EPISODE, weight=result.weight,
    )
    consult_result: ConsultResult = consult(store, candidate)
    edge = apply_consult(store, candidate, consult_result)
    intake.spawned_node_ids.append(candidate.id)
    return PipelineResult(node=candidate, relation=consult_result.relation, edge=edge, done=intake.fully_digested)
