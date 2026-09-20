"""Multi-hop edge-walking over the mesh.

Elasticsearch gives fast 1-hop lookups (fetch edges touching a node)
and kNN similarity search for free, but not graph traversal -- its own
Graph feature is term co-occurrence over an index, not edge-walking.
This module is that missing layer, built against the EdgeLookup
protocol below rather than against Elasticsearch directly, so it can
be exercised with a plain in-memory fake and never needs a live
cluster to prove the algorithm itself is correct.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Protocol

from .models import Edge, EdgeType, Node


class EdgeLookup(Protocol):
    """The only two operations traversal actually needs. ElasticStore
    implements this against a live cluster; tests implement it against
    a dict."""

    def get_node(self, node_id: str) -> Node | None: ...

    def get_edges_for_node(
        self, node_id: str, edge_types: Iterable[EdgeType] | None = None
    ) -> list[Edge]: ...


def _other_end(edge: Edge, node_id: str) -> str:
    return edge.target_id if edge.source_id == node_id else edge.source_id


@dataclass
class WalkStep:
    node_id: str
    hops: int
    path: list[str]  # edge ids from the start node to this one


def walk(
    lookup: EdgeLookup,
    start_id: str,
    edge_types: Iterable[EdgeType] | None = None,
    max_hops: int = 3,
) -> dict[str, WalkStep]:
    """Breadth-first reach from start_id, at most max_hops away.

    Edges are treated as undirected for this general traversal --
    reinforces/collides/reconciled_with all make sense walked either
    way. Cycle protection is unconditional (a visited set covering
    every node touched, not just ones matching edge_types) since the
    mesh can genuinely contain cycles: three mutually colliding
    nodes, or a reconciled_with edge looping back to an earlier one.
    Returns every reachable node keyed by id, never the start node
    itself.
    """
    if max_hops < 0:
        raise ValueError("max_hops must be >= 0")

    visited: dict[str, WalkStep] = {}
    seen_ids = {start_id}
    frontier: deque[tuple[str, int, list[str]]] = deque([(start_id, 0, [])])

    while frontier:
        node_id, hops, path = frontier.popleft()
        if hops == max_hops:
            continue
        for edge in lookup.get_edges_for_node(node_id, edge_types):
            neighbor = _other_end(edge, node_id)
            if neighbor in seen_ids:
                continue
            seen_ids.add(neighbor)
            step = WalkStep(node_id=neighbor, hops=hops + 1, path=path + [edge.id])
            visited[neighbor] = step
            frontier.append((neighbor, hops + 1, step.path))

    return visited


def trace_chain(
    lookup: EdgeLookup,
    start_id: str,
    end_id: str,
    edge_types: Iterable[EdgeType] | None = None,
    max_hops: int = 6,
) -> list[str] | None:
    """Shortest edge-id chain from start_id to end_id, or None if
    unreachable within max_hops. Answers "trace the chain that led to
    this reconciliation" -- e.g. edge_types=[SUPERSEDES,
    RECONCILED_WITH] to follow only resolution history, not every
    relationship in the mesh."""
    if start_id == end_id:
        return []

    result = walk(lookup, start_id, edge_types=edge_types, max_hops=max_hops)
    step = result.get(end_id)
    return step.path if step is not None else None
