"""Avvia il server MCP come farebbe Claude e usa tutti gli strumenti."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Client:
    def __init__(self, folder: Path):
        env = {**os.environ, "QUICKNOTES_DIR": str(folder / "notes"), "QUICKNOTES_CONFIG_DIR": str(folder / "cfg"),
               "PYTHONPATH": str(ROOT)}
        self.proc = subprocess.Popen([sys.executable, "-m", "quicknotes", "mcp"], cwd=ROOT, env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.next = 1

    def write(self, msg: dict) -> None:
        self.proc.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode())
        self.proc.stdin.flush()

    def send(self, method: str, params: dict) -> dict:
        msg_id = self.next
        self.next += 1
        self.write({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params})
        reply = json.loads(self.proc.stdout.readline().decode("utf-8"))
        assert reply["id"] == msg_id
        return reply

    def call(self, name: str, args: dict):
        r = self.send("tools/call", {"name": name, "arguments": args})
        assert r["result"]["isError"] is False, r
        return json.loads(r["result"]["content"][0]["text"])

    def close(self) -> None:
        self.proc.kill()
        self.proc.wait()
        self.proc.stdin.close()
        self.proc.stdout.close()


class Mcp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.c = Client(Path(self.tmp.name))

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_tutti_gli_strumenti(self):
        c = self.c
        init = c.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
        self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(init["result"]["serverInfo"]["name"], "quicknotes")
        c.write({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(c.send("ping", {})["result"], {})
        self.assertEqual(len(c.send("tools/list", {})["result"]["tools"]), 12)

        created = c.call("create_note", {"title": "Riepilogo budget",
                                         "content": "- [ ] @Marco manda il foglio due:2026-11-06\n- Tre tranche !decisione\n",
                                         "people": ["Marco"], "project": "clientex", "tags": ["lavoro"]})
        note_id = created["id"]
        self.assertEqual(c.call("search_notes", {"query": "tranche"})[0]["id"], note_id)
        self.assertEqual(len(c.call("list_notes", {"project": "clientex"})), 1)
        self.assertIn("Tre tranche", c.call("read_note", {"note_id": note_id})["content"])
        self.assertEqual(c.call("list_action_items", {"owner": "marco"})[0]["due"], "2026-11-06")
        self.assertEqual(c.call("list_decisions", {"query": "tranche"})[0]["text"], "Tre tranche")
        self.assertEqual(c.call("list_people_and_projects", {})["people"][0]["name"], "Marco")

        done = c.call("set_action_status", {"note_id": note_id, "action_text": "foglio"})
        self.assertTrue(done["done"])
        self.assertIn("done:", done["text"], "il tool MCP scrive anche la data")
        self.assertEqual(c.call("list_action_items", {}), [])

        c.call("append_to_note", {"note_id": note_id, "text": "Vedi [[Altra]]", "heading": "Dopo"})
        daily = c.call("append_to_daily_note", {"text": f"Rivisto [[{note_id}|Riepilogo]] con è e «»"})
        self.assertEqual(c.call("get_backlinks", {"note_id": note_id})[0]["note_id"], daily["id"])
        self.assertTrue(c.call("read_daily_note", {})["exists"])
        self.assertIn("con è e «»", c.call("read_daily_note", {})["content"], "UTF-8 in entrata e in uscita")
        self.assertFalse(c.call("read_daily_note", {"date": "2001-01-01"})["exists"])

        missing = c.send("tools/call", {"name": "read_note", "arguments": {"note_id": "assente"}})
        self.assertTrue(missing["result"]["isError"])
        self.assertEqual(c.send("tools/call", {"name": "boh"})["error"]["code"], -32602)
        self.assertEqual(c.send("metodo/assente", {})["error"]["code"], -32601)

    def test_prompt(self):
        c = self.c
        self.assertEqual(len(c.send("prompts/list", {})["result"]["prompts"]), 2)
        p = c.send("prompts/get", {"name": "riepilogo_settimanale", "arguments": {"settimana_che_inizia": "2026-11-02"}})
        self.assertIn("dal 2026-11-02 al 2026-11-08", p["result"]["messages"][0]["content"]["text"])
        b = c.send("prompts/get", {"name": "briefing_meeting", "arguments": {"persona_o_progetto": "Laura"}})
        self.assertIn("«Laura»", b["result"]["messages"][0]["content"]["text"])
        self.assertEqual(c.send("prompts/get", {"name": "briefing_meeting"})["error"]["code"], -32602)


if __name__ == "__main__":
    unittest.main()
