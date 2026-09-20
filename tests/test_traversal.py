"""Proves the edge-walking algorithm itself, independent of Elasticsearch.

FakeStore implements the same EdgeLookup protocol ElasticStore does,
so these tests exercise the real traversal code in palimpsest/traversal.py
-- not a simulation of it -- just against an in-memory dict instead of
a live cluster.
"""

from __future__ import annotations

from typing import Iterable

import pytest

from palimpsest.models import Edge, EdgeType, Node, Origin, Scope
from palimpsest.traversal import trace_chain, walk


class FakeStore:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def get_edges_for_node(
        self, node_id: str, edge_types: Iterable[EdgeType] | None = None
    ) -> list[Edge]:
        types = set(edge_types) if edge_types is not None else None
        return [
            e
            for e in self.edges
            if (node_id in (e.source_id, e.target_id)) and (types is None or e.type in types)
        ]


def _node(node_id: str, domain: str = "food") -> Node:
    return Node(
        id=node_id,
        text=f"conclusion {node_id}",
        domain=domain,
        referent="agent-b",
        scope=Scope.GENERAL,
        origin=Origin.EPISODE,
    )


def _edge(edge_id: str, source: str, target: str, edge_type: EdgeType) -> Edge:
    return Edge(id=edge_id, source_id=source, target_id=target, type=edge_type)


@pytest.fixture
def chain_store() -> FakeStore:
    """A -> B -> C -> D, a straight line, reinforces edges."""
    store = FakeStore()
    for n in "ABCD":
        store.add_node(_node(n))
    store.add_edge(_edge("e1", "A", "B", EdgeType.REINFORCES))
    store.add_edge(_edge("e2", "B", "C", EdgeType.REINFORCES))
    store.add_edge(_edge("e3", "C", "D", EdgeType.REINFORCES))
    return store


def test_walk_reaches_everything_within_max_hops(chain_store: FakeStore):
    result = walk(chain_store, "A", max_hops=2)
    assert set(result.keys()) == {"B", "C"}
    assert result["B"].hops == 1
    assert result["C"].hops == 2
    assert "D" not in result


def test_walk_respects_larger_max_hops(chain_store: FakeStore):
    result = walk(chain_store, "A", max_hops=3)
    assert set(result.keys()) == {"B", "C", "D"}
    assert result["D"].path == ["e1", "e2", "e3"]


def test_walk_never_includes_start_node(chain_store: FakeStore):
    result = walk(chain_store, "A", max_hops=5)
    assert "A" not in result


def test_walk_zero_hops_returns_nothing(chain_store: FakeStore):
    assert walk(chain_store, "A", max_hops=0) == {}


def test_walk_rejects_negative_max_hops(chain_store: FakeStore):
    with pytest.raises(ValueError):
        walk(chain_store, "A", max_hops=-1)


def test_walk_edges_are_traversed_undirected(chain_store: FakeStore):
    # source_id="C", target_id="D" -- walking from D should still reach C.
    result = walk(chain_store, "D", max_hops=1)
    assert "C" in result


def test_walk_filters_by_edge_type():
    store = FakeStore()
    for n in "ABC":
        store.add_node(_node(n))
    store.add_edge(_edge("e1", "A", "B", EdgeType.REINFORCES))
    store.add_edge(_edge("e2", "A", "C", EdgeType.COLLIDES))

    reinforced_only = walk(store, "A", edge_types=[EdgeType.REINFORCES], max_hops=1)
    assert set(reinforced_only.keys()) == {"B"}


def test_walk_handles_cycles_without_hanging():
    store = FakeStore()
    for n in "ABC":
        store.add_node(_node(n))
    store.add_edge(_edge("e1", "A", "B", EdgeType.COLLIDES))
    store.add_edge(_edge("e2", "B", "C", EdgeType.COLLIDES))
    store.add_edge(_edge("e3", "C", "A", EdgeType.COLLIDES))  # closes the loop

    result = walk(store, "A", max_hops=10)
    # A triangle, walked undirected: both B (via e1) and C (via e3) are
    # one hop from A directly -- the cycle closing doesn't make C
    # "farther away", it gives A a second, equally short way in. The
    # thing actually under test is that closing the loop doesn't hang
    # or duplicate C once BFS reaches it a second time via B.
    assert set(result.keys()) == {"B", "C"}
    assert result["B"].hops == 1
    assert result["C"].hops == 1


def test_trace_chain_finds_shortest_path(chain_store: FakeStore):
    path = trace_chain(chain_store, "A", "D")
    assert path == ["e1", "e2", "e3"]


def test_trace_chain_same_start_and_end_is_empty_path(chain_store: FakeStore):
    assert trace_chain(chain_store, "A", "A") == []


def test_trace_chain_returns_none_when_unreachable():
    store = FakeStore()
    store.add_node(_node("A"))
    store.add_node(_node("Z"))
    assert trace_chain(store, "A", "Z", max_hops=5) is None


def test_trace_chain_respects_edge_type_filter():
    """Only following SUPERSEDES/RECONCILED_WITH should skip a shorter
    path that goes through an unrelated REINFORCES edge -- e.g.
    tracing resolution history specifically, not every relationship."""
    store = FakeStore()
    for n in "ABC":
        store.add_node(_node(n))
    store.add_edge(_edge("e1", "A", "B", EdgeType.REINFORCES))  # shorter, wrong kind
    store.add_edge(_edge("e2", "A", "C", EdgeType.SUPERSEDES))
    store.add_edge(_edge("e3", "C", "B", EdgeType.SUPERSEDES))

    path = trace_chain(store, "A", "B", edge_types=[EdgeType.SUPERSEDES], max_hops=5)
    assert path == ["e2", "e3"]
