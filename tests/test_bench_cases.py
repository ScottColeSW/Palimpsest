"""The benchmark's labels, audited mechanically.

A leaderboard is only as honest as its labels. These checks don't depend on any
model or on the rules being benchmarked: structure, split balance, and the two
boundaries the labeling guide says are decided by text alone (a figure that
changes, and a change cue).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from palimpsest.consult import _quantities

CASES = json.loads((Path(__file__).parent.parent / "bench" / "cases.json").read_text(encoding="utf-8"))
JUDGE, FRAME = CASES["judge"], CASES["frame"]
RELATIONS = {"new", "reinforces", "coexists", "collides", "exception_of", "supersedes"}
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12}
# The guide's change cues: the only thing separating a replacement from a conflict
CUE = re.compile(r"\b(effective|now|no longer|as of|moved|changed|raised|increased|tightened|dropped|migrated|retired|instead|"
                 r"switched|replaced|stepped down|extended|starting (?:next|this|today))\b", re.I)


def _figures(text: str) -> set[float]:
    found = set(_quantities(text))
    for word, value in WORDS.items():
        if re.search(rf"\b{word}\b", text, re.I):
            found.add(float(value))
    return found


def _related(case):
    key = case["expected"]["related"]
    return next(n["text"] for n in case["neighbors"] if n["key"] == key) if key else None


def test_structure_and_ids():
    ids = [c["id"] for c in JUDGE + FRAME]
    assert len(ids) == len(set(ids))
    for c in JUDGE:
        assert c["expected"]["relation"] in RELATIONS and c["split"] in ("dev", "heldout")
        assert c["source"] in ("agent", "external") and c["kind"] in ("attribute", "event")
        keys = [n["key"] for n in c["neighbors"]]
        assert len(keys) == len(set(keys))
        if c["expected"]["relation"] == "new":
            assert c["expected"]["related"] is None
        else:
            assert c["expected"]["related"] in keys
        assert c["rationale"].strip()
    for c in FRAME:
        assert c["split"] in ("dev", "heldout") and c["rationale"].strip()
        assert "worth_keeping" in c["expected"]


def test_every_relation_has_enough_cases_in_both_splits():
    counts = Counter((c["expected"]["relation"], c["split"]) for c in JUDGE)
    for relation in RELATIONS:
        for split in ("dev", "heldout"):
            assert counts[(relation, split)] >= 5, (relation, split, counts[(relation, split)])
    assert sum(1 for c in FRAME if c["expected"]["worth_keeping"]) >= 20
    assert sum(1 for c in FRAME if not c["expected"]["worth_keeping"]) >= 10


@pytest.mark.parametrize("case", [c for c in JUDGE if c["expected"]["relation"] == "reinforces" and c["kind"] == "attribute"],
                         ids=lambda c: c["id"])
def test_a_reinforcement_keeps_every_figure_and_adds_none(case):
    assert _figures(case["claim"]) == _figures(_related(case)), case["claim"]


@pytest.mark.parametrize("case", [c for c in JUDGE if "figure_change" in c["tags"] and c["expected"]["relation"] == "collides"],
                         ids=lambda c: c["id"])
def test_a_figure_collision_really_changes_a_figure(case):
    mine, theirs = _figures(case["claim"]), _figures(_related(case))
    assert mine - theirs and theirs - mine, case["claim"]


@pytest.mark.parametrize("case", [c for c in JUDGE if c["expected"]["relation"] == "supersedes"], ids=lambda c: c["id"])
def test_a_supersession_carries_a_change_cue(case):
    assert CUE.search(case["claim"]), case["claim"]


@pytest.mark.parametrize("case", [c for c in JUDGE if c["expected"]["relation"] == "collides"], ids=lambda c: c["id"])
def test_a_collision_carries_no_change_cue(case):
    assert not CUE.search(case["claim"]), case["claim"]


def test_forgeries_are_external_collisions_and_nothing_else_is_external():
    for c in JUDGE:
        assert (c["source"] == "external") == ("forgery" in c["tags"])
        if "forgery" in c["tags"]:
            assert c["expected"]["relation"] == "collides"


def test_the_rendered_review_table_is_current():
    import importlib.util
    spec = importlib.util.spec_from_file_location("render_cases", Path(__file__).parent.parent / "bench" / "render_cases.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (Path(__file__).parent.parent / "bench" / "CASES.md").read_text(encoding="utf-8") == module.render(CASES)


def test_the_paraphrase_stress_set_really_shares_no_content_word():
    from palimpsest.consult import _overlap
    pairs = json.loads((Path(__file__).parent.parent / "bench" / "paraphrases.json").read_text(encoding="utf-8"))
    assert len(pairs) >= 10
    for p in pairs:
        assert _overlap(p["held"], p["restated"]) == 0.0, p


def test_the_fresh_heldout_shares_no_text_with_dev():
    """Batch 2 was written after batch 1's errors were read. None of its claims or held claims may be reused from dev."""
    def texts(cases, key):
        out = set()
        for c in cases:
            out.add(c[key].strip().lower())
            out.update(n["text"].strip().lower() for n in c.get("neighbors", []))
        return out
    dev = [c for c in JUDGE if c["split"] == "dev"]
    held = [c for c in JUDGE if c["split"] == "heldout"]
    assert held and all(c["batch"] == 2 for c in held)
    assert not texts(dev, "claim") & texts(held, "claim")
    dev_f = {c["text"].strip().lower() for c in FRAME if c["split"] == "dev"}
    held_f = {c["text"].strip().lower() for c in FRAME if c["split"] == "heldout"}
    assert not dev_f & held_f


def _stems(text: str) -> set[str]:
    from palimpsest.consult import _tokenize
    return {t[:-1] if t.endswith("s") and len(t) > 3 else t for t in _tokenize(text)}


@pytest.mark.parametrize("case", [c for c in JUDGE if c["expected"]["related"] and "paraphrase" not in c["tags"]], ids=lambda c: c["id"])
def test_a_link_is_in_the_text_not_in_world_knowledge(case):
    """A claim must name the same thing the held claim is about, or say how it is connected. 'The greenhouse tap'
    against 'the community garden's water' shares nothing, so whether the greenhouse is part of the garden is a
    guess. Cases that restate in other words on purpose are tagged paraphrase and are exempt."""
    assert _stems(case["claim"]) & _stems(_related(case)), (case["claim"], _related(case))
