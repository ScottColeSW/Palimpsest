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


_CLAIM_TEXTS = set()   # realistic claim texts that stand in for the claim vector (filled in below)


def embedder(sims):
    """text -> vector so that cosine(claim, text) is roughly sims[text]; claim is the unit x axis."""
    def embed(text):
        s = sims.get(text, 0.0)
        return [1.0, 0.0] if text == "CLAIM" or text in _CLAIM_TEXTS else [s, (1 - s * s) ** 0.5]
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
    change = "Effective today department heads may approve up to $15,000."
    replaced = judge(nli, ref=refiner("replacement", "Effective today"))(change, [HELD], "attribute")
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


# -- figures: a conflict NLI misses, found by comparing quantities with their units ---------------------

ALLOWANCE = {"id": "c7", "text": "Remote employees may expense up to $500 per year for home office equipment."}
RAISED = "The home office allowance was increased to $750 per year starting this quarter."
DEADLINE = "Receipts for home office purchases must be submitted within 30 days."
EVENT_CLAIM = "A second outage lasted 12 minutes on March 19."
_CLAIM_TEXTS.update({RAISED, DEADLINE, EVENT_CLAIM})


def test_comparable_differing_figures_on_the_same_subject_raise_a_conflict_nli_missed():
    """NLI sees "increased to $750" beside "$500" as compatible. The figures say otherwise."""
    v = judge(StubNLI(), {ALLOWANCE["text"]: 0.8, RAISED: 0.8}, refiner("replacement", "was increased to $750"))(RAISED, [ALLOWANCE], "attribute")
    assert v["relation"] == "supersedes" and "figures differ (750 vs 500)" in v["reason"]


def test_without_a_refiner_citation_the_figure_conflict_is_a_plain_collision():
    v = judge(StubNLI(), {ALLOWANCE["text"]: 0.8})(RAISED, [ALLOWANCE], "attribute")
    assert v["relation"] == "collides"


def test_figures_of_a_different_kind_do_not_conflict():
    """A 30-day deadline beside a $500 allowance: the rules once called this a collision."""
    v = judge(StubNLI(), {ALLOWANCE["text"]: 0.8})(DEADLINE, [ALLOWANCE], "attribute")
    assert v["relation"] == "coexists"


def test_the_figure_signal_needs_the_same_subject():
    v = judge(StubNLI(), {ALLOWANCE["text"]: 0.2})(RAISED, [ALLOWANCE], "attribute")
    assert v["relation"] == "new"


def test_the_figure_signal_can_be_switched_off():
    v = judge(StubNLI(), {ALLOWANCE["text"]: 0.8}, figures=False)(RAISED, [ALLOWANCE], "attribute")
    assert v["relation"] == "coexists"


def test_the_figure_signal_never_lowers_a_flag():
    """NLI already finds the conflict: figures change nothing about it."""
    nli = StubNLI(both={ALLOWANCE["text"]: (0.0, 0.0, 1.0)})
    for figures in (True, False):
        assert judge(nli, {ALLOWANCE["text"]: 0.8}, figures=figures)(RAISED, [ALLOWANCE], "attribute")["relation"] == "collides"


def test_in_an_event_domain_differing_figures_are_another_event():
    held = {"id": "c8", "text": "The outage lasted 40 minutes on March 3."}
    v = judge(StubNLI(), {held["text"]: 0.9})(EVENT_CLAIM, [held], "event")
    assert v["relation"] == "coexists"


# -- the restatement direction and the relatedness threshold (dev-fitted; see hybrid_judge) -----------------

LESS_SPECIFIC = "Sunday rides depart at 07:00."
HELD_LONG = {"id": "c9", "text": "The cycling club rides leave from the old mill at 7 am on Sundays."}


def test_a_claim_the_held_one_already_implies_is_a_restatement_even_when_less_specific():
    """held => claim is entailed; claim => held is not (the claim drops the place). It adds nothing: reinforces."""
    nli = StubNLI(probs={(HELD_LONG["text"], LESS_SPECIFIC): (0.99, 0.01, 0.0), (LESS_SPECIFIC, HELD_LONG["text"]): (0.02, 0.98, 0.0)})
    _CLAIM_TEXTS.add(LESS_SPECIFIC)
    v = judge(nli, {HELD_LONG["text"]: 0.8})(LESS_SPECIFIC, [HELD_LONG], "attribute")
    assert v["relation"] == "reinforces" and "already implies" in v["reason"]


def test_a_claim_that_implies_the_held_one_but_not_the_reverse_adds_something():
    more = "Sunday rides leave the old mill at 7 am and the club always stops at the cafe."
    _CLAIM_TEXTS.add(more)
    nli = StubNLI(probs={(more, HELD_LONG["text"]): (0.99, 0.01, 0.0), (HELD_LONG["text"], more): (0.03, 0.97, 0.0)})
    v = judge(nli, {HELD_LONG["text"]: 0.8})(more, [HELD_LONG], "attribute")
    assert v["relation"] == "coexists"


