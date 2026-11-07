"""Archivio e viste: gli stessi casi delle prove della versione Rust."""

import os
import tempfile
import time
import unittest
from datetime import date, datetime
from pathlib import Path

from quicknotes import dates, views
from quicknotes.index import Filter
from quicknotes.store import Note, NoteNotFound, NoteStore, QuickNotesError, StaleLine

OLD_MEETING = ("---\ntype: meeting\ntitle: Kickoff cliente X\ndate: 2026-10-27T10:00\npeople: [Marco, Laura]\n"
               "project: clientex\nextra: da conservare   # commento\n---\n- Budget confermato !decisione\n"
               "- [ ] @Marco invia preventivo due:2026-10-31\nVedi [[2026-10-28-giornata|Giornata]]\n")


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

    def write(self, rel: str, text: str | bytes) -> None:
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else text.encode())

    def text(self, rel: str) -> str:
        return (self.dir / rel).read_bytes().decode()


class Archivio(Base):
    def test_un_salvataggio_non_cambia_il_frontmatter(self):
        self.write("2026/10/2026-10-27-1000-kickoff.md", OLD_MEETING)
        self.assertEqual(self.store.refresh(), 1)
        note = self.store.read("2026-10-27-1000-kickoff")
        self.assertEqual((note.title, note.date, note.people), ("Kickoff cliente X", "2026-10-27T10:00", ["Marco", "Laura"]))
        self.store.update_body(note.id, note.body + "altro\n")
        text = self.text("2026/10/2026-10-27-1000-kickoff.md")
        self.assertIn("extra: da conservare   # commento", text)
        self.assertTrue(text.endswith("altro\n"))

    def test_gli_a_capo_windows_restano_tali(self):
        crlf = OLD_MEETING.replace("\n", "\r\n")
        self.write("2026/10/n.md", crlf)
        self.store.refresh()
        note = self.store.read("n")
        self.assertNotIn("\r", note.body)
        self.store.save(note)
        self.assertEqual(self.text("2026/10/n.md"), crlf)

    def test_titolo_e_data_dedotti_senza_frontmatter(self):
        self.write("x/2026-10-28-1530-prova.md", "# Titolo dal testo\ncorpo\n")
        self.write("x/semplice.md", "solo testo\n")
        self.store.refresh()
        a = self.store.read("2026-10-28-1530-prova")
        self.assertEqual((a.title, a.date), ("Titolo dal testo", "2026-10-28T15:30"))
        self.assertEqual(self.store.read("semplice").title, "semplice")
        self.assertEqual(self.text("x/semplice.md"), "solo testo\n", "nessuna scrittura implicita")

    def test_nota_del_giorno(self):
        self.assertIsNone(self.store.daily(d("2026-11-01"), False))
        note = self.store.daily(d("2026-11-01"), True)
        self.assertEqual((note.id, note.title), ("2026-11-01-giornata", "Giornata di domenica 01/11/2026"))
        self.assertEqual(self.text("2026/11/2026-11-01-giornata.md"),
                         "---\ntype: daily\ntitle: Giornata di domenica 01/11/2026\ndate: 2026-11-01\n---\n")
        self.assertEqual(self.store.daily(d("2026-11-01"), False).id, note.id)

    def test_nuove_note_con_id_unico(self):
        when = datetime(2026, 11, 3, 9, 5)
        a = self.store.create_note("Più idee", "x", "note", when=when)
        b = self.store.create_note("Più idee", "x", "note", when=when)
        self.assertEqual((a.id, b.id), ("2026-11-03-0905-piu-idee", "2026-11-03-0905-piu-idee-2"))
        read = self.store.read(a.id)
        self.assertEqual((read.body, read.note_type), ("x\n", "note"))

    def test_ricerca_e_filtri(self):
        self.write("2026/10/2026-10-27-1000-kickoff.md", OLD_MEETING)
        self.write("2026/10/2026-10-28-giornata.md", "---\ntype: daily\ntitle: Giornata\ndate: 2026-10-28\n---\nPreventivo cucina con @Giulia #casa\n")
        self.store.refresh()

        def find(text, flt=None):
            return [n["id"] for n in self.store.search(text, flt, 10)]
        self.assertEqual(len(find("preventiv")), 2, "parole parziali")
        self.assertEqual(find("preventivo budget"), ["2026-10-27-1000-kickoff"], "prima tutte le parole")
        self.assertEqual(find("cucina inesistente"), ["2026-10-28-giornata"], "poi almeno una")
        self.assertEqual(find("preventivo", Filter(person="@giul")), ["2026-10-28-giornata"])
        self.assertEqual(find("", Filter(project="clientex")), ["2026-10-27-1000-kickoff"])
        self.assertEqual(find("", Filter(date_from="2026-10-28", date_to="2026-10-28")), ["2026-10-28-giornata"])
        self.assertIn("«cucina»", self.store.search("cucina", None, 1)[0]["snippet"])

    def test_le_modifiche_esterne_si_vedono_con_refresh(self):
        self.write("a.md", "- [ ] uno\n")
        self.store.refresh()
        self.assertEqual(self.store.refresh(), 0, "senza modifiche non si reindicizza nulla")
        time.sleep(0.02)
        self.write("a.md", "- [ ] uno\n- [ ] due\n")
        self.assertEqual(self.store.refresh(), 1)
        self.assertEqual(len(self.store.actions(limit=10)), 2)
        os.remove(self.dir / "a.md")
        self.store.refresh()
        self.assertEqual(self.store.actions(limit=10), [])

    def test_azioni_decisioni_persone_e_collegamenti(self):
        self.write("2026/10/2026-10-27-1000-kickoff.md", OLD_MEETING)
        self.write("2026/10/2026-10-28-giornata.md", "---\ntype: daily\ntitle: Giornata\ndate: 2026-10-28\n---\n- [ ] Madre #casa\n    Una descrizione\n    - [x] Figlia done:2026-10-28\n")
        self.store.refresh()
        open_ = self.store.actions(limit=10)
        self.assertEqual(len(open_), 2)
        self.assertEqual(open_[0]["due"], "2026-10-31", "prima le azioni con scadenza")
        self.assertEqual(open_[1]["description"], "Una descrizione")
        child = next(a for a in self.store.actions(status="all", limit=10) if a["done"])
        self.assertEqual((child["parent_line"], child["done_on"]), (open_[1]["line"], "2026-10-28"))
        self.assertEqual(len(self.store.actions(owner="marco", limit=10)), 1)
        self.assertEqual(self.store.decisions(None, "budget", 10)[0]["text"], "Budget confermato")
        self.assertIn("Laura", [p["name"] for p in self.store.people()])
        self.assertTrue(any(p["name"] == "clientex" for p in self.store.projects()))
        self.assertEqual(self.store.backlinks("2026-10-28-giornata")[0]["note_id"], "2026-10-27-1000-kickoff")
        self.assertEqual(self.store.outgoing_links("2026-10-27-1000-kickoff")[0]["note_id"], "2026-10-28-giornata")

    def test_spunta_scrive_e_toglie_done(self):
        self.write("a.md", "- [ ] Rivedere il budget due:2026-11-02\n")
        self.store.refresh()
        self.assertTrue(self.store.set_action_status("a", "budget", d("2026-11-03"))["done"])
        self.assertEqual(self.text("a.md"), "- [x] Rivedere il budget due:2026-11-02 done:2026-11-03\n")
        self.store.set_action_status("a", "budget", None)
        self.assertEqual(self.text("a.md"), "- [ ] Rivedere il budget due:2026-11-02\n")
        with self.assertRaises(QuickNotesError):
            self.store.set_action_status("a", "niente", None)

    def test_chiudere_la_madre_conserva_le_date_delle_figlie(self):
        self.write("a.md", "- [ ] Madre\n    - [x] Già fatta done:2026-10-01\n    - [ ] Aperta\n- [ ] Altra\n")
        self.store.refresh()
        self.assertEqual(self.store.complete_with_children("a", 1, "- [ ] Madre", d("2026-11-03")), 2)
        self.assertEqual(self.text("a.md"), "- [x] Madre done:2026-11-03\n    - [x] Già fatta done:2026-10-01\n    - [x] Aperta done:2026-11-03\n- [ ] Altra\n")

    def test_dettagli_di_un_azione(self):
        line = "- [ ] Mandare a @Giulia la bozza #casa"
        self.write("a.md", line + "\n")
        self.store.refresh()
        self.store.set_action_details("a", 1, line, due="2026-11-06", person=(0, "Marco"), tag="lavoro",
                                      description="Allegare il foglio")
        self.assertEqual(self.text("a.md"), "- [ ] Mandare a @Marco la bozza #lavoro due:2026-11-06\n    Allegare il foglio\n")
        with self.assertRaises(StaleLine):
            self.store.set_action_details("a", 1, line)

    def test_aggiunte_alla_nota_e_alla_giornata(self):
        now = datetime(2026, 11, 3, 14, 30)
        note = self.store.append_to_daily("Telefonata", now, True)
        self.assertEqual(note.body, "- 14:30 Telefonata\n")
        note = self.store.append_to_daily("riga uno\nriga due", now, True)
        self.assertEqual(note.body, "- 14:30 Telefonata\n\n### 14:30\nriga uno\nriga due\n")
        note = self.store.add_to_section(note.id, "Priorità", "- [ ] Nuova")
        self.assertTrue(note.body.endswith("## Priorità\n- [ ] Nuova\n"))

    def test_un_file_non_utf8_non_ferma_gli_altri_e_reindex_ricostruisce(self):
        self.write("rotto.md", bytes([0xFF, 0xFE, 0x00]))
        self.write("ok.md", "#casa\n")
        self.assertEqual(self.store.refresh(), 1)
        self.assertEqual(self.store.reindex(), 1)
        self.assertEqual(self.store.projects()[0]["name"], "casa")

    def test_file_nascosti_e_temporanei_ignorati(self):
        self.write(".obsidian/x.md", "a")
        self.write(".tmp-1-n.md", "a")
        self.write("note.txt", "a")
        self.assertEqual(self.store.refresh(), 0)

    def test_non_tocca_gli_altri_indici(self):
        self.write(".quicknotes/index.db", "vecchio")
        self.write(".quicknotes/index-v3.db", "rust")
        NoteStore(self.dir).close()
        self.assertEqual((self.text(".quicknotes/index.db"), self.text(".quicknotes/index-v3.db")), ("vecchio", "rust"))
        self.assertTrue((self.dir / ".quicknotes/index-v4.db").exists())

    def test_salvataggio_con_conflitto(self):
        self.write("a.md", "uno\n")
        self.store.refresh()
        self.assertEqual(self.store.save_if_unchanged("a", "uno\n", "due\n"), {"status": "saved"})
        self.assertEqual(self.store.save_if_unchanged("a", "due\n", "due\n"), {"status": "saved"})
        self.write("a.md", "esterno\n")
        self.assertEqual(self.store.save_if_unchanged("a", "due\n", "mio\n"), {"status": "conflict", "disk": "esterno\n"})
        self.assertEqual(self.text("a.md"), "esterno\n")
        copy = self.store.save_conflict_copy("a", "mio\n", datetime(2026, 11, 3, 10, 0))
        self.assertEqual(self.store.read(copy.id).body, "mio\n")

    def test_refresh_elenca_solo_le_modifiche_esterne(self):
        self.write("a.md", "uno\n")
        self.assertEqual(self.store.refresh_changes(), ["a"])
        self.store.update_body("a", "due\n")
        self.assertEqual(self.store.refresh_changes(), [], "le scritture dell'app non contano")
        time.sleep(0.02)
        self.write("a.md", "tre\n")
        self.assertEqual(self.store.refresh_changes(), ["a"])
        os.remove(self.dir / "a.md")
        self.assertEqual(self.store.refresh_changes(), ["a"])

    def test_nuova_azione_con_scadenza_ed_etichetta_della_colonna(self):
        today = d("2026-11-03")
        self.store.add_action(today, "Chiamare l'idraulico", d("2026-11-05"), "casa")
        self.store.add_action(today, "Già datata due:2026-12-01 #lavoro", d("2026-11-05"), "casa")
        self.store.add_action(today, "Senza altro", None, None)
        text = self.text("2026/11/2026-11-03-giornata.md")
        self.assertIn("## Priorità\n- [ ] Chiamare l'idraulico #casa due:2026-11-05\n", text)
        self.assertIn("- [ ] Già datata due:2026-12-01 #lavoro\n", text)
        self.assertIn("- [ ] Senza altro\n", text)

    def test_azioni_completate_da_una_data(self):
        self.write("a.md", "- [x] Vecchia done:2026-10-01\n- [x] Nuova done:2026-11-05\n    - [x] Figlia done:2026-11-06\n"
                           "- [x] Senza data\n- [ ] Aperta\n")
        self.store.refresh()
        self.assertEqual(self.store.done_since("2026-11-05"), 2)
        self.assertEqual(self.store.done_since("2026-01-01"), 3)
        self.store.set_action_done("a", 5, "Aperta", d("2026-11-07"))
        self.assertEqual(self.store.done_since("2026-11-05"), 3)

    def test_priorita_dalla_bacheca_e_dalla_colonna(self):
        line = "- [ ] Preparare il budget #lavoro due:2026-11-06"
        self.write("a.md", line + "\n")
        self.store.refresh()
        self.store.set_action_details("a", 1, line, priority="alta")
        self.assertEqual(self.text("a.md"), "- [ ] Preparare il budget #lavoro prio:alta due:2026-11-06\n")
        self.assertEqual(self.store.actions()[0]["priority"], "alta")
        self.assertEqual(views.action_board(self.store, d("2026-11-03"))["items"][0]["priority"], "alta")
        self.assertEqual(views.action_board(self.store, d("2026-11-03"))["items"][0]["text"], "Preparare il budget")
        self.store.set_action_details("a", 1, None, priority=None)
        self.assertEqual(self.text("a.md"), line + "\n")
        today = d("2026-11-03")
        self.store.add_action(today, "Nuova", None, None, "bassa")
        self.store.add_action(today, "Scritta prio:alta", None, None, "bassa")
        text = self.text("2026/11/2026-11-03-giornata.md")
        self.assertIn("- [ ] Nuova prio:bassa\n- [ ] Scritta prio:alta\n", text)

    def test_sposta_a_domani_solo_le_azioni_in_ritardo_di_primo_livello(self):
        self.write("2026/11/a.md", "---\ntitle: A\ndate: 2026-11-01\n---\n- [ ] Vecchia #casa due:2026-11-01\n    - [ ] Figlia in ritardo due:2026-10-30\n- [ ] Futura due:2026-11-10\n- [x] Fatta due:2026-10-01 done:2026-10-02\n- [ ] Senza data\n")
        self.write("2026/11/b.md", "---\ntitle: B\ndate: 2026-11-02\n---\n- [ ] Altra in ritardo due:2026-11-02\n")
        self.store.refresh()
        moved, ids = self.store.postpone_late(d("2026-11-03"))
        self.assertEqual((moved, len(ids)), (2, 2))
        a = self.text("2026/11/a.md")
        self.assertIn("- [ ] Vecchia #casa due:2026-11-04\n", a)
        self.assertIn("    - [ ] Figlia in ritardo due:2026-10-30\n", a)
        self.assertIn("- [ ] Futura due:2026-11-10\n", a)
        self.assertIn("- [x] Fatta due:2026-10-01 done:2026-10-02\n", a)
        self.assertIn("- [ ] Altra in ritardo due:2026-11-04\n", self.text("2026/11/b.md"))
        self.assertEqual(self.store.postpone_late(d("2026-11-03"))[0], 0)

    def test_immagini_solo_dentro_la_cartella(self):
        note = self.store.create_note("Con immagine", "", "note")
        rel = self.store.save_image(note.id, b"\x89PNG\r\n\x1a\n" + b"0" * 30)
        self.assertTrue(rel.startswith("images/") and rel.endswith(".png"))
        folder = note.path.parent.relative_to(self.store.root).as_posix()
        self.assertIsNotNone(self.store.resolve_image(f"{folder}/{rel}"))
        self.assertIsNone(self.store.resolve_image("../fuori.png"))
        with self.assertRaises(QuickNotesError):
            self.store.save_image(note.id, b"non un'immagine")
        with self.assertRaises(NoteNotFound):
            self.store.read("assente")

    def test_chiusura_mentre_si_allinea_l_indice(self):
        import threading
        for i in range(30):
            self.write(f"n{i}.md", f"# Nota {i}\n- [ ] azione {i}\n")
        errors, stop = [], threading.Event()

        def watcher():
            # Come il thread che sorveglia la cartella: allinea finché l'app non esce.
            while not stop.is_set():
                try:
                    self.store.refresh_changes()
                    self.write("n0.md", f"# Nota 0\n{time.perf_counter()}\n")
                except Exception as e:  # noqa: BLE001
                    errors.append(e)
                    return
        t = threading.Thread(target=watcher)
        t.start()
        time.sleep(0.05)
        self.store.close()
        time.sleep(0.05)
        stop.set()
        t.join()
        self.assertEqual(errors, [])
        # Dopo la chiusura: niente allineamento, il salvataggio scrive comunque il file, la lettura lo dice.
        self.assertEqual(self.store.refresh_changes(), [])
        note = Note(self.dir / "n1.md", "# Nota 1\n")
        note.body = "# Nota 1\nscritta in chiusura\n"
        self.store.save(note)
        self.assertIn("scritta in chiusura", self.text("n1.md"))
        with self.assertRaises(QuickNotesError):
            self.store.list_notes()
        self.store.close = lambda: None  # tearDown la richiamerebbe

    def test_rinomina_cambia_titolo_file_e_link(self):
        when = datetime(2026, 11, 6, 10, 30)
        a = self.store.create_note("Meeting", "Testo\n", "meeting", when=when)
        self.store.create_note("Riunione", "", "meeting", when=when)
        ref = self.store.create_note("Rif", f"- [ ] vedi [[{a.id}|Meeting]] e [[{a.id}|mio]]\n```\n[[{a.id}]]\n```\n"
                                            f"![[{a.id}]]\n", "note", when=when)
        note, changed = self.store.rename(a.id, "  Riunione  ")
        # Il nome è già preso da un'altra nota: si aggiunge un numero.
        self.assertEqual((note.id, note.title), ("2026-11-06-1030-riunione-2", "Riunione"))
        self.assertFalse(a.path.exists())
        self.assertIn("title: Riunione\n", self.text("2026/11/2026-11-06-1030-riunione-2.md"))
        self.assertEqual(changed, [ref.id])
        # Il testo mostrato segue il titolo solo se era il titolo; codice e immagini restano come sono.
        self.assertEqual(self.store.read(ref.id).body, f"- [ ] vedi [[{note.id}|Riunione]] e [[{note.id}|mio]]\n"
                                                       f"```\n[[{a.id}]]\n```\n![[{a.id}]]\n")
        self.assertEqual({l["note_id"] for l in self.store.backlinks(note.id)}, {ref.id})
        self.assertEqual({n["id"] for n in self.store.list_notes()}, {note.id, ref.id, "2026-11-06-1030-riunione"})
        self.assertEqual(self.store.refresh(), 0)
        # Stesso nome di file: cambia solo il titolo.
        self.assertEqual(self.store.rename(note.id, "riunione!")[0].id, note.id)

    def test_rinomina_senza_frontmatter_e_per_titolo(self):
        self.write("Libera.md", "# Titolo libero\n\ncorpo\n")
        self.write("cita.md", "vedi [[Titolo libero]]\n")
        self.store.refresh()
        note, changed = self.store.rename("Libera", "Nuovo titolo")
        self.assertEqual((note.id, changed), ("nuovo-titolo", ["cita"]))
        self.assertEqual(self.text("nuovo-titolo.md"), "# Nuovo titolo\n\ncorpo\n")
        self.assertEqual(self.text("cita.md"), "vedi [[Nuovo titolo]]\n")
        with self.assertRaises(QuickNotesError):
            self.store.rename("nuovo-titolo", "   ")
        self.store.daily(d("2026-11-06"), True)
        with self.assertRaises(QuickNotesError):
            self.store.rename("2026-11-06-giornata", "Altro")

    def test_eliminare_porta_nel_cestino(self):
        a = self.store.create_note("Da buttare", "testo\n", "note")
        self.store.create_note("Da buttare", "altro\n", "note", when=datetime.now())
        self.assertFalse(self.store.trash(a.id, lambda p: False))
        self.assertEqual(self.text(f".quicknotes/cestino/{a.path.name}"), a.text())
        with self.assertRaises(NoteNotFound):
            self.store.read(a.id)
        self.assertNotIn(a.id, [n["id"] for n in self.store.list_notes()])
        # Il Cestino di Windows, quando c'è, prende il file al posto della cartella.
        b = self.store.list_notes()[0]["id"]
        self.assertTrue(self.store.trash(b, lambda p: p.unlink() is None))
        self.assertEqual(self.store.list_notes(), [])
        self.assertEqual(self.store.refresh(), 0)


