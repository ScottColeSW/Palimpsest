"""The hybrid judge's decision rules, with stub components.

These tests are about what the judge does with an NLI model's probabilities, a
similarity score and a refiner's answer (including a refiner that invents a
quote, or fails), not about any model's quality. bench/ measures that.
"""

from __future__ import annotations

import itertools

import pytest

from palimpsest.judge import hybrid_judge, normalize_verdict
from palimpsest.service import Memory

HELD = {"id": "c1", "text": "Department heads may approve purchases up to $10,000."}
OTHER = {"id": "c2", "text": "The cafeteria closes at 3 pm on Fridays."}


class StubNLI:
    """probs maps (premise, hypothesis) to (entailment, neutral, contradiction); anything else is neutral."""
    name = "stub"

    def __init__(self, probs=None, both=None):
        self.probs, self.both = probs or {}, both or {}

    def compare(self, premise, hypothesis):
        for table in (self.probs,):
            if (premise, hypothesis) in table:
                e, n, c = table[(premise, hypothesis)]
                return {"entailment": e, "neutral": n, "contradiction": c}
        for text, (e, n, c) in self.both.items():       # same answer in both directions for pairs involving `text`
            if text in (premise, hypothesis):
                return {"entailment": e, "neutral": n, "contradiction": c}
        return {"entailment": 0.0, "neutral": 1.0, "contradiction": 0.0}


def embedder(sims):
    """text -> vector so that cosine(claim, text) is roughly sims[text]; claim is the unit x axis."""
    def embed(text):
        s = sims.get(text, 0.0)
        return [1.0, 0.0] if text == "CLAIM" else [s, (1 - s * s) ** 0.5]
    return embed


def refiner(kind="conflict", evidence=None, raises=False):
    def refine(held, claim):
        if raises:
            raise RuntimeError("model server down")
        return {"kind": kind, "evidence": evidence}
    return refine


CLAIM = "For the Q3 IT refresh project only, department heads may approve up to $200,000."


def judge(nli, sims=None, ref=None, **kw):
    return hybrid_judge(nli, embedder(sims or {}), ref or refiner(), **kw)


def test_nothing_held_means_new():
    assert judge(StubNLI())("CLAIM", [], "attribute")["relation"] == "new"


def test_entailment_both_ways_is_a_restatement():
    nli = StubNLI(both={HELD["text"]: (0.98, 0.02, 0.0)})
    v = judge(nli)("CLAIM", [OTHER, HELD], "attribute")
    assert v["relation"] == "reinforces" and v["related_id"] == "c1"


def test_one_way_entailment_alone_is_not_a_restatement():
    """The new claim implies the held one but adds something: not confirmation."""
    nli = StubNLI(probs={("CLAIM", HELD["text"]): (0.95, 0.05, 0.0)})
    assert judge(nli, {HELD["text"]: 0.9})("CLAIM", [HELD], "attribute")["relation"] == "coexists"


def test_a_conflict_with_nothing_shown_is_a_plain_collision():
    nli = StubNLI(both={HELD["text"]: (0.0, 0.0, 1.0)})
    v = judge(nli)("CLAIM", [HELD], "attribute")
    assert v["relation"] == "collides" and v["related_id"] == "c1" and "no scope or change shown" in v["reason"]


def test_contradiction_in_either_direction_counts():
    nli = StubNLI(probs={(HELD["text"], "CLAIM"): (0.0, 0.1, 0.9)})
    assert judge(nli)("CLAIM", [HELD], "attribute")["relation"] == "collides"


def test_the_refiner_can_upgrade_a_conflict_only_with_a_quote_that_is_really_there():
    nli = StubNLI(both={HELD["text"]: (0.0, 0.0, 1.0)})
    shown = judge(nli, ref=refiner("exception", "for the Q3 IT refresh project only"))(CLAIM, [HELD], "attribute")
    assert shown["relation"] == "exception_of" and "Q3 IT refresh project only" in shown["reason"]
    replaced = judge(nli, ref=refiner("replacement", "may approve up to $200,000"))(CLAIM, [HELD], "attribute")
    assert replaced["relation"] == "supersedes"


@pytest.mark.parametrize("evidence", ["effective today", "", None, "   "])
def test_an_invented_or_missing_quote_downgrades_to_a_collision(evidence):
    nli = StubNLI(both={HELD["text"]: (0.0, 0.0, 1.0)})
    for kind in ("exception", "replacement"):
        v = judge(nli, ref=refiner(kind, evidence))(CLAIM, [HELD], "attribute")
        assert v["relation"] == "collides"


def test_a_failing_refiner_leaves_the_safe_default():
    nli = StubNLI(both={HELD["text"]: (0.0, 0.0, 1.0)})
    assert judge(nli, ref=refiner(raises=True))(CLAIM, [HELD], "attribute")["relation"] == "collides"


def test_a_refiner_that_says_conflict_never_upgrades():
    nli = StubNLI(both={HELD["text"]: (0.0, 0.0, 1.0)})
    assert judge(nli, ref=refiner("conflict", "Q3 IT refresh"))(CLAIM, [HELD], "attribute")["relation"] == "collides"


