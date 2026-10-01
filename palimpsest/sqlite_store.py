"""SQLite persistence for the mesh, the store that has actually run.

An InMemoryStore that loads everything at open and writes it back on save(),
so consult() and everything built on it work unchanged. save() upserts every
node and edge in one transaction: consult and commit mutate nodes in place
(weights, release marks), so a per-write hook would miss them. Fine at the
scale an agent's curated memory lives at; it is deliberately a curated store,
not a corpus. Standard library only.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .consult import DOMAIN_KINDS
from .memory_store import InMemoryStore
from .models import DomainKind, Edge, EdgeStatus, EdgeType, Node, Origin, Scope


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _node_doc(n: Node) -> str:
    return json.dumps({
        "text": n.text, "domain": n.domain, "referent": n.referent, "scope": n.scope.value, "origin": n.origin.value,
        "why": n.why, "weight": n.weight, "evidence_count": n.evidence_count, "embedding": n.embedding,
        "origin_date": n.origin_date.isoformat(), "last_touched": n.last_touched.isoformat(),
        "author": n.author, "source": n.source,
        "released_at": n.released_at.isoformat() if n.released_at else None, "release_why": n.release_why,
    })


def _node_from(node_id: str, raw: str) -> Node:
    d = json.loads(raw)
    return Node(id=node_id, text=d["text"], domain=d["domain"], referent=d["referent"], scope=Scope(d["scope"]),
                origin=Origin(d["origin"]), why=d["why"], weight=d["weight"], evidence_count=d["evidence_count"],
                embedding=d["embedding"], origin_date=_dt(d["origin_date"]), last_touched=_dt(d["last_touched"]),
                author=d["author"], source=d["source"], released_at=_dt(d["released_at"]), release_why=d["release_why"])


def _edge_doc(e: Edge) -> str:
    return json.dumps({
        "source_id": e.source_id, "target_id": e.target_id, "type": e.type.value,
        "status": e.status.value if e.status else None, "date": e.date.isoformat(),
        "tolerance_context": e.tolerance_context, "resolution_why": e.resolution_why,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "decided_by": e.decided_by, "floor": e.floor,
    })


def _edge_from(edge_id: str, raw: str) -> Edge:
    d = json.loads(raw)
    return Edge(id=edge_id, source_id=d["source_id"], target_id=d["target_id"], type=EdgeType(d["type"]),
                status=EdgeStatus(d["status"]) if d["status"] else None, date=_dt(d["date"]),
                tolerance_context=d["tolerance_context"], resolution_why=d["resolution_why"],
                resolved_at=_dt(d["resolved_at"]), decided_by=d["decided_by"], floor=d["floor"])


class SQLiteStore(InMemoryStore):
    def __init__(self, path: str | Path = ":memory:") -> None:
        super().__init__()
        if str(path) == ":memory:":
            target = ":memory:"
        else:
            target = Path(path).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
        # Used from whichever thread a server runs tools on; Memory serializes access with a lock
        self.db = sqlite3.connect(str(target), check_same_thread=False)
        with self.db:
            self.db.executescript(
                "CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, doc TEXT NOT NULL);"
                "CREATE TABLE IF NOT EXISTS edges (id TEXT PRIMARY KEY, doc TEXT NOT NULL);"
                "CREATE TABLE IF NOT EXISTS domains (name TEXT PRIMARY KEY, kind TEXT NOT NULL);")
        for node_id, raw in self.db.execute("SELECT id, doc FROM nodes"):
            self.nodes[node_id] = _node_from(node_id, raw)
        for edge_id, raw in self.db.execute("SELECT id, doc FROM edges"):
            self.edges[edge_id] = _edge_from(edge_id, raw)
        self.domains = {name: DomainKind(kind) for name, kind in self.db.execute("SELECT name, kind FROM domains")}
        DOMAIN_KINDS.update(self.domains)

    def set_domain_kind(self, name: str, kind: DomainKind) -> None:
        self.domains[name] = kind
        DOMAIN_KINDS[name] = kind

    def save(self) -> None:
        with self.db:
            self.db.executemany(
                "INSERT INTO nodes (id, doc) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET doc=excluded.doc",
                [(n.id, _node_doc(n)) for n in self.nodes.values()])
            self.db.executemany(
                "INSERT INTO edges (id, doc) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET doc=excluded.doc",
                [(e.id, _edge_doc(e)) for e in self.edges.values()])
            self.db.executemany(
                "INSERT INTO domains (name, kind) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET kind=excluded.kind",
                [(name, kind.value) for name, kind in self.domains.items()])

    def close(self) -> None:
        self.db.close()
