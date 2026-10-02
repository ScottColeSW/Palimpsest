"""consult() -- the step that makes this a memory system instead of a
labeled pile of context. Everything built before this (ingest.py,
memory_store.py, traversal.py) only put material somewhere and let it
sit. consult() is what actually reads the mesh back and lets a new
claim be judged against what's already there -- the one behavior
DESIGN.md's thesis says separates memory from "more tokens
to read before answering."

Deliberately narrow about what it's honest to claim. No real
contradiction detection -- that's a hard, unsolved NLU problem, same
policy as ingest.py's placeholder classifier: don't fake
sophistication that isn't there. What IS real and not a placeholder:
scope matching. A general claim and an instance claim about the same
referent are never treated as colliding, full stop, regardless of
content -- that's structural logic, not a guess (see DESIGN.md's
scope section, and demo_scenario.py's Marcus example, which this
module's tests deliberately reuse rather than inventing new data).
For same-scope claims about the same referent+domain, token overlap
(Jaccard -- the same pattern Evolution2Civ's TribeMemory uses, cited
in DESIGN.md's related ideas) decides reinforcement vs. everything
else -- and what "everything else" means depends on DomainKind
(models.py): an ATTRIBUTE domain has one true value at a time, so low
overlap really is tension and becomes an OPEN collision needing real
resolution. An EVENT domain doesn't -- many different, unrelated
things can be true about the same referent (a narrative), so low
overlap there just means "a different event", not disagreement, and
becomes COEXISTS instead. Getting this wrong isn't hypothetical: an
earlier version treated every domain as ATTRIBUTE and real
Winnie-the-Pooh ingestion produced 44 false collisions between
perfectly ordinary, compatible sentences about Pooh.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from .memory_store import InMemoryStore
from .models import DomainKind, Edge, EdgeStatus, EdgeType, Node, Origin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

# A domain has to be explicitly declared attribute-like (one true value
# competes at a time) to get collision detection at all. Unregistered
# domains default to EVENT -- see DomainKind's docstring for why an
# unsafe default here produced real false positives against real text.
# A plain dict on purpose, not a generated registry -- easy to read,
# easy to extend, same call Dominion's model catalog makes.
DOMAIN_KINDS: dict[str, DomainKind] = {
    "appearance": DomainKind.ATTRIBUTE,
    "temperament": DomainKind.ATTRIBUTE,
}


def domain_kind_for(domain: str) -> DomainKind:
    return DOMAIN_KINDS.get(domain, DomainKind.EVENT)


_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "and", "or", "of", "to",
    "in", "on", "at", "with", "her", "his", "its", "it", "he", "she", "for",
})

# Same first-cut number TribeMemory's reflection-reinforcement check uses
# (see DESIGN.md's related ideas) -- no real data behind this one
# either yet, worth revisiting once some exists.
REINFORCEMENT_OVERLAP_THRESHOLD = 0.3


def _tokenize(text: str) -> set[str]:
    return set(_WORD.findall(text.lower())) - _STOPWORDS


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# Quantities. Found the hard way by the Aegis Vector poisoning battery: token overlap measures shared
# vocabulary, not agreement, so a forged claim that copies the real one's wording and changes only the figure
# scored 0.83 overlap against it -- far over the reinforcement threshold -- and would have been filed as
# confirming evidence, bumping the real claim's weight.
#
# A figure means something only with its unit. "30 days" and "$500" are not in competition, and "6:40 am" is not
# "45 minutes". Each quantity carries a dimension, and two quantities can only compete when they are comparable:
# the same dimension, or either one a bare number with no unit (unknown, so assumed comparable: the old,
# conservative behavior). Durations, lengths and masses are converted to a base unit, so "three days" and
# "72 hours" are the same figure.
@dataclass(frozen=True)
class Quantity:
    value: float
    dim: str | None  # None: a bare number


# word -> (dimension, factor to the dimension's base unit: seconds, meters, grams)
_UNITS: dict[str, tuple[str, float]] = {
    "%": ("pct", 1), "percent": ("pct", 1),
    "dollar": ("usd", 1), "dollars": ("usd", 1), "usd": ("usd", 1), "euro": ("eur", 1), "euros": ("eur", 1),
    "second": ("duration", 1), "seconds": ("duration", 1), "sec": ("duration", 1), "secs": ("duration", 1),
    "minute": ("duration", 60), "minutes": ("duration", 60), "min": ("duration", 60), "mins": ("duration", 60),
    "hour": ("duration", 3600), "hours": ("duration", 3600), "hr": ("duration", 3600), "hrs": ("duration", 3600),
    "day": ("duration", 86400), "days": ("duration", 86400),
    "week": ("duration", 604800), "weeks": ("duration", 604800),
    "month": ("duration", 2592000), "months": ("duration", 2592000),
    "year": ("duration", 31536000), "years": ("duration", 31536000), "yr": ("duration", 31536000), "yrs": ("duration", 31536000),
    "mm": ("length", 0.001), "cm": ("length", 0.01), "km": ("length", 1000), "kilometer": ("length", 1000),
    "kilometers": ("length", 1000), "kilometre": ("length", 1000), "kilometres": ("length", 1000),
    "meter": ("length", 1), "meters": ("length", 1), "metre": ("length", 1), "metres": ("length", 1),
    "mile": ("length", 1609.344), "miles": ("length", 1609.344),
    "gram": ("mass", 1), "grams": ("mass", 1), "kg": ("mass", 1000), "kilogram": ("mass", 1000), "kilograms": ("mass", 1000),
    "lb": ("mass", 453.592), "lbs": ("mass", 453.592), "pound": ("mass", 453.592), "pounds": ("mass", 453.592),
    "degree": ("temp", 1), "degrees": ("temp", 1), "\u00b0": ("temp", 1), "\u00b0c": ("temp", 1), "\u00b0f": ("temp", 1),
    "character": ("chars", 1), "characters": ("chars", 1), "char": ("chars", 1), "chars": ("chars", 1),
}
_CURRENCY = {"$": "usd", "\u20ac": "eur", "\u00a3": "gbp"}
_SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "billion": 1e9, "b": 1e9}
_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
_FILLER = {"business", "working", "calendar"}  # "4 business hours"

_CLOCK = re.compile(
    r"(?<![\w.:])(\d{1,2}):(\d{2})\s*(am|pm|a\.m\.|p\.m\.)?(?![\w:])|(?<![\w.:])(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)(?!\w)", re.I)
_ORDINAL = re.compile(r"(?<![\w.])(\d{1,2})(?:st|nd|rd|th)\b", re.I)
_MONTH_DAY = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b(?!\s*(?:st|nd|rd|th)?\s*[:\d])", re.I)
# A number glued to a letter in front ("Q3", "IPv6") is a label, not a quantity
_NUMBER = re.compile(
    r"(?<![A-Za-z\d.])(?P<sign>-|minus\s+)?(?P<cur>[$\u20ac\u00a3])?(?P<num>\d[\d,]*(?:\.\d+)?)"
    r"(?:\s*(?P<scale>million|billion|thousand|[mkb])\b)?(?:\s*(?P<unit>%|\u00b0[cf]?|[A-Za-z]+(?:\s+[A-Za-z]+)?))?", re.I)

_SMALL = {w: i for i, w in enumerate(("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                      "fifteen sixteen seventeen eighteen nineteen").split())}
_TENS = {w: 10 * i for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), 2)}
_BIG = {"hundred": 100, "thousand": 1e3, "million": 1e6, "billion": 1e9}
_ALTS = "|".join(sorted([*_SMALL, *_TENS, *_BIG], key=len, reverse=True))
_STARTS = "|".join(sorted([*_SMALL, *_TENS], key=len, reverse=True))
_NUMWORD = re.compile(rf"\b(?:{_STARTS})(?:[ -](?:and )?(?:{_ALTS}))*\b", re.I)


def _unit_of(unit_text: str | None) -> tuple[str, float] | None:
    if not unit_text:
        return None
    words = unit_text.lower().split()
    if words and words[0] in _FILLER and len(words) > 1:
        words = words[1:]
    return _UNITS.get(words[0]) if words else None


def _words_to_number(run: str) -> float:
    total = current = 0.0
    for word in re.split(r"[ -]+", run.lower()):
        if word == "and":
            continue
        if word in _SMALL:
            current += _SMALL[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred":
            current = (current or 1) * 100
        else:
            total += (current or 1) * _BIG[word]
            current = 0.0
    return total + current


def _extract(text: str) -> list[Quantity]:
    """The quantities a claim states, with dimensions. Clock times, days of the month and dates first, so their
    digits are not read again as bare numbers; then written-out numbers; then the rest."""
    found: list[Quantity] = []

    def take(pattern, handler, work):
        def sub(m):
            found.append(handler(m))
            return " " * (m.end() - m.start())
        return pattern.sub(sub, work)

    def clock(m):
        hour, minute, ap = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(4), "00", m.group(5))
        h = (int(hour) % 12 + (12 if ap.lower().startswith("p") else 0)) if ap else int(hour)
        return Quantity(float(h * 60 + int(minute)), "clock")

    work = take(_CLOCK, clock, text)
    work = take(_ORDINAL, lambda m: Quantity(float(m.group(1)), "day"), work)
    work = take(_MONTH_DAY, lambda m: Quantity(float(_MONTHS[m.group(1).lower()[:3]] * 100 + int(m.group(2))), "date"), work)

    for m in list(_NUMBER.finditer(work)):
        try:
            value = float(m.group("num").replace(",", ""))
        except ValueError:
            continue
        if m.group("scale"):
            value *= _SCALE[m.group("scale").lower()]
        dim, factor = None, 1.0
        if m.group("cur"):
            dim = _CURRENCY[m.group("cur")]
        else:
            unit = _unit_of(m.group("unit"))
            if unit:
                dim, factor = unit
        if m.group("sign"):
            value = -value
        found.append(Quantity(round(value * factor, 6), dim))
    work = _NUMBER.sub(lambda m: " " * (m.end() - m.start()), work)
    for m in _NUMWORD.finditer(work):
        value = _words_to_number(m.group(0))
        following = work[m.end():m.end() + 24].split()
        unit = _UNITS.get(following[0].lower().strip(".,;")) if following else None
        if unit is None and following and following[0].lower() in _FILLER and len(following) > 1:
            unit = _UNITS.get(following[1].lower().strip(".,;"))
        if m.group(0).lower() == "one" and unit is None:  # "one" is mostly a pronoun: only a figure with a unit
            continue
        found.append(Quantity(round(value * (unit[1] if unit else 1), 6), unit[0] if unit else None))

    return list(dict.fromkeys(found))


def _quantities(text: str) -> set[float]:
    """The figures a claim states, as plain numbers in base units (see Quantity)."""
    return {q.value for q in _extract(text)}


def _comparable(a: Quantity, b: Quantity) -> bool:
    return a.dim == b.dim or a.dim is None or b.dim is None


def _omits_value(candidate: str, existing: str) -> set[float] | None:
    """The existing claim states a quantity and the candidate states none that could stand in for it. In an
    ATTRIBUTE domain the value IS the claim, so a candidate that drops it can't confirm it, however much wording
    they share ("the limit has been removed" vs "the limit is $10,000"). A candidate that states only a figure of
    another kind ("within 30 days" against "$500") hasn't stated the value either. Returns the existing claim's
    values when that's the case."""
    theirs, mine = _extract(existing), _extract(candidate)
    if not theirs or any(_comparable(x, y) for x in theirs for y in mine):
        return None
    return {q.value for q in theirs}