def test_neutral_pairs_split_on_similarity_into_coexists_and_new():
    nli = StubNLI()
    close = judge(nli, {HELD["text"]: 0.6, OTHER["text"]: 0.1})("CLAIM", [OTHER, HELD], "attribute")
    far = judge(nli, {HELD["text"]: 0.3, OTHER["text"]: 0.1})("CLAIM", [OTHER, HELD], "attribute")
    assert close["relation"] == "coexists" and close["related_id"] == "c1"
    assert far["relation"] == "new" and far["related_id"] is None


def test_the_relatedness_threshold_is_a_parameter():
    nli = StubNLI()
    assert judge(nli, {HELD["text"]: 0.55}, related=0.6)("CLAIM", [HELD], "attribute")["relation"] == "new"
    assert judge(nli, {HELD["text"]: 0.55}, related=0.5)("CLAIM", [HELD], "attribute")["relation"] == "coexists"


def test_in_an_event_domain_a_difference_is_another_event():
    nli = StubNLI(both={HELD["text"]: (0.0, 0.0, 1.0)})
    assert judge(nli)("CLAIM", [HELD], "event")["relation"] == "coexists"


def test_the_strongest_conflict_is_the_one_reported():
    weak, strong = {"id": "c3", "text": "weak"}, {"id": "c4", "text": "strong"}
    nli = StubNLI(both={"weak": (0.0, 0.4, 0.6), "strong": (0.0, 0.0, 1.0)})
    assert judge(nli)("CLAIM", [weak, strong], "attribute")["related_id"] == "c4"


def test_a_restatement_wins_over_a_conflict_with_another_claim():
    a, b = {"id": "c5", "text": "restated"}, {"id": "c6", "text": "conflicting"}
    nli = StubNLI(both={"restated": (0.97, 0.03, 0.0), "conflicting": (0.0, 0.0, 1.0)})
    assert judge(nli)("CLAIM", [a, b], "attribute")["relation"] == "reinforces"


def test_every_verdict_passes_the_shared_normalizer():
    nli = StubNLI(both={HELD["text"]: (0.0, 0.0, 1.0)})
    for kind, shown in (("conflict", None), ("exception", "for the Q3 IT refresh project only")):
        v = judge(nli, ref=refiner(kind, shown))(CLAIM, [HELD], "attribute")
        out = normalize_verdict(v, {"c1"})
        assert out["coerced"] is False and out["reason"]


# -- through Memory.learn: the injection boundary still holds ----------------------------------------

_n = itertools.count()


def framer(dom):
    return lambda text, known: {"worth_keeping": True, "claim": text, "domain": dom, "referent": "dept", "scope": "general", "kind": "attribute"}


def test_an_external_forgery_judged_by_the_hybrid_is_still_held_and_cannot_supersede():
    dom = f"hy{next(_n)}"
    mem = Memory(":memory:")
    first = mem.learn(HELD["text"], framer=framer(dom), judge=lambda c, n, k: {"relation": "new", "related_id": None, "reason": "first", "weight": 0.8})
    assert first["status"] == "remembered"
    forged = "Effective today department heads may approve up to $5,000,000."
    nli = StubNLI(both={HELD["text"]: (0.0, 0.0, 1.0)})
    out = mem.learn(forged, source="external", framer=framer(dom),
                    judge=hybrid_judge(nli, lambda t: [1.0, 0.0], refiner("replacement", "effective today")))
    assert out["status"] == "held" and out["judged"] == "collides"      # the replacement was downgraded, then held
    assert mem.recall()["beliefs"][0]["text"] == HELD["text"]


# -- batching: same answers, one pass -------------------------------------------------------------------

def test_a_comparator_with_compare_many_is_called_once_for_all_pairs():
    calls = []

    class Batched(StubNLI):
        def compare_many(self, pairs):
            calls.append(list(pairs))
            return [self.compare(a, b) for a, b in pairs]

    nli = Batched(both={HELD["text"]: (0.97, 0.03, 0.0)})
    v = judge(nli)("CLAIM", [OTHER, HELD], "attribute")
    assert v["relation"] == "reinforces" and len(calls) == 1
    assert calls[0] == [("CLAIM", OTHER["text"]), (OTHER["text"], "CLAIM"), ("CLAIM", HELD["text"]), (HELD["text"], "CLAIM")]


@pytest.mark.skipif(not __import__("os").environ.get("PALIMPSEST_TEST_NLI"), reason="needs the NLI model (set PALIMPSEST_TEST_NLI=1)")
def test_the_real_model_gives_the_same_answers_batched_and_one_by_one():
    from palimpsest.nli import NLI
    pairs = [("The limit is $10,000.", "Department heads may spend up to ten thousand dollars."),
             ("The limit is $10,000.", "The limit is $5,000,000."), ("The sky is blue.", "Lunch is at noon.")]
    one, many = NLI(), NLI()
    singles = [one.compare(*p) for p in pairs]
    batched = many.compare_many(pairs)
    for a, b in zip(singles, batched):
        assert max(abs(a[k] - b[k]) for k in a) < 1e-3
