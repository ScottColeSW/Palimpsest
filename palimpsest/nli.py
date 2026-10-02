"""Natural language inference: do two sentences agree, conflict, or neither?

A pretrained NLI model answers one narrow question about a pair of sentences
(does the second follow from the first, contradict it, or neither), which is
exactly the comparison a small chat model gets wrong when asked to pick among
six relations at once. It runs in milliseconds on CPU, gives the same answer
every time, and needs no prompt.

    pip install "palimpsest[nli]"        # transformers (below 5) + torch
    python -m palimpsest.nli --fetch     # one-time download of the pinned model revision
    python -m palimpsest.nli --check     # confirms the environment gives the right answers at a sane speed

The model is pinned to an exact revision so results are reproducible, and is loaded from the local cache
first, so starting up needs no network. The weights are fetched from Hugging Face rather than bundled, and
the check exists because the same model and the same answers can run an order of magnitude slower on an
untested library version (transformers 5 did, by about 12x, on CPU), with no error to say so.

What it can't do: tell what *kind* of conflict it is (an exception to a rule,
a replacement of it, or a plain disagreement), or separate "same topic,
compatible" from "different topic" (both are neutral). The hybrid judge in
judge.py takes those from similarity and an evidence-checked refiner.
"""

from __future__ import annotations

DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
DEFAULT_REVISION = "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"   # the revision the benchmark was run with


class NLI:
    """Lazy-loading wrapper. compare(premise, hypothesis) -> {"entailment", "neutral", "contradiction"}."""

    def __init__(self, model: str = DEFAULT_MODEL, device: str | None = None, revision: str | None = DEFAULT_REVISION) -> None:
        self.model_name = model
        self.revision = revision if model == DEFAULT_MODEL else None
        self.device = device
        self._tok = self._model = None
        self._cache: dict[tuple[str, str], dict[str, float]] = {}

    def _load(self) -> None:
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:  # pragma: no cover
            raise ImportError('NLI needs the optional dependencies: pip install "palimpsest[nli]"') from exc
        self._torch = torch
        # Local cache first: no network, no wait on a flaky connection. Fall back to downloading the pinned revision.
        def load(local_only: bool):
            kw = {"revision": self.revision, "local_files_only": local_only}
            return (AutoTokenizer.from_pretrained(self.model_name, **kw),
                    AutoModelForSequenceClassification.from_pretrained(self.model_name, **kw).eval())
        try:
            self._tok, self._model = load(True)
        except OSError:
            self._tok, self._model = load(False)
        if self.device:
            self._model.to(self.device)
        self._labels = {i: label.lower() for i, label in self._model.config.id2label.items()}

    def compare(self, premise: str, hypothesis: str) -> dict[str, float]:
        key = (premise, hypothesis)
        if key not in self._cache:
            if self._model is None:
                self._load()
            enc = self._tok(premise, hypothesis, return_tensors="pt", truncation=True, max_length=512)
            if self.device:
                enc = {k: v.to(self.device) for k, v in enc.items()}
            with self._torch.no_grad():
                probs = self._torch.softmax(self._model(**enc).logits[0], -1).tolist()
            self._cache[key] = {self._labels[i]: probs[i] for i in range(len(probs))}
        return self._cache[key]

    def compare_many(self, pairs: list[tuple[str, str]]) -> list[dict[str, float]]:
        """compare() for several (premise, hypothesis) pairs in one forward pass. Pairs already seen come from the
        cache; the rest are batched. Same answers as compare(), fewer trips through the model."""
        todo = [p for p in dict.fromkeys(pairs) if p not in self._cache]
        if todo:
            if self._model is None:
                self._load()
            enc = self._tok([p[0] for p in todo], [p[1] for p in todo], return_tensors="pt", truncation=True,
                            max_length=512, padding=True)
            if self.device:
                enc = {k: v.to(self.device) for k, v in enc.items()}
            with self._torch.no_grad():
                probs = self._torch.softmax(self._model(**enc).logits, -1).tolist()
            for pair, row in zip(todo, probs):
                self._cache[pair] = {self._labels[i]: row[i] for i in range(len(row))}
        return [self._cache[p] for p in pairs]

    @property
    def name(self) -> str:
        return f"nli:{self.model_name.split('/')[-1]}"


# Pairs with answers any working NLI model gives, and the slowest per-pair time (milliseconds, a batch of four on CPU)
# that still counts as healthy. Healthy stacks measured 40 to 45 ms per pair; the slow one measured 230 to 280.
CHECKS = [
    ("ignored Captain Vance's order", "complied with Captain Vance's order", "contradiction"),
    ("complied with Captain Vance's order", "complied with Captain Vance's order", "entailment"),
    ("The oven needs to be preheated to 425 degrees.", "The hotel does not allow pets.", "neutral"),
    ("The shop opens at 9 am on weekdays.", "The shop opens at 11 am on weekdays.", "contradiction"),
]
MAX_MS_PER_PAIR = 150


def main(argv: list[str] | None = None) -> int:
    import argparse
    import time
    ap = argparse.ArgumentParser(prog="python -m palimpsest.nli", description="Fetch or check the NLI model.")
    ap.add_argument("--fetch", action="store_true", help="download the pinned model revision into the Hugging Face cache")
    ap.add_argument("--check", action="store_true", help="verify answers and speed in this environment")
    args = ap.parse_args(argv)
    if not (args.fetch or args.check):
        ap.print_help()
        return 0
    try:
        import torch
        import transformers
    except ImportError:
        print('Missing dependencies. Install them with: pip install "palimpsest[nli]"')
        return 2
    nli = NLI()
    if args.fetch:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        AutoTokenizer.from_pretrained(nli.model_name, revision=nli.revision)
        AutoModelForSequenceClassification.from_pretrained(nli.model_name, revision=nli.revision)
        print(f"fetched {nli.model_name} @ {nli.revision}")
    if args.check:
        print(f"torch {torch.__version__}, transformers {transformers.__version__}, {torch.get_num_threads()} threads")
        if int(transformers.__version__.split(".")[0]) >= 5:
            print("WARNING: transformers 5 runs this model about 12x slower on CPU; install transformers<5")
        nli.compare("warm", "up")
        start = time.perf_counter()
        got = nli.compare_many([(a, b) for a, b, _ in CHECKS])
        per_pair = (time.perf_counter() - start) * 1000 / len(CHECKS)
        bad = 0
        for (a, b, want), r in zip(CHECKS, got):
            top = max(r, key=r.get)
            ok = top == want
            bad += not ok
            print(f"  {'ok ' if ok else 'BAD'} expected {want:13} got {top:13} ({r[top]:.2f})  {a[:38]} / {b[:30]}")
        print(f"  {per_pair:.0f} ms per pair (healthy is under {MAX_MS_PER_PAIR})")
        if bad:
            print("FAILED: the model gave wrong answers in this environment")
            return 1
        if per_pair > MAX_MS_PER_PAIR:
            print("SLOW: answers are right but this environment is much slower than the tested one")
            return 1
        print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
