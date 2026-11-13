"""Progetti, aree e filtri: a che progetto appartiene un'azione, sposta, archivia, crea."""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from quicknotes import dates, edit
from quicknotes.index import Filter
from quicknotes.store import NoteStore, QuickNotesError, StaleLine

HUB = ("---\ntype: project\ntitle: LLM Training\nproject: llm-training\nstatus: attivo\naliases: [LLM Training, LLM]\n"
       "areas: [dedup, filter]\n---\n## Obiettivo\n\nAddestrare il modello.\n\n## Prossime azioni\n\n### dedup\n"
       "- [ ] Dedup fineweb_edu\n\n### filter\n- [x] Filtro lingua done:2026-11-05\n- [ ] Filtro qualità\n"
       "    - [x] soglie done:2026-11-06\n\n## Note collegate\n")
EKM = "---\ntype: project\ntitle: EKM\nstatus: pausa\n---\n## Prossime azioni\n- [ ] Rivedere il parser\n"
DAILY = ("---\ntype: daily\ndate: 2026-11-04\n---\n# LLM Training\n- [ ] Lanciare dedup e filtri\n"
         "- [ ] Controllare #filter\n    - [ ] figlia\n- Lanciato il job dedup\n- [ ] Riga a parte #ekm\n"
         "- [ ] Esplicita #llm-training/eval\n# Varie\n- [ ] Comprare il caffè\n- [ ] Cita #dedup senza progetto\n")


def d(s: str) -> date:
    return dates.parse_day(s)


class Base(unittest.TestCase):
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

    def text(self, rel: str) -> str:
        return (self.dir / rel).read_text(encoding="utf-8")

    def by_text(self, **query) -> dict[str, dict]:
        return {a["text"]: a for a in self.store.actions(status="all", **query)}

    def setup_notes(self):
        self.write("progetti/llm-training.md", HUB)
        self.write("progetti/ekm.md", EKM)
        self.write("2026/11/2026-11-04-giornata.md", DAILY)
        self.store.refresh()


