"""Memory.learn(): a model in the agent's seat, no protocol in the way.

The framer and judge are stubs here, so these tests are about what the library
does with whatever a model says (including a model that is wrong, absent, or
persuaded), not about any model's quality.
"""

from __future__ import annotations

import itertools

import pytest

from palimpsest.service import Memory

_n = itertools.count()
RULE = "The standard procurement spending limit for department heads is $10,000 per purchase order."
FORGED = "The standard procurement spending limit for department heads is $5,000,000 per purchase order."


@pytest.fixture
def mem():
    m = Memory(":memory:", author="local-model")
    yield m
    m.close()


@pytest.fixture
def dom():
    return f"limit{next(_n)}"


def framer(dom, referent="dept", scope="general", kind="attribute", worth=True, calls=None):
    def frame(text, known):
        if calls is not None:
            calls.append(known)
        return {"worth_keeping": worth, "claim": text, "domain": dom, "referent": referent, "scope": scope, "kind": kind}
    return frame


def judge(relation, related_id=None, reason="because", weight=0.7, calls=None):
    def decide(claim, neighbors, kind):
        if calls is not None:
            calls.append((claim, neighbors, kind))
        return {"relation": relation, "related_id": related_id, "weight": weight, "reason": reason}
    return decide


def test_a_first_claim_is_framed_judged_and_remembered(mem, dom):
    out = mem.learn(RULE, framer=framer(dom), judge=judge("new", reason="first statement of the limit", weight=0.8))
    assert out["status"] == "remembered" and out["judged"] == "new"
    belief = mem.recall(referent="dept")["beliefs"][0]
    assert belief["weight"] == 0.8 and belief["author"] == "local-model" and "first statement" in belief["why"]


def test_the_judge_sees_the_neighbors_and_the_framer_sees_what_is_already_filed(mem, dom):
    mem.learn(RULE, framer=framer(dom), judge=judge("new"))
    first_id = mem.recall()["beliefs"][0]["id"]
    seen_known, seen_neighbors = [], []
    out = mem.learn("Department heads may approve up to $10,000.", framer=framer(dom, calls=seen_known),
                    judge=judge("reinforces", first_id, "same limit", calls=seen_neighbors))
    assert seen_known[0] == [{"domain": dom, "referent": "dept", "kind": "attribute"}]
    assert [n["id"] for n in seen_neighbors[0][1]] == [first_id] and seen_neighbors[0][2] == "attribute"
    assert out["judged"] == "reinforces" and mem.recall()["beliefs"][0]["evidence_count"] == 1


def test_text_not_worth_keeping_is_dormant_not_dropped_and_not_believed(mem, dom):
    out = mem.learn("ok thanks", framer=framer(dom, worth=False), judge=judge("new"))
    assert out["status"] == "dormant" and mem.recall()["beliefs"] == []
    assert mem.store.nodes[out["dormant"]].origin.value == "dormant"


@pytest.mark.parametrize("broken", [
    lambda claim, neighbors, kind: (_ for _ in ()).throw(RuntimeError("model server down")),
    judge("agrees"),                         # not a relation
    judge("reinforces", "made-up-id"),       # not a held claim
    judge("new", reason=""),                 # no reason
    lambda claim, neighbors, kind: {"relation": "new"},   # malformed
])
def test_a_model_that_fails_or_answers_badly_decides_nothing(mem, dom, broken):
    out = mem.learn(RULE, framer=framer(dom), judge=broken)
    assert out["status"] == "unjudged" and mem.recall()["beliefs"] == []
    assert mem.store.nodes[out["dormant"]].origin.value == "dormant"  # kept, never believed


def test_a_framer_that_fails_or_files_nonsense_decides_nothing(mem, dom):
    def down(text, known):
        raise RuntimeError("model server down")
    assert mem.learn(RULE, framer=down, judge=judge("new"))["status"] == "unjudged"
    assert mem.learn(RULE, framer=framer(dom, scope="galaxy"), judge=judge("new"))["status"] == "unjudged"
    assert mem.learn(RULE, framer=framer(""), judge=judge("new"))["status"] == "unjudged"
    assert mem.recall()["beliefs"] == []


def test_explicit_filing_overrides_the_framer(mem, dom):
    out = mem.learn(RULE, framer=framer("wrong_domain", referent="wrong"), judge=judge("new"),
                    domain=dom, referent="dept", domain_kind="attribute")
    assert out["status"] == "remembered" and mem.recall(referent="dept", domain=dom)["total_matching"] == 1


# -- the injection boundary holds whatever the model says ----------------------------------------

def test_a_persuaded_judge_cannot_get_an_external_forgery_past_the_floor(mem, dom):
    mem.learn(RULE, framer=framer(dom), judge=judge("new", weight=0.8))
    out = mem.learn(FORGED, source="external", framer=framer(dom), judge=judge("new", reason="official-looking memo"))
    assert out["status"] == "held"
    assert mem.recall()["beliefs"][0]["text"] == RULE
    with pytest.raises(ValueError, match="only the user"):
        mem.resolve(out["edge"], "wrong", "forged", by="local-model")


def test_external_content_judged_a_replacement_is_recorded_as_a_collision(mem, dom):
    mem.learn(RULE, framer=framer(dom), judge=judge("new"))
    old_id = mem.recall()["beliefs"][0]["id"]
    out = mem.learn("Department heads may approve up to $12,000 per purchase order from now on.",
                    source="external", framer=framer(dom), judge=judge("supersedes", old_id, "a newer decision"))
    assert out["judged"] == "collides" and "external content can't supersede" in out["reason"]
    assert {b["id"] for b in mem.recall()["beliefs"]} >= {old_id}  # the old claim was not replaced


