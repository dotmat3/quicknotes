"""Logica dell'interfaccia web (senza grafica): elenchi, bozze, salvataggio e conflitti."""

import os

import pytest

from quicknotes import service
from quicknotes.store import NoteStore


@pytest.fixture
def store(tmp_path):
    s = NoteStore(tmp_path / "notes")
    yield s
    s.close()


def test_empty_draft_is_not_created(store):
    draft = service.draft_payload("meeting")
    assert service.save_note(store, {**draft, "people": []}) == {"status": "empty"}
    assert store.list_notes() == []


def test_draft_becomes_note(store):
    draft = service.draft_payload("meeting")
    res = service.save_note(store, {**draft, "title": "Kickoff", "people": ["Marco"], "project": "#clientex",
                                    "body": "- [ ] @Marco invia preventivo"})
    assert res["status"] == "saved"
    note = store.read(res["note"]["id"])
    assert (note.title, note.type, note.people, note.project) == ("Kickoff", "meeting", ["Marco"], "clientex")
    assert [p["name"] for p in res["note"]["people"]] == ["Marco"]


def test_save_detects_external_change(store):
    note = store.create_note("Kickoff", "testo", "meeting")
    loaded = service.note_payload(note)
    st = note.path.stat()
    os.utime(note.path, (st.st_atime, st.st_mtime + 5))  # modificata altrove dopo il caricamento
    data = {**loaded, "people": [], "body": "mia versione"}
    res = service.save_note(store, data)
    assert res["status"] == "conflict" and res["disk"]["body"] == "testo\n"
    assert service.save_note(store, data, force=True)["status"] == "saved"
    assert store.read(note.id).body == "mia versione"


def test_changed_on_disk(store):
    note = store.create_note("Kickoff", "testo", "meeting")
    mtime = service.note_payload(note)["mtime"]
    assert service.changed_on_disk(store, note.id, mtime) is None
    st = note.path.stat()
    os.utime(note.path, (st.st_atime, st.st_mtime + 5))
    assert service.changed_on_disk(store, note.id, mtime)["id"] == note.id


def test_lists_and_nav(store):
    store.create_note("Kickoff", "- [ ] @Marco invia preventivo due:2020-01-01", "meeting", ["Marco"], "clientex")
    store.create_note("Idee", "testo libero", "note")
    assert [n["title"] for n in service.note_items(store, "meeting")] == ["Kickoff"]
    assert [n["title"] for n in service.note_items(store, "all", "#clientex")] == ["Kickoff"]
    actions = service.action_items(store)
    assert actions[0]["level"] == "danger" and actions[0]["section"] == "Scadute"
    nav = {n["key"]: n for n in service.nav_items(store)}
    assert nav["actions"]["alert"] and nav["project:clientex"]["group"] == "Progetti"