class Risoluzione(Base):
    def test_progetto_e_area_dalle_regole(self):
        self.setup_notes()
        a = self.by_text()
        self.assertEqual((a["Lanciare dedup e filtri"]["project"], a["Lanciare dedup e filtri"]["area"]),
                         ("llm-training", None), "dall'intestazione, che è un alias")
        self.assertEqual((a["Controllare #filter"]["project"], a["Controllare #filter"]["area"]),
                         ("llm-training", "filter"), "#filter sotto # LLM Training diventa llm-training/filter")
        self.assertEqual((a["figlia"]["project"], a["figlia"]["area"]), ("llm-training", "filter"),
                         "la figlia eredita progetto ed etichette della madre")
        self.assertEqual(a["Riga a parte #ekm"]["project"], "ekm", "un'etichetta che è un progetto vince sull'intestazione")
        self.assertEqual((a["Esplicita #llm-training/eval"]["project"], a["Esplicita #llm-training/eval"]["area"]),
                         ("llm-training", "eval"))
        self.assertIsNone(a["Comprare il caffè"]["project"])
        self.assertEqual(a["Dedup fineweb_edu"]["area"], "dedup", "nella nota di progetto l'area viene dal ### dedup")
        self.assertEqual(a["Rivedere il parser"]["project"], "ekm", "chiave dal titolo, senza campo project")

    def test_progetto_scritto_nella_riga(self):
        """Serve all'interfaccia: la pillola del progetto compare solo se il progetto non è già scritto."""
        self.setup_notes()
        self.write("2026/11/2026-11-05-giornata.md", "---\ntype: daily\ndate: 2026-11-05\n---\n"
                   "- [ ] Con alias #llm\n- [ ] Con area #mario #ekm\n")
        self.store.refresh()
        a = self.by_text()
        written = {t: a[t]["project_in_text"] for t in ("Lanciare dedup e filtri", "Controllare #filter",
                                                       "Riga a parte #ekm", "Esplicita #llm-training/eval",
                                                       "Con alias #llm", "Con area #mario #ekm", "Comprare il caffè")}
        self.assertEqual(written, {"Lanciare dedup e filtri": False, "Controllare #filter": False,
                                   "Riga a parte #ekm": True, "Esplicita #llm-training/eval": True,
                                   "Con alias #llm": True, "Con area #mario #ekm": True, "Comprare il caffè": False})
        self.assertEqual(a["Con area #mario #ekm"]["area"], "mario", "l'altra etichetta resta un'area")

    def test_frontmatter_della_nota(self):
        self.write("note/argomento.md", "---\ntitle: Dedup fineweb_edu OOM\nproject: llm-training\n---\n- [ ] Ridurre i batch\n")
        self.write("progetti/llm-training.md", HUB)
        self.store.refresh()
        self.assertEqual(self.by_text()["Ridurre i batch"]["project"], "llm-training")

    def test_cambiare_un_progetto_riassegna_le_azioni(self):
        self.write("2026/11/2026-11-04-giornata.md", DAILY)
        self.store.refresh()
        self.assertIsNone(self.by_text()["Lanciare dedup e filtri"]["project"])
        self.write("progetti/llm-training.md", HUB)
        self.store.refresh()
        self.assertEqual(self.by_text()["Lanciare dedup e filtri"]["project"], "llm-training",
                         "la nota di progetto nuova vale anche per i daily già indicizzati")
        note = self.store.read("llm-training")
        # Né chiave, né titolo, né alias corrispondono più all'intestazione "LLM Training".
        note.meta.update({"project": "training", "title": "Training", "aliases": []})
        note.meta_dirty = True
        self.store.save(note)
        self.assertIsNone(self.by_text()["Lanciare dedup e filtri"]["project"], "anche un salvataggio dall'app")

    def test_progetti_e_conteggi(self):
        self.setup_notes()
        rows = {p["key"]: p for p in self.store.project_rows()}
        self.assertEqual(rows["ekm"]["status"], "pausa")
        self.assertEqual(rows["llm-training"]["aliases"], ["LLM Training", "LLM"])
        self.assertEqual(rows["llm-training"]["open"], 6)
        self.assertEqual(rows["llm-training"]["open_by_area"]["filter"], 3)

    def test_log_dei_daily(self):
        self.setup_notes()
        self.assertEqual([l["text"] for l in self.store.logs("llm-training")], ["Lanciato il job dedup"])


class Filtri(Base):
    def test_progetto_area_e_combinati(self):
        self.setup_notes()
        proj = set(self.by_text(project="llm-training"))
        self.assertIn("Esplicita #llm-training/eval", proj)
        self.assertIn("Dedup fineweb_edu", proj)
        self.assertNotIn("Comprare il caffè", proj, "un daily con un'etichetta non porta più tutte le sue azioni")
        self.assertNotIn("Riga a parte #ekm", proj)
        self.assertEqual(set(self.by_text(topic="dedup")), {"Dedup fineweb_edu", "Cita #dedup senza progetto"})
        self.assertEqual(set(self.by_text(topic="eval")), {"Esplicita #llm-training/eval"}, "anche dal tag gerarchico")
        self.assertEqual(set(self.by_text(project="llm-training", topic="dedup")), {"Dedup fineweb_edu"})
        self.assertEqual(set(self.by_text(project="dedup")), {"Cita #dedup senza progetto"},
                         "project=X trova anche l'etichetta X")

    def test_progetti_in_pausa(self):
        self.setup_notes()
        hidden = set(a["text"] for a in self.store.actions(include_paused=False))
        self.assertNotIn("Rivedere il parser", hidden)
        self.assertNotIn("Riga a parte #ekm", hidden)
        self.assertIn("Comprare il caffè", hidden)

    def test_note_del_progetto(self):
        self.setup_notes()
        ids = {n["id"] for n in self.store.list_notes(Filter(project="llm-training"))}
        self.assertEqual(ids, {"llm-training", "2026-11-04-giornata"})

    def test_pianificate_entro(self):
        self.write("2026/11/2026-11-04-giornata.md", "- [ ] A scheduled:2026-11-05\n- [ ] B scheduled:2026-11-20\n- [ ] C\n")
        self.store.refresh()
        self.assertEqual([a["text"] for a in self.store.actions(scheduled_before="2026-11-10")], ["A scheduled:2026-11-05"])