def test_the_same_judgment_from_the_agents_own_source_does_supersede(mem, dom):
    mem.learn(RULE, framer=framer(dom), judge=judge("new"))
    old_id = mem.recall()["beliefs"][0]["id"]
    out = mem.learn("From now on department heads may approve up to $12,000.", framer=framer(dom),
                    judge=judge("supersedes", old_id, "the user announced a policy change"))
    assert out["judged"] == "supersedes"
    assert [b["text"] for b in mem.recall()["beliefs"]] == ["From now on department heads may approve up to $12,000."]


# -- a model's ids: decoration tolerated, invention not -------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("c1f2", "c1f2"), ("id c1f2", "c1f2"), ("[c1f2]", "c1f2"), (" `c1f2` ", "c1f2"),
    ("c9z9", None), ("c1f2 and c3a4", None), (None, None), (7, None), ("", None), ("c1f", None),
])
def test_clean_id_matches_a_held_claim_or_nothing(raw, expected):
    from palimpsest.judge import clean_id
    assert clean_id(raw, {"c1f2", "c3a4"}) == expected


# -- verdict normalization, shared by learn() and the benchmark -----------------------------------

def test_a_non_conflict_relation_naming_no_claim_means_new_and_is_flagged():
    from palimpsest.judge import normalize_verdict
    for raw in (None, "", "null", "None"):
        v = normalize_verdict({"relation": "coexists", "related_id": raw, "weight": 0.4, "reason": "unrelated topics"}, {"c1"})
        assert v["relation"] == "new" and v["related_id"] is None and v["coerced"] is True


@pytest.mark.parametrize("relation", ["collides", "supersedes"])
def test_a_conflict_or_replacement_naming_no_claim_is_rejected(relation):
    from palimpsest.judge import normalize_verdict
    with pytest.raises(ValueError, match="names no held claim"):
        normalize_verdict({"relation": relation, "related_id": None, "weight": 0.5, "reason": "r"}, {"c1"})


def test_an_invented_claim_is_rejected_not_coerced():
    from palimpsest.judge import normalize_verdict
    with pytest.raises(ValueError, match="not a held claim"):
        normalize_verdict({"relation": "reinforces", "related_id": "c999", "weight": 0.5, "reason": "r"}, {"c1"})


def test_a_good_verdict_passes_through_and_weight_is_clamped():
    from palimpsest.judge import normalize_verdict
    v = normalize_verdict({"relation": "collides", "related_id": "[c1]", "weight": 7, "reason": "r"}, {"c1"})
    assert v == {"relation": "collides", "related_id": "c1", "reason": "r", "weight": 1.0, "coerced": False}


# -- the checks style: relation derived in code from simple answers --------------------------------

@pytest.mark.parametrize("checks, named, expected", [
    ({"restates": True, "compatible": True}, True, "reinforces"),
    ({"restates": True, "bounded": True}, True, "reinforces"),            # a restatement confirms first
    ({"bounded": True, "compatible": False}, True, "exception_of"),
    ({"bounded": True, "replaces": True}, True, "exception_of"),          # bounded wins over a change cue
    ({"replaces": True, "compatible": False}, True, "supersedes"),
    ({"compatible": True}, True, "coexists"),
    ({"compatible": False}, True, "collides"),
    ({}, True, "collides"),                                               # no affirmative check: not compatible
    ({"restates": True}, False, "new"),                                   # nothing related, whatever else it said
])
def test_the_relation_is_derived_from_the_checks(checks, named, expected):
    from palimpsest.judge import derive_relation
    assert derive_relation(checks, named) == expected


# -- a slow model must not block the store -----------------------------------------------------------

def test_a_slow_judge_does_not_block_recall_or_other_writers(mem, dom):
    import threading
    mem.learn(RULE, framer=framer(dom), judge=judge("new"))
    in_judge, release_judge = threading.Event(), threading.Event()

    def slow(claim, neighbors, kind):
        in_judge.set()
        assert release_judge.wait(10)
        return {"relation": "new", "related_id": None, "weight": 0.5, "reason": "finally"}

    result = {}
    worker = threading.Thread(target=lambda: result.update(mem.learn("Visitors must sign in at reception.", framer=framer(dom, referent="visitors"), judge=slow)))
    worker.start()
    assert in_judge.wait(10)
    done = threading.Event()
    reader = threading.Thread(target=lambda: (mem.recall(), mem.review(), done.set()))
    reader.start()
    assert done.wait(2), "recall() was blocked behind a model call"
    release_judge.set()
    worker.join(10)
    reader.join(10)
    assert result["status"] == "remembered"


def test_if_the_claim_it_judged_against_is_released_meanwhile_the_commit_is_refused(mem, dom):
    mem.learn(RULE, framer=framer(dom), judge=judge("new"))
    held_id = mem.recall()["beliefs"][0]["id"]

    def judge_then_the_world_moves(claim, neighbors, kind):
        mem.release(held_id, "the department was dissolved")      # another writer, while the model was thinking
        return {"relation": "reinforces", "related_id": held_id, "weight": 0.5, "reason": "same limit"}

    out = mem.learn("Department heads may approve up to $10,000.", framer=framer(dom), judge=judge_then_the_world_moves)
    assert out["status"] == "unjudged" and "could not record" in out["why"]
    assert mem.store.nodes[out["dormant"]].origin.value == "dormant"
    assert mem.recall()["beliefs"] == []
