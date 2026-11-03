"""Genera note finte per misurare i tempi, poi misura indicizzazione e ricerca.

    .venv/Scripts/python scripts/genera_note.py <cartella vuota> [numero]
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quicknotes.store import NoteStore  # noqa: E402

WORDS = ["budget", "preventivo", "cucina", "riunione", "fornitori", "scadenza", "ricerca", "embedding", "cliente",
         "contratto", "revisione", "trimestre", "obiettivi", "bozza", "misure", "lavello", "trascrizione", "modello",
         "architettura", "requisiti"]


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = Path(sys.argv[1])
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    if any(root.glob("*/**/*.md")):
        sys.exit("La cartella contiene già note: usane una vuota.")
    for i in range(count):
        month, dom = i % 12 + 1, i % 28 + 1
        folder = root / "2026" / f"{month:02}"
        folder.mkdir(parents=True, exist_ok=True)
        body = (f"---\ntype: meeting\ntitle: Riunione {i}\ndate: 2026-{month:02}-{dom:02}T10:00\n"
                "people: [Giulia, Marco]\n---\n")
        for p in range(40):
            def w(k):
                return WORDS[(i * 7 + p * 13 + k) % len(WORDS)]
            body += f"{w(0)} {w(1)} {w(2)} {w(3)} con @Persona{p % 9} #tag{i % 12}\n"
            if p % 8 == 0:
                body += f"- [ ] {w(4)} {w(5)} due:2026-{month:02}-{dom:02}\n"
            if p % 19 == 0:
                body += f"{w(6)} {w(7)} !decisione\n"
        (folder / f"2026-{month:02}-{dom:02}-1000-riunione-{i}.md").write_text(body, encoding="utf-8")

    def timed(label, func):
        t = time.perf_counter()
        result = func()
        print(f"{label}: {(time.perf_counter() - t) * 1000:.1f} ms")
        return result

    store = timed("apertura indice", lambda: NoteStore(root))
    n = timed("indicizzazione completa", store.refresh)
    print(f"  ({n} note)")
    timed("allineamento senza modifiche", store.refresh)
    for q in ("bud", "preventivo cucina", "lavello trascrizione modello"):
        found = timed(f"ricerca '{q}'", lambda q=q: store.search(q, None, 20))
        print(f"  ({len(found)} risultati)")
    actions = timed("azioni aperte", lambda: store.actions(limit=500))
    print(f"  ({len(actions)} azioni)")


if __name__ == "__main__":
    main()
