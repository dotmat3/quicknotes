import datetime as dt

import pytest

from quicknotes import parser
from quicknotes.store import NoteNotFound, NoteStore

BODY = """Riunione di avvio con @Marco e @laura.bianchi per #clientex.

- Budget confermato a 50k !decisione
- Il sito email@esempio.it non e' una persona, e [link](file.md#ancora) non e' un tag
- [ ] @Marco invia preventivo due:2026-10-31
- [x] @Laura condivide le slide
- [ ] Prenotare sala per la demo

```
- [ ] dentro un blocco di codice: da ignorare #nontag
```
"""


@pytest.fixture
def store(tmp_path):
    s = NoteStore(tmp_path / "notes")
    yield s
    s.close()


def test_extract_conventions():
    ex = parser.extract(BODY)
    assert ex.people == ["Marco", "laura.bianchi", "Laura"]
    assert ex.tags == ["clientex"]
    assert [a.text for a in ex.actions] == [
        "@Marco invia preventivo due:2026-10-31", "@Laura condivide le slide", "Prenotare sala per la demo"]
    assert ex.actions[0].owner == "Marco" and ex.actions[0].due == "2026-10-31"
    assert ex.actions[1].done and not ex.actions[2].done and ex.actions[2].owner is None
    assert [d.text for d in ex.decisions] == ["Budget confermato a 50k"]


def test_frontmatter_roundtrip():
    meta = {"type": "meeting", "title": "Prova: due punti", "people": ["Marco"], "project": ""}
    text = parser.render(meta, "corpo\n")
    back, body = parser.split_frontmatter(text)
    assert back == {"type": "meeting", "title": "Prova: due punti", "people": ["Marco"]}
    assert body == "corpo\n"


def test_create_search_and_filters(store):
    when = dt.datetime(2026, 10, 27, 10, 0)
    note = store.create_note("Kickoff Cliente X", BODY, people=["Marco Rossi"], project="ClienteX", when=when)
    assert note.id == "2026-10-27-1000-kickoff-cliente-x"
    assert note.path.exists() and note.path.parent.name == "10"
    store.create_note("Retro sprint", "Discussione sul deploy con @Giulia", when=when.replace(day=20))

    hits = store.search("preventivo")
    assert [h["id"] for h in hits] == [note.id] and "«preventivo»" in hits[0]["snippet"]
    assert store.search("preven")  # prefisso
    assert [h["id"] for h in store.search("budget astronave")] == [note.id]  # fallback in OR
    assert store.search("", person="marco")[0]["id"] == note.id
    assert store.search("deploy", project="clientex") == []
    assert len(store.list_notes(date_from="2026-10-21")) == 1
    assert store.search("ClienteX")  # tag e progetto indicizzati


def test_actions_decisions_and_toggle(store):
    note = store.create_note("Kickoff", BODY, when=dt.datetime(2026, 10, 27, 9, 30))
    open_actions = store.actions()
    assert [a["text"] for a in open_actions][0].startswith("@Marco invia")  # con scadenza prima
    assert len(open_actions) == 2
    assert len(store.actions(owner="marco")) == 1
    assert len(store.actions(due_before="2026-11-01")) == 1
    assert store.decisions()[0]["text"] == "Budget confermato a 50k"

    res = store.set_action_status(note.id, "preventivo", True)
    assert res["done"] and "[x]" in store.read(note.id).body.splitlines()[res["line"] - 1]
    assert len(store.actions()) == 1
    with pytest.raises(NoteNotFound):
        store.set_action_status(note.id, "inesistente", True)


def test_daily_and_append(store):
    d1 = store.daily("2026-10-27")
    assert d1.id == "2026-10-27-giornata" and "martedì" in d1.title
    store.append_to_daily("Chiamata con @Paolo", day="2026-10-27")
    store.append_to_daily("Riga uno\nRiga due", day="2026-10-27")
    body = store.read(d1.id).body
    assert "Chiamata con @Paolo" in body and "### " in body
    assert store.daily("2026-10-27").id == d1.id  # non duplica
    assert store.people()[0]["name"] == "Paolo"


def test_external_edits_are_indexed(store):
    folder = store.root / "importate"
    folder.mkdir()
    (folder / "2025-01-15-vecchia.md").write_text("# Nota esterna\n\nParliamo di #budget con @Anna\n", encoding="utf-8")
    hits = store.search("esterna")
    assert hits and hits[0]["title"] == "Nota esterna" and hits[0]["date"] == "2025-01-15"
    (folder / "2025-01-15-vecchia.md").unlink()
    assert store.search("esterna") == []


def test_unique_ids(store):
    when = dt.datetime(2026, 10, 27, 10, 0)
    a = store.create_note("Stesso titolo", when=when)
    b = store.create_note("Stesso titolo", when=when)
    assert a.id != b.id and b.id.endswith("-2")


def test_index_rebuild(tmp_path):
    s = NoteStore(tmp_path)
    s.create_note("Persistente", "contenuto unico zebra")
    s.close()
    (tmp_path / ".quicknotes" / "index.db").unlink()
    for extra in ("-wal", "-shm"):
        p = tmp_path / ".quicknotes" / f"index.db{extra}"
        if p.exists():
            p.unlink()
    s2 = NoteStore(tmp_path)
    assert s2.search("zebra")
    s2.close()


def test_delete_removes_note_audio_and_index(store):
    note = store.create_note("Da buttare", "- [ ] azione orfana", "meeting")
    other = store.create_note("Da buttare 2", "testo")
    audio = note.path.parent / "audio"
    audio.mkdir()
    mine = audio / f"{note.id}-101500.wav"
    theirs = audio / f"{other.id}-101500.wav"
    mine.write_bytes(b"x")
    theirs.write_bytes(b"x")
    removed = store.delete(note.id)
    assert removed == [note.path, mine]
    assert not note.path.exists() and not mine.exists() and theirs.exists()
    with pytest.raises(NoteNotFound):
        store.read(note.id)
    assert store.actions("open") == []
    assert [r["id"] for r in store.list_notes()] == [other.id]
