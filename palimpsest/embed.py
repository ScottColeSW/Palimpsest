"""Embeddings: find the held claims nearest a new one by meaning, not wording.

Which claims the judge is shown is decided before any judging happens, and
wording overlap misses a claim that says the same thing in other words ("staff
working remotely get $500 a year for desk gear" against "remote employees may
expense up to $500 per year for home office equipment"). An embedder is any
callable text -> list[float]; the reference one asks a local Ollama embedding
model, standard library only. Memory(embedder=...) stores each claim's vector on
its node (SQLite keeps it) and propose() ranks neighbors by cosine when both
sides have one, falling back to wording overlap when either doesn't.

Retrieval only: an embedding never decides what a claim *is* to another. That
stays with the judge and the rules floor.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request

DEFAULT_MODEL = "nomic-embed-text"


def ollama_embedder(model: str = DEFAULT_MODEL, url: str = "http://localhost:11434", timeout: float = 60):
    def embed(text: str) -> list[float]:
        body = json.dumps({"model": model, "input": text, "keep_alive": "5m"}).encode("utf-8")
        request = urllib.request.Request(f"{url.rstrip('/')}/api/embed", data=body,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())["embeddings"][0]
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError, OSError) as exc:
            raise RuntimeError(f"embedding failed: {exc}") from exc
    embed.name = f"ollama:{model}"
    return embed


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
