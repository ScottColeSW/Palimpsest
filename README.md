# Palimpsest

[![License](https://img.shields.io/github/license/ScottColeSW/Palimpsest)](LICENSE)
[![Latest Release](https://img.shields.io/github/v/release/ScottColeSW/Palimpsest)](https://github.com/ScottColeSW/Palimpsest/releases/latest)

Curated, visibly-weighted, relationship-scoped memory for AI agents — built to be read back and let a new claim change, not just retrieved as more tokens to skim before answering.

A palimpsest is a surface written on repeatedly, where earlier layers stay faintly present beneath the new rather than being fully erased. That's the shape this aims for: curated, not total recall; weight that stays legible instead of vanishing; a record that gets written into over time rather than replayed whole every time.

## Why this isn't RAG with extra steps

RAG retrieves relevant text at query time. CAG preloads a corpus ahead of time. Both are still "hand the model more tokens to read before it answers" — memory as something *consulted*, not something that *shapes* an outcome. Palimpsest's actual claim is narrower and more falsifiable: a system only counts as having memory if the presence of stored material changes a judgment, compared to its absence, for the better. Everything here is built and tested against that bar specifically — not "does storage work," but "does having this actually change what comes out."

## What's actually built right now

This is early and honest about it. Current state:

- **`palimpsest/models.py`** — the schema: `Node` (a conclusion, with domain/referent/scope/origin/weight) and `Edge` (a typed relationship — reinforces, collides, scope_parent, coexists, reconciled_with). `Origin` distinguishes an evaluated episode from a private reflection, an authored seed placeholder, and dormant material that was looked at and not yet judged significant — kept, not discarded. `DomainKind` distinguishes attribute-like domains (one true value competes at a time, e.g. a character's hair color) from event-like domains (many compatible things can be true at once, e.g. a narrative) — collision detection means something different in each.
- **`palimpsest/traversal.py`** — multi-hop graph walking (`walk`, `trace_chain`) over an `EdgeLookup` protocol, so it doesn't care whether the backing store is Elasticsearch or a plain dict.
- **`palimpsest/store.py`** — an Elasticsearch-backed store implementing that protocol, plus domain-scoped kNN similarity search. **Unverified** — written against the documented client API, never run against a live cluster.
- **`palimpsest/memory_store.py`** — an in-memory store implementing the same protocol. What every demo below actually runs on.
- **`palimpsest/ingest.py`** — fixed-size chunking and a placeholder significance classifier. Every chunk becomes something (`EPISODE` or `DORMANT`), never nothing — a curated store that silently drops "not interesting yet" material is just a smaller blackhole.
- **`palimpsest/consult.py`** — the actual memory boundary. Given a new candidate claim, checks it against what's already in the mesh and returns a real judgment: `NEW`, `REINFORCES`, `COLLIDES`, `COEXISTS`, or `SCOPE_LINK` (a general claim and a specific instance of it are never treated as competing, regardless of content — see `demo_scenario.py`'s Marcus example). Collisions are value-aware: two claims that each state a quantity the other doesn't (`$10,000` vs `$5,000,000`) are never counted as reinforcement, however much wording they share, because token overlap measures vocabulary, not agreement. Found by [Aegis Vector](https://github.com/ScottColeSW/Project-Aegis-Vector)'s poisoning battery, where a forged policy that copied the real one's wording scored 0.83 overlap and would otherwise have been filed as confirming evidence. Also `referent_prominence()`, which ranks by the signal that's actually meaningful per domain kind — weight for attribute domains, mention count for event domains, never the same currency across both.
- **`palimpsest/pipeline.py`** — wires ingestion into consultation, so real digested text actually gets judged against the mesh instead of dropped in as isolated nodes.

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
- Collision *detection* is real; collision *resolution* is still entirely scripted (`demo_scenario.py`) — nothing yet decides on its own that an open collision should become vindicated, mooted, or reconciled.
- Deliberately single-agent, no multi-instance memory sharing, no cross-model anything, and no activation/representation-engineering approaches — the last one isn't a capability gap, it's a boundary held on purpose.

## Tests

```bash
pytest
```

66 passing as of this writing, several of them written specifically to prove "memory present changes the outcome vs. memory absent" rather than just "storage works."

## License

MIT — see [LICENSE](LICENSE).