def test_the_first_version_required_entailment_both_ways_and_is_still_available():
    nli = StubNLI(probs={(HELD_LONG["text"], LESS_SPECIFIC): (0.99, 0.01, 0.0), (LESS_SPECIFIC, HELD_LONG["text"]): (0.02, 0.98, 0.0)})
    _CLAIM_TEXTS.add(LESS_SPECIFIC)
    v = judge(nli, {HELD_LONG["text"]: 0.8}, restate="both")(LESS_SPECIFIC, [HELD_LONG], "attribute")
    assert v["relation"] == "coexists"


def test_a_contradicted_claim_is_never_a_restatement():
    """Even if entailment points the right way, a high contradiction makes it a conflict."""
    nli = StubNLI(probs={(HELD_LONG["text"], LESS_SPECIFIC): (0.9, 0.0, 0.9), (LESS_SPECIFIC, HELD_LONG["text"]): (0.0, 0.1, 0.9)})
    _CLAIM_TEXTS.add(LESS_SPECIFIC)
    assert judge(nli, {HELD_LONG["text"]: 0.8})(LESS_SPECIFIC, [HELD_LONG], "attribute")["relation"] == "collides"


@pytest.mark.parametrize("similarity, expected", [(0.50, "new"), (0.55, "new"), (0.57, "coexists"), (0.80, "coexists")])
def test_the_default_relatedness_threshold(similarity, expected):
    """Neutral pairs: 0.56 splits same-subject from different-subject (0.48 was fitted to 12 cases and did not hold)."""
    v = judge(StubNLI(), {HELD["text"]: similarity})("CLAIM", [HELD], "attribute")
    assert v["relation"] == expected


# -- a replacement's evidence must say something new (found by batch 3: the refiner quoted the whole claim back) ----------

COORD_HELD = {"id": "c20", "text": "Maria is the coordinator for the choir."}
COORD_NEW = "Elena is the coordinator for the choir."


def test_a_replacement_that_quotes_the_whole_claim_back_is_not_evidence():
    """The real failure: a plain conflict (a different name, no handover signaled) called a replacement, with the claim itself as the quote."""
    nli = StubNLI(both={COORD_HELD["text"]: (0.0, 0.0, 1.0)})
    v = judge(nli, ref=refiner("replacement", COORD_NEW))(COORD_NEW, [COORD_HELD], "attribute")
    assert v["relation"] == "collides"


def test_a_real_change_signal_adds_words_the_held_claim_lacks():
    nli = StubNLI(both={COORD_HELD["text"]: (0.0, 0.0, 1.0)})
    claim = "Maria left the post; Dara is now the choir coordinator."
    v = judge(nli, ref=refiner("replacement", "Maria left the post; Dara is now"))(claim, [COORD_HELD], "attribute")
    assert v["relation"] == "supersedes"


def test_an_exception_needs_only_a_quote_that_is_really_there():
    """The bar differs with the harm: a replacement overwrites a belief, an exception adds a scoped link and leaves both live."""
    nli = StubNLI(both={COORD_HELD["text"]: (0.0, 0.0, 1.0)})
    v = judge(nli, ref=refiner("exception", COORD_NEW))(COORD_NEW, [COORD_HELD], "attribute")
    assert v["relation"] == "exception_of"


def test_the_novelty_bar_can_be_switched_off_to_reproduce_the_first_version():
    nli = StubNLI(both={COORD_HELD["text"]: (0.0, 0.0, 1.0)})
    v = judge(nli, ref=refiner("replacement", COORD_NEW), replace_novelty=0.0)(COORD_NEW, [COORD_HELD], "attribute")
    assert v["relation"] == "supersedes"


def test_adds_words():
    from palimpsest.judge import _adds_words
    held = "The pharmacy closes at 8 pm on weekdays."
    assert _adds_words("As of Monday", held, 0.5)
    assert _adds_words("now closes at 9 pm", held, 0.5)                       # 'now' and '9 pm' are new, 'closes' is not: 2/3
    assert not _adds_words("The pharmacy closes on weekdays", held, 0.5)
    assert not _adds_words("", held, 0.5)
    assert not _adds_words("the of and", held, 0.5)                           # nothing but stopwords: no content


# -- no refiner: no language model at all ------------------------------------------------------------------------

def test_without_a_refiner_every_conflict_is_a_plain_collision():
    nli = StubNLI(both={HELD["text"]: (0.0, 0.0, 1.0)})
    v = hybrid_judge(nli, embedder({}), None)(CLAIM, [HELD], "attribute")
    assert v["relation"] == "collides" and "no scope or change shown" in v["reason"]


def test_without_a_refiner_the_other_relations_are_unchanged():
    both = StubNLI(both={HELD["text"]: (0.97, 0.03, 0.0)})
    assert hybrid_judge(both, embedder({}), None)("CLAIM", [HELD], "attribute")["relation"] == "reinforces"
    assert hybrid_judge(StubNLI(), embedder({HELD["text"]: 0.8}), None)("CLAIM", [HELD], "attribute")["relation"] == "coexists"
    assert hybrid_judge(StubNLI(), embedder({HELD["text"]: 0.2}), None)("CLAIM", [HELD], "attribute")["relation"] == "new"
