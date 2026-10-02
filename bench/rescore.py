"""Re-score saved results after cases are excluded from the held-out split, without re-running any model.

    python bench/rescore.py

Dropping a case only removes its row: every other case's answer is unchanged, so the scores for the remaining cases are
exact. (Nothing is carried over for a model whose answers were not saved.) Each carried entry records what it came from.
Entries already run on the current cases are left alone. A change to the cases starts a fresh board, per GUIDE.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as R  # noqa: E402


def main() -> None:
    cases = json.loads(R.CASES_PATH.read_text(encoding="utf-8"))
    current = R.versions(cases)["cases"]
    keep = {c["id"] for c in cases["judge"] if c["split"] == "heldout"}
    board = json.loads(R.LEADERBOARD.read_text(encoding="utf-8"))
    have = {(e["contender"], e["versions"][e["prompt_key"]]) for e in board if e["versions"]["cases"] == current and e["split"] == "heldout" and e["suite"] == "judge"}
    carried = 0
    for e in [e for e in board if e["suite"] == "judge" and e["split"] == "heldout" and e["versions"]["cases"] != current]:
        if (e["contender"], e["versions"][e["prompt_key"]]) in have:
            continue
        safe = e["contender"].replace(":", "_").replace("/", "_")
        path = R.RESULTS / f"judge-heldout-{safe}-{e['versions'][e['prompt_key']]}-c{e['versions']['cases'][:6]}.json"
        if not path.exists():
            print(f"skip {e['contender']}: no saved answers at {path.name}")
            continue
        rows = [r for r in json.loads(path.read_text(encoding="utf-8"))["cases"] if r["id"] in keep]
        if len(rows) != len(keep):
            print(f"skip {e['contender']}: has {len(rows)} of {len(keep)} cases")
            continue
        new = {**e, "versions": {**e["versions"], "cases": current}, "metrics": R.summarize_judge(rows),
               "carried_from": f"cases {e['versions']['cases']}, same answers, excluded cases dropped"}
        R.record(new, rows)
        have.add((e["contender"], e["versions"][e["prompt_key"]]))
        carried += 1
    print(f"carried {carried} entries onto cases {current}")


if __name__ == "__main__":
    main()
