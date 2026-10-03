"""
Would Palimpsest fix Evo's reflection reinforcement? Pre-registered in PREREGISTRATION-evo-reflections.md.

Evo's `TribeMemory` is imported read-only from EVO_PATH (default: the sibling project folder); nothing there is changed.

    python bench/integration/evo_reflections.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
EVO = os.environ.get("EVO_PATH", r"H:\pet_projects\Evo-LLM-Evolution2Civ")
sys.path.insert(0, EVO)

from backend.memory import TribeMemory, _cosine_similarity  # noqa: E402  (Evo)
from palimpsest.embed import cosine, ollama_embedder  # noqa: E402
from palimpsest.judge import hybrid_judge  # noqa: E402
from palimpsest.nli import NLI  # noqa: E402

PAIRS = {
    "restatement": [
        ("We must keep a watch on the northern pass, because raiders come that way.",
         "Raiders use the northern pass, so a watch must always be kept there."),
        ("Our grain stores should be spread across several storehouses.",
         "We ought not keep all the grain in one place, but split it between storehouses."),
        ("The river clan has been honest with us, so we should keep the alliance.",
         "Because the river clan has dealt honestly, our alliance with them should continue."),
        ("Fishing in the shallows is safer than hunting in the deep forest.",
         "The shallows are the safer place to find food, safer than the deep forest hunt."),
        ("We should build the next long house near the well.",
         "The well is where the next long house ought to go."),
        ("Winter preparations must begin before the first frost.",
         "We have to start getting ready for winter before frost arrives."),
    ],
    "reversal": [
        ("We must keep a watch on the northern pass, because raiders come that way.",
         "We need not keep a watch on the northern pass, because raiders do not come that way."),
        ("We should trust the river clan and share our grain with them.",
         "We should never trust the river clan and must hide our grain from them."),
        ("The deep forest is safe to hunt in, so send the hunters there.",
         "The deep forest is dangerous to hunt in, so keep the hunters out of it."),
        ("We should build the next long house near the well.",
         "We should not build the next long house near the well."),
        ("Winter preparations must begin before the first frost.",
         "Winter preparations should wait until after the first frost."),
        ("The alliance with the hill tribe makes us stronger and should be kept.",
         "The alliance with the hill tribe makes us weaker and should be ended."),
    ],
    "refinement": [
        ("We should trust the river clan and share our grain with them.",
         "We should share grain with the river clan only in years when our own harvest is good."),
        ("Raiders come by the northern pass, so a watch must be kept there.",
         "Raiders come by the northern pass mostly at night, so the watch matters most after dark."),
        ("Fishing in the shallows is safer than hunting in the deep forest.",
         "Fishing in the shallows is unsafe when the river is in flood."),
        ("We should build the next long house near the well.",
         "The next long house near the well should be built of stone, not timber."),
        ("Winter preparations must begin before the first frost.",
         "The orchard harvest is the first winter preparation to start."),
        ("The hill tribe is our ally and should be kept as one.",
         "We should ask the hill tribe for help with the wall."),
    ],
    "unrelated": [
        ("We should trust the river clan and share our grain with them.",
         "The northern pass floods in spring, so we must wait before crossing."),
        ("Raiders come by the northern pass, so a watch must be kept there.",
         "The grain harvest this year was larger than any we remember."),
        ("The deep forest is safe to hunt in, so send the hunters there.",
         "Our chief's tent needs new hides before the cold arrives."),
        ("We should build the next long house near the well.",
         "The elders say the old songs are being forgotten."),
        ("Winter preparations must begin before the first frost.",
         "The river clan sent a gift of salt last season."),
        ("The alliance with the hill tribe makes us stronger and should be kept.",
         "Fishing nets should be mended before the spring run."),
    ],
}


def main():
    embed = ollama_embedder()
    judge = hybrid_judge(NLI(), embed, None)
    rows = []
    for group, pairs in PAIRS.items():
        for earlier, later in pairs:
            m = TribeMemory("t")
            first = m.remember(earlier, 1, 0.5, kind="reflection")
            token = m.remember(later, 2, 0.5, kind="reflection") is first
            ea, eb = embed(earlier), embed(later)
            sim = _cosine_similarity(ea, eb)
            verdict = judge(later, [{"id": "held", "text": earlier, "similarity": cosine(ea, eb)}], "attribute")
            rows.append({"group": group, "earlier": earlier, "later": later, "evo_token_reinforces": token,
                         "evo_embedding_cosine": round(sim, 3), "evo_embedding_reinforces": sim >= 0.75,
                         "palimpsest_relation": verdict["relation"], "palimpsest_reinforces": verdict["relation"] == "reinforces",
                         "palimpsest_reason": verdict["reason"]})
    summary = {}
    for group in PAIRS:
        g = [r for r in rows if r["group"] == group]
        summary[group] = {"n": len(g), "evo_token": sum(r["evo_token_reinforces"] for r in g),
                          "evo_embedding": sum(r["evo_embedding_reinforces"] for r in g),
                          "palimpsest": sum(r["palimpsest_reinforces"] for r in g),
                          "palimpsest_relations": {rel: sum(r["palimpsest_relation"] == rel for r in g) for rel in
                                                   sorted({r["palimpsest_relation"] for r in g})}}
    out = HERE / "evo_reflections_results.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(f"{'group':12s} {'n':>2s}  reinforced:  Evo token  Evo embedding  Palimpsest")
    for group, s in summary.items():
        print(f"{group:12s} {s['n']:>2d}               {s['evo_token']:>5d}  {s['evo_embedding']:>12d}  {s['palimpsest']:>10d}   {s['palimpsest_relations']}")


if __name__ == "__main__":
    main()
