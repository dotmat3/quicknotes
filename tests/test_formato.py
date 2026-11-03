"""Formato delle note, modifiche alle righe e date: gli stessi casi delle prove della versione Rust."""

import unittest
from datetime import date

from quicknotes import dates, edit, parser
from quicknotes.parser import extract, mentions, split_frontmatter, tags


def d(s: str) -> date:
    return dates.parse_day(s)


class Parser(unittest.TestCase):
    def test_registrazioni_e_trascrizioni(self):
        body = ("Intro\n🎙️ [Registrazione 9:42 (12:30)](audio/n-094200.wav)\n\n### Trascrizione 09:42\n"
                "[00:00] Allora, il budget.\n[01:12] Tre tranche mensili.\n\n## Note\n[02:00] Fuori dalla trascrizione\n"
                "```\n[Registrazione 10:00](x.wav)\n```\n### Trascrizione 16:05\n[1:02:03] Lunga\n")
        r = parser.recordings(body)
        self.assertEqual(len(r), 2)
        self.assertEqual((r[0].time, r[0].duration, r[0].file, r[0].transcribed), ("09:42", "12:30", "audio/n-094200.wav", True))
        self.assertEqual((r[1].time, r[1].file, r[1].transcribed), ("16:05", None, True))
        t = parser.transcript_lines(body)
        self.assertEqual(len(t), 4)
        self.assertEqual((t[0].time, t[0].stamp, t[0].text), ("09:42", "00:00", "Allora, il budget."))
        self.assertIsNone(t[2].time, "un altro titolo chiude la trascrizione")
        self.assertEqual((t[3].time, t[3].stamp), ("16:05", "1:02:03"))

    def test_frontmatter_conservato_e_separato(self):
        raw, meta, body = split_frontmatter("---\ntype: meeting\ntitle: Kickoff\npeople: [Marco, Laura]\n---\nCorpo\n")
        self.assertEqual(body, "Corpo\n")
        self.assertEqual(raw, "---\ntype: meeting\ntitle: Kickoff\npeople: [Marco, Laura]\n---\n")
        self.assertEqual(parser.meta_str(meta, "title"), "Kickoff")
        self.assertEqual(parser.meta_list(meta, "people"), ["Marco", "Laura"])

    def test_frontmatter_con_a_capo_windows_e_date(self):
        _, meta, body = split_frontmatter("---\r\ntitle: A\r\ndate: 2026-10-27\r\n---\r\nCorpo\r\n")
        self.assertEqual(body, "Corpo\r\n")
        self.assertEqual(parser.meta_str(meta, "title"), "A")
        self.assertEqual(meta["date"], "2026-10-27", "la data resta testo")

    def test_frontmatter_non_valido_resta_nel_corpo(self):
        for text in ["---\n: : [\n---\nx\n", "---\nnon chiuso\n", "--- no\ntitle: x\n---\n", "---\n- a\n---\nx"]:
            raw, _, body = split_frontmatter(text)
            self.assertEqual(body, text)
            self.assertEqual(raw, "")

    def test_frontmatter_riscritto_senza_virgolette_sulle_date(self):
        text = parser.render_frontmatter({"type": "daily", "title": "Giornata", "date": "2026-11-03", "people": []})
        self.assertEqual(text, "---\ntype: daily\ntitle: Giornata\ndate: 2026-11-03\n---\n")

    def test_persone(self):
        self.assertEqual(mentions("@Marco e @laura.b, @a @è-x"), ["Marco", "laura.b", "a", "è-x"])
        self.assertEqual(mentions("mail@example.com .@no @@no"), [])
        self.assertEqual(mentions("(@Marco.) @Giulia-"), ["Marco", "Giulia"])
        self.assertEqual(mentions("@ - @-x"), [])

    def test_etichette(self):
        self.assertEqual(tags("#casa #lavoro-q4 #a/b (#città)"), ["casa", "lavoro-q4", "a/b", "città"])
        self.assertEqual(tags("# titolo ## due #1 x#y a/#z &#39; ##w"), [])
        self.assertEqual(tags("#_ok"), ["_ok"])

    def test_azioni_con_scadenza_e_completamento(self):
        ex = extract("- [ ] @Marco invia preventivo #Casa due:2026-10-31\n* [x] fatta done:2026-11-01 entro: 2026-10-01\n- [ ]   \n")
        self.assertEqual(len(ex.actions), 2)
        a, b = ex.actions
        self.assertEqual((a.line_no, a.done, a.owner, a.due, a.tags), (1, False, "Marco", "2026-10-31", ["casa"]))
        self.assertEqual((b.done, b.done_on, b.due), (True, "2026-11-01", "2026-10-01"))

    def test_sotto_attivita_e_descrizione(self):
        body = ("- [ ] Madre #casa\n    Prima riga\n    Seconda riga\n    - [x] Figlia done:2026-11-01\n"
                "\t- [ ] Con tab\n        - [ ] Più interna\n- [ ] Altra\n")
        by = {a.line_no: a for a in extract(body).actions}
        self.assertIsNone(by[1].parent_line)
        self.assertEqual(by[1].description, "Prima riga\nSeconda riga")
        self.assertEqual([by[n].parent_line for n in (4, 5, 6)], [1, 1, 1])
        self.assertIsNone(by[7].parent_line)

    def test_figlia_senza_madre_e_interruzioni(self):
        ex = extract("    - [ ] Senza madre\n- Punto normale\n    - [ ] Sotto un punto\nTesto\n- [ ] A\nTesto\n    - [ ] Dopo il testo\n")
        self.assertTrue(all(a.parent_line is None for a in ex.actions))

    def test_la_descrizione_non_cambia_la_persona_dell_azione(self):
        ex = extract("- [ ] Azione\n    chiedere a @Elena #x\n\n    fuori dalla descrizione\n")
        self.assertEqual(ex.actions[0].description, "chiedere a @Elena #x")
        self.assertEqual((ex.actions[0].people, ex.actions[0].tags), ([], []))
        self.assertEqual(ex.people, ["Elena"])

    def test_blocchi_di_codice_ignorati(self):
        ex = extract("```\n- [ ] no @no #no !decisione [[no]]\n```\n- [ ] sì\n~~~\n# no\n~~~\n")
        self.assertEqual(len(ex.actions), 1)
        self.assertFalse(ex.people or ex.tags or ex.decisions or ex.links or ex.headings)

    def test_decisioni(self):
        ex = extract("- Budget confermato !decisione\n!Dec - Top in quarzo\n!decisionex no\n!decisione\n")
        self.assertEqual([x.text for x in ex.decisions], ["Budget confermato", "Top in quarzo"])

    def test_collegamenti_e_incorporamenti(self):
        ex = extract("Vedi [[2026-id|Titolo]] e [[Altra]] e [[]] ![[schizzo.excalidraw]] [[aperto\n")
        self.assertEqual([(l.target, l.label) for l in ex.links], [("2026-id", "Titolo"), ("Altra", None)])
        self.assertEqual([(e.line_no, e.target) for e in ex.embeds], [(1, "schizzo.excalidraw")])

    def test_link_markdown_ed_elementi_unici(self):
        ex = extract("[testo](file.md#ancora) [a](mailto:x@y.it)\n")
        self.assertFalse(ex.tags or ex.people)
        ex = extract("@Marco @marco #Casa #casa\n")
        self.assertEqual((ex.people, ex.tags), (["Marco"], ["casa"]))

    def test_slug_testo_e_titolo(self):
        self.assertEqual(parser.slugify("Città & Più: Kickoff_cliente  X!"), "citta-piu-kickoff-cliente-x")
        self.assertEqual(parser.slugify("🎙️"), "nota")
        self.assertLessEqual(len(parser.slugify("a" * 80)), 50)
        self.assertEqual(parser.action_display_text("Chiamare @Marco  due:2026-01-01 done:2026-01-02 ora"), "Chiamare @Marco ora")
        self.assertEqual(parser.first_h1("```\n# no\n```\n## no\n# Sì \n"), "Sì")


