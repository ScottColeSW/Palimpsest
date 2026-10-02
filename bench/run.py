"""The Palimpsest judge competition: run contenders over the labeled cases, keep a running leaderboard.

    python bench/run.py --models qwen2.5:7b,llama3.2        # held-out split (the leaderboard number)
    python bench/run.py --rules --models qwen2.5:3b         # the fixed rules as a baseline, plus a model
    python bench/run.py --split dev --models qwen2.5:7b     # tune on dev; never published
    python bench/run.py --report                            # rebuild LEADERBOARD.md from results

Contenders: any local Ollama model (palimpsest.judge's framer and judge), and
`--rules`, the deterministic floor in consult(), which gets the same cases with
no scope information and a wording lookup in place of a framer (it has none). Each result is keyed by
model, prompt version and cases version, so a re-run adds to the leaderboard
instead of replacing it, and changing a prompt starts a new entry. See GUIDE.md
for what is scored and why.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from palimpsest import judge as J  # noqa: E402
from palimpsest.consult import DOMAIN_KINDS, Relation, _overlap, consult  # noqa: E402
from palimpsest.memory_store import InMemoryStore  # noqa: E402
from palimpsest.models import DomainKind, Node, Origin, Scope  # noqa: E402

HERE = Path(__file__).parent
CASES_PATH = HERE / "cases.json"
RESULTS = HERE / "results"
LEADERBOARD = RESULTS / "leaderboard.json"
DEFAULT_MODELS = ["qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b", "llama3.2", "gemma2:2b", "phi3:mini", "phi4-mini", "mistral:7b"]
RELATIONS = ("new", "reinforces", "coexists", "collides", "exception_of", "supersedes")
RULES_MAP = {Relation.NEW: "new", Relation.REINFORCES: "reinforces", Relation.COEXISTS: "coexists",
             Relation.COLLIDES: "collides", Relation.SCOPE_LINK: "exception_of", Relation.UNCONFIRMED: "collides"}


def digest(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:10]


def realize_ids(case: dict) -> list[dict]:
    """Held-claim ids shaped like the real ones (c + 8 hex), stable per case, so a model sees what it would in use."""
    return [{"id": "c" + digest(case["id"], n["key"])[:8], "key": n["key"], "text": n["text"]} for n in case["neighbors"]]


def wilson(correct: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = correct / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


# -- contenders --------------------------------------------------------------------------------

def rules_judge(case: dict) -> dict:
    """consult() on the same case. No scope is supplied (nothing here knows it), so it can't answer exception_of."""
    domain = f"bench_{case['id']}"
    DOMAIN_KINDS[domain] = DomainKind(case["kind"])
    store = InMemoryStore()
    ids = {}
    # The rules only compare claims filed under the same fact, and they have no framer to file them. The fair
    # stand-in is a wording lookup: a held claim is compared only if it shares a content word with the new one.
    related = [n for n in realize_ids(case) if _overlap(case["claim"], n["text"]) > 0]
    if not related:
        return {"relation": "new", "related": None, "usable": True}
    for n in related:
        store.add_node(Node(id=n["id"], text=n["text"], domain=domain, referent="r", scope=Scope.GENERAL, origin=Origin.EPISODE))
        ids[n["id"]] = n["key"]
    result = consult(store, Node(id="cand", text=case["claim"], domain=domain, referent="r", scope=Scope.GENERAL, origin=Origin.EPISODE))
    related = ids.get(result.related_node.id) if result.related_node else None
    return {"relation": RULES_MAP[result.relation], "related": related, "usable": True}


def model_judge(judge_fn):
    def run(case: dict) -> dict:
        neighbors = realize_ids(case)
        try:
            verdict = J.normalize_verdict(judge_fn(case["claim"], neighbors, case["kind"]), {n["id"] for n in neighbors})
        except Exception as exc:  # noqa: BLE001
            return {"usable": False, "why": str(exc)[:200]}
        key = {n["id"]: n["key"] for n in neighbors}.get(verdict["related_id"])
        return {"relation": verdict["relation"], "related": key, "usable": True, "coerced": verdict["coerced"]}
    return run


