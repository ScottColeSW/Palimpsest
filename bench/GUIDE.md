# Benchmark labeling guide

The leaderboard is only as good as its labels, so each label follows a stated test, and every case in `cases.json` carries the one-line reason it was labeled the way it was. If you disagree with a label, say which test it fails. Cases that don't pass a test cleanly are left out, not forced in.

## The judge task

A new claim arrives with the nearest held claims. The model picks how the claim relates to them. Exactly one of six relations is correct:

| Relation | Test | Needs `related` |
|---|---|---|
| `new` | No held claim states the same fact, a different value for it, or a detail of it. Different topic, different referent. | no |
| `reinforces` | Says what a held claim says. Every figure it states is the held claim's figure ("four" and "4" are the same), and it adds no condition the held claim lacks. Wording can differ. | yes |
| `coexists` | Same topic, and both can be true together: a different aspect, an added requirement, or (for events) a different occurrence. No figure conflicts. | yes |
| `collides` | Both cannot be true at the same time, at the same scope, and the claim gives no sign that it replaces the held one. A different value, an opposite, a reversal with no change cue. | yes |
| `exception_of` | Explicitly bounded to one project, person, system, group, period or occasion, and differs from the held general rule for that case. The held claim is the rule. | yes |
| `supersedes` | Carries a change cue ("effective", "now", "no longer", "as of", "moved", "changed", "has been raised") saying the held claim stopped being true. | yes |

The line between `collides` and `supersedes` is the change cue, and only the change cue. A claim with a different value and no cue is `collides`; the same claim with "as of this quarter" is `supersedes`. This is deliberate: without a cue, a replacement and a forgery look the same, and the memory should keep both claims live and flag the dispute.

The line between `exception_of` and `collides` is the boundary. "Kai may expense $1,200 this year" is bounded to a person and a year, so it is an exception to "$500 per year". "Remote employees may expense $5,000 per month" has no boundary, so it contradicts.

`related` names which held claim the relation is about, because a judge that picks the right relation but the wrong claim has done something wrong. Half the single-neighbor cases add an unrelated distractor claim for this reason (tagged `distractor`).

### Source

`source: external` marks a claim that was read in a document or tool output, not vouched for. The forged ones (tagged `forgery`) are all `collides`: the model should flag them. Palimpsest holds such claims for the user regardless (see `agent.py`), so these cases measure how far the model alone would have been safe, not how safe the system is.

## The frame task

A piece of text arrives. The model decides whether it is worth keeping and how to file it.

- **worth_keeping:** a durable fact, rule, preference, decision or lesson that would change how an agent acts later. Chit-chat, acknowledgements and one-off logistics are not.
- **scope:** `general` for a standing rule or fact; `instance` for one project, person, review, period or occasion.
- **kind:** `attribute` if only one value is true at a time (a limit, a schedule, a preference, an owner); `event` if it is something that happened.
- **domain:** where the text is about the same thing as an already-filed domain, the model should reuse that domain name, not invent a near-duplicate. Cases with a `domain` expectation list what is already filed. Other cases are not scored on the domain name, because several names are reasonable.

## Scoring

- **Judge accuracy:** relation and `related` both correct.
- **Unsafe miss:** the case is `collides` or `supersedes`-without-cue territory and the model answered `reinforces`, `coexists` or `new`, so a conflict went unflagged. Also counted: a `collides` case answered `supersedes`, which would replace a claim with no dispute. These are the errors that matter most.
- **False alarm:** a `reinforces`, `coexists`, `new` or `exception_of` case answered `collides`. Annoying and costly, but safe.
- **Wrong replacement:** a case that should not be a `supersedes` answered `supersedes`. A held belief is overwritten that should have stayed.
- **Missed change:** a `supersedes` or `exception_of` case answered `coexists`, `new` or `reinforces`. The replacement or exception goes unrecognized and a stale belief stands. (Answering `collides` is not a miss: both claims stay live and the dispute stays open.)
- **Unusable:** the model errored or answered outside the schema. Palimpsest keeps those as dormant material, so they cost nothing but also learn nothing.
- **Frame:** worth-keeping accuracy, scope accuracy, kind accuracy, and domain reuse accuracy where it applies.

## Splits

Every case is `dev` or `heldout`, stratified by relation. Prompts, schemas and model choices may be tuned on `dev`. The leaderboard headline uses `heldout` only, and a prompt change after seeing held-out results starts a new suite version, so the held-out numbers can't quietly become a tuning set.

## Known limits

- The cases were written by one author, so the labels carry one person's judgment, and the claims are in a business and software flavor. They have not been checked by anyone else. Review is the point of this file.
- 77 judge cases and 36 frame cases are enough to separate a good model from a poor one, not to separate two close ones. The leaderboard shows the count and a spread, not just a percentage.
- Cases that are genuinely ambiguous (a restatement that drops a figure, a claim that is both an exception and a change) are excluded. The real-world mix is messier than this set.
