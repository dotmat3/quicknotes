"""La migrazione delle note: proposta, scelte, applicazione con copia; anche da riga di comando."""

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from quicknotes import migrate
from quicknotes.store import NoteStore, QuickNotesError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("migra_note", ROOT / "scripts" / "migra_note.py")
cli = importlib.util.module_from_spec(spec)
sys.modules["migra_note"] = cli
spec.loader.exec_module(cli)

D1 = ("---\ntype: daily\ndate: 2026-11-03\n---\r\n# LLM Training\r\n- [x] Vecchio filtro #filter done:2026-11-01\r\n"
      "    Deprecato: sostituito dal filtro qualità\r\n- [ ] Usare bf16? #llm-training\r\n- [ ] Lanciare dedup #dedup\r\n"
      "- Lanciato il job #dedup\r\n# Varie\r\n- [ ] Comprare il toner\r\n")
D2 = ("---\ntype: daily\ndate: 2026-11-04\n---\n# LLM Training\n- [ ] Controllare #filter\n- [x] Fatta davvero done:2026-11-02\n"
      "# MBDA\n- [ ] Preparare la gara #gara\n")
MEETING = ("---\ntype: meeting\ntitle: Parser\ndate: 2026-10-01T10:00\n---\n- [ ] Rivedere il parser #ekm\n"
           "- [ ] Test del parser #ekm\n- [ ] Documentare #ekm/doc\n")
TODAY = date(2026, 11, 10)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "QuickNotes"
        for rel, text in {"2026/11/2026-11-03-giornata.md": D1, "2026/11/2026-11-04-giornata.md": D2,
                          "2026/10/2026-10-01-1000-parser.md": MEETING}.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode())

    def tearDown(self):
        self.tmp.cleanup()

    def raw(self, rel: str) -> str:
        return (self.root / rel).read_bytes().decode()


class Proposta(Base):
    def test_progetti_proposti(self):
        p = migrate.plan(self.root, TODAY)
        by = {x["key"]: x for x in p["projects"]}
        self.assertEqual(set(by), {"llm-training", "ekm", "mbda"}, "# Varie non è un progetto")
        llm = by["llm-training"]
        self.assertEqual((llm["title"], llm["sources"], llm["notes"], llm["selected"]),
                         ("LLM Training", ["heading"], 2, True))
        self.assertEqual([(a["name"], a["count"], a["selected"]) for a in llm["areas"]],
                         [("filter", 2, True), ("dedup", 2, True)])
        self.assertEqual((by["ekm"]["sources"], by["ekm"]["actions"], by["ekm"]["status"]), (["tag"], 3, "pausa"),
                         "un progetto fermo da più di 30 giorni si propone in pausa")
        self.assertEqual([a["name"] for a in by["ekm"]["areas"]], ["doc"])
        self.assertFalse(by["mbda"]["selected"], "una sola nota e una sola azione: da scegliere a mano")

    def test_righe_per_regola(self):
        p = migrate.plan(self.root, TODAY)
        got = {(e["rule"], e["rel"], e["line"]): (e["before"], e["after"]) for e in p["edits"]}
        self.assertEqual(got[("cancelled", "2026/11/2026-11-03-giornata.md", 6)],
                         ("- [x] Vecchio filtro #filter done:2026-11-01", "- [-] Vecchio filtro #filter done:2026-11-01"))
        self.assertEqual(got[("question", "2026/11/2026-11-03-giornata.md", 8)][1], "- [?] Usare bf16? #llm-training")
        self.assertEqual(got[("redundant_tag", "2026/11/2026-11-03-giornata.md", 8)][1], "- [ ] Usare bf16?")
        self.assertEqual({r["key"]: r["count"] for r in p["rules"]}, {"cancelled": 1, "question": 1, "redundant_tag": 1})
        self.assertFalse(any("Fatta davvero" in e["before"] for e in p["edits"]))
        self.assertEqual(self.raw("2026/11/2026-11-03-giornata.md"), D1, "la proposta non scrive nulla")
        self.assertFalse((self.root / "progetti").exists())

    def test_scelte_predefinite(self):
        c = migrate.default_choices(migrate.plan(self.root, TODAY))
        self.assertEqual([p["title"] for p in c["projects"]], ["LLM Training", "ekm"])
        self.assertEqual(len(c["edits"]), 2, "le etichette ripetute non sono attive di default")


