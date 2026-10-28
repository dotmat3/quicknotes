"""Test end-to-end: avvia il server MCP come farebbe Claude Desktop (stdio) e chiama i tool."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")
from mcp import StdioServerParameters  # noqa: E402

try:
    from mcp import Client  # SDK 2.x
except ImportError:  # pragma: no cover
    Client = None

ROOT = Path(__file__).resolve().parents[1]


def _is_error(result):
    return getattr(result, "is_error", None) or getattr(result, "isError", None)


def _payload(result):
    assert not _is_error(result), result.content
    data = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if data is not None:
        return data["result"] if isinstance(data, dict) and set(data) == {"result"} else data
    return json.loads(result.content[0].text)


@pytest.mark.skipif(Client is None, reason="richiede SDK MCP 2.x")
def test_stdio_roundtrip(tmp_path):
    env = {**os.environ, "QUICKNOTES_DIR": str(tmp_path / "notes"),
           "QUICKNOTES_CONFIG_DIR": str(tmp_path / "cfg"), "PYTHONPATH": str(ROOT)}
    params = StdioServerParameters(command=sys.executable, args=["-m", "quicknotes.mcp_server"],
                                   env=env, cwd=str(tmp_path))

    async def run():
        async with Client(params) as client:
            tools = {t.name for t in (await client.list_tools()).tools}
            assert {"search_notes", "read_note", "list_action_items", "create_note"} <= tools
            prompts = {p.name for p in (await client.list_prompts()).prompts}
            assert "briefing_meeting" in prompts

            created = _payload(await client.call_tool("create_note", {
                "title": "Kickoff Cliente X", "note_type": "meeting", "people": ["Marco"],
                "project": "clientex",
                "content": "- Budget 50k !decisione\n- [ ] @Marco invia preventivo due:2026-10-31\n"}))
            hits = _payload(await client.call_tool("search_notes", {"query": "preventivo"}))
            assert hits[0]["id"] == created["id"]
            note = _payload(await client.call_tool("read_note", {"note_id": created["id"]}))
            assert "preventivo" in note["content"] and note["project"] == "clientex"
            actions = _payload(await client.call_tool("list_action_items", {"owner": "marco"}))
            assert actions[0]["due"] == "2026-10-31"
            decisions = _payload(await client.call_tool("list_decisions", {}))
            assert decisions[0]["text"] == "Budget 50k"
            await client.call_tool("set_action_status", {"note_id": created["id"], "action_text": "preventivo"})
            assert _payload(await client.call_tool("list_action_items", {})) == []
            await client.call_tool("append_to_daily_note", {"text": "Sentito @Anna"})
            daily = _payload(await client.call_tool("read_daily_note", {}))
            assert daily["exists"] and "Sentito @Anna" in daily["content"]
            missing = await client.call_tool("read_note", {"note_id": "non-esiste"})
            assert _is_error(missing)

    asyncio.run(run())
    assert list((tmp_path / "notes").rglob("*kickoff-cliente-x.md"))
