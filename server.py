"""Local demo server -- serves the live mesh dashboard and the scripted
scenario from palimpsest/demo_scenario.py. In-memory only, no ES
required. Run with:

    uvicorn server:app --reload --port 8420

then open http://127.0.0.1:8420/
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from palimpsest.demo_scenario import Scenario

app = FastAPI(title="Palimpsest demo")
scenario = Scenario()

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


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