class Modifiche(unittest.TestCase):
    def test_done(self):
        self.assertEqual(edit.with_done("    - [x] Fatta", "2026-11-01"), "    - [x] Fatta done:2026-11-01")
        self.assertEqual(edit.with_done("    - [ ] Fatta done:2026-11-01 ora", None), "    - [ ] Fatta ora")
        self.assertEqual(edit.with_done("- [x] A done:2026-01-01", "2026-02-02"), "- [x] A done:2026-02-02")

    def test_due_sta_prima_di_done(self):
        self.assertEqual(edit.with_due("- [x] A done:2026-01-01", "2026-02-02"), "- [x] A due:2026-02-02 done:2026-01-01")
        self.assertEqual(edit.with_due("- [ ] A due:2026-01-01 #x", "2026-02-02"), "- [ ] A #x due:2026-02-02")
        self.assertEqual(edit.with_due("- [ ] A entro: 2026-01-01", None), "- [ ] A")

    def test_spunta_e_riapertura(self):
        self.assertEqual(edit.with_checked("  - [ ] A due:2026-01-01", "2026-11-03"), "  - [x] A due:2026-01-01 done:2026-11-03")
        self.assertEqual(edit.with_checked("* [X] A done:2026-11-03", None), "* [ ] A")
        self.assertEqual(edit.with_checked("testo senza casella", None), "testo senza casella")

    def test_persona_sostituita_al_suo_posto(self):
        l = "- [ ] Mandare a @Giulia la bozza #casa due:2026-11-02"
        self.assertEqual(edit.with_person(l, 0, "@Marco"), "- [ ] Mandare a @Marco la bozza #casa due:2026-11-02")
        self.assertEqual(edit.with_person(l, 1, "Elena"), "- [ ] Mandare a @Giulia la bozza #casa @Elena due:2026-11-02")
        self.assertEqual(edit.with_person(l, 0, None), "- [ ] Mandare a la bozza #casa due:2026-11-02")
        self.assertEqual(edit.with_person("- [ ] A", 0, "B"), "- [ ] A @B")
        self.assertEqual(edit.with_person("- [ ] A @x @y", 1, None), "- [ ] A @x")
        self.assertEqual(edit.with_person("- [ ] A", 3, None), "- [ ] A")

    def test_etichetta_lascia_invariate_le_altre(self):
        self.assertEqual(edit.with_tag("- [ ] A #a #b", "c"), "- [ ] A #c #b")
        self.assertEqual(edit.with_tag("- [ ] A #a #b", None), "- [ ] A #b")
        self.assertEqual(edit.with_tag("- [ ] A done:2026-01-01", "#Nuova etichetta"), "- [ ] A #Nuova-etichetta done:2026-01-01")

    def test_descrizione_scritta_prima_delle_figlie(self):
        b = "- [ ] A\n    vecchia\n    riga\n    - [ ] figlia\n- [ ] B\n"
        self.assertEqual(edit.with_description(b, 1, "nuova\n\naltra"), "- [ ] A\n    nuova\n    altra\n    - [ ] figlia\n- [ ] B\n")
        self.assertEqual(edit.with_description(b, 1, ""), "- [ ] A\n    - [ ] figlia\n- [ ] B\n")
        self.assertEqual(edit.with_description("  - [ ] A", 1, "x"), "  - [ ] A\n      x")
        self.assertEqual(edit.with_description(b, 99, "x"), b)

    def test_sezione_assente_o_nota_vuota(self):
        self.assertEqual(edit.add_to_section("", "Note", "x"), "## Note\nx\n")
        self.assertEqual(edit.add_to_section("testo\n", "Note", "x\n"), "testo\n\n## Note\nx\n")
        self.assertEqual(edit.add_to_section("", None, "x"), "x\n")
        self.assertEqual(edit.add_to_section("testo\n\n", None, "x"), "testo\n\nx\n")

    def test_sezione_esistente(self):
        b = "## Note\na\n\n## Altro\nb\n"
        self.assertEqual(edit.add_to_section(b, "note", "x"), "## Note\na\nx\n\n## Altro\nb\n")
        self.assertEqual(edit.add_to_section("## Note\n\n\n", "NOTE", "x"), "## Note\nx\n")
        self.assertEqual(edit.add_to_section("## N\n### sotto\na\n# Dopo\n", "N", "x"), "## N\n### sotto\na\nx\n# Dopo\n")

    def test_titoli_nei_blocchi_di_codice_ignorati(self):
        b = "```\n## Note\n```\n## Note\n```\n# no\n```\n"
        self.assertEqual(edit.add_to_section(b, "Note", "x"), "```\n## Note\n```\n## Note\n```\n# no\n```\nx\n")


