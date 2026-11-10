"""Migrazione delle note al formato con progetti e stati (QuickNotes 0.6.0), da riga di comando.

    .venv/Scripts/python scripts/migra_note.py --dry-run [--cartella <note>] [--report migrazione.txt]
    .venv/Scripts/python scripts/migra_note.py --applica [--cartella <note>]

La stessa migrazione si fa dall'app (Impostazioni › Note › Migrazione, o Ctrl K › "Migra le note"), dove si
scelgono progetto per progetto e riga per riga. Qui si applicano le scelte predefinite: le regole attive di
default e i progetti proposti come scelti. Senza `--applica` non si scrive nulla. Le regole e la proposta dei
progetti sono in `quicknotes/migrate.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quicknotes import migrate  # noqa: E402


def report(proposal: dict, choices: dict) -> str:
    chosen = {e["id"] for e in choices["edits"]}
    picked = {p["from_key"] for p in choices["projects"]}
    out = [f"Note lette: {proposal['notes']}", ""]
    if proposal["existing"]:
        out.append("Progetti già presenti: " + ", ".join(p["title"] for p in proposal["existing"]))
        out.append("")
    out.append("PROGETTI PROPOSTI ([x] = si crea)")
    for p in proposal["projects"]:
        mark = "x" if p["key"] in picked else " "
        areas = ", ".join(f"{a['name']}{'' if a['selected'] else '?'}" for a in p["areas"]) or "-"
        out.append(f"  [{mark}] {p['title']} ({p['key']}) · {p['status']} · {p['actions']} azioni in {p['notes']} note"
                   f" · da {', '.join(p['sources'])} · aree: {areas}")
    if not proposal["projects"]:
        out.append("  nessuno")
    for r in proposal["rules"]:
        out += ["", f"{r['title'].upper()} ({r['count']}{'' if r['default'] else ', non attiva di default'}): {r['description']}"]
        for e in (e for e in proposal["edits"] if e["rule"] == r["key"]):
            mark = "x" if e["id"] in chosen else " "
            out.append(f"  [{mark}] {e['rel']}:{e['line']}")
            out.append(f"        - {e['before'].strip()}")
            out.append(f"        + {e['after'].strip()}")
    out.append("")
    out.append("Le aree con ? non sono scelte di default (usate una volta sola).")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="mostra la proposta senza scrivere (predefinito)")
    mode.add_argument("--applica", action="store_true", help="fa una copia della cartella e applica le scelte predefinite")
    ap.add_argument("--cartella", type=Path, help="cartella delle note (di default quella della configurazione)")
    ap.add_argument("--report", type=Path, help="scrive la proposta anche in questo file")
    args = ap.parse_args(argv)

    if args.cartella:
        root = args.cartella.resolve()
    else:
        from quicknotes.config import Config
        root = Config.load().notes_path().resolve()
    if not root.is_dir():
        raise SystemExit(f"Cartella delle note inesistente: {root}")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    proposal = migrate.plan(root)
    choices = migrate.default_choices(proposal)
    text = report(proposal, choices)
    print(text)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    if not choices["edits"] and not choices["projects"]:
        print("Niente da cambiare con le scelte predefinite.")
        return 0
    if not args.applica:
        print("Nessun file scritto. Rivedi la proposta, poi rilancia con --applica oppure usa la vista Migrazione dell'app.")
        return 0
    from quicknotes.store import NoteStore
    store = NoteStore(root)
    try:
        done = migrate.apply(store, choices)
    finally:
        store.close()
    print(f"Copia della cartella: {done['backup']}")
    print(f"Progetti creati: {len(done['projects'])} · righe cambiate: {done['applied']} · saltate: {len(done['skipped'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
