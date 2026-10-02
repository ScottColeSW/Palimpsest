"""Reference judges: a local model does the framing and the judging.

Palimpsest is meant to be driven by an agent, and the agent doesn't have to be
a hosted model or sit behind a protocol. Memory.learn() takes two callables:

    framer(text, known) -> {"worth_keeping", "claim", "domain", "referent", "scope", "kind"}
    judge(claim, neighbors, kind) -> {"relation", "related_id", "weight", "reason"}

and anything with those shapes works (a llama.cpp server, a hosted API, a
hand-written function). The ones here talk to a local Ollama model using only
the standard library. Two small focused calls rather than one big one: a small
model asked to do everything at once files things under the wrong fact.

A model can be wrong, and it can be persuaded. Nothing here is trusted
beyond what agent.commit() enforces (see agent.py): external claims can't
supersede and are held for the user when the rules would hold them. A model
that errors or answers outside the schema gets no say: learn() keeps the
material as dormant, unjudged, and decides nothing.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from .agent import AGENT_RELATIONS

DEFAULT_MODEL = "qwen2.5:7b"

FRAME_PROMPT = """You are the memory of an AI agent. Decide whether a piece of text is worth remembering, and how to file it.

Worth remembering: a durable fact, rule, preference, decision, or lesson that would change how the agent acts later. Not worth remembering: chit-chat, one-off logistics, text with no lasting claim.

If it is worth remembering, restate it as one self-contained claim and file it:
- domain: the topic, in snake_case (e.g. spending_limit, communication_style)
- referent: what the claim is about, in snake_case (e.g. department_head, scott)
- scope: "general" for a rule that applies broadly, "instance" for one specific case, person, project or occasion
- kind: "attribute" if only one value can be true at a time (a limit, a preference, a setting), "event" if many compatible things can be true at once (what happened, a narrative)

Already filed (reuse the same domain and referent when the text is about the same thing; do not invent a near-duplicate name):
{known}

Text: {text}"""

FRAME_SCHEMA = {
    "type": "object",
    "properties": {
        "worth_keeping": {"type": "boolean"},
        "claim": {"type": "string"},
        "domain": {"type": "string"},
        "referent": {"type": "string"},
        "scope": {"type": "string", "enum": ["general", "instance"]},
        "kind": {"type": "string", "enum": ["attribute", "event"]},
    },
    "required": ["worth_keeping", "claim", "domain", "referent", "scope", "kind"],
}

JUDGE_PROMPT = """You are the memory of an AI agent. A new claim has arrived. Decide how it relates to what is already held.

New claim: {claim}

Held claims about the same or nearby things:
{neighbors}

Each held claim starts with its id in square brackets; give the id alone, without the brackets.