class Viste(Base):
    def demo(self):
        self.write("2026-11-02-giornata.md", "---\ntype: daily\ntitle: G\ndate: 2026-11-02\n---\n- [ ] Madre @Giulia #casa due:2026-11-01\n    - [ ] Figlia @Marco due:2026-11-05\nTop in quarzo !decisione con @Marco\nVedi [[riunione]]\n")
        self.write("riunione.md", "---\ntype: meeting\ntitle: Riunione budget\ndate: 2026-11-03T10:00\npeople: [Giulia]\ntags: [casa]\n---\n- [x] Fatta done:2026-11-03\n")
        self.store.refresh()

    def with_recording(self):
        self.demo()
        self.write("budget.md", "---\ntype: meeting\ntitle: Budget Q4\ndate: 2026-10-28T15:00\n---\n🎙️ [Registrazione 15:02 (18:40)](audio/budget-150200.wav)\n\n"
                   "### Trascrizione 15:02\n[00:00] Punto della situazione sul budget.\n[12:40] Il budget per il quarto trimestre va diviso in tre tranche.\n\n"
                   "- [ ] Dividere il budget per mese @Giulia due:2026-11-02\n")
        self.store.refresh()

    def test_bacheca_con_gruppi_figlie_e_conteggi(self):
        self.write("a.md", "---\ntitle: Nota A\ndate: 2026-11-02\nproject: clientex\n---\n- [ ] Madre #casa due:2026-11-01\n    Descrizione\n    - [x] Figlia done:2026-11-02\n    - [ ] Altra due:2026-11-03\n"
                   "- [ ] Domani @Marco due:2026-11-04\n- [ ] Senza scadenza\n- [x] Fatta #casa done:2026-11-03\n- [x] Vecchia done:2026-01-01\n")
        self.store.refresh()
        board = views.action_board(self.store, d("2026-11-03"))
        self.assertEqual((board["open"], board["late"], board["done_this_week"], len(board["items"])), (3, 1, 1, 5))
        madre = next(i for i in board["items"] if i["text"] == "Madre")
        self.assertEqual((madre["group"], madre["tag"], madre["description"], len(madre["subs"])), ("late", "casa", "Descrizione", 2))
        self.assertEqual((madre["subs"][0]["text"], madre["subs"][1]["due_label"]), ("Figlia", "oggi"))
        domani = next(i for i in board["items"] if i["text"].startswith("Domani"))
        self.assertEqual((domani["group"], domani["people"], domani["tag"]), ("soon", ["Marco"], "clientex"))
        self.assertEqual(board["column_due"], {"soon": "2026-11-03", "week": "2026-11-05", "later": "2026-11-09"})

    def test_pagina_persona_con_figlie_e_madre(self):
        self.demo()
        p = views.person_page(self.store, "marco", d("2026-11-03"))
        self.assertEqual((p["name"], len(p["actions"]), p["actions"][0]["parent"]), ("Marco", 1, "Madre @Giulia #casa"))
        self.assertEqual(p["decisions"][0]["text"], "Top in quarzo  con @Marco")
        giulia = next(r for r in views.people_list(self.store, d("2026-11-03")) if r["name"] == "Giulia")
        self.assertEqual((giulia["notes"], giulia["open"], giulia["late"]), (2, 1, 1))

    def test_grafo_completo(self):
        self.demo()
        g = views.full_graph(self.store)
        find = {n["page"]: i for i, n in enumerate(g["nodes"])}
        daily, meeting = find["note:2026-11-02-giornata"], find["note:riunione"]
        self.assertEqual((g["nodes"][daily]["kind"], g["nodes"][daily]["label"]), ("daily", "Lunedì 2 novembre"))
        edges = {tuple(e) for e in g["edges"]}

        def has(a, b):
            return (min(a, b), max(a, b)) in edges
        self.assertTrue(has(daily, meeting))
        self.assertTrue(has(daily, find["person:Marco"]) and has(meeting, find["person:Giulia"]))
        self.assertTrue(has(meeting, find["tag:casa"]) and has(daily, find["tag:casa"]))
        self.assertEqual(sum(1 for n in g["nodes"] if n["kind"] == "person"), 2)

    def test_pagina_etichetta(self):
        self.demo()
        t = views.tag_page(self.store, "Casa", d("2026-11-03"))
        self.assertEqual((t["tag"], t["notes_count"], len(t["actions"])), ("casa", 2, 1))
        self.assertEqual(t["actions"][0]["raw"], "Madre @Giulia #casa due:2026-11-01")
        self.assertEqual(len(t["actions"][0]["subs"]), 1)
        self.assertIn("Giulia", t["people"])

    def test_calendario_per_giorno(self):
        self.demo()
        c = views.calendar_data(self.store, "2026-11-01", "2026-11-30", d("2026-11-03"))
        self.assertEqual(c["2026-11-02"]["daily"], "2026-11-02-giornata")
        self.assertEqual(c["2026-11-01"]["events"][0]["kind"], "late")
        self.assertEqual(c["2026-11-05"]["events"][0]["kind"], "due")
        kinds = [e["kind"] for e in c["2026-11-03"]["events"]]
        self.assertTrue("note" in kinds and "done" in kinds)

    def test_ricerca_con_filtri(self):
        self.demo()

        def labels(q):
            return [h["label"] for h in views.search_all(self.store, q, d("2026-11-03"))]
        self.assertEqual(labels("riunion")[:2], ["Riunione budget", "Lunedì 2 novembre"])
        self.assertEqual(labels("!quarzo"), ["Top in quarzo  con @Marco"])
        self.assertIn("@Giulia", labels("@gi"))
        self.assertIn("#casa", labels("#ca"))
        self.assertEqual(labels("riunione @Giulia #casa")[0], "Riunione budget")

    def test_registrazioni_nel_calendario(self):
        self.with_recording()
        c = views.calendar_data(self.store, "2026-10-26", "2026-11-08", d("2026-11-03"))
        rec = [e for e in c["2026-10-28"]["events"] if e["kind"] == "rec"]
        self.assertEqual(len(rec), 1)
        self.assertEqual((rec[0]["text"], rec[0]["note_id"], rec[0]["line"]), ("Registrazione 15:02 (18:40)", "budget", 1))

    def test_ricerca_in_azioni_decisioni_e_trascrizioni(self):
        self.with_recording()
        today = d("2026-11-03")
        t = next(h for h in views.search_all(self.store, "budget trimestre", today) if h["kind"] == "transcript")
        self.assertEqual((t["hint"], t["line"], t["page"]), ("12:40", 5, "note:budget"))
        self.assertEqual(t["snippet"], "Budget Q4 · Trascrizione 15:02")
        self.assertIn("quarto trimestre", t["label"])
        a = next(h for h in views.search_all(self.store, "budget mese", today) if h["kind"] == "action")
        self.assertEqual((a["label"], a["hint"], a["level"], a["line"]), ("Dividere il budget per mese @Giulia", "2 nov", "late", 7))
        self.assertTrue(all(h["kind"] != "action" for h in views.search_all(self.store, "budget @Marco", today)))
        self.assertTrue(any(h["kind"] == "decision" and h["line"] == 3 for h in views.search_all(self.store, "quarzo", today)))
        self.assertEqual(views.excerpt("uno due tre quattro cinque sei sette otto nove dieci", "otto", 20), "…sette otto nove…")
        self.assertEqual(views.excerpt("abcdefghij klmnopqrst uvwxyz", "uvw", 12), "…uvwxyz")


if __name__ == "__main__":
    unittest.main()
