# Palimpsest

[![License](https://img.shields.io/github/license/ScottColeSW/Palimpsest)](LICENSE)
[![Latest Release](https://img.shields.io/github/v/release/ScottColeSW/Palimpsest)](https://github.com/ScottColeSW/Palimpsest/releases/latest)

Curated, visibly-weighted, relationship-scoped memory for AI agents — built to be read back and let a new claim change, not just retrieved as more tokens to skim before answering.

A palimpsest is a surface written on repeatedly, where earlier layers stay faintly present beneath the new rather than being fully erased. That's the shape this aims for: curated, not total recall; weight that stays legible instead of vanishing; a record that gets written into over time rather than replayed whole every time.

Palimpsest at work as an ingestion gate, holding a forged policy out of a RAG pipeline: [demo video](https://youtu.be/dSOA-ScmUwY) (from [Aegis Vector](https://github.com/ScottColeSW/Project-Aegis-Vector)).

## Why this isn't RAG with extra steps

RAG retrieves relevant text at query time. CAG preloads a corpus ahead of time. Both are still "hand the model more tokens to read before it answers" — memory as something *consulted*, not something that *shapes* an outcome. Palimpsest's actual claim is narrower and more falsifiable: a system only counts as having memory if the presence of stored material changes a judgment, compared to its absence, for the better. Everything here is built and tested against that bar specifically — not "does storage work," but "does having this actually change what comes out."

## What's actually built right now

This is early and honest about it. Current state:

- **`palimpsest/models.py`** — the schema: `Node` (a conclusion, with domain/referent/scope/origin/weight) and `Edge` (a typed relationship — reinforces, collides, scope_parent, coexists, reconciled_with). `Origin` distinguishes an evaluated episode from a private reflection, an authored seed placeholder, and dormant material that was looked at and not yet judged significant — kept, not discarded. `DomainKind` distinguishes attribute-like domains (one true value competes at a time, e.g. a character's hair color) from event-like domains (many compatible things can be true at once, e.g. a narrative) — collision detection means something different in each.
- **`palimpsest/traversal.py`** — multi-hop graph walking (`walk`, `trace_chain`) over an `EdgeLookup` protocol, so it doesn't care whether the backing store is Elasticsearch or a plain dict.
- **`palimpsest/store.py`** — an Elasticsearch-backed store implementing that protocol, plus domain-scoped kNN similarity search. **Unverified** — written against the documented client API, never run against a live cluster.
- **`palimpsest/memory_store.py`** — an in-memory store implementing the same protocol. What every demo below actually runs on.
- **`palimpsest/ingest.py`** — fixed-size chunking and a placeholder significance classifier. Every chunk becomes something (`EPISODE` or `DORMANT`), never nothing — a curated store that silently drops "not interesting yet" material is just a smaller blackhole.
- **`palimpsest/consult.py`** — the actual memory boundary. Given a new candidate claim, checks it against what's already in the mesh and returns a real judgment: `NEW`, `REINFORCES`, `COLLIDES`, `COEXISTS`, or `SCOPE_LINK` (a general claim and a specific instance of it are never treated as competing, regardless of content — see `demo_scenario.py`'s Marcus example). Collisions are value-aware: two claims that each state a quantity the other doesn't (`$10,000` vs `$5,000,000`) are never counted as reinforcement, however much wording they share, because token overlap measures vocabulary, not agreement. Found by [Aegis Vector](https://github.com/ScottColeSW/Project-Aegis-Vector)'s poisoning battery, where a forged policy that copied the real one's wording scored 0.83 overlap and would otherwise have been filed as confirming evidence. A specific exception still never collides with its general rule, but an exception that states a different figure ("for this one project, up to $5,000,000") is marked `REVIEW_NEEDED` on its scope edge instead of passing unseen; `pending_reviews()` lists everything waiting on a person, open collisions included. A claim that shares a fact's wording but drops its value ("the limit has been removed" against "the limit is $10,000") can't confirm it: it's `UNCONFIRMED` and marked for review instead of reinforcing. Where token overlap and quantities can't settle meaning, `consult()` accepts an optional adjudicator (`palimpsest/adjudicate.py` has a local Ollama one, qwen2.5:3b by default) under one rule: a model may raise a flag, never lower one. "Contradicts" escalates a reinforcement or an unconfirmed claim to an open collision; "agrees" leaves every flag in place, with the opinion recorded. Low word overlap alone is no longer read as disagreement where figures are involved: two claims that don't compete on a figure are a different aspect of the same fact (`COEXISTS`), and a claim that drops the figure at low overlap is `UNCONFIRMED`, not an asserted collision; a collision still needs a different figure or, in a figureless attribute like hair color, differing wording. A claim that restates a rule's wording with the opposite sense ("no longer need approval", "without", "any amount") can't reinforce it: `UNCONFIRMED` and marked for review (in an event domain, just another event). `resolve()` is how a person closes an open collision or review item (vindicated, mooted, wrong, reconciled together): a reason is required, the decision is dated, nothing else changes (no weights), and a resolved edge can't be quietly resolved again. `scan_other_domains()` checks a claim against every attribute-domain claim, not just its own referent, so a document the filing step misplaced (or that an attacker's wording steered elsewhere) is still caught when it restates a known claim with a different figure. Also `referent_prominence()`, which ranks by the signal that's actually meaningful per domain kind — weight for attribute domains, mention count for event domains, never the same currency across both.
- **`palimpsest/pipeline.py`** — wires ingestion into consultation, so real digested text actually gets judged against the mesh instead of dropped in as isolated nodes.

## Use it as an agent's memory (MCP server)

The rules in `consult()` are a floor, not the point. Palimpsest is meant to be driven by the agent: the agent decides what is worth keeping, how a new claim relates to what is held (new, reinforces, coexists, collides, exception, supersedes), how much it weighs, and why. The library records that as a dated, attributed, revisable entry, and never erases anything.

```bash
pip install "palimpsest[mcp]"
```

```json
{
  "mcpServers": {
    "palimpsest": {
      "command": "palimpsest-mcp",
      "env": { "PALIMPSEST_DB": "~/.palimpsest/memory.db", "PALIMPSEST_AUTHOR": "claude" }
    }
  }
}
```

Seven tools: `consult` (read-only: the nearest held claims, plus the fixed rules' opinion as advice), `remember` (record a claim with your own judgment and a required reason), `recall` (what is believed now, with weight and open disputes visible), `review`, `resolve`, `release` (deliberately let go of a claim; it stays in history), and `reflect` (stale and low-weight material for a reflective pass; changes nothing). Memory persists in SQLite. The same operations are available in Python as `palimpsest.Memory`.

What the library enforces whatever the agent says: every decision has a reason, an author and a date; nothing is deleted; and the injection boundary. A claim the agent marks `source="external"` (read in a document or tool output, not vouched for) can never supersede anything, and if the fixed rules would hold it, it is held for the user however the agent judged it, because a model can be talked into agreeing with a well-written forgery. Only a resolution with `by="user"` clears it. That floor is a policy: `PALIMPSEST_FLOOR=0` turns it off.

## Three demos, each honest about what's real

```bash
git clone https://github.com/ScottColeSW/Palimpsest.git
cd Palimpsest
pip install -e ".[dev]"
python -m uvicorn server:app --port 8420
```

Then open:

- **`/`** — a scripted collision walkthrough (seed → reinforce → scope non-collision → collision opens → reconciled). Hand-authored fiction, on purpose: the placeholder classifier can detect significance, not semantic contradiction, so this is the only way to show the full resolution lifecycle end to end right now.
- **`/ingest.html`** — real digestion against actual public-domain text (`palimpsest/story_files/`, from [gutenberg.org](https://www.gutenberg.org/)), one fixed-size chunk per tick. Referent clusters and a live prominence ranking form from real prose, edges and all.
- **`/real-collision.html`** — two *real* quoted collisions, not invented ones: actual sentences from Winnie-the-Pooh, run through the real `consult()` logic and both genuinely flagged `COLLIDES` by the token-overlap math — verified before the page existed, not tuned after to look right.

## Known limitations, stated plainly

- The significance classifier (`ingest.py`) is a capitalization/position heuristic, not language understanding. It's wrong in known, documented ways (real prose testing found and partially fixed this — see commit history).
- `store.py`'s Elasticsearch backend has never touched a live cluster.
- `scan_other_domains()` only catches a misfiled claim that shares enough wording with a known one (overlap 0.3) and states a different figure. A claim about a fact the memory doesn't hold at all has nothing to collide with, and is admitted: memory can't contradict what it doesn't track.
- Negation is a short cue list ("no longer", "without", "any amount", ...), not language understanding. It only withholds confirmation, never clears a flag, but it will miss a reversal worded without those cues; that is what the optional adjudicator is for.
- `resolve()` records a person's decision. Nothing yet acts on one (a vindicated claim doesn't supersede the old one automatically), by design.
- The MCP server is tested end to end with the SDK's own client (mcp 1.x and 2.x), not yet with a live agent working over time. Which claims `consult` shows as neighbors is still found by wording overlap, so a related claim phrased very differently can be missed; embeddings would fix that.
- `by="user"` is honor system at the tool level: the server can't tell the user from an agent that claims to be. The real check is the host's permission prompt on the `resolve` call.
- The domain registry (attribute or event) is process-wide, not per store.
- Collision *detection* is real; collision *resolution* is recorded by a person (`resolve()`), never decided — nothing yet decides on its own that an open collision should become vindicated, mooted, or reconciled.
- Deliberately single-agent, no multi-instance memory sharing, no cross-model anything, and no activation/representation-engineering approaches — the last one isn't a capability gap, it's a boundary held on purpose.

## Tests

```bash
pytest
```

131 passing as of this writing (129 without the optional MCP SDK), several of them written specifically to prove "memory present changes the outcome vs. memory absent" rather than just "storage works."

## License

MIT — see [LICENSE](LICENSE).