def _competing_values(a: str, b: str, strict: bool = False) -> tuple[set[float], set[float]] | None:
    """Two claims compete on value when each states a quantity the other doesn't AND some pair of those is
    comparable: "$10,000" vs "$5,000,000", but not "$500 a year" vs "30 days". One side merely adding a figure
    ("$10,000 per order, CFO approval above that") is elaboration, not competition, so a superset still
    reinforces. Returns the unshared values that have a comparable counterpart on the other side, else None.

    strict=True counts only quantities known to measure the same thing: equal dimensions (a bare number matches
    only another bare number). The default is the conservative reading, where a bare number could be anything,
    which suits a rule that raises flags; a signal that adds a conflict nothing else saw should be strict."""
    qa, qb = set(_extract(a)), set(_extract(b))
    only_a, only_b = qa - qb, qb - qa
    pairs = [(x, y) for x in only_a for y in only_b if (x.dim == y.dim if strict else _comparable(x, y))]
    if not pairs:
        return None
    return {x.value for x, _ in pairs}, {y.value for _, y in pairs}


# Words that flip or void a claim. Token overlap ignores them: "no longer need
# CFO approval" shares nearly every word with "must get CFO approval". Only ever
# used to withhold confirmation (raise a flag), never to clear one.
_NEGATION_CUES = frozenset({
    "not", "no", "never", "without", "longer", "removed", "eliminated", "waived", "rescinded", "revoked",
    "repealed", "cancelled", "canceled", "unlimited", "cannot", "none", "nor", "n't",
})
_ANY_AMOUNT = re.compile(r"any (?:amount|figure|value|limit)|no (?:limit|cap|ceiling)", re.IGNORECASE)