class Date(unittest.TestCase):
    def test_titoli(self):
        self.assertEqual(dates.daily_title(d("2026-11-01")), "Domenica 1 novembre")
        self.assertEqual(dates.daily_file_title(d("2026-11-01")), "Giornata di domenica 01/11/2026")

    def test_etichette(self):
        t = d("2026-11-01")
        self.assertEqual(dates.due_label(d("2026-10-30"), t), ("30 ott", "late"))
        self.assertEqual(dates.due_label(t, t), ("oggi", "soon"))
        self.assertEqual(dates.due_label(d("2026-11-02"), t), ("domani", "soon"))
        self.assertEqual(dates.due_label(d("2026-11-04"), t), ("mer 4 nov", "normal"))

    def test_gruppi(self):
        sunday, monday = d("2026-11-01"), d("2026-11-02")
        self.assertEqual(dates.due_group(d("2026-11-02"), sunday), "soon")
        self.assertEqual(dates.due_group(d("2026-11-03"), sunday), "later", "di domenica la settimana è finita")
        self.assertEqual(dates.due_group(d("2026-11-08"), monday), "week")
        self.assertEqual(dates.due_group(d("2026-11-09"), monday), "later")
        self.assertEqual(dates.due_group(d("2026-11-01"), monday), "late")
        self.assertEqual(dates.due_group(None, monday), "none")
        self.assertEqual(dates.due_group(d("2027-01-01"), d("2026-12-25")), "later")

    def test_primo_giorno_di_ogni_colonna(self):
        monday = d("2026-11-02")
        self.assertEqual(dates.first_day_in("soon", monday), monday)
        self.assertEqual(dates.first_day_in("week", monday), d("2026-11-04"))
        self.assertEqual(dates.first_day_in("later", monday), d("2026-11-09"))
        self.assertIsNone(dates.first_day_in("late", monday))
        self.assertIsNone(dates.first_day_in("none", monday))
        saturday = d("2026-11-07")
        self.assertIsNone(dates.first_day_in("week", saturday), "di sabato dopodomani è già lunedì")
        self.assertEqual(dates.first_day_in("later", saturday), d("2026-11-09"))
        self.assertEqual(dates.first_day_in("later", d("2026-11-08")), d("2026-11-10"))


if __name__ == "__main__":
    unittest.main()
