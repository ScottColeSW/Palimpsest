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
    def __init__(self, path: str | Path = DEFAULT_PATH, author: str = "agent", floor: bool = True,
                 embedder=None) -> None:
        """embedder: optional callable text -> list[float] (see embed.py). With one, claims are found by meaning
        as well as wording; without, retrieval is wording only."""
        self.store = SQLiteStore(path)
        self.author = author
        self.floor = floor
        self.embedder = embedder
        self._embedded: dict[str, list[float] | None] = {}
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

    def _embed(self, text: str) -> list[float] | None:
        """A failed embedding is not an error: that claim is just found by wording."""
        if self.embedder is None:
            return None
        if text not in self._embedded:
            try:
                self._embedded[text] = self.embedder(text)
            except Exception:  # noqa: BLE001
                self._embedded[text] = None
        return self._embedded[text]

    def _candidate(self, text, domain, referent, scope, weight, source, why) -> Node:
        if scope not in _SCOPES:
            raise ValueError(f"scope must be 'general' or 'instance', got {scope!r}")
        if not text.strip():
            raise ValueError("a claim needs text")
        return Node(id=f"c{uuid.uuid4().hex[:8]}", text=text.strip(), domain=domain, referent=referent,
                    scope=_SCOPES[scope], origin=Origin.EPISODE, weight=weight, why=why, source=source,
                    author=self.author, embedding=self._embed(text.strip()))

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
                           "similarity": None if n.similarity is None else round(n.similarity, 2),
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

    def _known(self) -> list[dict]:
        seen = {(n.domain, n.referent) for n in self.store.all_nodes() if n.origin != Origin.DORMANT}
        return [{"domain": d, "referent": r, "kind": DOMAIN_KINDS[d].value} for d, r in sorted(seen) if d in DOMAIN_KINDS]

    def _dormant(self, text: str, why: str, domain: str = "unfiled", referent: str = "unfiled") -> Node:
        node = Node(id=f"c{uuid.uuid4().hex[:8]}", text=text.strip()[:400], domain=domain, referent=referent,
                    scope=Scope.GENERAL, origin=Origin.DORMANT, weight=0.05, why=why, author=self.author)
        self.store.add_node(node)
        self.store.save()
        return node

    @_locked
    def learn(self, text: str, *, framer=None, judge=None, source: str = "agent", domain: str | None = None,
              referent: str | None = None, scope: str | None = None, domain_kind: str | None = None) -> dict:
        """The whole loop with a model in the agent's seat and no protocol in the way: frame the text (is it worth
        keeping, and under what domain, referent and scope), see what is held nearby, have the judge decide how it
        relates, and record that. `framer` and `judge` are callables (see judge.py); the defaults use a local Ollama
        model. Anything given explicitly (domain, referent, scope, domain_kind) overrides the framer.

        A model that errors or answers outside the schema decides nothing: the text is kept as dormant material,
        unjudged, never dropped and never believed. External content keeps the injection boundary from agent.py:
        it can't supersede (a judged replacement is recorded as a collision instead) and is held for the user when
        the rules would hold it, whatever the judge said."""
        from . import judge as defaults
        framer = framer or defaults.ollama_framer()
        judge = judge or defaults.ollama_judge()
        try:
            frame = framer(text, self._known())
        except Exception as exc:  # noqa: BLE001 -- a model failure must not decide anything
            return {"status": "unjudged", "why": f"framing failed: {exc}", "dormant": self._dormant(text, "unframed").id}
        if not frame.get("worth_keeping", False):
            return {"status": "dormant", "why": "judged not worth keeping yet", "dormant": self._dormant(text, "not judged significant").id}
        claim = (frame.get("claim") or text).strip()
        domain = domain or frame.get("domain") or ""
        referent = referent or frame.get("referent") or ""
        scope = scope or frame.get("scope") or "general"
        # A domain that is already declared keeps its kind; otherwise the caller's, then the framer's
        kind = DOMAIN_KINDS[domain].value if domain in DOMAIN_KINDS else (domain_kind or frame.get("kind"))
        if not domain or not referent or scope not in _SCOPES or kind not in ("attribute", "event"):
            return {"status": "unjudged", "why": f"unusable framing: {frame}", "dormant": self._dormant(text, "unframed").id}

        near = self.consult(claim, domain, referent, scope, kind)
        try:
            verdict = defaults.normalize_verdict(judge(claim, near["neighbors"], kind), {n["id"] for n in near["neighbors"]})
        except Exception as exc:  # noqa: BLE001
            return {"status": "unjudged", "why": f"judging failed: {exc}", "frame": frame,
                    "dormant": self._dormant(claim, "unjudged", domain, referent).id}
        relation, related_id, reason, weight = verdict["relation"], verdict["related_id"], verdict["reason"], verdict["weight"]
        if source == "external" and relation == "supersedes":
            relation, reason = "collides", f"{reason} (judged a replacement, recorded as a collision: external content can't supersede)"
        done = self.remember(claim, domain, referent, relation, reason, scope, related_id, weight, source, domain_kind=kind)
        return {"status": "held" if done["held"] else "remembered", "frame": frame, "judged": relation,
                "related_id": related_id, "reason": reason, "coerced": verdict["coerced"], **done}

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
    def reindex(self) -> int:
        """Embed every claim that has no vector yet (after adding an embedder to an existing store)."""
        done = 0
        for node in self.store.all_nodes():
            if node.embedding is None and node.origin != Origin.DORMANT:
                node.embedding = self._embed(node.text)
                done += node.embedding is not None
        self.store.save()
        return done

    @_locked
    def close(self) -> None:
        self.store.close()