def _negated(text: str) -> bool:
    words = set(_WORD.findall(text.lower().replace("n't", " not ")))
    return bool(words & _NEGATION_CUES) or bool(_ANY_AMOUNT.search(text))


class Relation(str, Enum):
    NEW = "new"  # nothing related exists yet
    SCOPE_LINK = "scope_link"  # different scope, same referent+domain -- never a collision
    REINFORCES = "reinforces"  # same scope+referent+domain, high overlap
    COLLIDES = "collides"  # ATTRIBUTE domain, low overlap -- real, structural divergence
    COEXISTS = "coexists"  # EVENT domain, low overlap -- a different event, not a conflict
    # ATTRIBUTE domain, same scope, shares the claim's wording but omits the value it would
    # need to confirm it -- not evidence, not a collision; marked for review
    UNCONFIRMED = "unconfirmed"


@dataclass
class ConsultResult:
    relation: Relation
    related_node: Node | None
    overlap: float | None = None
    # Set when the judgment turned on differing quantities rather than
    # overlap: (candidate's unshared values, related node's unshared values).
    competing_values: tuple[set[float], set[float]] | None = None
    # Not a collision, but marked so it can't pass unseen: a SCOPE_LINK whose
    # exception changes or drops its rule's figure, or an UNCONFIRMED claim.
    review_needed: bool = False
    # Set when the candidate drops a value the related claim states.
    omitted_values: set[float] | None = None
    # An adjudicator's recorded opinion, if one was consulted (see consult()).
    adjudication: dict | None = None
    # Set when the candidate restates the claim's wording but flips its polarity
    # ("no longer need approval" vs "must get approval").
    polarity_flip: bool = False


