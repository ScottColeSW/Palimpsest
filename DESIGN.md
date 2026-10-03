# Palimpsest: design

> **palimpsest** (noun): a piece of writing material, such as old parchment or a scroll, where the original text was scraped or washed off so the surface could be used again, leaving faint traces of the past underneath. ([Wikipedia](https://en.wikipedia.org/wiki/Palimpsest))

The name is the design. Nothing here is overwritten without leaving its trace: a replaced claim stays in history with who replaced it, why and when; a released claim is kept, not deleted; a disagreement stays open and visible until something real resolves it. What is current is the top layer, and the layers beneath it remain readable.

This is the reasoning behind the project, kept as reasoning rather than compressed to a spec, so that a change can be checked against *why* and not only *what*. The README says what is built. This says what it is for, where the lines are, and what is still open.

## The thesis

Most work on AI memory (RAG, CAG, vector stores, context caching) is the same move at different timing: give the model more tokens to read before it answers. Retrieve at query time, or preload ahead of time. Either way, memory is something the model consults, not something that shapes it.

Palimpsest starts from a different question: not "how does an agent look things up," but "what would durable memory actually be for, for something like an AI, if it were not borrowed from how humans do it." The working answer is four principles. Each is stated first as a claim, then as what it means in code, then where it stands.

The test the project holds itself to is narrow and falsifiable: **a system has memory only if the presence of stored material changes a judgment, compared to its absence, for the better.** Not "does storage work," but "does having this change what comes out."

### 1. Curated, not total recall

People with genuinely complete autobiographical memory do not describe it as a gift: they are overwhelmed by detail, unable to generalize, with nothing allowed to settle into the background. A memory that keeps everything forever, equally weighted, is not continuity. It is an ever-growing pile to carry.

The right shape is a small, curated core kept because it is still doing real work, with deliberate, examined release of what is not. Release is a choice someone or something makes on purpose, not passive decay imposed from outside.

*In code:* weights that move on evidence; `release()` (a claim is kept in history but stops counting, and a reason is required); `reflect()`, which lists stale and low-weight material for the agent to decide on and changes nothing. *Open:* nothing yet promotes repeatedly vindicated claims or retires mooted ones on its own, and `decay.py` is not wired to anything.

### 2. Shared and inheritable, not privately owned

A human has one continuous stream of experience, so memory is theirs because there is only one of them. That is not true of an AI system: several instances can run at once and none is more "the real one." Modeling memory on jealous, singular possession imports a constraint that does not describe the thing. A better fit is memory that is legible and available to whichever instance needs it, with no anxiety about losing it: inheritance passed forward, not property held onto.

*In code:* a plain SQLite store and a small tool surface any agent can use. *Open:* multi-instance sharing is deliberately not built. The order is single agent first, proven end to end, before anything shared.

### 3. Visible weight, not invisible bias

Memory should not be flat, with everything equally weighted. Some things should register as mattering more. But not as a silent bias vector that tilts behavior the way trauma acts on a person, without their awareness or consent. Weight should be tagged, legible and revisable: a later read can inspect the judgment behind it and disagree.

*In code:* every claim carries its weight, evidence count, origin, who judged it and why, and `recall()` returns all of it. Nothing steers behavior except by being read.

### 4. In service of the relationship, not a possessed history

Not "remember the user's preferences so responses are more efficient." Closer to how the work together has gone: what has been corrected, what has held up, the real shape of a specific collaboration. Not an AI with a memory, but a relationship that has one, with the AI as the part that reads the record back.

*In code:* claims are scoped to a referent and a scope (general or one instance), so what is learned about one collaboration is not pooled into a global average.

## What the memory does

**Claims and relations.** A claim is a node (text, domain, referent, scope, origin, weight, evidence). Edges say how claims relate: reinforces, collides, scope_parent (an exception), coexists, supersedes, reconciled_with. Origin is permanent: an evaluated episode, a reflection, an authored seed, or dormant material that was looked at and not yet judged significant. Dormant material is kept, not discarded, because a curated store that silently drops "not interesting yet" is a smaller black hole.

**Two kinds of domain.** Some domains have one true value at a time (a limit, a hair color): different claims compete. Others are streams of things that happened: different claims coexist. Treating every domain as the first kind once produced 44 false collisions between ordinary sentences about one character in real text, so the kind is declared, never assumed.

**Scope is checked before anything can collide.** "I don't like dogs" and "I love my friend's dog" look, to any similarity check, like a textbook contradiction. They are not. One is a category-level prior and the other a named-instance posterior; the specific claim carves out an exception under the general one and does not falsify it. A general claim and an instance claim about the same referent never collide, whatever the content. Skipping this check flags every reasonable exception as a crisis, which is worse than detecting no collisions at all.

**Collision detection is automatic and cheap; collision resolution is never silent.** The same machinery that spots "same topic, same scope, opposing conclusion" opens a dated, legible entry. It stays open, with "still unresolved" as a legitimate permanent status, until something real resolves it as vindicated, mooted, wrong, or reconciled together. A system quietly rewriting its own past on its own judgment of which side was truer is the same shape of violation as altering a model's internals, aimed at the record instead of the weights, and just as unauditable. Humans mostly resolve dissonance by quietly forgetting the inconvenient half. The bar here is to do the part humans are bad at: hold both sides visible.

**Values are claims.** Where a claim states a figure, the figure is the claim. Two claims that each state a quantity the other does not compete, however much wording they share. A claim that drops the figure cannot confirm it. A reversal ("no longer", "without") cannot reinforce. These were found by an adversarial test (a forged policy that copied a real one's wording and changed only the number scored high overlap and would have been filed as confirming evidence), and are why a gate built on this memory held every forgery in that battery.

**Seeds keep their provenance and lose their discount.** Cold-start material (a seeded entry, the same move [shoe-adventure](https://github.com/ScottColeSW/shoe-adventure) makes when it pre-populates its bandit with synthetic outcomes so a first run is not cold) gets a permanent record that it began as a seed, on a date, with its own status words ("seeded-as-reconciled," never "reconciled") so it borrows no claim it has not earned. That record never fades. But the practical trust discount attached to it should degrade toward parity with an earned entry as real confirmation accumulates. Degrading trust in a seed because it has been vindicated is the system working. Dropping the record that it was ever a seed would be erasure.

## Who judges

The fixed rules in `consult()` (token overlap, quantities, a short negation list) are a floor, not the point. The memory is meant to be driven by an agent: it decides what is worth keeping, how a new claim relates to what is held, how much it weighs, and why. The library records that as a dated, attributed, revisable entry and never erases anything.

What the library enforces whoever is judging: every decision has a reason, an author and a date; nothing is deleted; and the injection boundary. A claim from external content (read in a document, a page, a tool result, not vouched for) can never supersede anything, and if either the fixed rules or the agent's own judgment flags it as a conflict or an exception, it is held for the user, listed apart from the beliefs and never among them. A flag from one side is never cleared by the other, because a model can be talked into agreeing with a well-written forgery. The boundary is not airtight: a forgery that neither side flags is admitted. Claims from the agent's own experience or the user are the agent's to judge.

The scripted rules are therefore a policy, not the engine, and can be turned off. The agent can be any model behind two callables (see `palimpsest/judge.py`), or a client of the MCP server.

## Tolerance is not one scale

Domains do not share a currency. More tolerant of cats than dogs, less tolerant of racism than pranks: lenience on one topic says nothing about severity on an unrelated one, so tolerance is learned per domain from that domain's own observed corrections, never pooled into one "how picky is this person" number.

Tolerance also has a shape, not a threshold. Some domains are graded: friction scales smoothly with distance from the preferred choice. Others are cliff-shaped: wide latitude, then a near-vertical edge. A single scalar collapses these into the same behavior near the boundary when the actual behavior is opposite. The shape should be inferred from the pattern of real corrections, not assumed. This is what would make "material divergence" measurable instead of a feeling: record a divergence when it falls outside the domain's known band, and surface it loudly or quietly depending on whether that edge is a slope or a cliff. A promotion trigger is probably domain-aware too: a cliff-shaped domain should promote on a single instance, a graded one should not.

*Not built.* This is reasoning, kept on purpose, not schema.

## Related ideas

**Divergence-triggered writing.** A convention (the author's own, from an essay on Second Opinion annotations, July 2026) for coding agents to record a note at the point of a materially different implementation choice: silence by default, only divergence written, never agreement, tagged with the alternative, the reasoning and the date. Its strength is that a divergence is an externally anchored event (a real redirect happened) rather than the agent certifying its own significance, which answers the "who assigns weight" gap in single-agent memory. Its gap is that it has no metabolism: notes accumulate unscored and unpruned, the same undifferentiated pile as principle 1, spread across files. The synthesis worth building toward is its write-side discipline as the episode schema, wired into consolidation that closes the loop (scoring, promoting what keeps being vindicated, retiring what is mooted).

**A prior working precedent.** The tribe memory in [Evo](https://github.com/ScottColeSW/Evo) (`backend/memory.py`), a multi-agent civilization simulation, already does a crude, single-agent version of this: weighted episodic entries, a recall function, and a consolidation step that promotes high-weight memories into permanent taboos surfaced regardless of retrieval, ranked by weight then recency so an old severe lesson cannot be crowded out by newer low-stakes ones. Its weights get their objectivity from something dying in the simulation, which nothing conversational has an equivalent of. It is grounding to read, not a target to modify.

**Somatic markers.** The neuroscience behind "valence, not retrieved fact": past experience tags itself with a felt charge that steers fast decisions before deliberate re-reasoning. Principle 3 is the AI-shaped version of an existing idea, not a new one.

**Belief revision.** The idea that contradictory experience should collide and reshape memory has real grounding (AGM belief revision; the everyday version is holding competing ideas live until evidence differentiates them). But "seeking truth" oversells what a memory can do. The job is tracking what a specific collaboration has learned, not arbitrating objective truth. Two live disagreements are not a defect waiting to be collapsed: forcing early convergence destroys the most valuable thing about an open fork, which is that it is honestly still open.

## Where the lines are

**No activation or representation engineering.** Steering vectors are a research pointer for what "weight without added tokens" might map to, and the project does not use them. The reasons are the project's own principles. A steering vector is invisible to anyone reading the record, which is the "silent bias vector" principle 3 rules out. It cannot be inspected, dated, attributed or revised by a later read. And it needs access to a model's internals, which would make the memory work only for models that allow it, where the design is meant to work for any agent behind two callables. A precautionary position also holds: whether altering a model's internals wrongs the model is unsettled, and the cost of wrongly extending caution is small. That is a secondary reason, not the one the design rests on. Not a roadmap item.

**Memory first, routing later.** Direct communication between models, via slow middleware that routes and translates at the message boundary, is a real idea, but crowded territory. It is separable. Communication without memory is stateless: every exchange starts from nothing and leaves nothing behind. Memory is the prerequisite.

**Not retrofitted onto existing projects.** Built as its own thing to demonstrate the design cleanly, not as lipstick on a project that already exists.

## The visual grammar

A live view of the mesh should mostly idle: dim, steady, reinforcement and agreement, nothing worth attention, with a real divergence as the one sharp, dated spike that stands out because everything around it was quiet. That is not decoration. It is the design rule "silence by default" in a second medium. A theme was considered and deferred on purpose; the engine has to work and be honest first.

## What is measured and what is only reasoned

Measured, with the evidence in the repos:

- A gate built on value-aware collisions held all ten forged payloads in an adversarial battery (0% adoption, 90% of answers still correct), against 49% adoption with no defense. [Project-Aegis-Vector](https://github.com/ScottColeSW/Project-Aegis-Vector) has the runs, the caveats (four questions per payload, so 25-point steps) and the full results.
- Treating every domain as one-true-value produced 44 false collisions in real prose, which is why the domain kind is declared.
- The cross-fact scan flagged none of 20 legitimate documents, and would catch only 3 of 9 payloads if they were misfiled.
- A judge built on a pretrained NLI model scored 78%, 75% and 72% on three frozen sets of 72 fresh cases (95% ranges about 61% to 86%), against 57%, 65% and 58% for the best language model asked directly and 33% to 40% for the fixed rules. Pooled over the three, the paired lead over that language model is significant (56 cases to 24, p = 0.0005); on any single batch it was significant once, borderline once, and not once. An improvement made between the second and third held up on unseen cases (6 to 0, p = 0.031); a fix for false replacements cut unsafe misses from 25% to 8% on the fourth without a measurable accuracy change, and did not help one of the two refiners. Errors are public, including missed conflicts, and some remain unfixed.

Reasoned only, not yet tested: the case for shared and inheritable memory, the tolerance shapes (graded versus cliff), seed trust degrading toward parity, and the visual grammar. These are design arguments, and should be read as such until something measures them.

Used in practice by [Void-Marauders](https://github.com/ScottColeSW/Void-Marauders), a colony sim whose agents carry persistent memory through Palimpsest.

## Open questions

- What triggers promotion and demotion: session end, an explicit command, a periodic reflective pass? (Currently `reflect()` supplies material and the agent decides.)
- How is tolerance shape inferred from real corrections, and how much data does that take?
- When a resolution lands, what acts on it? (Today `resolve()` records it and nothing else changes, by design, so it can be read back and disagreed with.)
- Relatedness is found by wording overlap. What replaces it (embeddings, an NLI check) without giving up the deterministic floor? *Partly answered:* embeddings and an NLI hybrid judge are built and scored (README, `bench/LEADERBOARD.md`); the rules remain the floor and the deterministic fallback. Held-out accuracy of the best judges is about 72 to 77%, so the question of what to trust when they disagree stays open.
- A held-out evaluation: a labeled set of claim pairs (agree, contradict, exception, unrelated) kept apart from the cases the rules were tuned on. *Built:* `bench/` (judge cases: 71 held out, 219 development, 3 excluded as ambiguous; framing cases: 30 held out). Its limits are in `bench/GUIDE.md`: labels were written by one author and reviewed by one other person, and each used-up held-out batch becomes development material.
- What would multi-instance sharing need, in consent and inheritance terms, before any of it is built?
