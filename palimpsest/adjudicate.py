"""A reference adjudicator for consult(): a local model asked whether a new
claim agrees with, contradicts, or doesn't address an existing one.

consult() only asks where token overlap and quantities can't settle meaning
(reinforcements and items marked for review), and only lets the answer raise
a flag, never lower one -- see consult.consult. Standard library only, so
Palimpsest takes on no new dependency; any callable with the same shape works.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

PROMPT = """You check whether a new statement conflicts with an existing statement about the same fact.

Existing: {existing}
New: {candidate}

Answer with exactly one verdict:
- "contradicts": both cannot be true at the same time. The new statement changes, removes, or denies what the existing one says. Example: "The limit is $10,000" vs "There is no longer any limit."
- "agrees": the new statement says the same thing, or something consistent with it, even if it is less specific. Example: "The limit is $10,000" vs "Department heads have a spending limit."
- "unrelated": the new statement adds a separate rule or detail that can be true alongside the existing one. Example: "The limit is $10,000" vs "Orders above the limit need CFO approval."
Adding a requirement is not a contradiction. Being less specific is not a contradiction."""

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["agrees", "contradicts", "unrelated"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
}


def ollama_adjudicator(model: str = "qwen2.5:3b", url: str = "http://localhost:11434", timeout: float = 60):
    """Returns an adjudicator backed by an Ollama model. Failures return an
    empty opinion, which consult() treats as no opinion at all.

    Model choice matters more than it looks. On four probe pairs (a forged
    "the limit has been removed", a vaguer restatement, an added CFO rule, and
    a second removal), qwen2.5:3b and phi4-mini got all four right with this
    prompt; gemma2:2b called the added rule "agrees" (harmless); llama3.2
    answered "contradicts" to everything with a bare prompt and "unrelated" to
    everything with this one. Because consult() only lets a verdict raise a
    flag, a wrong model can create false collisions but never clear a forgery."""

    def adjudicate(existing: str, candidate: str) -> dict:
        body = json.dumps({
            "model": model, "stream": False, "format": SCHEMA, "keep_alive": "1m",
            "prompt": PROMPT.format(existing=existing, candidate=candidate),
            "options": {"temperature": 0, "num_predict": 96, "num_ctx": 2048},
        }).encode("utf-8")
        request = urllib.request.Request(f"{url.rstrip('/')}/api/generate", data=body,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(json.loads(response.read())["response"])
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError):
            return {}

    adjudicate.name = f"ollama:{model}"
    return adjudicate