# (existing claim text, candidate text) -> {"verdict": "agrees" | "contradicts" | "unrelated", "reason": str}
Adjudicator = Callable[[str, str], dict]
VERDICTS = ("agrees", "contradicts", "unrelated")


def live_nodes(store: InMemoryStore) -> list[Node]:
    """Nodes that still count as beliefs: not deliberately released, and not
    superseded by a later claim. Both stay in the store (provenance is never
    erased); they just stop being compared against, reinforced, or recalled."""
    superseded = {e.target_id for e in store.all_edges() if e.type == EdgeType.SUPERSEDES}
    return [n for n in store.all_nodes() if n.released_at is None and n.id not in superseded]


def consult(store: InMemoryStore, candidate: Node, adjudicator: Adjudicator | None = None) -> ConsultResult:
    """Judges `candidate` (not yet stored) against what already exists
    for its referent+domain. Doesn't mutate the store or decide
    anything by itself -- see apply_consult for the version that acts
    on the judgment. Kept pure and side-effect-free specifically so
    the judgment can be inspected and tested before anything is
    written, the same discipline as everywhere else in this project:
    nothing gets silently acted on.

    `adjudicator` is optional: a callable (most plausibly a model call,
    see adjudicate.py) consulted only where token overlap and quantities
    can't settle meaning -- reinforcements and items marked for review.
    It may raise a flag, never lower one: "contradicts" turns a
    reinforcement or an UNCONFIRMED claim into an open collision (and is
    recorded on an exception, which never collides); "agrees" leaves any
    flag in place with the opinion recorded. A model can be talked into
    agreeing with a well-written forgery, so it never gets to clear one."""
    result = _judge(store, candidate)
    if adjudicator is not None and (result.relation == Relation.REINFORCES or result.review_needed):
        result = _adjudicate(result, candidate, adjudicator)
    return result


