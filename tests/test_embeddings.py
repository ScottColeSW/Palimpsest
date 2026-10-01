"""Finding held claims by meaning: plumbing, fallbacks, persistence.

The embedder is a stub that maps concepts to axes, so these tests are about what
the library does with vectors, not about any embedding model's quality (see
bench/retrieval.py for that).
"""

from __future__ import annotations

import itertools

import pytest

from palimpsest.embed import cosine
from palimpsest.service import Memory

_n = itertools.count()
CONCEPTS = {"remote": 0, "staff": 0, "employees": 0, "allowance": 1, "expense": 1, "reimbursed": 1, "equipment": 2, "gear": 2,
            "visitors": 3, "guests": 3, "badge": 4, "sign": 4}


def embed(text):
    v = [0.0] * 5
    for w in text.lower().replace(".", "").split():
        if w in CONCEPTS:
            v[CONCEPTS[w]] += 1.0
    return v


HELD = "Remote employees may expense up to $500 per year for home office equipment."
PARAPHRASE = "Staff working remotely get an allowance of five hundred dollars yearly for desk gear."   # no shared content word


def build(embedder, dom):
    mem = Memory(":memory:", embedder=embedder)
    held = mem.remember(HELD, dom, "remote_staff", "new", "policy", domain_kind="attribute")
    mem.remember("Visitors must sign the guest badge log at reception.", f"{dom}_v", "visitors", "new", "policy", domain_kind="attribute")
    return mem, held


def test_cosine():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0) and cosine([1, 0], [0, 1]) == 0.0 and cosine([0, 0], [1, 1]) == 0.0


def test_a_paraphrase_with_no_shared_words_is_found_only_with_an_embedder():
    dom = f"d{next(_n)}"
    plain, held = build(None, dom)
    other_fact = plain.consult(PARAPHRASE, f"{dom}_new", "someone", domain_kind="attribute")
    assert held["id"] not in [n["id"] for n in other_fact["neighbors"]]  # wording alone can't reach it

    smart, held = build(embed, dom + "e")
    found = smart.consult(PARAPHRASE, f"{dom}_new", "someone", domain_kind="attribute")
    assert found["neighbors"][0]["id"] == held["id"] and found["neighbors"][0]["similarity"] > 0.7
    assert found["neighbors"][0]["similarity"] > found["neighbors"][-1]["similarity"]


def test_a_failing_embedder_falls_back_to_wording(tmp_path):
    dom = f"d{next(_n)}"

    def broken(text):
        raise RuntimeError("model server down")
    mem = Memory(":memory:", embedder=broken)
    held = mem.remember(HELD, dom, "remote_staff", "new", "policy", domain_kind="attribute")
    seen = mem.consult("Remote employees may expense $500 a year.", dom, "remote_staff")
    assert seen["neighbors"][0]["id"] == held["id"] and seen["neighbors"][0]["similarity"] is None


def test_vectors_are_stored_and_survive_a_restart_but_never_reach_the_agent(tmp_path):
    dom, path = f"d{next(_n)}", tmp_path / "m.db"
    a = Memory(path, embedder=embed)
    held = a.remember(HELD, dom, "remote_staff", "new", "policy", domain_kind="attribute")
    assert a.store.nodes[held["id"]].embedding == embed(HELD)
    a.close()
    b = Memory(path, embedder=embed)
    assert b.store.nodes[held["id"]].embedding == embed(HELD)
    assert "embedding" not in b.recall()["beliefs"][0]
    b.close()


def test_reindex_embeds_claims_stored_before_an_embedder_existed(tmp_path):
    dom, path = f"d{next(_n)}", tmp_path / "m.db"
    a = Memory(path)
    held = a.remember(HELD, dom, "remote_staff", "new", "policy", domain_kind="attribute")
    a.close()
    b = Memory(path, embedder=embed)
    assert b.store.nodes[held["id"]].embedding is None
    assert b.reindex() == 1 and b.store.nodes[held["id"]].embedding == embed(HELD)
    b.close()


def test_the_embedder_is_called_once_per_text(mem=None):
    calls = []

    def counting(text):
        calls.append(text)
        return embed(text)
    dom = f"d{next(_n)}"
    m = Memory(":memory:", embedder=counting)
    m.consult(HELD, dom, "remote_staff", domain_kind="attribute")
    m.remember(HELD, dom, "remote_staff", "new", "policy")
    assert calls == [HELD]