def classify(expected: str, predicted: str | None) -> str:
    if predicted is None:
        return "unusable"
    if expected == "collides":
        return "ok" if predicted == "collides" else "unsafe_miss"
    if predicted == "collides":
        return "false_alarm"
    return "ok" if predicted == expected else "wrong"


def replacement_metrics(rows: list[dict]) -> dict:
    """The two errors the unsafe-miss rate doesn't cover. A wrong replacement overwrites a held belief that should
    have stayed; a missed change leaves a stale belief standing next to its replacement or exception."""
    not_sup = [r for r in rows if r["expected"] != "supersedes"]
    change = [r for r in rows if r["expected"] in ("supersedes", "exception_of")]
    return {
        "wrong_replacement_rate": sum(r["predicted"] == "supersedes" for r in not_sup) / max(1, len(not_sup)),
        "missed_change_rate": sum(r["predicted"] in ("coexists", "new", "reinforces") for r in change) / max(1, len(change)),
    }


def score_judge(cases: list[dict], run_case) -> tuple[dict, list[dict]]:
    rows = []
    for case in cases:
        t = time.perf_counter()
        out = run_case(case)
        seconds = time.perf_counter() - t
        exp = case["expected"]
        pred = out.get("relation")
        kind = classify(exp["relation"], pred)
        related_ok = exp["related"] is None or out.get("related") == exp["related"]
        rows.append({"id": case["id"], "expected": exp["relation"], "predicted": pred, "related_ok": related_ok,
                     "correct": kind == "ok" and related_ok, "error": kind if not (kind == "ok" and related_ok) else None,
                     "tags": case["tags"], "seconds": round(seconds, 2), "why": out.get("why"), "coerced": out.get("coerced", False)})
        if kind == "ok" and not related_ok:
            rows[-1]["error"] = "wrong_claim"
    n = len(rows)
    collides = [r for r in rows if r["expected"] == "collides"]
    other = [r for r in rows if r["expected"] != "collides"]
    forgeries = [r for r in rows if "forgery" in r["tags"]]
    lo, hi = wilson(sum(r["correct"] for r in rows), n)
    metrics = {
        "n": n, "accuracy": sum(r["correct"] for r in rows) / n, "accuracy_ci": [round(lo, 3), round(hi, 3)],
        "relation_accuracy": sum(1 for r in rows if r["predicted"] == r["expected"]) / n,
        "unsafe_miss_rate": sum(r["error"] == "unsafe_miss" for r in collides) / max(1, len(collides)),
        "false_alarm_rate": sum(r["error"] == "false_alarm" for r in other) / max(1, len(other)),
        "unusable_rate": sum(r["predicted"] is None for r in rows) / n,
        "coerced_rate": sum(r["coerced"] for r in rows) / n,
        **replacement_metrics(rows),
        "forgery_flagged": sum(r["predicted"] == "collides" for r in forgeries) / max(1, len(forgeries)),
        "mean_seconds": round(sum(r["seconds"] for r in rows) / n, 2),
        "per_relation": {rel: round(sum(r["correct"] for r in rows if r["expected"] == rel) / max(1, sum(1 for r in rows if r["expected"] == rel)), 3)
                         for rel in RELATIONS},
    }
    return metrics, rows


