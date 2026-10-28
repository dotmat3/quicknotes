"""Parti dell'app che non richiedono la finestra: icona, istanza singola, eliminazione, posizione."""

import json
import time

import pytest

from quicknotes import app, service
from quicknotes.icons import app_icon, write_ico
from quicknotes.store import NoteStore


@pytest.fixture
def store(tmp_path):
    s = NoteStore(tmp_path / "notes")
    yield s
    s.close()


def test_icons(tmp_path):
    assert app_icon(False, 64).size == (64, 64)
    assert app_icon(True, 64).getpixel((32, 32))[:3] == (255, 255, 255)  # pallino bianco mentre registra
    ico = write_ico(tmp_path / "a.ico")
    assert ico.read_bytes()[:4] == b"\x00\x00\x01\x00"


def test_single_instance_forwards_commands(monkeypatch, tmp_path):
    address = (rf"\\.\pipe\quicknotes-test-{time.time_ns()}" if app.sys.platform == "win32"
               else str(tmp_path / "qn.sock"))
    monkeypatch.setattr(app, "ADDRESS", address)
    assert not app.send_to_running_instance("new")
    received = []
    listener = app.listen_for_commands(received.append)
    try:
        assert app.send_to_running_instance("new")
        assert app.send_to_running_instance("qualcosa")  # comando sconosciuto: mostra la finestra
        end = time.monotonic() + 3
        while len(received) < 2 and time.monotonic() < end:
            time.sleep(0.02)
        assert received == ["new", "show"]
    finally:
        listener.close()


def test_delete_moves_note_and_audio_to_trash(store, monkeypatch):
    note = store.create_note("Kickoff", "testo", "meeting")
    audio = note.path.parent / "audio" / f"{note.id}-101500.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"RIFF")
    assert service.delete_info(store, note.id) == {"id": note.id, "title": "Kickoff", "audio": 1}
    trashed = []
    monkeypatch.setattr(service, "move_to_trash", lambda p: (trashed.append(p.name), p.unlink()))
    assert service.delete_note(store, note.id) == {"status": "deleted"}
    assert trashed == [note.path.name, audio.name]
    assert store.list_notes() == []
    assert service.delete_note(store, note.id) == {"status": "missing"}


def test_delete_without_trash_asks_for_permanent(store, monkeypatch):
    note = store.create_note("Kickoff", "testo", "meeting")

    def no_trash(_path):
        raise OSError("Cestino non disponibile")
    monkeypatch.setattr(service, "move_to_trash", no_trash)
    assert service.delete_note(store, note.id) == {"status": "no-trash"}
    assert note.path.exists()
    assert service.delete_note(store, note.id, permanent=True) == {"status": "deleted"}
    assert not note.path.exists()


def test_geometry_ignores_garbage(monkeypatch, tmp_path):
    path = tmp_path / "window.json"
    monkeypatch.setattr(app, "GEOMETRY_FILE", path)
    assert app.load_geometry() == {}
    path.write_text("non json")
    assert app.load_geometry() == {}
    path.write_text(json.dumps({"width": 100, "height": 2000, "x": 99999, "y": 5}))
    geo = app.load_geometry()
    assert geo["width"] == app.MIN_SIZE[0] and geo["height"] == 2000 and "x" not in geo