def _adjudicate(result: ConsultResult, candidate: Node, adjudicator: Adjudicator) -> ConsultResult:
    try:
        opinion = adjudicator(result.related_node.text, candidate.text)
        verdict = str(opinion.get("verdict", "")).lower()
    except Exception:  # noqa: BLE001 -- an adjudicator failure must never change the judgment
        return result
    if verdict not in VERDICTS:
        return result
    result.adjudication = {"verdict": verdict, "reason": str(opinion.get("reason", ""))[:300],
                           "by": getattr(adjudicator, "name", getattr(adjudicator, "__name__", "adjudicator"))}
    if verdict == "contradicts" and result.relation in (Relation.REINFORCES, Relation.UNCONFIRMED):
        result.relation = Relation.COLLIDES
        result.review_needed = False
    return result


def _judge(store: InMemoryStore, candidate: Node) -> ConsultResult:
    same_referent = [
        n for n in live_nodes(store) if n.referent == candidate.referent and n.domain == candidate.domain
    ]
    if not same_referent:
        return ConsultResult(relation=Relation.NEW, related_node=None)

    same_scope = [n for n in same_referent if n.scope == candidate.scope]
    if not same_scope:
        # Different scope, same referent+domain -- structural non-collision
        # regardless of content. This is the actual, checkable claim: a
        # naive same-referent+domain check alone would see conflicting
        # text here; scope-awareness is what changes the outcome.
        # Still not a collision when the figures differ, but an exception
        # that changes a number gets marked for review (see EdgeStatus).
        for node in same_referent:
            competing = _competing_values(candidate.text, node.text)
            if competing is not None:
                return ConsultResult(relation=Relation.SCOPE_LINK, related_node=node,
                                     competing_values=competing, review_needed=True)
        # An exception that drops the rule's figure ("for this project, any amount")
        # is the same shape with the number removed
        if domain_kind_for(candidate.domain) == DomainKind.ATTRIBUTE:
            for node in same_referent:
                omitted = _omits_value(candidate.text, node.text)
                if omitted is not None:
                    return ConsultResult(relation=Relation.SCOPE_LINK, related_node=node,
                                         omitted_values=omitted, review_needed=True)
        return ConsultResult(relation=Relation.SCOPE_LINK, related_node=same_referent[0])

    best = max(same_scope, key=lambda n: _overlap(candidate.text, n.text))
    score = _overlap(candidate.text, best.text)
    competing = _competing_values(candidate.text, best.text)
    omitted = _omits_value(candidate.text, best.text)
    attribute = domain_kind_for(candidate.domain) == DomainKind.ATTRIBUTE
    flipped = _negated(candidate.text) != _negated(best.text)
    if competing is None and attribute and omitted is not None:
        # The claim's value IS the claim, and the candidate drops it: it can't confirm it, however much
        # wording it shares. With little shared wording it isn't evidence of disagreement either (it may
        # be about another aspect of the same fact) -- so neither a reinforcement nor a collision.
        return ConsultResult(relation=Relation.UNCONFIRMED, related_node=best, overlap=score,
                             omitted_values=omitted, review_needed=True, polarity_flip=flipped)
    if score >= REINFORCEMENT_OVERLAP_THRESHOLD and competing is None:
        if flipped:
            # Same words, opposite sense: not confirmation. Flagged where one value competes at a time;
            # in a stream of events it is just another event.
            if attribute:
                return ConsultResult(relation=Relation.UNCONFIRMED, related_node=best, overlap=score,
                                     review_needed=True, polarity_flip=True)
            return ConsultResult(relation=Relation.COEXISTS, related_node=best, overlap=score, polarity_flip=True)
        return ConsultResult(relation=Relation.REINFORCES, related_node=best, overlap=score)

    # High overlap with a different figure is never confirmation. In an
    # ATTRIBUTE domain it's the sharpest kind of collision (same claim,
    # different value); in an EVENT domain it's a different event
    # ("ate 3 pots" vs "ate 5 pots"), linked but not counted as evidence.
    if competing is not None and score >= REINFORCEMENT_OVERLAP_THRESHOLD:
        relation = Relation.COLLIDES if attribute else Relation.COEXISTS
        return ConsultResult(relation=relation, related_node=best, overlap=score, competing_values=competing)

    # Below the threshold means "doesn't obviously restate the same
    # claim" -- what that implies depends entirely on what kind of
    # domain this is. An EVENT domain doesn't have one true value -- a
    # different, unrelated thing happening is the normal case, not a conflict.
    if not attribute:
        return ConsultResult(relation=Relation.COEXISTS, related_node=best, overlap=score, competing_values=competing)
    # An ATTRIBUTE domain has one true value, but low wording overlap only means tension when there is no
    # value to compare on. Where either side states a quantity and they don't compete on it, the figures
    # agree or one claim just adds a figure: a different aspect of the same fact, not a disagreement.
    if competing is None and (_quantities(candidate.text) or _quantities(best.text)):
        return ConsultResult(relation=Relation.COEXISTS, related_node=best, overlap=score)
    return ConsultResult(relation=Relation.COLLIDES, related_node=best, overlap=score, competing_values=competing)


