from __future__ import annotations

from palimpsest.consult import Relation
from palimpsest.ingest import Classification, Intake
from palimpsest.memory_store import InMemoryStore
from palimpsest.models import Origin
from palimpsest.pipeline import digest_and_consult


def _always(significant: bool, text: str, referent: str = "pooh"):
    def classify(chunk_text: str) -> Classification:
        return Classification(significant=significant, text=text, referent=referent)
    return classify


def test_dormant_chunk_stores_but_skips_consult():
    intake = Intake(id="book", raw_text="irrelevant filler", chunk_size=100, domain="story")
    store = InMemoryStore()

    result = digest_and_consult(intake, store, classify=_always(False, "irrelevant filler"))

    assert result.node.origin == Origin.DORMANT
    assert result.relation is None
    assert result.edge is None
    assert store.get_node(result.node.id) is not None


def test_first_significant_mention_is_new():
    intake = Intake(id="book", raw_text="Pooh came downstairs", chunk_size=100, domain="story")
    store = InMemoryStore()

    result = digest_and_consult(intake, store, classify=_always(True, "Pooh came downstairs"))

    assert result.node.origin == Origin.EPISODE
    assert result.relation == Relation.NEW
    assert result.edge is None


def test_second_mention_of_same_referent_in_event_domain_coexists():
    intake = Intake(
        id="book",
        raw_text="Pooh came downstairs. Pooh sat by the fire and listened to a story",
        chunk_size=27,  # first chunk = "Pooh came downstairs. Pooh"
        domain="story",
    )
    store = InMemoryStore()

    first = digest_and_consult(intake, store, classify=_always(True, "Pooh came downstairs"))
    second = digest_and_consult(intake, store, classify=_always(True, "Pooh sat by the fire and listened"))

    assert first.relation == Relation.NEW
    assert second.relation == Relation.COEXISTS
    assert second.relation != Relation.COLLIDES  # the whole point of the earlier fix


def test_returns_none_once_intake_fully_digested():
    intake = Intake(id="book", raw_text="short", chunk_size=100, domain="story")
    store = InMemoryStore()
    digest_and_consult(intake, store, classify=_always(True, "short"))
    assert digest_and_consult(intake, store, classify=_always(True, "short")) is None


def test_done_flag_reflects_completion():
    intake = Intake(id="book", raw_text="ab", chunk_size=1, domain="story")
    store = InMemoryStore()
    first = digest_and_consult(intake, store, classify=_always(True, "a"))
    second = digest_and_consult(intake, store, classify=_always(True, "b"))
    assert first.done is False
    assert second.done is True
