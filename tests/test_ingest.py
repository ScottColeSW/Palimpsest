from __future__ import annotations

import pytest

from palimpsest.ingest import Classification, Intake, digest_all, digest_next_chunk
from palimpsest.memory_store import InMemoryStore
from palimpsest.models import Origin


def test_digest_next_chunk_advances_cursor_by_chunk_size():
    intake = Intake(id="book1", raw_text="a" * 25, chunk_size=10)
    store = InMemoryStore()
    digest_next_chunk(intake, store)
    assert intake.cursor == 10
    assert not intake.fully_digested


def test_last_chunk_can_be_shorter_than_chunk_size():
    intake = Intake(id="book1", raw_text="a" * 25, chunk_size=10)
    store = InMemoryStore()
    digest_next_chunk(intake, store)  # 0-10
    digest_next_chunk(intake, store)  # 10-20
    result = digest_next_chunk(intake, store)  # 20-25, only 5 chars left
    assert result.done is True
    assert intake.fully_digested
    assert intake.cursor == 25


def test_digest_next_chunk_returns_none_once_fully_digested():
    intake = Intake(id="book1", raw_text="short", chunk_size=100)
    store = InMemoryStore()
    digest_next_chunk(intake, store)
    assert digest_next_chunk(intake, store) is None


def test_every_chunk_produces_exactly_one_node_never_zero():
    """The core claim: digestion never silently drops a chunk. Every
    fixed-size slice of the raw text becomes some node, whether or not
    it turns out significant."""
    text = "Elena walked through the garden. it was quiet and dull. nothing happened at all here really. Marcus arrived."
    intake = Intake(id="book1", raw_text=text, chunk_size=20)
    store = InMemoryStore()
    results = digest_all(intake, store)

    expected_chunks = -(-len(text) // 20)  # ceiling division
    assert len(results) == expected_chunks
    assert len(store.all_nodes()) == expected_chunks


def test_insignificant_chunks_become_dormant_not_discarded():
    def always_insignificant(chunk_text: str) -> Classification:
        return Classification(significant=False, text=chunk_text)

    intake = Intake(id="book1", raw_text="nothing of note happens in this passage at all", chunk_size=15)
    store = InMemoryStore()
    digest_all(intake, store, classify=always_insignificant)

    nodes = store.all_nodes()
    assert len(nodes) > 0
    assert all(n.origin == Origin.DORMANT for n in nodes)
    assert all(n.weight < 0.1 for n in nodes)  # low weight, but present -- not deleted


def test_significant_chunks_become_episode_nodes():
    def always_significant(chunk_text: str) -> Classification:
        return Classification(significant=True, text=chunk_text, referent="elena", weight=0.7)

    intake = Intake(id="book1", raw_text="Elena's raven hair caught the light in the hall", chunk_size=48)
    store = InMemoryStore()
    digest_all(intake, store, classify=always_significant)

    nodes = store.all_nodes()
    assert len(nodes) == 1
    assert nodes[0].origin == Origin.EPISODE
    assert nodes[0].referent == "elena"
    assert nodes[0].weight == 0.7


def test_dormant_nodes_are_permanently_traceable_via_domain():
    """Dormant material isn't deleted -- it stays a real, queryable
    node in the same domain, just at low weight. Nothing about being
    dormant makes it invisible to a later, deliberate search."""

    def always_insignificant(chunk_text: str) -> Classification:
        return Classification(significant=False, text=chunk_text)

    intake = Intake(id="book1", raw_text="a passing detail nobody cared about yet", chunk_size=40, domain="scenery")
    store = InMemoryStore()
    digest_all(intake, store, classify=always_insignificant)

    dormant_in_domain = [n for n in store.all_nodes() if n.domain == "scenery" and n.origin == Origin.DORMANT]
    assert len(dormant_in_domain) == 1


def test_chunk_size_must_be_positive():
    with pytest.raises(ValueError):
        Intake(id="book1", raw_text="text", chunk_size=0)


def test_naive_placeholder_classifier_flags_named_significant_text():
    from palimpsest.ingest import naive_placeholder_classifier

    result = naive_placeholder_classifier("Marcus stormed out of the room without another word to anyone.")
    assert result.significant is True
    assert result.referent == "marcus"


def test_naive_placeholder_classifier_treats_short_or_nameless_text_as_insignificant():
    from palimpsest.ingest import naive_placeholder_classifier

    assert naive_placeholder_classifier("it was quiet").significant is False
    assert naive_placeholder_classifier("The rain fell steadily all through the long grey afternoon").significant is False
