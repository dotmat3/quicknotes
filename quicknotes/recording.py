"""Registrazione collegata a una nota e trascrizione in background, senza grafica.

Gli avvisi per l'interfaccia passano da `emit(evento, dati)`:
    transcription   {"active": bool, "percent": int}
    append          {"noteId", "text", "heading"}   testo da aggiungere alla nota (trascrizione)
    toast           {"text", "icon"}
    dialog          {"title", "text"}
e `on_recording(bool)` cambia l'aspetto dell'icona dell'app mentre si registra.
"""

from __future__ import annotations

import datetime as dt
import threading
from pathlib import Path
from typing import Callable

from .audio import AudioUnavailable, Recorder, Transcriber, format_duration
from .config import Config
from .store import NoteStore


class Recordings:
    def __init__(self, cfg: Config, store: NoteStore, emit: Callable[[str, dict], None],
                 on_recording: Callable[[bool], None] = lambda _on: None):
        self.cfg, self.store, self.emit, self.on_recording = cfg, store, emit, on_recording
        self.recorder = Recorder()
        self.transcriber = Transcriber(cfg.whisper_model, cfg.language)
        self.note_id: str | None = None
        self.started = dt.datetime.now()
        self.threads: list[threading.Thread] = []
        self._lock = threading.Lock()

    @property
    def recording(self) -> bool:
        return self.recorder.recording

    def status(self) -> dict:
        return {"recording": self.recording, "noteId": self.note_id,
                "elapsed": format_duration(self.recorder.elapsed), "level": min(self.recorder.level * 3, 1.0)}

    def start(self, note_id: str) -> dict:
        with self._lock:
            if self.recording:
                return self.status()
            note = self.store.read(note_id)
            path = note.path.parent / "audio" / f"{note.id}-{dt.datetime.now():%H%M%S}.wav"
            try:
                self.recorder.start(path)
            except AudioUnavailable as exc:
                return {"error": str(exc)}
            self.note_id, self.started = note.id, dt.datetime.now()
        self.on_recording(True)
        self.emit("toast", {"text": f"Registrazione su «{note.title}»", "icon": "mic"})
        return self.status()

    def stop(self, transcribe: bool = True) -> dict | None:
        """Ferma la registrazione. Restituisce la riga col link all'audio da aggiungere alla nota."""
        with self._lock:
            if not self.recording:
                return None
            path, duration = self.recorder.stop()
            note_id, started = self.note_id, self.started
            self.note_id = None
        self.on_recording(False)
        note = self.store.read(note_id)
        rel = path.relative_to(note.path.parent).as_posix()
        line = f"🎙️ [Registrazione {started:%H:%M} ({format_duration(duration)})]({rel})"
        self.emit("toast", {"text": f"Registrazione salvata ({format_duration(duration)})", "icon": "mic"})
        if transcribe and self.cfg.transcribe_after_recording and duration >= 1:
            self.transcribe(note_id, path, started)
        return {"noteId": note_id, "text": line}

    # ------------------------------------------------------------ trascrizione
    def transcribe(self, note_id: str, path: Path, started: dt.datetime) -> threading.Thread:
        thread = threading.Thread(target=self._transcribe, args=(note_id, path, started), daemon=True)
        with self._lock:
            self.threads.append(thread)
        self.emit("transcription", {"active": True, "percent": 0})
        self.emit("toast", {"text": "Trascrizione avviata: la prima volta scarica il modello", "icon": "clock"})
        thread.start()
        return thread

    def _transcribe(self, note_id: str, path: Path, started: dt.datetime) -> None:
        last = [-1]

        def progress(value: float):
            percent = int(value * 100)
            if percent != last[0]:
                last[0] = percent
                self.emit("transcription", {"active": True, "percent": percent})

        try:
            text = self.transcriber.transcribe(path, progress)
        except Exception as exc:  # noqa: BLE001 - qualsiasi errore va mostrato all'utente
            self.emit("dialog", {"title": "Trascrizione non riuscita",
                                 "text": f"{exc}\n\nL'audio resta salvato in:\n{path}"})
        else:
            if text.strip():
                self.emit("append", {"noteId": note_id, "text": text, "heading": f"Trascrizione {started:%H:%M}"})
            else:
                self.emit("toast", {"text": "Trascrizione vuota (nessun parlato rilevato)", "icon": "mic"})
        finally:
            with self._lock:
                self.threads.remove(threading.current_thread())
                busy = bool(self.threads)
            if not busy:
                self.emit("transcription", {"active": False, "percent": 0})
