"""Two real collisions, not invented ones -- unlike demo_scenario.py
(hand-authored fiction, because the placeholder classifier can't
detect semantic contradiction on its own), this uses actual quoted
text from Winnie-the-Pooh chapter II (story_files/winnie-the-pooh.txt,
gutenberg.org), run through the real consult() logic. What's manual
here is which two real passages to compare and what domain to tag
them with -- the classifier still can't infer that on its own -- but
the sentences themselves and consult()'s judgment are both real, not
scripted.

Pair 1 (lines ~661, ~700-727): Pooh squeezes into Rabbit's hole before
eating, then can't get back out after. Registered under domain="fit"
(ATTRIBUTE -- at any given moment, he either fits or he doesn't).

Pair 2 (lines ~729, ~732): Pooh and Rabbit give two different real
in-story explanations for why he's stuck. Registered under
domain="blame" (ATTRIBUTE -- there's one real cause being argued
about, even if the honest answer turns out to be "both, a little").

Both pairs were verified against the actual consult() function before
this page existed -- see the commit this file shipped in for the raw
numbers -- not tuned afterward to make the demo look right.
"""

from __future__ import annotations

from dataclasses import dataclass

from .consult import DOMAIN_KINDS, ConsultResult, Relation, apply_consult, consult
from .memory_store import InMemoryStore
from .models import DomainKind, Node, Origin, Scope

DOMAIN_KINDS.setdefault("fit", DomainKind.ATTRIBUTE)
DOMAIN_KINDS.setdefault("blame", DomainKind.ATTRIBUTE)


@dataclass
class RealPairResult:
    step: int
    source: str
    domain: str
    first_text: str
    second_text: str
    relation: str
    overlap: float
    done: bool


class RealCollisionDemo:
    def __init__(self) -> None:
        self.store = InMemoryStore()
        self.step = 0
        self._pairs = [
            {
                "source": "Winnie-the-Pooh, ch. II, lines ~661 and ~700-727 (gutenberg.org)",
                "domain": "fit",
                "referent": "pooh",
                "first": Node(
                    id="fits", text="Pooh pushed and pushed and pushed his way through the "
                    "hole, and at last he got in.",
                    domain="fit", referent="pooh", scope=Scope.GENERAL,
                    origin=Origin.EPISODE, weight=0.5,
                ),
                "second_text": (
                    "Rabbit pulled and pulled and pulled, and ‘the fact is,’ "
                    "said Rabbit, ‘you’re stuck.’"
                ),
            },
            {
                "source": "Winnie-the-Pooh, ch. II, lines ~729 and ~732 (gutenberg.org)",
                "domain": "blame",
                "referent": "pooh-stuck",
                "first": Node(
                    id="pooh-blame", text="It all comes of not having front doors big enough.",
                    domain="blame", referent="pooh-stuck", scope=Scope.GENERAL,
                    origin=Origin.EPISODE, weight=0.5,
                ),
                "second_text": "It all comes of eating too much.",
            },
        ]

    def state(self) -> dict:
        return {"step": self.step, "total": len(self._pairs)}

    def advance(self) -> RealPairResult | None:
        if self.step >= len(self._pairs):
            return None
        pair = self._pairs[self.step]
        self.store.add_node(pair["first"])
        second = Node(
            id=f"{pair['first'].id}-second", text=pair["second_text"],
            domain=pair["domain"], referent=pair["referent"], scope=Scope.GENERAL,
            origin=Origin.EPISODE, weight=0.5,
        )
        result: ConsultResult = consult(self.store, second)
        apply_consult(self.store, second, result)
        self.step += 1
        return RealPairResult(
            step=self.step,
            source=pair["source"],
            domain=pair["domain"],
            first_text=pair["first"].text,
            second_text=pair["second_text"],
            relation=result.relation.value,
            overlap=round(result.overlap or 0.0, 3),
            done=self.step >= len(self._pairs),
        )