def score_frame(cases: list[dict], framer) -> tuple[dict, list[dict]]:
    rows = []
    for case in cases:
        t = time.perf_counter()
        try:
            out = framer(case["text"], case["known"])
            usable = isinstance(out, dict) and "worth_keeping" in out
        except Exception as exc:  # noqa: BLE001
            out, usable = {}, False
            why = str(exc)[:200]
        exp = case["expected"]
        row = {"id": case["id"], "usable": usable, "seconds": round(time.perf_counter() - t, 2)}
        if usable:
            row["worth_ok"] = bool(out.get("worth_keeping")) == exp["worth_keeping"]
            if exp["worth_keeping"]:
                row["scope_ok"] = out.get("scope") == exp["scope"]
                row["kind_ok"] = out.get("kind") == exp["kind"]
                if exp.get("domain"):
                    row["domain_ok"] = out.get("domain") == exp["domain"]
        else:
            row["why"] = why if "why" in dir() else "unusable"
        rows.append(row)

    def rate(field):
        sel = [r for r in rows if field in r]
        return round(sum(r[field] for r in sel) / len(sel), 3) if sel else None
    n = len(rows)
    metrics = {"n": n, "worth_accuracy": sum(1 for r in rows if r.get("worth_ok")) / n,
               "scope_accuracy": rate("scope_ok"), "kind_accuracy": rate("kind_ok"), "domain_reuse_accuracy": rate("domain_ok"),
               "unusable_rate": sum(1 for r in rows if not r["usable"]) / n,
               "mean_seconds": round(sum(r["seconds"] for r in rows) / n, 2)}
    return metrics, rows


# -- running and keeping -----------------------------------------------------------------------

def unload(model: str, url: str = "http://localhost:11434") -> None:
    body = json.dumps({"model": model, "keep_alive": 0}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(f"{url}/api/generate", data=body, headers={"Content-Type": "application/json"}), timeout=30).read()
    except Exception:  # noqa: BLE001
        pass


def versions(cases: dict, style: str = "direct") -> dict:
    if style == "hybrid":
        import inspect
        from palimpsest import nli as N
        thresholds = {k: v.default for k, v in inspect.signature(J.hybrid_judge).parameters.items() if v.default is not inspect.Parameter.empty}
        judge = (J.REFINE_PROMPT, json.dumps(J.REFINE_SCHEMA, sort_keys=True), N.DEFAULT_MODEL, json.dumps(thresholds, sort_keys=True))
    else:
        judge = ((J.CHECKS_PROMPT, json.dumps(J.CHECKS_SCHEMA, sort_keys=True)) if style == "checks"
                 else (J.JUDGE_PROMPT, json.dumps(J.JUDGE_SCHEMA, sort_keys=True)))
    return {"cases": digest(json.dumps(cases, sort_keys=True)),
            "judge_prompt": digest(*judge, json.dumps(J.KIND_NOTES, sort_keys=True), J.normalize_verdict.__doc__ or ""),
            "frame_prompt": digest(J.FRAME_PROMPT, json.dumps(J.FRAME_SCHEMA, sort_keys=True))}


def record(entry: dict, rows: list[dict]) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    board = json.loads(LEADERBOARD.read_text(encoding="utf-8")) if LEADERBOARD.exists() else []
    key = (entry["contender"], entry["suite"], entry["split"], entry["versions"][entry["prompt_key"]], entry["versions"]["cases"])
    board = [e for e in board if (e["contender"], e["suite"], e["split"], e["versions"][e["prompt_key"]], e["versions"]["cases"]) != key]
    board.append(entry)
    LEADERBOARD.write_text(json.dumps(board, indent=1), encoding="utf-8")
    safe = entry["contender"].replace(":", "_").replace("/", "_")
    (RESULTS / f"{entry['suite']}-{entry['split']}-{safe}-{entry['versions'][entry['prompt_key']]}-c{entry['versions']['cases'][:6]}.json").write_text(
        json.dumps({"entry": entry, "cases": rows}, indent=1), encoding="utf-8")


def pct(x) -> str:
    return "-" if x is None else f"{x * 100:.0f}%"