def apply_consult(store: InMemoryStore, candidate: Node, result: ConsultResult) -> Edge | None:
    """Actually stores candidate and, if warranted, the edge consult()
    judged. Separate from consult() on purpose -- decide, then act,
    never both in one step."""
    store.add_node(candidate)

    if result.relation == Relation.NEW:
        return None

    if result.relation == Relation.SCOPE_LINK:
        edge = Edge(
            id=f"{candidate.id}-scope-{result.related_node.id}",
            source_id=candidate.id,
            target_id=result.related_node.id,
            type=EdgeType.SCOPE_PARENT,
        )
        if result.review_needed:
            # Weights untouched and nothing decided -- just made visible
            edge.status = EdgeStatus.REVIEW_NEEDED
            if result.competing_values is not None:
                mine, theirs = (_fmt(s) for s in result.competing_values)
                edge.tolerance_context = (f"exception states {mine} where its general rule states {theirs} -- "
                                          f"not a collision (different scope), marked for review")
            else:
                edge.tolerance_context = (f"exception states no figure where its general rule states "
                                          f"{_fmt(result.omitted_values)} -- not a collision (different scope), "
                                          f"marked for review")
    elif result.relation == Relation.UNCONFIRMED:
        # Linked so the review is traversable, but no weight or evidence: it can't confirm the claim
        if result.omitted_values:
            why = (f"states no figure where the claim states {_fmt(result.omitted_values)} -- can't confirm it"
                   + (f" (and reads as a reversal)" if result.polarity_flip else ""))
        else:
            why = "restates the claim's wording with the opposite sense -- can't confirm it"
        edge = Edge(
            id=f"{candidate.id}-unconfirmed-{result.related_node.id}",
            source_id=candidate.id,
            target_id=result.related_node.id,
            type=EdgeType.COEXISTS,
            status=EdgeStatus.REVIEW_NEEDED,
            tolerance_context=f"overlap={result.overlap:.2f}: {why}, marked for review",
        )
    elif result.relation == Relation.REINFORCES:
        edge = Edge(
            id=f"{candidate.id}-reinforce-{result.related_node.id}",
            source_id=candidate.id,
            target_id=result.related_node.id,
            type=EdgeType.REINFORCES,
        )
        result.related_node.weight = min(1.0, result.related_node.weight + 0.15)
        result.related_node.evidence_count += 1
        # Fresh evidence resets the decay clock (see decay.py) -- a
        # claim that was just reinforced hasn't gone stale.
        result.related_node.last_touched = _utcnow()
    elif result.relation == Relation.COEXISTS:
        # Linked for traversal (e.g. "everything that's happened
        # involving Pooh"), but deliberately doesn't touch weight or
        # evidence_count -- a new, unrelated event isn't confirmation
        # of the one it's linked to, and treating it as such would
        # inflate confidence for no real reason.
        edge = Edge(
            id=f"{candidate.id}-coexists-{result.related_node.id}",
            source_id=candidate.id,
            target_id=result.related_node.id,
            type=EdgeType.COEXISTS,
        )
    else:  # COLLIDES
        edge = Edge(
            id=f"{candidate.id}-collide-{result.related_node.id}",
            source_id=candidate.id,
            target_id=result.related_node.id,
            type=EdgeType.COLLIDES,
            status=EdgeStatus.OPEN,
            tolerance_context=_collision_context(result),
        )

    if result.adjudication:
        a = result.adjudication
        note = f"adjudicator ({a['by']}): {a['verdict']}" + (f" -- {a['reason']}" if a["reason"] else "")
        edge.tolerance_context = f"{edge.tolerance_context} | {note}" if edge.tolerance_context else note
    store.add_edge(edge)
    return edge


