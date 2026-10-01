"""Memory: one object an agent (or an MCP server) can hold.

A thin facade over agent.py and a SQLiteStore. It owns persistence, ids, and
the domain registry, and returns plain JSON-safe dicts. All judgment stays with
the caller; see agent.py for what the library enforces regardless.
"""

from __future__ import annotations

import functools
import threading
import uuid
from pathlib import Path

from . import agent
from .consult import DOMAIN_KINDS, pending_reviews, resolve as resolve_edge
from .models import DomainKind, EdgeStatus, Node, Origin, Scope
from .sqlite_store import SQLiteStore

DEFAULT_PATH = Path("~/.palimpsest/memory.db")
_SCOPES = {"general": Scope.GENERAL, "instance": Scope.INSTANCE}
# Resolutions a decision can end in; OPEN and REVIEW_NEEDED are what is being decided out of
_STATUSES = {s.value: s for s in EdgeStatus if s not in (EdgeStatus.OPEN, EdgeStatus.REVIEW_NEEDED)}


def _locked(method):
    """One operation at a time: a server may call tools from several threads."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


class Memory:
    def __init__(self, path: str | Path = DEFAULT_PATH, author: str = "agent", floor: bool = True) -> None:
        self.store = SQLiteStore(path)
        self.author = author
        self.floor = floor
        self._lock = threading.RLock()

    # -- helpers --------------------------------------------------------------------
    def _declare(self, domain: str, kind: str | None) -> None:
        known = DOMAIN_KINDS.get(domain)
        if kind is None:
            if known is None:
                raise ValueError(
                    f"unknown domain {domain!r}: say whether it is 'attribute' (one true value at a time, e.g. a "
                    f"limit or a preference) or 'event' (many compatible things can be true, e.g. what happened) "
                    f"with domain_kind")
            return
        wanted = DomainKind(kind)
        if domain in self.store.domains:
            if self.store.domains[domain] != wanted:
                raise ValueError(f"domain {domain!r} is already declared {self.store.domains[domain].value}")
        else:
            self.store.set_domain_kind(domain, wanted)

    def _candidate(self, text, domain, referent, scope, weight, source, why) -> Node:
        if scope not in _SCOPES:
            raise ValueError(f"scope must be 'general' or 'instance', got {scope!r}")
        if not text.strip():
            raise ValueError("a claim needs text")
        return Node(id=f"c{uuid.uuid4().hex[:8]}", text=text.strip(), domain=domain, referent=referent,
                    scope=_SCOPES[scope], origin=Origin.EPISODE, weight=weight, why=why, source=source,
                    author=self.author)

    # -- the tools ------------------------------------------------------------------
    @_locked
    def consult(self, text: str, domain: str, referent: str, scope: str = "general",
                domain_kind: str | None = None) -> dict:
        """Read-only: nothing is remembered. A newly declared domain is kept."""
        self._declare(domain, domain_kind)
        proposal = agent.propose(self.store, self._candidate(text, domain, referent, scope, 0.5, "agent", ""))
        self.store.save()
        return {
            "neighbors": [{**agent.node_view(self.store, n.node), "overlap": round(n.overlap, 2),
                           "same_fact": n.same_fact} for n in proposal.neighbors],
            "rules_opinion": proposal.rules_opinion,
            "domain_kind": DOMAIN_KINDS[domain].value,
        }

    @_locked
    def remember(self, text: str, domain: str, referent: str, relation: str, reason: str, scope: str = "general",
                 related_id: str | None = None, weight: float = 0.5, source: str = "agent", why: str = "",
                 domain_kind: str | None = None, bump: float = agent.REINFORCE_BUMP) -> dict:
        if not 0.0 <= weight <= 1.0:
            raise ValueError("weight must be between 0 and 1")
        self._declare(domain, domain_kind)
        node = self._candidate(text, domain, referent, scope, weight, source, why or reason)
        done = agent.commit(self.store, node, relation=relation, reason=reason, related_id=related_id,
                            by=self.author, floor=self.floor, bump=bump)
        self.store.save()
        out = {"id": done.node.id, "held": done.held, "relation": relation,
               "edge": done.edge.id if done.edge else None}
        if done.held:
            out["held_because"] = done.held_because
            out["next"] = "A flag on external content can only be cleared by the user (resolve with by='user')."
        return out

    @_locked
    def recall(self, query: str | None = None, referent: str | None = None, domain: str | None = None,
               include_history: bool = False, limit: int = 10) -> dict:
        return agent.recall(self.store, query=query, referent=referent, domain=domain,
                            include_history=include_history, limit=limit)

    @_locked
    def review(self) -> dict:
        return {"pending": agent.reflect(self.store)["pending_reviews"]}

    @_locked
    def resolve(self, edge_id: str, status: str, reason: str, by: str = "agent") -> dict:
        if status not in _STATUSES:
            raise ValueError(f"status must be one of {sorted(_STATUSES)}, got {status!r}")
        edge = resolve_edge(self.store, edge_id, _STATUSES[status], reason, by=by)
        self.store.save()
        return {"edge": edge.id, "status": edge.status.value, "by": by,
                "pending_reviews": len(pending_reviews(self.store))}

    @_locked
    def release(self, node_id: str, reason: str) -> dict:
        node = agent.release(self.store, node_id, reason, by=self.author)
        self.store.save()
        return {"released": node.id, "why": node.release_why}

    @_locked
    def reflect(self, stale_days: float = 30, low_weight: float = 0.15) -> dict:
        return agent.reflect(self.store, stale_days=stale_days, low_weight=low_weight)

    @_locked
    def close(self) -> None:
        self.store.close()
