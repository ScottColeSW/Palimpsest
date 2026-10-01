"""Natural language inference: do two sentences agree, conflict, or neither?

A pretrained NLI model answers one narrow question about a pair of sentences
(does the second follow from the first, contradict it, or neither), which is
exactly the comparison a small chat model gets wrong when asked to pick among
six relations at once. It runs in milliseconds on CPU, gives the same answer
every time, and needs no prompt.

    pip install "palimpsest[nli]"        # transformers + torch

What it can't do: tell what *kind* of conflict it is (an exception to a rule,
a replacement of it, or a plain disagreement), or separate "same topic,
compatible" from "different topic" (both are neutral). The hybrid judge in
judge.py takes those from similarity and an evidence-checked refiner.
"""

from __future__ import annotations

DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"


class NLI:
    """Lazy-loading wrapper. compare(premise, hypothesis) -> {"entailment", "neutral", "contradiction"}."""

    def __init__(self, model: str = DEFAULT_MODEL, device: str | None = None) -> None:
        self.model_name = model
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
        self._tok = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name).eval()
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

    @property
    def name(self) -> str:
        return f"nli:{self.model_name.split('/')[-1]}"
