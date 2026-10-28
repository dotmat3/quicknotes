"""Punto d'ingresso:

    python -m quicknotes            apre l'app (o la porta in primo piano)
    python -m quicknotes new        nuovo meeting
    python -m quicknotes daily      nota del giorno
    python -m quicknotes record     avvia/ferma la registrazione
    python -m quicknotes mcp        server MCP per Claude (stdio)
    python -m quicknotes reindex    ricostruisce l'indice di ricerca
    python -m quicknotes where      mostra dove sono note e configurazione
    python -m quicknotes claude-config   configurazione da incollare in Claude Desktop
    python -m quicknotes --dev      interfaccia dal server di sviluppo Vite (npm run dev in frontend/)
"""

import argparse
import json
import os
import sys
from pathlib import Path


def claude_desktop_config_path() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "Claude" / "claude_desktop_config.json"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    return Path.home() / ".config/Claude/claude_desktop_config.json"


def main() -> int:
    ap = argparse.ArgumentParser(prog="quicknotes", description="Note rapide consultabili da Claude")
    ap.add_argument("command", nargs="?", default="show",
                    choices=["show", "new", "daily", "record", "mcp", "reindex", "where", "claude-config"])
    ap.add_argument("--dev", action="store_true", help="carica l'interfaccia dal server di sviluppo Vite")
    args = ap.parse_args()

    if args.command == "mcp":  # niente GUI: stdout e' riservato al protocollo
        from .mcp_server import main as mcp_main
        mcp_main()
        return 0
    if args.command == "claude-config":
        snippet = {"mcpServers": {"quicknotes": {"command": sys.executable, "args": ["-m", "quicknotes", "mcp"]}}}
        print("Aggiungi questo blocco a:", claude_desktop_config_path())
        print("(se il file contiene gia' \"mcpServers\", aggiungi solo la voce \"quicknotes\")\n")
        print(json.dumps(snippet, indent=2))
        print("\nPer Claude Code:\n  claude mcp add --transport stdio --scope user quicknotes -- "
              f'"{sys.executable}" -m quicknotes mcp')
        return 0
    if args.command in ("reindex", "where"):
        from .config import CONFIG_FILE, load_config
        from .store import NoteStore
        cfg = load_config()
        if args.command == "where":
            print(f"Note:          {cfg.notes_path}\nConfigurazione: {CONFIG_FILE}\nPython:        {sys.executable}")
            return 0
        store = NoteStore(cfg.notes_path)
        index = store.root / ".quicknotes" / "index.db"
        store.close()
        for suffix in ("", "-wal", "-shm"):
            p = index.with_name(index.name + suffix)
            if p.exists():
                p.unlink()
        store = NoteStore(cfg.notes_path)
        print(f"Indice ricostruito: {len(store.list_notes(limit=100000))} note")
        return 0

    from .app import run
    return run(args.command, dev=args.dev)


if __name__ == "__main__":
    sys.exit(main())
