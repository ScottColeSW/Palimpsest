"""Does finding held claims by meaning beat finding them by wording?

For each labeled case that names the held claim it is about, rank every held
claim in the whole benchmark (pooled, so there are many distractors) against
the new claim, and see where the right one lands. Compares the wording overlap
the rules use against an embedding model. Retrieval only: nothing is judged.

    python bench/retrieval.py                       # nomic-embed-text, all cases
    python bench/retrieval.py --model mxbai-embed-large
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from palimpsest.consult import _overlap  # noqa: E402
from palimpsest.embed import cosine, ollama_embedder  # noqa: E402

CASES = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
PARAPHRASES = json.loads((Path(__file__).parent / "paraphrases.json").read_text(encoding="utf-8"))


def rank_of(target: str, scores: dict[str, float]) -> int:
    """1-based rank of the target, counting ties against it (the pessimistic reading)."""
    better = sum(1 for text, s in scores.items() if text != target and s >= scores[target])
    return better + 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="nomic-embed-text")
    args = ap.parse_args()
    embed = ollama_embedder(args.model)

    pool = sorted({n["text"] for c in CASES["judge"] for n in c["neighbors"]} | {p["held"] for p in PARAPHRASES})
    vectors = {t: embed(t) for t in pool}
    queries = []
    for c in CASES["judge"]:
        key = c["expected"]["related"]
        if key:
            target = next(n["text"] for n in c["neighbors"] if n["key"] == key)
            queries.append((c, target))

    results = {"wording": [], "embedding": []}
    by_relation: dict[str, dict[str, list[int]]] = {}
    for case, target in queries:
        qv = embed(case["claim"])
        ranks = {"wording": rank_of(target, {t: _overlap(case["claim"], t) for t in pool}),
                 "embedding": rank_of(target, {t: cosine(qv, vectors[t]) for t in pool})}
        for method, r in ranks.items():
            results[method].append(r)
            by_relation.setdefault(case["expected"]["relation"], {"wording": [], "embedding": []})[method].append(r)

    def at(rs, k):
        return sum(1 for r in rs if r <= k) / len(rs)
    print(f"{len(queries)} queries, {len(pool)} held claims in the pool, model {args.model}")
    print(f"{'':14}{'top-1':>8}{'top-3':>8}{'top-5':>8}{'mean rank':>11}")
    for method, rs in results.items():
        print(f"{method:14}{at(rs, 1):8.0%}{at(rs, 3):8.0%}{at(rs, 5):8.0%}{sum(rs) / len(rs):11.1f}")
    print("\ntop-3 by relation (wording -> embedding):")
    for relation, d in sorted(by_relation.items()):
        print(f"  {relation:13} {at(d['wording'], 3):4.0%} -> {at(d['embedding'], 3):4.0%}  (n={len(d['wording'])})")
    # The regime embeddings are for: a restatement sharing no content word with the claim it restates
    para = {"wording": [], "embedding": []}
    for p in PARAPHRASES:
        qv = embed(p["restated"])
        para["wording"].append(rank_of(p["held"], {t: _overlap(p["restated"], t) for t in pool}))
        para["embedding"].append(rank_of(p["held"], {t: cosine(qv, vectors[t]) for t in pool}))
    print(f"\nrestatements with no shared content word ({len(PARAPHRASES)} pairs, same pool):")
    for method, rs in para.items():
        print(f"{method:14}{at(rs, 1):8.0%}{at(rs, 3):8.0%}{at(rs, 5):8.0%}{sum(rs) / len(rs):11.1f}")
    misses = [(c["id"], c["claim"][:60], rank) for (c, _), rank in zip(queries, results["embedding"]) if rank > 3]
    if misses:
        print("\nembedding misses (rank > 3):")
        for m in misses[:8]:
            print("  ", m)


if __name__ == "__main__":
    main()
