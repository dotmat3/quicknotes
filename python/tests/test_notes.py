"""Il formato delle note deve restare quello della versione Rust: python -m unittest discover python/tests"""

import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quicknotes_py import dates  # noqa: E402
from quicknotes_py.notes import NoteStore, extract, mentions, slugify, split_frontmatter, tags  # noqa: E402


class Formato(unittest.TestCase):
    def test_persone_ed_etichette(self):
        self.assertEqual(mentions("ciao @Marco e @laura.rossi. mail a x@y.it"), ["Marco", "laura.rossi"])
        self.assertEqual(tags("#clienteX e #2026 e a#b e #a/b-c"), ["clienteX", "a/b-c"])

    def test_azioni_con_madre(self):
        body = "- [ ] @Marco invia preventivo due:2026-10-31 #clientex\n  - [x] bozza\n- [x] fatto\ntesto\n"
        ex = extract(body)
        self.assertEqual([(a.line_no, a.done, a.parent_line) for a in ex.actions], [(1, False, None), (2, True, 1), (3, True, None)])
        self.assertEqual(ex.actions[0].due, "2026-10-31")
        self.assertEqual(ex.people, ["Marco"])
        self.assertEqual(ex.tags, ["clientex"])

    def test_codice_ignorato_e_link(self):
        ex = extract("```\n@nessuno\n```\nvedi [[2026-10-27-giornata|Lunedì]] e ![[schizzo.excalidraw]]\n[a](file#ancora)\n")
        self.assertEqual(ex.people, [])
        self.assertEqual(ex.tags, [])
        self.assertEqual([(l.target, l.label) for l in ex.links], [("2026-10-27-giornata", "Lunedì")])

    def test_frontmatter_con_date_resta_testo(self):
        raw, meta, body = split_frontmatter("---\ntitle: Prova\ndate: 2026-10-27\n---\ncorpo\n")
        self.assertEqual(meta["date"], "2026-10-27")
        self.assertEqual(raw, "---\ntitle: Prova\ndate: 2026-10-27\n---\n")
        self.assertEqual(body, "corpo\n")

    def test_slug_e_titoli(self):
        self.assertEqual(slugify("Kick-off  Cliente È!"), "kick-off-cliente-e")
        self.assertEqual(dates.daily_title(date(2026, 11, 3)), "Martedì 3 novembre")


class Archivio(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = NoteStore(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_salvataggio_conserva_frontmatter_e_crlf(self):
        path = Path(self.tmp.name) / "2026" / "10" / "2026-10-27-1000-kickoff.md"
        path.parent.mkdir(parents=True)
        original = "---\ntitle:   Kickoff   # spazi strani\npeople: [Marco]\n---\nprima\n".replace("\n", "\r\n")
        path.write_bytes(original.encode())
        self.store.refresh()
        note = self.store.read("2026-10-27-1000-kickoff")
        self.assertEqual(note.title, "Kickoff")
        self.assertEqual(note.date, "2026-10-27T10:00")
        res = self.store.save_if_unchanged(note.id, "prima\n", "dopo @Laura\n")
        self.assertEqual(res, {"status": "saved"})
        self.assertEqual(path.read_bytes().decode(), original.replace("prima", "dopo @Laura"))
        self.assertEqual({p["name"] for p in self.store.people()}, {"Marco", "Laura"})

    def test_conflitto(self):
        note = self.store.create_note("Riunione", "meeting", "uno\n", datetime(2026, 11, 3, 9, 30))
        self.assertEqual(note.id, "2026-11-03-0930-riunione")
        note.path.write_text(note.path.read_text(encoding="utf-8").replace("uno", "da fuori"), encoding="utf-8")
        res = self.store.save_if_unchanged(note.id, "uno\n", "mio\n")
        self.assertEqual(res, {"status": "conflict", "disk": "da fuori\n"})

    def test_nota_del_giorno_e_collegamenti(self):
        day = self.store.daily(date(2026, 11, 3), True)
        self.assertEqual(day.id, "2026-11-03-giornata")
        self.assertIn("type: daily", day.path.read_text(encoding="utf-8"))
        other = self.store.create_note("Altro", "note", "vedi [[2026-11-03-giornata|oggi]]\n")
        self.store.refresh()
        links = self.store.backlinks(day.id, day.title)
        self.assertEqual([(l["note_id"], l["line"]) for l in links], [(other.id, 1)])
        self.assertEqual(self.store.outgoing_links(other.id)[0]["note_id"], day.id)

    def test_immagini_solo_dentro_la_cartella(self):
        note = self.store.create_note("Con immagine", "note")
        rel = self.store.save_image(note.id, b"\x89PNG\r\n\x1a\n" + b"0" * 30)
        self.assertTrue(rel.startswith("images/") and rel.endswith(".png"))
        folder = note.path.parent.relative_to(self.store.root).as_posix()
        self.assertIsNotNone(self.store.resolve_image(f"{folder}/{rel}"))
        self.assertIsNone(self.store.resolve_image("../fuori.png"))
        with self.assertRaises(ValueError):
            self.store.save_image(note.id, b"non un'immagine")


if __name__ == "__main__":
    unittest.main()
