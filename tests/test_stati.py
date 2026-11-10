"""I sei stati delle azioni e `scheduled:`: lettura, scrittura, conteggi."""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from quicknotes import dates, edit, parser
from quicknotes.store import NoteStore, StaleLine


def d(s: str) -> date:
    return dates.parse_day(s)


class Lettura(unittest.TestCase):
    def test_i_sei_stati(self):
        body = ("- [ ] da fare\n- [/] in corso\n- [w] in attesa @Laura\n- [?] si fa così?\n"
                "- [-] annullata: superata done:2026-11-10\n- [x] fatta done:2026-11-09\n- [X] fatta maiuscola\n")
        acts = parser.extract(body).actions
        self.assertEqual([a.status for a in acts], ["todo", "doing", "waiting", "question", "cancelled", "done", "done"])
        self.assertEqual([a.done for a in acts], [False, False, False, False, False, True, True],
                         "done resta vero solo per [x]: statistiche e Micio non cambiano")
        self.assertEqual([a.closed for a in acts], [False, False, False, False, True, True, True])
        self.assertEqual(acts[2].owner, "Laura", "in attesa: la prima @menzione è la persona che si aspetta")

    def test_un_segno_sconosciuto_non_e_un_azione(self):
        self.assertEqual(parser.extract("- [!] no\n- [xx] no\n").actions, [])

    def test_scheduled_e_diverso_da_due(self):
        a = parser.extract("- [ ] Rilanciare dedup scheduled:2026-11-12 due:2026-11-14 prio:alta\n").actions[0]
        self.assertEqual((a.scheduled, a.due), ("2026-11-12", "2026-11-14"))
        self.assertEqual(parser.action_display_text(a.text), "Rilanciare dedup")

    def test_intestazioni_ed_etichette_della_madre(self):
        body = "# LLM Training\n## Dedup\n- [ ] Madre #filter\n    - [ ] Figlia\n# Altro\n- [ ] Fuori\n"
        acts = parser.extract(body).actions
        self.assertEqual(acts[0].headings, ["LLM Training", "Dedup"])
        self.assertEqual(acts[1].inherited_tags, ["filter"])
        self.assertEqual(acts[2].headings, ["Altro"])

    def test_righe_di_log(self):
        ex = parser.extract("# EKM\n- Lanciato il job #ekm\n- [ ] azione\n- ↗ spostata → [[x]]\n"
                            "- Budget ok !decisione\ntesto libero\n")
        self.assertEqual([(l.text, l.headings) for l in ex.logs], [("Lanciato il job #ekm", ["EKM"])])


class Scrittura(unittest.TestCase):
    def test_with_status(self):
        line = "  - [ ] Invia report due:2026-11-14"
        self.assertEqual(edit.with_status(line, "doing", "2026-11-10"), "  - [/] Invia report due:2026-11-14")
        self.assertEqual(edit.with_status(line, "cancelled", "2026-11-10"), "  - [-] Invia report due:2026-11-14 done:2026-11-10")
        self.assertEqual(edit.with_status(line, "done", "2026-11-10"), "  - [x] Invia report due:2026-11-14 done:2026-11-10")
        self.assertEqual(edit.with_status("- [x] A done:2026-11-09", "waiting", "2026-11-10"), "- [w] A")
        self.assertEqual(edit.with_status("- [ ] A", "question", None), "- [?] A")
        with self.assertRaises(ValueError):
            edit.with_status(line, "boh", None)

    def test_with_scheduled(self):
        self.assertEqual(edit.with_scheduled("- [ ] A due:2026-11-14", "2026-11-12"), "- [ ] A scheduled:2026-11-12 due:2026-11-14")
        self.assertEqual(edit.with_scheduled("- [ ] A scheduled:2026-11-12 #x", "2026-11-13"), "- [ ] A #x scheduled:2026-11-13")
        self.assertEqual(edit.with_scheduled("- [ ] A scheduled:2026-11-12 due:2026-11-14", None), "- [ ] A due:2026-11-14")
        self.assertEqual(edit.with_due("- [ ] A scheduled:2026-11-12", "2026-11-14"), "- [ ] A scheduled:2026-11-12 due:2026-11-14")


class Archivio(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.store = NoteStore(self.dir)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def write(self, rel: str, text: str) -> None:
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")
        self.store.refresh()

    def test_stati_nell_indice(self):
        self.write("2026/11/2026-11-10-giornata.md", "- [ ] A\n- [/] B\n- [w] C @Laura\n- [?] D\n- [-] E\n- [x] F\n")
        st = lambda status: sorted(a["text"] for a in self.store.actions(status=status))  # noqa: E731
        self.assertEqual(st("open"), ["A", "B", "C @Laura", "D"], "le annullate non sono aperte")
        self.assertEqual(st("closed"), ["E", "F"])
        self.assertEqual(st("done"), ["F"])
        self.assertEqual(st(["waiting", "question"]), ["C @Laura", "D"])
        self.assertEqual(len(self.store.actions(status="all")), 6)

    def test_cambio_di_stato_e_pianificazione(self):
        self.write("2026/11/2026-11-10-giornata.md", "- [ ] Rilanciare dedup\n")
        r = self.store.set_action_state("2026-11-10-giornata", 1, "Rilanciare dedup", "cancelled", d("2026-11-10"))
        self.assertEqual(r["text"], "- [-] Rilanciare dedup done:2026-11-10")
        with self.assertRaises(StaleLine):
            self.store.set_action_state("2026-11-10-giornata", 1, "Rilanciare dedup", "done", d("2026-11-10"))
        self.store.set_action_state("2026-11-10-giornata", 1, None, "todo", d("2026-11-10"))
        self.store.set_action_details("2026-11-10-giornata", 1, "Rilanciare dedup", scheduled="2026-11-12")
        a = self.store.actions()[0]
        self.assertEqual((a["status"], a["scheduled"], a["text"]), ("todo", "2026-11-12", "Rilanciare dedup scheduled:2026-11-12"))

    def test_chiudere_la_madre_non_tocca_le_figlie_annullate(self):
        self.write("2026/11/2026-11-10-giornata.md", "- [ ] Madre\n    - [-] Superata done:2026-11-09\n    - [ ] Aperta\n")
        self.assertEqual(self.store.complete_with_children("2026-11-10-giornata", 1, "Madre", d("2026-11-10")), 2)
        text = (self.dir / "2026/11/2026-11-10-giornata.md").read_text(encoding="utf-8")
        self.assertIn("    - [-] Superata done:2026-11-09\n", text)
        self.assertIn("    - [x] Aperta done:2026-11-10\n", text)

    def test_stato_via_mcp_compatibile(self):
        self.write("2026/11/2026-11-10-giornata.md", "- [ ] Chiamare Laura\n")
        self.assertTrue(self.store.set_action_status("2026-11-10-giornata", "Laura", d("2026-11-10"))["done"])
        self.assertFalse(self.store.set_action_status("2026-11-10-giornata", "Laura", None)["done"])
        r = self.store.set_action_status("2026-11-10-giornata", "Laura", None, status="waiting", scheduled="2026-11-11")
        self.assertEqual((r["status"], r["text"]), ("waiting", "- [w] Chiamare Laura scheduled:2026-11-11"))