class Applicazione(Base):
    def setUp(self):
        super().setUp()
        self.store = NoteStore(self.root)

    def tearDown(self):
        self.store.close()
        super().tearDown()

    def test_applica_le_scelte_con_copia(self):
        p = migrate.plan(self.root, TODAY)
        done = migrate.apply(self.store, migrate.default_choices(p))
        self.assertEqual((done["applied"], done["skipped"]), (2, []))
        text = self.raw("2026/11/2026-11-03-giornata.md")
        self.assertIn("- [-] Vecchio filtro #filter done:2026-11-01\r\n", text, "gli a capo di Windows restano")
        self.assertIn("- [?] Usare bf16? #llm-training\r\n", text)
        self.assertTrue(text.startswith("---\ntype: daily\n"), "il frontmatter non si tocca")
        copy = Path(done["backup"])
        self.assertEqual((copy / "2026/11/2026-11-03-giornata.md").read_bytes().decode(), D1)
        self.assertFalse((copy / ".quicknotes").exists(), "la copia non porta l'indice")
        hub = self.store.read("llm-training")
        self.assertEqual(hub.meta["areas"], ["filter", "dedup"], "in ordine d’uso")
        self.assertEqual(self.store.read("ekm").meta["status"], "pausa")
        acts = {a["text"]: a for a in self.store.actions(status="all")}
        self.assertEqual((acts["Controllare #filter"]["project"], acts["Controllare #filter"]["area"]), ("llm-training", "filter"))
        self.assertEqual(acts["Usare bf16? #llm-training"]["status"], "question")
        again = migrate.plan(self.root, TODAY)
        self.assertEqual(migrate.default_choices(again)["edits"], [], "una seconda volta non resta niente di predefinito")
        self.assertEqual([x["key"] for x in again["projects"]], ["mbda"])

    def test_piu_regole_sulla_stessa_riga_e_titolo_cambiato(self):
        p = migrate.plan(self.root, TODAY)
        line = [e for e in p["edits"] if e["line"] == 8]
        choices = {"projects": [{"title": "Addestramento", "from_key": "llm-training", "aliases": ["LLM Training"], "status": "attivo", "areas": []}],
                   "edits": [{"id": e["id"], "before": e["before"]} for e in line]}
        done = migrate.apply(self.store, choices, make_backup=False)
        self.assertEqual(done["applied"], 2)
        self.assertIn("- [?] Usare bf16?\r\n", self.raw("2026/11/2026-11-03-giornata.md"))
        self.assertEqual(self.store.actions(status="all", project="addestramento")[0]["project"], "addestramento")

    def test_una_riga_cambiata_nel_frattempo_si_salta(self):
        p = migrate.plan(self.root, TODAY)
        e = next(e for e in p["edits"] if e["rule"] == "question")
        path = self.root / e["rel"]
        path.write_bytes(path.read_bytes().replace(b"Usare bf16?", b"Usare bf16 o fp8?"))
        done = migrate.apply(self.store, {"edits": [{"id": e["id"], "before": e["before"]}]}, make_backup=False)
        self.assertEqual((done["applied"], done["skipped"]), (0, [e["id"]]))

    def test_progetto_gia_presente_non_scrive_nulla(self):
        self.store.create_project("EKM")
        with self.assertRaises(QuickNotesError):
            migrate.apply(self.store, {"projects": [{"title": "ekm"}], "edits": []})
        self.assertEqual([p.name for p in self.root.parent.iterdir()], ["QuickNotes"], "nessuna copia se si ferma prima")


class RigaDiComando(Base):
    def run_main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            cli.main(["--cartella", str(self.root), *args])
        return out.getvalue()

    def test_a_secco_poi_applica(self):
        out = self.run_main("--dry-run")
        self.assertIn("[x] LLM Training (llm-training)", out)
        self.assertIn("[ ] MBDA (mbda)", out)
        self.assertIn("+ - [-] Vecchio filtro", out)
        self.assertEqual(self.raw("2026/11/2026-11-03-giornata.md"), D1)
        out = self.run_main("--applica")
        self.assertIn("Progetti creati: 2 · righe cambiate: 2", out)
        self.assertTrue((self.root / "progetti" / "llm-training.md").exists())