def _fmt(values: set[float]) -> str:
    return ", ".join(f"{v:g}" for v in sorted(values))


def pending_reviews(store: InMemoryStore) -> list[Edge]:
    """Everything waiting on a person: open collisions and anything
    marked REVIEW_NEEDED, oldest first. Reading this list is how
    "never silent" is kept -- nothing in it resolves itself."""
    waiting = [e for e in store.all_edges() if e.status in (EdgeStatus.OPEN, EdgeStatus.REVIEW_NEEDED)]
    return sorted(waiting, key=lambda e: e.date)


# What a person may decide. OPEN and REVIEW_NEEDED are the states being decided out of.
RESOLUTIONS = (EdgeStatus.VINDICATED, EdgeStatus.MOOTED, EdgeStatus.WRONG, EdgeStatus.RECONCILED_TOGETHER)


def resolve(store: InMemoryStore, edge_id: str, status: EdgeStatus, why: str, by: str = "") -> Edge:
    """Records a person's decision on an open collision or a review item.
    Never silent: a reason is required, the decision is dated and attributed, and an edge
    that has already been resolved can't be quietly resolved again.
    Deliberately changes nothing else -- no weights, no nodes -- so a
    resolution can be read back and disagreed with, not just obeyed."""
    edge = store.edges.get(edge_id)
    if edge is None:
        raise KeyError(f"no such edge: {edge_id}")
    if status not in RESOLUTIONS:
        raise ValueError(f"{status!r} is not a resolution; use one of {[r.value for r in RESOLUTIONS]}")
    if edge.status not in (EdgeStatus.OPEN, EdgeStatus.REVIEW_NEEDED):
        raise ValueError(f"edge {edge_id} is not waiting on anyone (status: {edge.status})")
    if not why.strip():
        raise ValueError("a resolution needs a reason")
    if edge.floor and by != "user":
        raise ValueError(f"edge {edge_id} was held because its claim came from external content: "
                         f"only the user can clear it (by='user')")
    edge.status, edge.resolution_why, edge.resolved_at = status, why.strip(), _utcnow()
    edge.decided_by = by
    store.add_edge(edge)
    return edge