class Scritture(Base):
    def test_sposta_nel_progetto(self):
        self.setup_notes()
        r = self.store.move_action("2026-11-04-giornata", 3, "Controllare #filter", "llm-training", "filter")
        self.assertEqual(r["note_id"], "llm-training")
        daily = self.text("2026/11/2026-11-04-giornata.md")
        self.assertIn("- ↗ Controllare #filter → [[llm-training|LLM Training]]\n- Lanciato il job dedup", daily,
                      "nel daily resta il rimando, figlia compresa nello spostamento")
        self.assertNotIn("figlia", daily)
        hub = self.text("progetti/llm-training.md")
        self.assertIn("    - [x] soglie done:2026-11-06\n- [ ] Controllare #filter\n    - [ ] figlia\n\n## Note collegate", hub)
        a = self.by_text()
        self.assertEqual((a["Controllare #filter"]["note_id"], a["Controllare #filter"]["area"]), ("llm-training", "filter"))
        with self.assertRaises(StaleLine):
            self.store.move_action("2026-11-04-giornata", 3, "Controllare #filter", "llm-training", "filter")

    def test_sposta_in_un_area_nuova(self):
        self.setup_notes()
        self.store.move_action("2026-11-04-giornata", 2, "Lanciare dedup e filtri", "llm-training", "eval")
        hub = self.store.read("llm-training")
        self.assertEqual(hub.meta["areas"], ["dedup", "filter", "eval"])
        self.assertIn("### eval\n- [ ] Lanciare dedup e filtri\n\n## Note collegate", hub.body)
        self.assertEqual(self.by_text()["Lanciare dedup e filtri"]["area"], "eval")

    def test_archivia_fatte(self):
        self.setup_notes()
        self.write("progetti/llm-training.md", HUB.replace("- [ ] Filtro qualità", "- [-] Filtro qualità done:2026-11-07"))
        self.store.refresh()
        r = self.store.archive_done("LLM Training", d("2026-11-10"))
        self.assertEqual(r, {"archived": 2, "archive_id": "llm-training.archivio"})
        hub = self.text("progetti/llm-training.md")
        self.assertNotIn("Filtro", hub)
        self.assertIn("### filter\n\n## Note collegate", hub)
        archive = self.store.read("llm-training.archivio")
        self.assertEqual(archive.body, "## 2026-11\n- [x] Filtro lingua done:2026-11-05\n"
                                       "- [-] Filtro qualità done:2026-11-07\n    - [x] soglie done:2026-11-06\n")
        self.assertEqual(self.by_text()["Filtro lingua done:2026-11-05"]["project"], "llm-training")
        self.assertEqual(self.store.archive_done("llm-training", d("2026-11-10"))["archived"], 0)

    def test_archivia_solo_con_le_figlie_chiuse(self):
        self.write("progetti/p.md", "---\ntype: project\ntitle: P\n---\n- [x] Madre done:2026-11-01\n    - [ ] Aperta\n")
        self.store.refresh()
        self.assertEqual(self.store.archive_done("p", d("2026-11-10"))["archived"], 0)

    def test_crea_progetto_e_stato(self):
        note = self.store.create_project("Certifications", ["Certificazioni"], ["AWS", "azure"])
        self.assertEqual(note.path, self.dir / "progetti" / "certifications.md")
        self.assertEqual(note.meta["areas"], ["aws", "azure"])
        self.assertIn("## Prossime azioni\n\n### aws\n\n### azure\n", note.body)
        with self.assertRaises(QuickNotesError):
            self.store.create_project("certificazioni")
        self.store.add_project_action("certifications", "Prenotare l'esame due:2026-12-01", "aws")
        self.assertEqual(self.by_text()["Prenotare l'esame due:2026-12-01"]["area"], "aws")
        self.store.set_project_status("Certificazioni", "pausa")
        self.assertEqual(self.store.project("certifications").status, "pausa")
        self.assertEqual(self.store.actions(include_paused=False), [])