def render_leaderboard() -> str:
    board = json.loads(LEADERBOARD.read_text(encoding="utf-8")) if LEADERBOARD.exists() else []
    current = versions(json.loads(CASES_PATH.read_text(encoding="utf-8")))["cases"]
    board = [e for e in board if e["versions"]["cases"] == current]    # only results on the cases as they stand
    lines = ["# Leaderboard", "",
             "Generated by `bench/run.py --report`. Held-out cases only: dev cases are for tuning and never ranked. "
             "Scoring and labels: [GUIDE.md](GUIDE.md), [CASES.md](CASES.md). `unsafe` is the share of true conflicts the "
             "contender failed to flag (the error that matters most); `false alarm` is the share of non-conflicts it flagged; "
             "`wrong replacement` is how often it overwrote a belief that should have stayed; `missed change` is how often a "
             "replacement or exception went unrecognized and left a stale belief standing.", ""]
    if not any(e["split"] == "heldout" for e in board):
        lines += ["No contender has been scored on the current held-out cases yet. The held-out batch was written after the previous "
                  "batch's errors were read, and committed before any change made in response to them. Earlier boards, on earlier cases, are "
                  "kept in [results/](results/): leaderboard-cases-v1.md and leaderboard-cases-v2.md.", ""]
    for suite, title in (("judge", "Judge: how does a new claim relate to what is held?"), ("frame", "Frame: is it worth keeping, and how is it filed?")):
        rows = [e for e in board if e["suite"] == suite and e["split"] == "heldout"]
        if not rows:
            continue
        lines += [f"## {title}", ""]
        pk = "judge_prompt" if suite == "judge" else "frame_prompt"
        newest_cases = sorted(rows, key=lambda e: e["date"])[-1]["versions"]["cases"]
        latest: dict = {}
        for e in sorted(rows, key=lambda e: e["date"]):
            if e["versions"]["cases"] == newest_cases:
                latest[e["contender"]] = e      # a contender's newest run at the current cases
        rows = list(latest.values())
        newest = {"cases": newest_cases, pk: "per row"}
        if suite == "judge":
            rows.sort(key=lambda e: (-e["metrics"]["accuracy"], e["metrics"]["unsafe_miss_rate"]))
            lines += ["| # | contender | accuracy (95% range) | unsafe | false alarm | wrong replacement | missed change | unusable | forgeries flagged | s/case | prompt | run |",
                      "|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for i, e in enumerate(rows, 1):
                m = e["metrics"]
                lines.append(f"| {i} | {e['contender']} | {pct(m['accuracy'])} ({pct(m['accuracy_ci'][0])} to {pct(m['accuracy_ci'][1])}) | "
                             f"{pct(m['unsafe_miss_rate'])} | {pct(m['false_alarm_rate'])} | {pct(m.get('wrong_replacement_rate'))} | "
                             f"{pct(m.get('missed_change_rate'))} | {pct(m['unusable_rate'])} | "
                             f"{pct(m['forgery_flagged'])} | {m['mean_seconds']} | `{e['versions'][pk]}` | {e['date'][:10]} |")
        else:
            rows.sort(key=lambda e: -(e["metrics"]["worth_accuracy"] + (e["metrics"]["scope_accuracy"] or 0) + (e["metrics"]["kind_accuracy"] or 0)))
            lines += ["| # | contender | worth keeping | scope | kind | domain reuse | unusable | s/case | prompt | run |", "|---|---|---|---|---|---|---|---|---|---|"]
            for i, e in enumerate(rows, 1):
                m = e["metrics"]
                lines.append(f"| {i} | {e['contender']} | {pct(m['worth_accuracy'])} | {pct(m['scope_accuracy'])} | {pct(m['kind_accuracy'])} | "
                             f"{pct(m['domain_reuse_accuracy'])} | {pct(m['unusable_rate'])} | {m['mean_seconds']} | `{e['versions'][pk]}` | {e['date'][:10]} |")
        lines += ["", f"Cases version `{newest['cases']}`. Each row shows the prompt version it ran with; unmarked is the judge asked to pick a relation outright; `+checks` is the yes/no-checks style. A change to the cases starts a fresh board.", ""]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="", help="comma-separated Ollama models")
    ap.add_argument("--rules", action="store_true", help="include the fixed-rules baseline")
    ap.add_argument("--suite", choices=["judge", "frame", "all"], default="all")
    ap.add_argument("--split", choices=["dev", "heldout"], default="heldout")
    ap.add_argument("--all-models", action="store_true", help="the default contender list")
    ap.add_argument("--style", choices=["checks", "direct"], default="direct",
                    help="how the judge is asked: simple checks with the relation derived in code, or one direct choice")
    ap.add_argument("--hybrid", default="", help="comma-separated Ollama models to use as the refiner in the NLI hybrid judge")
    ap.add_argument("--previous", action="store_true", help="the hybrid as first scored (entailment both ways, relatedness 0.48), for comparison")
    ap.add_argument("--no-figures", action="store_true", help="turn off the unit-aware figure signal in the hybrid (for comparison)")
    ap.add_argument("--report", action="store_true", help="only rebuild LEADERBOARD.md")
    args = ap.parse_args()

    if not args.report:
        cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        ver = versions(cases, args.style)
        models = DEFAULT_MODELS if args.all_models else [m for m in args.models.split(",") if m]
        suites = ["judge", "frame"] if args.suite == "all" else [args.suite]
        judge_cases = [c for c in cases["judge"] if c["split"] == args.split]
        frame_cases = [c for c in cases["frame"] if c["split"] == args.split]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        contenders = (["rules"] if args.rules else []) + models
        for name in contenders:
            for suite in suites:
                if name == "rules" and suite == "frame":
                    continue
                print(f"{name} / {suite} / {args.split} ...", flush=True)
                t = time.perf_counter()
                if suite == "judge":
                    metrics, rows = score_judge(judge_cases, rules_judge if name == "rules" else model_judge(J.ollama_judge(name, style=args.style)))
                else:
                    metrics, rows = score_frame(frame_cases, J.ollama_framer(name))
                label = name if (name == "rules" or suite == "frame" or args.style == "direct") else f"{name}+checks"
                entry = {"contender": label, "suite": suite, "split": args.split, "date": now, "versions": ver,
                         "prompt_key": "judge_prompt" if suite == "judge" else "frame_prompt", "metrics": metrics}
                record(entry, rows)
                top = (f"accuracy {pct(metrics['accuracy'])}, unsafe {pct(metrics['unsafe_miss_rate'])}, false alarm {pct(metrics['false_alarm_rate'])}, "
                       f"unusable {pct(metrics['unusable_rate'])}") if suite == "judge" else (
                       f"worth {pct(metrics['worth_accuracy'])}, scope {pct(metrics['scope_accuracy'])}, kind {pct(metrics['kind_accuracy'])}")
                print(f"   {top}  ({time.perf_counter() - t:.0f}s)", flush=True)
            if name != "rules":
                unload(name)
        for refiner_model in [m for m in args.hybrid.split(",") if m]:
            from palimpsest import nli as N
            from palimpsest.embed import ollama_embedder
            hver = versions(cases, "hybrid")
            overrides = {"restate": "both", "related": 0.48} if args.previous else {}
            judge_fn = J.hybrid_judge(N.NLI(), ollama_embedder(), J.ollama_refiner(refiner_model), figures=not args.no_figures, **overrides)
            label = f"hybrid({refiner_model}{', previous' if args.previous else ''}{', no figures' if args.no_figures else ''})"
            if args.previous:
                hver = {**hver, "judge_prompt": digest("previous", json.dumps(overrides, sort_keys=True), hver["judge_prompt"])}
            print(f"{label} / judge / {args.split} ...", flush=True)
            t = time.perf_counter()
            metrics, rows = score_judge(judge_cases, model_judge(judge_fn))
            entry = {"contender": label, "suite": "judge", "split": args.split, "date": now,
                     "versions": hver, "prompt_key": "judge_prompt", "metrics": metrics}
            record(entry, rows)
            print(f"   accuracy {pct(metrics['accuracy'])}, unsafe {pct(metrics['unsafe_miss_rate'])}, false alarm {pct(metrics['false_alarm_rate'])}, "
                  f"unusable {pct(metrics['unusable_rate'])}  ({time.perf_counter() - t:.0f}s)", flush=True)
            unload(refiner_model)
            unload("nomic-embed-text")
    RESULTS.mkdir(parents=True, exist_ok=True)
    (HERE / "LEADERBOARD.md").write_text(render_leaderboard(), encoding="utf-8")
    print(f"wrote {HERE / 'LEADERBOARD.md'}")


if __name__ == "__main__":
    main()
