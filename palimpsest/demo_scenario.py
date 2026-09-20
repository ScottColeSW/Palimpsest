"""A small, scripted, deterministic scenario for the local demo server.

Not a real reading pipeline -- there's no text parser here, no
Stability, nothing from StoryTeller (that project's incomplete and
wasn't shared). This is honest, hand-authored seed data standing in
for what a real "read a book, form beliefs, hit contradictions" loop
would produce, so there's something real to look at on the graph
before that pipeline exists. Same reason Shoe Adventure ships
seed-agent-memory -- a demo shouldn't be dead on screen just because
the real data source isn't built yet.

Ten ticks, in order, walking one small character-appearance thread
through: a seeded (unearned) belief, real reinforcement, a
general/instance non-collision (the dog/Rex case), a real collision
going OPEN, and a resolution to RECONCILED_TOGETHER with a dated why
-- the whole apparatus in miniature.
"""

from __future__ import annotations

from dataclasses import dataclass

from .memory_store import InMemoryStore
from .models import Edge, EdgeStatus, EdgeType, Node, Origin, Scope


@dataclass
class TickResult:
    tick: int
    description: str
    done: bool
    kind: str  # "seed" | "reinforce" | "scope" | "collide_open" | "still_open" | "resolve"


def _n(id: str, text: str, domain: str, referent: str, scope: Scope, origin: Origin, weight: float) -> Node:
    return Node(id=id, text=text, domain=domain, referent=referent, scope=scope, origin=origin, weight=weight)


def _e(id: str, source: str, target: str, type: EdgeType, **kw) -> Edge:
    return Edge(id=id, source_id=source, target_id=target, type=type, **kw)


class Scenario:
    def __init__(self) -> None:
        self.store = InMemoryStore()
        self.tick = 0
        self._steps = [
            self._t0_seed,
            self._t1_reinforce_hair,
            self._t2_reinforce_eyes,
            self._t3_scope_non_collision,
            self._t4_real_collision_opens,
            self._t5_still_open,
            self._t6_resolve_reconciled,
        ]

    def state(self) -> dict:
        return {
            "tick": self.tick,
            "nodes": [self._node_json(n) for n in self.store.all_nodes()],
            "edges": [self._edge_json(e) for e in self.store.all_edges()],
        }

    def _node_json(self, n: Node) -> dict:
        return {
            "id": n.id,
            "text": n.text,
            "domain": n.domain,
            "referent": n.referent,
            "scope": n.scope.value,
            "origin": n.origin.value,
            "weight": round(n.weight, 3),
            "evidence_count": n.evidence_count,
        }

    def _edge_json(self, e: Edge) -> dict:
        return {
            "id": e.id,
            "source": e.source_id,
            "target": e.target_id,
            "type": e.type.value,
            "status": e.status.value if e.status else None,
            "tolerance_context": e.tolerance_context,
            "resolution_why": e.resolution_why,
        }

    def advance(self) -> TickResult:
        if self.tick >= len(self._steps):
            return TickResult(self.tick, "Scenario complete -- no more scripted ticks.", True, "done")
        description, kind = self._steps[self.tick]()
        self.tick += 1
        return TickResult(self.tick, description, self.tick >= len(self._steps), kind)

    # -- scripted ticks, each returns (description, kind) ----------------

    def _t0_seed(self) -> tuple[str, str]:
        self.store.add_node(_n(
            "elena-hair-seed", "raven black hair", "appearance", "elena",
            Scope.GENERAL, Origin.SEED, weight=0.3,
        ))
        self.store.add_node(_n(
            "elena-eyes-seed", "green eyes", "appearance", "elena",
            Scope.GENERAL, Origin.SEED, weight=0.3,
        ))
        self.store.add_node(_n(
            "marcus-temperament-seed", "quick-tempered", "temperament", "marcus",
            Scope.GENERAL, Origin.SEED, weight=0.3,
        ))
        return "Seeded three unearned beliefs (dim, origin=seed) -- nothing has confirmed them yet.", "seed"

    def _t1_reinforce_hair(self) -> tuple[str, str]:
        node = _n(
            "ch2-hair-mention", "her raven hair caught the light", "appearance", "elena",
            Scope.GENERAL, Origin.EPISODE, weight=0.6,
        )
        self.store.add_node(node)
        self.store.add_edge(_e("e1", node.id, "elena-hair-seed", EdgeType.REINFORCES))
        seed = self.store.get_node("elena-hair-seed")
        seed.weight = min(1.0, seed.weight + 0.25)
        seed.evidence_count += 1
        return "Ch.2: hair mention reinforces the seed -- its trust discount starts closing, the seed record itself doesn't change.", "reinforce"

    def _t2_reinforce_eyes(self) -> tuple[str, str]:
        node = _n(
            "ch5-eyes-mention", "green eyes narrowed", "appearance", "elena",
            Scope.GENERAL, Origin.EPISODE, weight=0.6,
        )
        self.store.add_node(node)
        self.store.add_edge(_e("e2", node.id, "elena-eyes-seed", EdgeType.REINFORCES))
        seed = self.store.get_node("elena-eyes-seed")
        seed.weight = min(1.0, seed.weight + 0.25)
        seed.evidence_count += 1
        return "Ch.5: eyes mention reinforces the seed the same way.", "reinforce"

    def _t3_scope_non_collision(self) -> tuple[str, str]:
        node = _n(
            "ch9-marcus-calm", "Marcus, uncharacteristically patient, waited",
            "temperament", "marcus", Scope.INSTANCE, Origin.EPISODE, weight=0.5,
        )
        self.store.add_node(node)
        self.store.add_edge(_e("e3", node.id, "marcus-temperament-seed", EdgeType.SCOPE_PARENT))
        return "Ch.9: Marcus acts calm in one scene -- instance-scoped, linked as an exception under the general trait, NOT flagged as a collision. The dog/Rex case, for real.", "scope"

    def _t4_real_collision_opens(self) -> tuple[str, str]:
        node = _n(
            "ch14-hair-contradiction", "her golden curls", "appearance", "elena",
            Scope.GENERAL, Origin.EPISODE, weight=0.6,
        )
        self.store.add_node(node)
        self.store.add_edge(_e(
            "e4", node.id, "elena-hair-seed", EdgeType.COLLIDES,
            status=EdgeStatus.OPEN,
            tolerance_context="appearance/identity is cliff-shaped -- near-zero tolerance for an unexplained contradiction",
        ))
        return "Ch.14: 'golden curls' directly contradicts the standing hair belief, same scope, same referent. Real collision -- edge goes OPEN, dated, nothing hidden.", "collide_open"

    def _t5_still_open(self) -> tuple[str, str]:
        return "No new evidence this tick. The collision stays OPEN -- unresolved is a legitimate state, not a bug to hide.", "still_open"

    def _t6_resolve_reconciled(self) -> tuple[str, str]:
        edge = self.store.edges["e4"]
        edge.status = EdgeStatus.RECONCILED_TOGETHER
        edge.resolution_why = (
            "Ch.14 footnote reveals 'golden curls' describes Elena's sister, "
            "impersonating her -- not Elena. Both descriptions are correct once "
            "the referent is corrected; nothing was ever actually wrong."
        )
        return "Ch.14 footnote resolves it: RECONCILED_TOGETHER, not vindicated-vs-wrong -- both sides were right about different people.", "resolve"