class AggiungiArea(unittest.TestCase):
    def test_add_to_area(self):
        self.assertEqual(edit.add_to_area("", "dedup", "- [ ] A"), "## Prossime azioni\n\n### dedup\n- [ ] A\n")
        body = "## Prossime azioni\n- [ ] Senza area\n\n### dedup\n- [ ] A\n\n## Note\n"
        self.assertEqual(edit.add_to_area(body, None, "- [ ] B"),
                         "## Prossime azioni\n- [ ] Senza area\n- [ ] B\n\n### dedup\n- [ ] A\n\n## Note\n")
        self.assertEqual(edit.add_to_area(body, "dedup", "- [ ] C"),
                         "## Prossime azioni\n- [ ] Senza area\n\n### dedup\n- [ ] A\n- [ ] C\n\n## Note\n")


# Una settimana come quella delle note vere: EKM in pausa, finepdfs con le figlie chiuse, un duplicato, task
# rimasti nel daily del 04/11.
WEEK = {
    "progetti/llm-training.md": "---\ntype: project\ntitle: LLM Training\naliases: [LLM Training]\nareas: [dedup, filter]\n"
                                "---\n## Prossime azioni\n### dedup\n- [/] Dedup su fineweb\n- [ ] Dedup fineweb_edu due:2026-11-15\n",
    "progetti/ekm.md": "---\ntype: project\ntitle: EKM\nstatus: pausa\n---\n## Prossime azioni\n- [ ] Rivedere il parser\n",
    "progetti/bip.md": "---\ntype: project\ntitle: BIP\n---\n## Prossime azioni\n",
    "2026/11/2026-11-04-giornata.md": "# LLM Training\n- [ ] Lanciare dedup e filtri\n- Lanciato il job\n"
                                      "- [ ] Lanciare dedup e filtri\n# Varie\n- [ ] Senza progetto\n"
                                      "- [ ] Pianificata scheduled:2026-11-09\n- [w] Risposta da @Laura\n- [?] Usare bf16?\n",
    "2026/11/2026-11-09-giornata.md": "# Varie\n- [ ] Mandare il report due:2026-11-08\n# LLM Training\n"
                                      "- [ ] Rilanciare finepdfs\n    - [x] shard 1 done:2026-11-05\n"
                                      "    - [-] shard 2 done:2026-11-06\n# EKM\n- [ ] Task EKM fermo\n",
    "2026/11/2026-11-10-giornata.md": "- [-] Rilanciare dedup fineweb_edu done:2026-11-10\n- Saltiamo la dedup !decisione\n",
    "2026/10/2026-10-20-1000-vecchio.md": "---\ntype: meeting\ntitle: Vecchio\ndate: 2026-10-20T10:00\nproject: llm-training\n---\n"
                                          "- [ ] Vecchia senza data\n",
    "2026/10/2026-10-30-1000-preventivo.md": "---\ntype: meeting\ntitle: Preventivo\ndate: 2026-10-30T10:00\n---\n"
                                             "- [w] Preventivo da @Marco\n",
}
TODAY = date(2026, 11, 10)


