"""Elasticsearch-backed storage for nodes and edges. Experimental, optional.

    pip install "palimpsest[elastic]"

Not the store anything runs on. SQLiteStore (sqlite_store.py) is, and it is
what the memory, the demos and the MCP server use. This one is incomplete in
two ways you should know about before choosing it:

- It implements the traversal protocol (add_node, get_node, add_edge,
  get_edges_for_node) plus find_similar_nodes, but not all_nodes() or
  all_edges(), which consult(), recall(), pending_reviews() and decay_store()
  all call. It can back graph walking, not the memory itself.
- It has never been run against a live cluster. The query DSL is written
  against the elasticsearch-py 8.x documentation, which is not the same claim
  as verified.

A curated memory holds hundreds to thousands of claims, which SQLite handles
without a server. This store is worth finishing only if scale ever demands it.

Two indices: "palimpsest-nodes" and "palimpsest-edges". Kept separate
rather than one index with a type discriminator -- nodes carry a
dense_vector for kNN similarity search, edges never need one, and
mixing them would mean every edge document wastes that field's index
overhead for nothing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

try:
    from elasticsearch import Elasticsearch
except ImportError as exc:  # pragma: no cover
    raise ImportError('ElasticStore needs the optional dependency: pip install "palimpsest[elastic]"') from exc

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
            "author": {"type": "keyword"},
            "source": {"type": "keyword"},
            "released_at": {"type": "date"},
            "release_why": {"type": "text"},
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
            "decided_by": {"type": "keyword"},
            "floor": {"type": "boolean"},
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
        "author": node.author,
        "source": node.source,
        "released_at": node.released_at.isoformat() if node.released_at else None,
        "release_why": node.release_why,
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
        author=doc.get("author", ""),
        source=doc.get("source", "agent"),
        released_at=datetime.fromisoformat(doc["released_at"]) if doc.get("released_at") else None,
        release_why=doc.get("release_why", ""),
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
        "decided_by": edge.decided_by,
        "floor": edge.floor,
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
        decided_by=doc.get("decided_by", ""),
        floor=doc.get("floor", False),
    )


class ElasticStore:
    """Implements traversal.EdgeLookup, plus node/edge writes and
    domain-scoped kNN similarity search for collision-detection
    candidates. Domain-scoped deliberately -- domains don't share a
    tolerance currency (see DESIGN.md), so a global similarity search
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
