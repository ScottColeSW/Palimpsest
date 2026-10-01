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
- "new": none of the held claims relate to it
- "reinforces": it says the same thing as a held claim (give that claim's id). Restating with the same figure counts. Dropping a figure the held claim states does not.
- "coexists": same topic but both can be true together (a different aspect, an added detail)
- "collides": it conflicts with a held claim, so both cannot be true (a different figure, an opposite). Give that claim's id.
- "exception_of": a specific case, person or project under a held general rule, even if it changes the rule's figure for that case. Give the rule's id.
- "supersedes": the new claim says the held one is no longer true and replaces it (a newer decision, a change). Give that claim's id.

Also give weight from 0 to 1 for how much this claim should matter later, and a one-sentence reason. For "new", related_id is null.
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


def ollama_judge(model: str = DEFAULT_MODEL, url: str = "http://localhost:11434", timeout: float = 120):
    def judge(claim: str, neighbors: list[dict], kind: str) -> dict:
        listing = "\n".join(f"[{n['id']}] {n['text']}" for n in neighbors) or "(nothing held yet)"
        prompt = JUDGE_PROMPT.format(claim=claim, neighbors=listing, kind_note=KIND_NOTES.get(kind, ""))
        return _ask(model, url, timeout, prompt, JUDGE_SCHEMA, 200)
    judge.name = f"ollama:{model}"
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
