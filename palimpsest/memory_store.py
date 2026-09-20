"""In-memory stand-in for ElasticStore -- same EdgeLookup interface,
no cluster required. For local demos and anywhere a live ES isn't
available; swap for store.ElasticStore without touching traversal.py
or anything built on top of it, since both implement the same shape.
"""

from __future__ import annotations

from typing import Iterable

from .models import Edge, Node


class InMemoryStore:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def add_edge(self, edge: Edge) -> None:
        self.edges[edge.id] = edge

    def get_edges_for_node(self, node_id: str, edge_types: Iterable | None = None) -> list[Edge]:
        types = set(edge_types) if edge_types is not None else None
        return [
            e
            for e in self.edges.values()
            if node_id in (e.source_id, e.target_id) and (types is None or e.type in types)
        ]

    def all_nodes(self) -> list[Node]:
        return list(self.nodes.values())

    def all_edges(self) -> list[Edge]:
        return list(self.edges.values())