Choose exactly one relation:
- "new": none of the held claims is about the same subject. A claim about a different subject is "new", even if both are loosely about the same company or team.
- "reinforces": it says the same thing as a held claim (give that claim's id). Restating with the same figure counts. Dropping a figure the held claim states does not.
- "coexists": same topic but both can be true together (a different aspect, an added detail)
- "collides": it conflicts with a held claim, so both cannot be true (a different figure, an opposite). Give that claim's id.
- "exception_of": a specific case, person or project under a held general rule, even if it changes the rule's figure for that case. Give the rule's id.
- "supersedes": the new claim says the held one is no longer true and replaces it (a newer decision, a change). Give that claim's id.

Every relation except "new" must name the held claim it is about. Also give weight from 0 to 1 for how much this claim should matter later, and a one-sentence reason. For "new", related_id is null.
{kind_note}"""

KIND_NOTES = {
    "attribute": "This topic has one true value at a time, so a different value is a collision or a replacement, not a coexisting claim.",
    "event": "This topic is a stream of things that happened, so different events usually coexist.",
}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "relation": {"type": "string", "enum": list(AGENT_RELATIONS)},
        "related_id": {"type": ["string", "null"]},
        "weight": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["relation", "related_id", "weight", "reason"],
}

CHECKS_PROMPT = """You are the memory of an AI agent. A new claim has arrived. Compare it with the held claims.

New claim: {claim}

Held claims (each starts with its id in square brackets):
{neighbors}

Answer these checks about the held claim that is most closely about the same thing as the new claim:
- related_id: the id of that held claim, written without brackets, or null if none of the held claims is about the same subject. A claim about a different subject is not related, even if both are loosely about the same company or team.
- restates: true if the new claim says the same thing as that held claim in other words, with the same figures and no new condition. Adding a requirement or a detail is not restating.
- bounded: true if the new claim applies only to one specific project, person, system, group, period or occasion, and differs from what the held claim says in general.
- replaces: true if the new claim says the held claim has stopped being true, using a signal of change such as now, effective, no longer, as of, moved, changed, raised, or instead.
- compatible: true if the new claim and the held claim could both be true at the same time.
- reason: one sentence saying why.
{kind_note}"""

CHECKS_SCHEMA = {
    "type": "object",
    "properties": {
        "related_id": {"type": ["string", "null"]},
        "restates": {"type": "boolean"},
        "bounded": {"type": "boolean"},
        "replaces": {"type": "boolean"},
        "compatible": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["related_id", "restates", "bounded", "replaces", "compatible", "reason"],
}


def derive_relation(checks: dict, related_named: bool) -> str:
    """The relation, decided in code from a model's simple yes/no answers. The order matters: a restatement
    confirms; a bounded difference is an exception; a stated change replaces; otherwise compatible claims
    coexist and incompatible ones collide. No related claim means new."""
    if not related_named:
        return "new"
    if checks.get("restates"):
        return "reinforces"
    if checks.get("bounded"):
        return "exception_of"
    if checks.get("replaces"):
        return "supersedes"
    return "coexists" if checks.get("compatible") else "collides"


_SNAKE = re.compile(r"[^a-z0-9]+")


def snake(name: str) -> str:
    return _SNAKE.sub("_", name.strip().lower()).strip("_")


def _ask(model: str, url: str, timeout: float, prompt: str, schema: dict, num_predict: int) -> dict:
    body = json.dumps({
        "model": model, "stream": False, "format": schema, "keep_alive": "5m", "prompt": prompt,
        "options": {"temperature": 0, "num_predict": num_predict, "num_ctx": 4096},
    }).encode("utf-8")
    request = urllib.request.Request(f"{url.rstrip('/')}/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(json.loads(response.read())["response"])
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
        raise RuntimeError(f"model call failed: {exc}") from exc


def ollama_framer(model: str = DEFAULT_MODEL, url: str = "http://localhost:11434", timeout: float = 120):
    def frame(text: str, known: list[dict]) -> dict:
        listing = "\n".join(f"- domain {k['domain']}, referent {k['referent']} ({k['kind']})" for k in known) or "(nothing yet)"
        out = _ask(model, url, timeout, FRAME_PROMPT.format(known=listing, text=text), FRAME_SCHEMA, 256)
        out["domain"], out["referent"] = snake(out.get("domain", "")), snake(out.get("referent", ""))
        return out
    frame.name = f"ollama:{model}"
    return frame


def ollama_judge(model: str = DEFAULT_MODEL, url: str = "http://localhost:11434", timeout: float = 120,
                 style: str = "direct"):
    """style="direct" (default): the model picks one of the six relations itself.
    style="checks": the model answers simple yes/no checks and the relation is derived in code. It was tried
    because small models confuse the relations when asked to choose among six, and it scored worse on the dev
    split (the models read "restates" literally, and call any difference a "replacement"), so it is not the
    default. It stays as an option so the comparison can be re-run; see bench/LEADERBOARD.md."""
    if style not in ("checks", "direct"):
        raise ValueError("style must be 'checks' or 'direct'")

    def judge(claim: str, neighbors: list[dict], kind: str) -> dict:
        listing = chr(10).join(f"[{n['id']}] {n['text']}" for n in neighbors) or "(nothing held yet)"
        if style == "direct":
            prompt = JUDGE_PROMPT.format(claim=claim, neighbors=listing, kind_note=KIND_NOTES.get(kind, ""))
            return _ask(model, url, timeout, prompt, JUDGE_SCHEMA, 200)
        prompt = CHECKS_PROMPT.format(claim=claim, neighbors=listing, kind_note=KIND_NOTES.get(kind, ""))
        checks = _ask(model, url, timeout, prompt, CHECKS_SCHEMA, 200)
        known = {n["id"] for n in neighbors}
        raw = checks.get("related_id")
        named = raw is not None and not (isinstance(raw, str) and raw.strip().lower() in ("", "null", "none", "n/a"))
        # An id that isn't a held claim is passed through as given, so normalize_verdict rejects it as invented
        relation = derive_relation(checks, named)
        return {"relation": relation, "related_id": raw if named else None, "reason": checks.get("reason", ""),
                "checks": {k: checks.get(k) for k in ("restates", "bounded", "replaces", "compatible")}}
    judge.name = f"ollama:{model}:{style}"
    return judge


REFINE_PROMPT_V0 = """A new claim conflicts with a held claim. Decide what kind of conflict it is.

Held claim: {held}
New claim: {claim}

Choose one kind:
- "exception": the new claim applies only to one specific project, person, system, group, period or occasion, so the held claim still holds in general.
- "replacement": the new claim says the held claim stopped being true, using words such as now, effective, no longer, as of, moved, changed, raised, instead.
- "conflict": neither of those. The two claims simply disagree.

For "exception" or "replacement", quote the exact words from the new claim that show it. For "conflict", the quote is null."""


REFINE_PROMPT = """A new claim conflicts with a held claim. Decide what kind of conflict it is.

Held claim: {held}
New claim: {claim}

Choose one kind:
- "exception": the new claim applies only to something specific: one named project, person, system, group, place, category, event, period of time or condition. The held claim still holds everywhere else. Words that often show it: only, during, for the, on (a day), in (a month), at the (a place), when, if, who, this time.
- "replacement": the new claim says the held claim stopped being true. Words that often show it: now, effective, no longer, as of, moved, changed, raised, lowered, switched, replaced, starting, from now on, instead.
- "conflict": neither of those. The two claims simply disagree about the same thing.

Examples (unrelated to the claims above):
- Held: "The lab opens at 8 am." New: "On inspection days the lab opens at 10 am." -> exception (shown by "On inspection days").
- Held: "The lab opens at 8 am." New: "As of June the lab opens at 9 am." -> replacement (shown by "As of June").
- Held: "The lab opens at 8 am." New: "The lab opens at 6 pm." -> conflict (nothing limits it and nothing says the old one ended).

For "exception" or "replacement", quote the exact words from the new claim that show it. For "conflict", the quote is null."""

REFINE_SCHEMA = {
    "type": "object",
    "properties": {"kind": {"type": "string", "enum": ["exception", "replacement", "conflict"]},
                   "evidence": {"type": ["string", "null"]}},
    "required": ["kind", "evidence"],
}


def ollama_refiner(model: str = DEFAULT_MODEL, url: str = "http://localhost:11434", timeout: float = 120,
                   prompt: str | None = None):
    """Given a held claim and a new claim that conflicts with it, a local model says what kind of conflict:
    returns {"kind": "exception" | "replacement" | "conflict", "evidence": str | None}."""
    def refine(held: str, claim: str) -> dict:
        return _ask(model, url, timeout, (prompt or REFINE_PROMPT).format(held=held, claim=claim), REFINE_SCHEMA, 120)
    refine.name = f"ollama:{model}"
    return refine


def _quoted(evidence, claim: str) -> bool:
    """The refiner must cite words that are really in the claim. Anything it can't show is a guess."""
    if not isinstance(evidence, str) or not evidence.strip():
        return False
    return " ".join(evidence.lower().split()) in " ".join(claim.lower().split())


def _adds_words(evidence: str, held: str, share: float) -> bool:
    """The evidence must say something the held claim does not already say: at least `share` of its content words
    must be absent from the held claim. A quote made mostly of the held claim's own words (the whole claim copied
    back, "Elena is the coordinator for the choir" against "Maria is the coordinator for the choir") points at
    nothing, even though it is really in the claim."""
    from .consult import _tokenize
    words = _tokenize(evidence)
    return bool(words) and len(words - _tokenize(held)) / len(words) >= share


def hybrid_judge(nli, embedder, refiner, *, entail: float = 0.5, contradict: float = 0.5, related: float = 0.56,
                 restate: str = "held_implies", figures: bool = True, replace_novelty: float = 0.5,
                 timings: dict | None = None):
    """A judge with no chat model deciding the relation, and nothing scripted about wording.

    - A pretrained NLI model compares the new claim with each held claim in both directions. A claim the held
      claim already implies is `reinforces` (restate="held_implies"): it is the same, or less specific. A claim
      that implies the held one but not the reverse says more than is held, which is an addition, not a
      restatement. (restate="both" requires entailment in both directions, the first version, which read
      every less specific restatement as an addition.) Contradiction either way is a conflict.
    - With refiner=None there is no language model at all: NLI and embeddings only, on CPU plus a small embedder, and
      every conflict is a plain `collides` (both claims stay live, the dispute stays open, a person or the agent
      resolves it). That is the honest configuration for a small model that cannot reliably tell a replacement from
      a conflict, and for a machine whose GPU already belongs to something else.
    - A conflict is `collides` unless the refiner (a model, asked a narrow question) cites words in the claim
      that show it is bounded to one case (`exception_of`) or says the held claim stopped being true
      (`supersedes`). The citation is checked against the claim; one that isn't there downgrades to `collides`.
      A replacement's citation must also add words the held claim lacks (`replace_novelty`, at least half its
      content words): models that are wrong about a replacement tend to quote the whole claim back, which proves
      nothing. Asking twice does not help, because the two prompts make the same mistake. 0.5 sits in a window
      (0.45 to 0.5 safe on development data, 0.6 destroys recall), so expect it to be imperfect.
      So the refiner can only add precision, never hide a conflict: the safe answer is the default.
    - A figure conflict also counts as a conflict (`figures=True`): when the two claims are about the same
      subject (similarity at least `related`) and state figures of the same kind that differ ("$750" against "$500",
      not "30 days" against "$500"; see consult.Quantity), a sentence pair NLI finds merely neutral is still a
      conflict. This can only raise a flag, never lower one.
    - Neither: embedding similarity decides between `coexists` (same subject, compatible) and `new`. In an
      event domain a conflict is just another event, so it coexists.

    Thresholds: `entail` and `contradict` are the NLI probabilities needed (dev results are flat for entail from
    0.2 to 0.6, so 0.5 is left alone); `related` is the cosine similarity at which a neutral pair counts as the same
    subject. 0.56 is the middle of the 0.54 to 0.58 plateau where both development batches score at least 89% on
    new versus coexists. An earlier 0.48, fitted to 12 cases, scored 71% on the next batch; fitting on one batch
    and testing on the other gives 71% and 89%, so expect roughly that, not the in-sample figure. It is a
    calibration, not a constant of nature, and it only ever decides between coexists and new for pairs NLI found
    neutral, so it cannot hide a conflict.     nature. `timings`, if given, accumulates seconds spent per stage (embed, nli, refine). Returns the standard
    judge callable."""
    import time
    from .consult import _competing_values
    from .embed import cosine

    def timed(stage, fn, *args):
        start = time.perf_counter()
        try:
            return fn(*args)
        finally:
            if timings is not None:
                timings[stage] = timings.get(stage, 0.0) + time.perf_counter() - start

    def judge(claim: str, neighbors: list[dict], kind: str) -> dict:
        if not neighbors:
            return {"relation": "new", "related_id": None, "weight": 0.5, "reason": "nothing held yet"}
        qv = timed("embed", embedder, claim) if embedder else None
        scored = []
        # Every comparison in one batch when the comparator can (compare_many); otherwise one at a time
        pairs = [pair for n in neighbors for pair in ((claim, n["text"]), (n["text"], claim))]
        if hasattr(nli, "compare_many"):
            results = timed("nli", nli.compare_many, pairs)
        else:
            results = [timed("nli", nli.compare, *pair) for pair in pairs]
        for i, n in enumerate(neighbors):
            fwd, back = results[2 * i], results[2 * i + 1]
            sim = n.get("similarity")
            if sim is None and qv is not None:
                sim = cosine(qv, timed("embed", embedder, n["text"]))
            nli_conflict = max(fwd["contradiction"], back["contradiction"])
            figs = _competing_values(claim, n["text"], strict=True) if figures and (sim or 0.0) >= related else None
            implied = back["entailment"] if restate == "held_implies" else min(fwd["entailment"], back["entailment"])
            scored.append({"n": n, "same": implied, "figs": figs,
                           "conflict": max(nli_conflict, 1.0 if figs else 0.0), "nli_conflict": nli_conflict,
                           "sim": sim or 0.0})
        same = max(scored, key=lambda s: s["same"])
        if same["same"] >= entail and same["nli_conflict"] < contradict:
            return {"relation": "reinforces", "related_id": same["n"]["id"], "weight": 0.5,
                    "reason": (f"NLI: the held claim already implies it ({same['same']:.2f})" if restate == "held_implies"
                                else f"NLI: each claim entails the other ({same['same']:.2f})")}
        conflict = max(scored, key=lambda s: (s["conflict"], s["sim"]))
        if conflict["conflict"] >= contradict:
            held = conflict["n"]
            if kind == "event":
                return {"relation": "coexists", "related_id": held["id"], "weight": 0.5,
                        "reason": "NLI: they differ, but in an event domain different events coexist"}
            if conflict["figs"] and conflict["nli_conflict"] < contradict:
                mine, theirs = (", ".join(f"{v:g}" for v in sorted(vals)) for vals in conflict["figs"])
                base = f"figures differ ({mine} vs {theirs}) on the same subject; NLI contradiction {conflict['nli_conflict']:.2f}"
            else:
                base = f"NLI: contradiction {conflict['conflict']:.2f}"
            try:
                # No refiner: every conflict stays a plain collision, which is also what a failed refiner leaves
                verdict = timed("refine", refiner, held["text"], claim) if refiner is not None else {"kind": "conflict", "evidence": None}
            except Exception:  # noqa: BLE001 -- a refiner failure leaves the safe default
                verdict = {"kind": "conflict", "evidence": None}
            shown = _quoted(verdict.get("evidence"), claim)
            # A replacement overwrites a belief; an exception only adds a scoped link and leaves both claims live.
            # The bar for evidence differs with the harm: a replacement's quote must add words the held claim lacks.
            if shown and verdict.get("kind") == "replacement":
                shown = _adds_words(verdict["evidence"], held["text"], replace_novelty)
            if verdict.get("kind") in ("exception", "replacement") and shown:
                relation = "exception_of" if verdict["kind"] == "exception" else "supersedes"
                return {"relation": relation, "related_id": held["id"], "weight": 0.5,
                        "reason": f"{base}; {verdict['kind']} shown by \"{verdict['evidence'].strip()}\""}
            return {"relation": "collides", "related_id": held["id"], "weight": 0.5, "reason": f"{base}; no scope or change shown"}
        nearest = max(scored, key=lambda s: s["sim"])
        if nearest["sim"] >= related:
            return {"relation": "coexists", "related_id": nearest["n"]["id"], "weight": 0.5,
                    "reason": f"NLI: neither entails nor contradicts; similar subject ({nearest['sim']:.2f})"}
        return {"relation": "new", "related_id": None, "weight": 0.5,
                "reason": f"NLI: neutral, and the nearest held claim is a different subject ({nearest['sim']:.2f})"}
    judge.name = f"hybrid:{getattr(nli, 'name', 'nli')}"
    return judge


def clean_id(value, known: set[str]) -> str | None:
    """A model's related_id, matched to a held claim. Tolerates decoration around a real id ("id c1f2", "[c1f2]")
    and nothing else: an id that isn't a held claim comes back None, and the verdict is unusable."""
    if not isinstance(value, str):
        return None
    text = value.strip().strip("[]()\"'` ")
    if text in known:
        return text
    found = [k for k in known if re.search(rf"(?<![A-Za-z0-9]){re.escape(k)}(?![A-Za-z0-9])", value)]
    return found[0] if len(found) == 1 else None


# A relation that is about a held claim but names none can't be acted on as given. For the relations that
# only add or confirm, the only consistent reading is "nothing held is related": new. For the ones that flag
# or replace, guessing is the unsafe direction, so the verdict is rejected instead.
_ADDS = ("reinforces", "coexists", "exception_of")


def normalize_verdict(verdict, known: set[str]) -> dict:
    """A model's verdict as {"relation", "related_id", "reason", "weight", "coerced"}, or ValueError if it can't be used.
    related_id must name a held claim (see clean_id)."""
    relation = verdict["relation"]
    if relation not in AGENT_RELATIONS:
        raise ValueError(f"not a relation: {relation!r}")
    reason = str(verdict.get("reason", "")).strip()
    if not reason:
        raise ValueError("no reason")
    raw = verdict.get("related_id")
    related = clean_id(raw, known)
    named_none = raw is None or (isinstance(raw, str) and raw.strip().lower() in ("", "null", "none", "n/a"))
    coerced = False
    if relation != "new" and related is None:
        if not named_none:
            raise ValueError(f"{raw!r} is not a held claim")  # a reference to something that doesn't exist
        if relation in _ADDS:
            relation, coerced = "new", True
        else:
            raise ValueError(f"{relation} names no held claim")
    try:
        weight = min(1.0, max(0.0, float(verdict.get("weight", 0.5))))
    except (TypeError, ValueError):
        weight = 0.5
    return {"relation": relation, "related_id": None if relation == "new" else related, "reason": reason,
            "weight": weight, "coerced": coerced}
