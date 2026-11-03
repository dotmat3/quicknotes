//! Avvia il server come farebbe Claude e usa tutti gli strumenti.

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};

use serde_json::{json, Value};

struct Client {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
    next: i64,
}

impl Client {
    fn start(dir: &std::path::Path) -> Self {
        let mut child = Command::new(env!("CARGO_BIN_EXE_quicknotes-mcp"))
            .env("QUICKNOTES_DIR", dir.join("notes"))
            .env("QUICKNOTES_CONFIG_DIR", dir.join("cfg"))
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let stdin = child.stdin.take().unwrap();
        let stdout = BufReader::new(child.stdout.take().unwrap());
        Self { child, stdin, stdout, next: 1 }
    }

    fn send(&mut self, method: &str, params: Value) -> Value {
        let id = self.next;
        self.next += 1;
        writeln!(self.stdin, "{}", json!({"jsonrpc": "2.0", "id": id, "method": method, "params": params})).unwrap();
        let mut line = String::new();
        self.stdout.read_line(&mut line).unwrap();
        let v: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(v["id"], id);
        v
    }

    fn call(&mut self, name: &str, args: Value) -> Value {
        let r = self.send("tools/call", json!({"name": name, "arguments": args}));
        assert_eq!(r["result"]["isError"], false, "{r}");
        serde_json::from_str(r["result"]["content"][0]["text"].as_str().unwrap()).unwrap()
    }
}

impl Drop for Client {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

#[test]
fn tutti_gli_strumenti() {
    let dir = tempfile::tempdir().unwrap();
    let mut c = Client::start(dir.path());

    let init = c.send("initialize", json!({"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}));
    assert_eq!(init["result"]["protocolVersion"], "2025-06-18");
    assert_eq!(init["result"]["serverInfo"]["name"], "quicknotes");
    writeln!(c.stdin, "{}", json!({"jsonrpc": "2.0", "method": "notifications/initialized"})).unwrap();
    assert_eq!(c.send("ping", json!({}))["result"], json!({}));
    assert_eq!(c.send("tools/list", json!({}))["result"]["tools"].as_array().unwrap().len(), 12);

    let created = c.call("create_note", json!({
        "title": "Riepilogo budget",
        "content": "- [ ] @Marco manda il foglio due:2026-11-06\n- Tre tranche !decisione\n",
        "people": ["Marco"], "project": "clientex", "tags": ["lavoro"],
    }));
    let id = created["id"].as_str().unwrap().to_string();

    let found = c.call("search_notes", json!({"query": "tranche"}));
    assert_eq!(found[0]["id"], id.as_str());
    assert_eq!(c.call("list_notes", json!({"project": "clientex"})).as_array().unwrap().len(), 1);
    let read = c.call("read_note", json!({"note_id": id}));
    assert!(read["content"].as_str().unwrap().contains("Tre tranche"));

    let actions = c.call("list_action_items", json!({"owner": "marco"}));
    assert_eq!(actions[0]["due"], "2026-11-06");
    assert_eq!(c.call("list_decisions", json!({"query": "tranche"}))[0]["text"], "Tre tranche");
    let facets = c.call("list_people_and_projects", json!({}));
    assert_eq!(facets["people"][0]["name"], "Marco");

    let done = c.call("set_action_status", json!({"note_id": id, "action_text": "foglio"}));
    assert_eq!(done["done"], true);
    assert!(done["text"].as_str().unwrap().contains("done:"), "il tool MCP scrive anche la data");
    assert!(c.call("list_action_items", json!({})).as_array().unwrap().is_empty());

    c.call("append_to_note", json!({"note_id": id, "text": "Vedi [[Altra]]", "heading": "Dopo"}));
    let daily = c.call("append_to_daily_note", json!({"text": format!("Rivisto [[{id}|Riepilogo]]")}));
    let back = c.call("get_backlinks", json!({"note_id": id}));
    assert_eq!(back[0]["note_id"], daily["id"]);
    let today = c.call("read_daily_note", json!({}));
    assert_eq!(today["exists"], true);
    assert_eq!(c.call("read_daily_note", json!({"date": "2001-01-01"}))["exists"], false);

    let missing = c.send("tools/call", json!({"name": "read_note", "arguments": {"note_id": "assente"}}));
    assert_eq!(missing["result"]["isError"], true);
    assert_eq!(c.send("tools/call", json!({"name": "boh"}))["error"]["code"], -32602);
    assert_eq!(c.send("metodo/assente", json!({}))["error"]["code"], -32601);
}

#[test]
fn prompt() {
    let dir = tempfile::tempdir().unwrap();
    let mut c = Client::start(dir.path());
    assert_eq!(c.send("prompts/list", json!({}))["result"]["prompts"].as_array().unwrap().len(), 2);
    let p = c.send("prompts/get", json!({"name": "riepilogo_settimanale", "arguments": {"settimana_che_inizia": "2026-11-02"}}));
    assert!(p["result"]["messages"][0]["content"]["text"].as_str().unwrap().contains("dal 2026-11-02 al 2026-11-08"));
    let b = c.send("prompts/get", json!({"name": "briefing_meeting", "arguments": {"persona_o_progetto": "Laura"}}));
    assert!(b["result"]["messages"][0]["content"]["text"].as_str().unwrap().contains("«Laura»"));
    assert_eq!(c.send("prompts/get", json!({"name": "briefing_meeting"}))["error"]["code"], -32602);
}
