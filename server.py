"""Local demo server -- serves two things.

/            the scripted collision-narrative demo (demo_scenario.py)
             -- hand-authored, because the placeholder classifier has
             no way to detect semantic contradiction, only
             significance. Proves scope/collision/resolution work.
/ingest.html real fixed-size digestion running against an actual
             Gutenberg book (ingest.py). Proves the EPISODE/DORMANT
             split holds up against real prose, not scripted fiction.

Both in-memory only, no ES required. Run with:

    uvicorn server:app --reload --port 8420

then open http://127.0.0.1:8420/
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from palimpsest.demo_scenario import Scenario
from palimpsest.ingest import Intake, digest_next_chunk
from palimpsest.memory_store import InMemoryStore

app = FastAPI(title="Palimpsest demo")
scenario = Scenario()

STATIC_DIR = Path(__file__).parent / "static"
STORY_DIR = Path(__file__).parent / "palimpsest" / "story_files"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _load_chapter_one(filename: str) -> str:
    """Winnie-the-Pooh and The Box-Car Children both start their real
    narrative well after a Project Gutenberg license header -- find
    the first "CHAPTER" marker and start there, so digestion runs
    against the story instead of licensing boilerplate."""
    text = (STORY_DIR / filename).read_text(encoding="utf-8")
    marker = text.find("CHAPTER")
    start = marker if marker != -1 else 0
    # Stop at the second CHAPTER heading (start of ch. 2) if findable,
    # so the demo stays a readable single chapter, not a whole book.
    second = text.find("CHAPTER", start + 20)
    end = second if second != -1 else min(len(text), start + 15000)
    return text[start:end]


BOOK_FILE = "winnie-the-pooh.txt"
CHUNK_SIZE = 300

ingest_store = InMemoryStore()
intake = Intake(id="book", raw_text=_load_chapter_one(BOOK_FILE), chunk_size=CHUNK_SIZE, domain="story")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/ingest.html")
def ingest_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "ingest.html")


@app.get("/state")
def get_state() -> dict:
    return scenario.state()


@app.post("/tick")
def tick() -> dict:
    result = scenario.advance()
    return {
        "tick": result.tick,
        "description": result.description,
        "done": result.done,
        "kind": result.kind,
        "state": scenario.state(),
    }


@app.post("/reset")
def reset() -> dict:
    global scenario
    scenario = Scenario()
    return scenario.state()


def _ingest_node_json(n) -> dict:
    return {
        "id": n.id,
        "text": n.text,
        "domain": n.domain,
        "referent": n.referent,
        "origin": n.origin.value,
        "weight": round(n.weight, 3),
    }


def _ingest_state() -> dict:
    return {
        "book": BOOK_FILE,
        "chunk_size": CHUNK_SIZE,
        "percent_digested": round(intake.percent_digested, 3),
        "fully_digested": intake.fully_digested,
        "nodes": [_ingest_node_json(n) for n in ingest_store.all_nodes()],
    }


@app.get("/ingest/state")
def get_ingest_state() -> dict:
    return _ingest_state()


@app.post("/ingest/tick")
def ingest_tick() -> dict:
    result = digest_next_chunk(intake, ingest_store)
    if result is None:
        return {"done": True, "node": None, "state": _ingest_state()}
    return {
        "done": result.done,
        "node": _ingest_node_json(result.node),
        "state": _ingest_state(),
    }


@app.post("/ingest/reset")
def ingest_reset() -> dict:
    global ingest_store, intake
    ingest_store = InMemoryStore()
    intake = Intake(id="book", raw_text=_load_chapter_one(BOOK_FILE), chunk_size=CHUNK_SIZE, domain="story")
    return _ingest_state()