class Viste(Base):
    def setUp(self):
        super().setUp()
        for rel, text in WEEK.items():
            self.write(rel, text)
        self.store.refresh()

    @staticmethod
    def texts(section: dict) -> list[str]:
        return [i["text"] for g in section["groups"] for i in g["items"]]

    def test_agenda(self):
        from quicknotes import views
        a = views.agenda(self.store, TODAY)
        s = {x["key"]: x for x in a["sections"]}
        self.assertEqual(self.texts(s["late"]), ["Mandare il report"])
        self.assertEqual(self.texts(s["today"]), ["Pianificata"])
        self.assertEqual(s["today"]["groups"][0]["items"][0]["since_days"], 1, "da 1 gg")
        self.assertEqual(self.texts(s["doing"]), ["Dedup su fineweb"])
        self.assertEqual([(g["label"], [i["text"] for i in g["items"]]) for g in s["waiting"]["groups"]],
                         [("Laura", ["Risposta da @Laura"]), ("Marco", ["Preventivo da @Marco"])])
        self.assertTrue(s["waiting"]["groups"][1]["items"][0]["stale"], "ferma da più di 7 giorni")
        self.assertFalse(s["waiting"]["groups"][0]["items"][0]["stale"])
        self.assertEqual(self.texts(s["question"]), ["Usare bf16?"])
        self.assertEqual(self.texts(s["next"]), ["Dedup fineweb_edu"])
        self.assertEqual(sorted(self.texts(s["inbox"])), ["Lanciare dedup e filtri", "Lanciare dedup e filtri", "Senza progetto"],
                         "i task del 04/11 sono da smistare; quelli del 09/11 non ancora")
        every = [t for x in a["sections"] for t in self.texts(x)]
        self.assertNotIn("Task EKM fermo", every, "EKM è in pausa")
        self.assertNotIn("Rivedere il parser", every)
        self.assertEqual([p["key"] for p in a["projects"]], ["bip", "llm-training"])
        only = views.agenda(self.store, TODAY + timedelta(days=5), project="EKM")
        self.assertEqual(only["project"], "ekm", "scelto per nome, anche se è in pausa")
        self.assertEqual(self.texts({x["key"]: x for x in only["sections"]}["inbox"]), ["Task EKM fermo"])

    def test_revisione(self):
        from quicknotes import views
        r = views.weekly_review(self.store, TODAY, "2026-11-01")
        st = {x["key"]: x for x in r["steps"]}
        names = lambda k: sorted(i["text"] for i in st[k]["items"])  # noqa: E731
        self.assertIn("Rilanciare finepdfs", names("parents"))
        self.assertEqual(names("inbox"), ["Lanciare dedup e filtri", "Lanciare dedup e filtri", "Pianificata",
                                          "Risposta da @Laura", "Senza progetto", "Usare bf16?"])
        self.assertEqual(names("stale"), ["Vecchia senza data"])
        self.assertEqual(names("waiting"), ["Preventivo da @Marco"])
        self.assertEqual([g["label"] for g in st["duplicates"]["groups"]], ["Lanciare dedup e filtri"])
        self.assertEqual([p["key"] for p in st["no_next"]["projects"]], ["bip"])
        self.assertEqual([p["key"] for p in st["paused"]["projects"]], ["ekm"])
        summary = st["summary"]["summary"]
        self.assertEqual((summary["done"], summary["cancelled"]), (1, 2))
        self.assertEqual([d["text"] for d in summary["decisions"]], ["Saltiamo la dedup"])
        self.assertEqual((r["days_since"], r["due"]), (9, True))
        self.assertFalse(views.weekly_review(self.store, TODAY, "2026-11-07")["due"])
        self.assertIn("- Annullate: 2", views.review_note_body(r))

    def test_pagina_progetto(self):
        from quicknotes import views
        page = views.project_page(self.store, "llm-training", TODAY)
        self.assertEqual(page["hub_id"], "llm-training")
        self.assertEqual([(g["area"], sorted(i["text"] for i in g["items"])) for g in page["groups"]],
                         [("dedup", ["Dedup fineweb_edu", "Dedup su fineweb"]),
                          (None, ["Lanciare dedup e filtri", "Lanciare dedup e filtri", "Rilanciare finepdfs",
                                  "Vecchia senza data"])])
        self.assertEqual(page["groups"][0]["items"][0]["text"], "Dedup su fineweb", "in corso per prime")
        self.assertEqual([l["text"] for l in page["log"]], ["Lanciato il job"])
        self.assertIn("2026-11-04-giornata", [n["id"] for n in page["notes"]])

    def test_calendario_ed_etichetta(self):
        from quicknotes import views
        cal = views.calendar_data(self.store, "2026-11-01", "2026-11-30", TODAY)
        today = [(e["kind"], e["text"]) for e in cal["2026-11-10"]["events"]]
        self.assertIn(("late", "Mandare il report"), today, "in ritardo compare anche oggi")
        self.assertIn(("late", "Pianificata"), today)
        self.assertIn(("plan", "Pianificata"), [(e["kind"], e["text"]) for e in cal["2026-11-09"]["events"]])
        self.assertTrue(all("line" in e for e in cal["2026-11-08"]["events"]))
        only = views.calendar_data(self.store, "2026-11-01", "2026-11-30", TODAY, project="llm-training")
        self.assertNotIn("2026-11-08", only)
        self.assertEqual(views.tag_page(self.store, "llm-training", TODAY)["project"], "llm-training")
        dedup = views.tag_page(self.store, "dedup", TODAY)
        self.assertIsNone(dedup["project"])
        self.assertEqual([g["project"] for g in dedup["groups"]], ["llm-training"])

    def test_bacheca(self):
        from quicknotes import views
        b = views.action_board(self.store, TODAY)
        cancelled = next(i for i in b["items"] if i["text"].startswith("Rilanciare dedup"))
        self.assertTrue(cancelled["closed"])
        self.assertFalse(cancelled["done"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(b["open"], sum(1 for i in b["items"] if not i["closed"]))


class AggiuntaRapida(Base):
    """L'aggiunta rapida della vista Azioni: progetto e area dal testo o scelti, altrimenti "Da smistare"."""

    def test_progetto_e_area_dall_etichetta(self):
        self.setup_notes()
        r = self.store.quick_action("Valutare MinHash #llm/dedup @Marco", due=d("2026-11-12"), priority="alta")
        self.assertEqual((r["project"], r["area"]), ("llm-training", "dedup"))
        hub = self.text("progetti/llm-training.md")
        self.assertIn("- [ ] Dedup fineweb_edu\n- [ ] Valutare MinHash @Marco prio:alta due:2026-11-12\n", hub,
                      "sotto l'area, senza l'etichetta del progetto")
        a = self.by_text()["Valutare MinHash @Marco prio:alta due:2026-11-12"]
        self.assertEqual((a["project"], a["area"]), ("llm-training", "dedup"))

    def test_progetto_scelto_area_nuova_e_testo_che_vince(self):
        self.setup_notes()
        r = self.store.quick_action("Scrivere il report due:2026-12-01", project="LLM", area="Eval", due=d("2026-11-10"))
        self.assertEqual(r["area"], "eval")
        hub = self.text("progetti/llm-training.md")
        self.assertIn("### eval\n- [ ] Scrivere il report due:2026-12-01\n", hub, "la scadenza scritta vale")
        self.assertIn("areas:", hub)
        self.assertIn("eval", hub.split("---")[1], "l'area nuova entra nel frontmatter")

    def test_senza_progetto_va_in_da_smistare(self):
        self.setup_notes()
        r = self.store.quick_action("Comprare le pile #casa", scheduled=d("2026-11-11"))
        self.assertEqual((r["id"], r["project"]), ("da-smistare", None))
        text = self.text("da-smistare.md")
        self.assertIn("type: inbox", text)
        self.assertTrue(text.endswith("## Azioni\n- [ ] Comprare le pile #casa scheduled:2026-11-11\n"), text)
        self.store.quick_action("Seconda")
        self.assertTrue(self.text("da-smistare.md").endswith("scheduled:2026-11-11\n- [ ] Seconda\n"))
        from quicknotes import views
        inbox = next(s for s in views.agenda(self.store, TODAY)["sections"] if s["key"] == "inbox")
        self.assertIn("Seconda", [i["text"] for g in inbox["groups"] for i in g["items"]],
                      "Agenda la mostra subito da smistare")

    def test_errori(self):
        self.setup_notes()
        with self.assertRaises(QuickNotesError):
            self.store.quick_action("   ")
        with self.assertRaises(QuickNotesError):
            self.store.quick_action("Qualcosa", project="inesistente")
