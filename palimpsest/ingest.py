"""Fixed-size intake and digestion -- the layer between raw material
arriving and a proper Node existing in the mesh.

Digestion doesn't force every chunk into a fully-formed, weighted
conclusion. A chunk becomes either an EPISODE node (the classifier
judged it significant enough to warrant a real domain/referent/scope)
or a DORMANT node (real material, not yet judged significant, kept
rather than discarded -- see models.Origin.DORMANT). Nothing gets
thrown away during digestion. "Not interesting yet" and "gone" are
different things, and collapsing them was the actual gap: a curated
store that silently discards whatever didn't look important on first
pass is just a smaller, more selective blackhole.

The classifier here is a placeholder, not real language understanding
-- deliberately. This project isn't going to fake sophistication it
doesn't have. Swap `classify` for a real model call once one exists;
digest_next_chunk() doesn't care what's behind it, the same way
traversal.py doesn't care whether EdgeLookup is backed by Elastic or
a plain dict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from .memory_store import InMemoryStore
from .models import Node, Origin, Scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Intake:
    """A raw, unprocessed chunk of material sitting in the pipeline --
    a book chapter, a batch of observations, whatever arrived larger
    than one conclusion at a time. cursor tracks how far digestion has
    gotten; raw_text itself is never mutated, so the source stays
    inspectable start to finish, not just the extracted pieces."""

    id: str
    raw_text: str
    chunk_size: int
    domain: str = "general"
    cursor: int = 0
    spawned_node_ids: list[str] = field(default_factory=list)
    received_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")

    @property
    def fully_digested(self) -> bool:
        return self.cursor >= len(self.raw_text)

    @property
    def percent_digested(self) -> float:
        if not self.raw_text:
            return 1.0
        return min(1.0, self.cursor / len(self.raw_text))


@dataclass
class Classification:
    """What a classifier decides about one chunk. significant=False
    means dormant, not discarded -- see module docstring."""

    significant: bool
    text: str
    referent: str = "unknown"
    scope: Scope = Scope.GENERAL
    weight: float = 0.5


_CAPITALIZED_WORD = re.compile(r"[A-Z][a-z]+")
_SENTENCE_END = re.compile(r"[.!?]\s+$")
# Near-universally not proper nouns regardless of where they land --
# distinct from the position check below, which handles the much
# larger set of words that are only capitalized because of *where*
# they are (any word starting a sentence), not what they are.
_NEVER_A_NAME = {"the", "a", "an", "and", "but", "or", "it", "he", "she", "they", "we", "you", "i"}


def naive_placeholder_classifier(chunk_text: str) -> Classification:
    """NOT real language understanding -- a capitalization heuristic
    standing in for a real classifier (most plausibly an LLM call)
    until one is wired in. Tested against real prose (Winnie-the-Pooh,
    chunked at 300 chars) rather than only hand-picked examples, which
    is what surfaced the thing worth documenting here: a first cut
    that just excluded a fixed list of common sentence-starters
    ("The", "It", ...) still flagged 41/41 real chunks as significant,
    because any capitalized word right after a ". " is a sentence
    start regardless of whether it's on that list -- "Sometimes",
    "Once", anything. Capitalized isn't proper-noun; capitalized AND
    not immediately following sentence-ending punctuation is a better
    (still crude) proxy. The first chunk's un-checkable leading word is
    excluded outright rather than guessed at, since there's no text
    before it in this chunk to check.

    Real language understanding will get this right in ways no regex
    can; this only has to be honestly better than "any capital letter
    counts," not actually correct."""
    candidates = []
    for match in _CAPITALIZED_WORD.finditer(chunk_text):
        word = match.group()
        if word.lower() in _NEVER_A_NAME:
            continue
        preceding = chunk_text[: match.start()]
        # No text before this chunk to check at position 0 -- can't
        # rule it out as a sentence start, so it stays a candidate
        # rather than being guessed away in either direction.
        if preceding and _SENTENCE_END.search(preceding):
            continue
        candidates.append(word)

    significant = bool(candidates) and len(chunk_text.strip()) > 40
    referent = candidates[0].lower() if candidates else "unknown"
    return Classification(significant=significant, text=chunk_text.strip(), referent=referent)


ClassifyFn = Callable[[str], Classification]


@dataclass
class DigestResult:
    node: Node
    done: bool


def digest_next_chunk(
    intake: Intake,
    store: InMemoryStore,
    classify: ClassifyFn = naive_placeholder_classifier,
) -> Optional[DigestResult]:
    """Advances digestion by exactly one fixed-size chunk. Returns
    None if the intake is already fully digested -- callers loop on
    that, not on a count, since the last chunk is usually shorter than
    chunk_size. Always produces exactly one node: EPISODE if the
    classifier found it significant, DORMANT if not. Never zero nodes
    -- that would be the silent-discard failure mode this module
    exists to close off."""
    if intake.fully_digested:
        return None

    end = min(intake.cursor + intake.chunk_size, len(intake.raw_text))
    chunk = intake.raw_text[intake.cursor : end]
    intake.cursor = end

    result = classify(chunk)
    node = Node(
        id=f"{intake.id}-chunk-{len(intake.spawned_node_ids)}",
        text=result.text[:160],
        domain=intake.domain,
        referent=result.referent,
        scope=result.scope,
        origin=Origin.EPISODE if result.significant else Origin.DORMANT,
        weight=result.weight if result.significant else 0.05,
    )
    store.add_node(node)
    intake.spawned_node_ids.append(node.id)
    return DigestResult(node=node, done=intake.fully_digested)


def digest_all(
    intake: Intake, store: InMemoryStore, classify: ClassifyFn = naive_placeholder_classifier
) -> list[DigestResult]:
    """Runs digestion to completion in one call, for callers that
    don't need to watch it happen chunk by chunk (a script, a test).
    The live demo should prefer calling digest_next_chunk per tick
    instead -- that's the whole point of making this incremental."""
    results = []
    while (result := digest_next_chunk(intake, store, classify)) is not None:
        results.append(result)
    return results
