"""Elasticsearch-backed storage for nodes and edges.

Not exercised against a live cluster in this session -- there isn't
one running here to test against. The query DSL below is written
against the elasticsearch-py 8.x client and is correct as far as the
API goes, but "correct against the docs" and "verified against a real
cluster" are different claims; treat this file as unverified until
it's actually run against one. traversal.py, by contrast, is tested
for real in tests/test_traversal.py against a plain in-memory fake --
that's the part of this layer that's actually proven right now.

Two indices: "palimpsest-nodes" and "palimpsest-edges". Kept separate
rather than one index with a type discriminator -- nodes carry a
dense_vector for kNN similarity search, edges never need one, and
mixing them would mean every edge document wastes that field's index
overhead for nothing.
"""

from __future__ import annotations

from typing import Iterable

from elasticsearch import Elasticsearch

from .models import Edge, EdgeStatus, EdgeType, Node, Origin, Scope

NODES_INDEX = "palimpsest-nodes"
EDGES_INDEX = "palimpsest-edges"

NODES_MAPPING = {
    "mappings": {
        "properties": {
            "text": {"type": "text"},
            "why": {"type": "text"},
            "domain": {"type": "keyword"},
            "referent": {"type": "keyword"},
            "scope": {"type": "keyword"},
            "origin": {"type": "keyword"},
            "weight": {"type": "float"},
            "evidence_count": {"type": "integer"},
            "embedding": {"type": "dense_vector", "dims": 768, "index": True, "similarity": "cosine"},
            "origin_date": {"type": "date"},
            "last_touched": {"type": "date"},
        }
    }
}

EDGES_MAPPING = {
    "mappings": {
        "properties": {
            "source_id": {"type": "keyword"},
            "target_id": {"type": "keyword"},
            "type": {"type": "keyword"},
            "status": {"type": "keyword"},
            "tolerance_context": {"type": "text"},
            "resolution_why": {"type": "text"},
            "date": {"type": "date"},
            "resolved_at": {"type": "date"},
        }
    }
}


def _node_to_doc(node: Node) -> dict:
    doc = {
        "text": node.text,
        "why": node.why,
        "domain": node.domain,
        "referent": node.referent,
        "scope": node.scope.value,
        "origin": node.origin.value,
        "weight": node.weight,
        "evidence_count": node.evidence_count,
        "origin_date": node.origin_date.isoformat(),
        "last_touched": node.last_touched.isoformat(),
    }
    if node.embedding is not None:
        doc["embedding"] = node.embedding
    return doc


def _doc_to_node(node_id: str, doc: dict) -> Node:
    return Node(
        id=node_id,
        text=doc["text"],
        why=doc.get("why", ""),
        domain=doc["domain"],
        referent=doc["referent"],
        scope=Scope(doc["scope"]),
        origin=Origin(doc["origin"]),
        weight=doc.get("weight", 0.5),
        evidence_count=doc.get("evidence_count", 0),
        embedding=doc.get("embedding"),
    )


def _edge_to_doc(edge: Edge) -> dict:
    return {
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "type": edge.type.value,
        "status": edge.status.value if edge.status else None,
        "tolerance_context": edge.tolerance_context,
        "resolution_why": edge.resolution_why,
        "date": edge.date.isoformat(),
        "resolved_at": edge.resolved_at.isoformat() if edge.resolved_at else None,
    }


def _doc_to_edge(edge_id: str, doc: dict) -> Edge:
    return Edge(
        id=edge_id,
        source_id=doc["source_id"],
        target_id=doc["target_id"],
        type=EdgeType(doc["type"]),
        status=EdgeStatus(doc["status"]) if doc.get("status") else None,
        tolerance_context=doc.get("tolerance_context", ""),
        resolution_why=doc.get("resolution_why", ""),
    )


class ElasticStore:
    """Implements traversal.EdgeLookup, plus node/edge writes and
    domain-scoped kNN similarity search for collision-detection
    candidates. Domain-scoped deliberately -- domains don't share a
    tolerance currency (see CLAUDE.md), so a global similarity search
    across every domain at once would surface false collision
    candidates between things that were never comparable to begin
    with."""

    def __init__(self, client: Elasticsearch):
        self._es = client

    def ensure_indices(self) -> None:
        if not self._es.indices.exists(index=NODES_INDEX):
            self._es.indices.create(index=NODES_INDEX, body=NODES_MAPPING)
        if not self._es.indices.exists(index=EDGES_INDEX):
            self._es.indices.create(index=EDGES_INDEX, body=EDGES_MAPPING)

    # -- nodes ---------------------------------------------------------

    def add_node(self, node: Node) -> None:
        self._es.index(index=NODES_INDEX, id=node.id, document=_node_to_doc(node), refresh=True)

    def get_node(self, node_id: str) -> Node | None:
        result = self._es.get(index=NODES_INDEX, id=node_id, ignore=[404])
        if not result.get("found"):
            return None
        return _doc_to_node(node_id, result["_source"])

    def find_similar_nodes(
        self, embedding: list[float], domain: str, top_k: int = 5
    ) -> list[tuple[Node, float]]:
        """Collision-detection candidates: nearest neighbors by
        embedding, restricted to one domain. The caller decides what a
        contradictory conclusion within those candidates looks like --
        this only narrows "what's even worth comparing"."""
        response = self._es.search(
            index=NODES_INDEX,
            knn={
                "field": "embedding",
                "query_vector": embedding,
                "k": top_k,
                "num_candidates": max(top_k * 10, 50),
                "filter": {"term": {"domain": domain}},
            },
        )
        return [
            (_doc_to_node(hit["_id"], hit["_source"]), hit["_score"])
            for hit in response["hits"]["hits"]
        ]

    # -- edges -----------------------------------------------------------

    def add_edge(self, edge: Edge) -> None:
        self._es.index(index=EDGES_INDEX, id=edge.id, document=_edge_to_doc(edge), refresh=True)

    def get_edges_for_node(
        self, node_id: str, edge_types: Iterable[EdgeType] | None = None
    ) -> list[Edge]:
        must = [
            {
                "bool": {
                    "should": [
                        {"term": {"source_id": node_id}},
                        {"term": {"target_id": node_id}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        ]
        if edge_types is not None:
            must.append({"terms": {"type": [t.value for t in edge_types]}})

        response = self._es.search(
            index=EDGES_INDEX,
            query={"bool": {"must": must}},
            size=1000,
        )
        return [_doc_to_edge(hit["_id"], hit["_source"]) for hit in response["hits"]["hits"]]
