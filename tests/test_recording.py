"""Registrazione e trascrizione con microfono e Whisper simulati."""

import sys
import types
import wave

import pytest

np = pytest.importorskip("numpy")

from quicknotes.config import Config  # noqa: E402
from quicknotes.recording import Recordings  # noqa: E402
from quicknotes.store import NoteStore  # noqa: E402


class FakeStream:
    def __init__(self, samplerate, channels, dtype, callback):
        self.callback, self.rate = callback, samplerate

    def start(self):
        # 1,5 secondi di tono a 440 Hz
        t = np.arange(int(self.rate * 1.5)) / self.rate
        data = (np.sin(2 * np.pi * 440 * t) * 8000).astype("int16").reshape(-1, 1)
        for i in range(0, len(data), 1600):
            chunk = data[i:i + 1600]
            self.callback(chunk, len(chunk), None, None)

    def stop(self):
        pass

    def close(self):
        pass


class FakeModel:
    def __init__(self, *a, **k):
        pass

    def transcribe(self, path, **kwargs):
        seg = types.SimpleNamespace
        segs = [seg(start=0.0, end=40.0, text=" Buongiorno a tutti."),
                seg(start=40.0, end=75.0, text=" Confermiamo il budget."),
                seg(start=75.0, end=90.0, text=" A presto.")]
        return iter(segs), types.SimpleNamespace(duration=90.0)


@pytest.fixture
def rec(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(
        InputStream=FakeStream, query_devices=lambda kind=None: {"default_samplerate": 44100}))
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    store = NoteStore(tmp_path / "notes")
    events, looks = [], []
    r = Recordings(Config(notes_dir=str(tmp_path / "notes"), hotkeys={}), store,
                   lambda name, data: events.append((name, data)), looks.append)
    r.events, r.looks = events, looks
    yield r
    for t in list(r.threads):
        t.join(5)
    store.close()


def test_record_and_transcribe(rec):
    note = rec.store.create_note("Kickoff", "testo", "meeting")
    status = rec.start(note.id)
    assert status["recording"] and status["noteId"] == note.id and rec.looks == [True]
    rec.recorder.started_at -= 5  # simula 5 secondi di registrazione
    stopped = rec.stop()
    assert rec.looks == [True, False] and not rec.recording
    assert stopped["noteId"] == note.id
    assert stopped["text"].startswith("🎙️ [Registrazione ") and "](audio/" in stopped["text"]

    for t in list(rec.threads):
        t.join(5)
    appended = [d for name, d in rec.events if name == "append"]
    assert appended == [{"noteId": note.id, "heading": appended[0]["heading"],
                         "text": "[00:00] Buongiorno a tutti. Confermiamo il budget.\n\n[01:15] A presto."}]
    assert appended[0]["heading"].startswith("Trascrizione ")
    progress = [d for name, d in rec.events if name == "transcription"]
    assert progress[0] == {"active": True, "percent": 0} and progress[-1] == {"active": False, "percent": 0}

    wav_path = next(rec.store.root.rglob("*.wav"))
    with wave.open(str(wav_path)) as w:
        assert w.getframerate() == 16000 and w.getnframes() == 24000


def test_short_recording_is_not_transcribed(rec):
    note = rec.store.create_note("Kickoff", "", "meeting")
    rec.start(note.id)
    assert rec.stop()["noteId"] == note.id
    assert not rec.threads and not [e for e in rec.events if e[0] == "transcription"]


def test_stop_without_recording(rec):
    assert rec.stop() is None


def test_transcription_error_becomes_dialog(rec, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("modello non trovato")
    monkeypatch.setattr(rec.transcriber, "transcribe", boom)
    note = rec.store.create_note("Kickoff", "", "meeting")
    rec.start(note.id)
    rec.recorder.started_at -= 5
    rec.stop()
    for t in list(rec.threads):
        t.join(5)
    dialogs = [d for name, d in rec.events if name == "dialog"]
    assert "modello non trovato" in dialogs[0]["text"] and ".wav" in dialogs[0]["text"]