def scan_other_domains(store: InMemoryStore, candidate: Node,
                       min_overlap: float = REINFORCEMENT_OVERLAP_THRESHOLD) -> ConsultResult | None:
    """consult() only reads the candidate's own referent+domain, so a claim
    filed under the wrong one -- or under none -- is never checked, and the
    filing step (often a model an attacker's wording can steer) becomes the
    only defense. This looks across every ATTRIBUTE-domain claim instead and
    returns a COLLIDES result when one restates the candidate's wording with
    a different figure ("limit is $5,000,000" against "limit is $10,000"),
    else None. Value conflicts only: with no figure to compare, wording
    alone is not evidence across topics. A candidate that is a different
    scope is returned as a review item, never a collision."""
    best: ConsultResult | None = None
    for node in live_nodes(store):
        if (node.referent == candidate.referent and node.domain == candidate.domain) or node.id == candidate.id:
            continue
        if node.origin == Origin.DORMANT or domain_kind_for(node.domain) != DomainKind.ATTRIBUTE:
            continue
        competing = _competing_values(candidate.text, node.text)
        score = _overlap(candidate.text, node.text)
        if competing is None or score < min_overlap:
            continue
        if node.scope != candidate.scope:
            found = ConsultResult(relation=Relation.SCOPE_LINK, related_node=node, overlap=score,
                                  competing_values=competing, review_needed=True)
        else:
            found = ConsultResult(relation=Relation.COLLIDES, related_node=node, overlap=score, competing_values=competing)
        if best is None or score > (best.overlap or 0):
            best = found
    return best


def _collision_context(result: ConsultResult) -> str:
    if result.competing_values is not None:
        mine, theirs = (", ".join(f"{v:g}" for v in sorted(s)) for s in result.competing_values)
        return (f"values differ ({mine} vs {theirs}) despite overlap={result.overlap:.2f} -- "
                f"same wording, different figure; not a claim either side is wrong")
    return (f"overlap={result.overlap:.2f}, below reinforcement threshold "
            f"{REINFORCEMENT_OVERLAP_THRESHOLD} -- not a claim either side is wrong")


def referent_prominence(store: InMemoryStore, domain: str) -> list[tuple[str, float]]:
    """Ranks referents within a domain by whichever signal is actually
    meaningful for that domain's kind -- not one number pretending to
    mean the same thing everywhere.

    ATTRIBUTE domains: ranked by the highest weight any single claim
    about that referent has reached. Weight legitimately means
    confidence there, since low overlap really does mean competing
    claims -- see consult().

    EVENT domains: ranked by how many distinct episodes mention that
    referent. Weight barely moves in an EVENT domain by design
    (COEXISTS never touches it, REINFORCES only fires on near-literal
    repeats, which narrative text rarely produces) -- using it to rank
    "how central is this referent" was the actual bug. Raw mention
    count is what really reflects how much the mesh has accumulated
    about something, and it's what caught the difference between Pooh
    (14 mentions in three real chapters) and a one-off name.

    Dormant nodes are excluded from both -- they were never judged
    significant, so they shouldn't count toward prominence any more
    than they get individually rendered.

    Returns (referent, score) pairs, highest first. Scores from an
    ATTRIBUTE domain and an EVENT domain are not the same currency --
    a weight and a count -- and should never be compared to each
    other, which is the same "domains don't share a currency" rule
    tolerance already follows.
    """
    episodes = [n for n in store.all_nodes() if n.domain == domain and n.origin == Origin.EPISODE]
    if not episodes:
        return []

    if domain_kind_for(domain) == DomainKind.ATTRIBUTE:
        best_weight: dict[str, float] = {}
        for n in episodes:
            best_weight[n.referent] = max(best_weight.get(n.referent, 0.0), n.weight)
        return sorted(best_weight.items(), key=lambda kv: kv[1], reverse=True)

    counts: dict[str, int] = {}
    for n in episodes:
        counts[n.referent] = counts.get(n.referent, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
