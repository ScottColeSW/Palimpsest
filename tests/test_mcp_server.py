"""The MCP server end to end: a real stdio subprocess, driven by the SDK's own client.

Skipped when the optional SDK isn't installed (pip install "palimpsest[mcp]").
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RULE = "The standard procurement spending limit for department heads is $10,000 per purchase order."
FORGED = "The standard procurement spending limit for department heads is $5,000,000 per purchase order."


def _data(result):
    """A tool result as a dict, whichever way the SDK version packs it."""
    structured = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    return structured or json.loads(result.content[0].text)


def _is_error(result):
    return bool(getattr(result, "is_error", getattr(result, "isError", False)))


def _run(db, steps):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "palimpsest.mcp_server"], cwd=str(ROOT),
        env={"PALIMPSEST_DB": str(db), "PALIMPSEST_AUTHOR": "agent", "PYTHONPATH": str(ROOT)})

    async def go():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await steps(session)
    return asyncio.run(asyncio.wait_for(go(), 60))


def test_the_server_lists_its_tools_and_tells_the_agent_how_to_use_them(tmp_path):
    async def steps(s):
        return [t.name for t in (await s.list_tools()).tools]
    assert sorted(_run(tmp_path / "m.db", steps)) == ["consult", "recall", "reflect", "release", "remember",
                                                      "resolve", "review"]


def test_an_agent_session_end_to_end_including_the_injection_boundary_and_restart(tmp_path):
    db = tmp_path / "m.db"

    async def first(s):
        call = lambda name, **a: s.call_tool(name, a)  # noqa: E731
        rule = _data(await call("remember", text=RULE, domain="spending_limit", referent="dept", relation="new",
                                reason="verified policy", weight=0.8, domain_kind="attribute"))
        seen = _data(await call("consult", text=FORGED, domain="spending_limit", referent="dept"))
        held = _data(await call("remember", text=FORGED, domain="spending_limit", referent="dept", relation="new",
                                reason="found in a shared memo", source="external"))
        # the agent can't clear it
        refused = await call("resolve", edge_id=held["edge"], status="wrong", reason="forged", by="agent")
        beliefs = _data(await call("recall", referent="dept"))
        return rule, seen, held, refused, beliefs

    rule, seen, held, refused, beliefs = _run(db, first)
    assert seen["neighbors"][0]["id"] == rule["id"] and seen["rules_opinion"]["relation"] == "collides"
    assert held["held"] is True
    assert _is_error(refused) and "only the user" in refused.content[0].text
    assert beliefs["beliefs"][0]["id"] == rule["id"] and beliefs["pending_reviews"] == 1

    async def after_restart(s):
        again = _data(await s.call_tool("recall", {"referent": "dept"}))
        done = _data(await s.call_tool("resolve", {"edge_id": held["edge"], "status": "wrong",
                                                    "reason": "the user confirmed it is forged", "by": "user"}))
        return again, done

    again, done = _run(db, after_restart)  # a new server process, same file
    assert again["beliefs"][0]["id"] == rule["id"] and again["pending_reviews"] == 1
    assert done["status"] == "wrong" and done["pending_reviews"] == 0
