"""Registrazione dal microfono (WAV mono 16-bit) e trascrizione locale con faster-whisper.

Entrambe le dipendenze sono opzionali: se mancano, l'app funziona lo stesso e
mostra un messaggio quando si prova a registrare o trascrivere.
"""

from __future__ import annotations

import queue
import threading
import time
import wave
from pathlib import Path
from typing import Callable


class AudioUnavailable(RuntimeError):
    pass


class Recorder:
    def __init__(self, samplerate: int = 16000):
        self.preferred_rate = samplerate
        self.path: Path | None = None
        self.started_at: float | None = None
        self.level = 0.0  # 0..1, per l'indicatore di livello
        self._stream = None
        self._queue: queue.Queue = queue.Queue()
        self._writer: threading.Thread | None = None

    @property
    def recording(self) -> bool:
        return self._stream is not None

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started_at if self.started_at else 0.0

    def start(self, path: Path) -> None:
        try:
            import numpy as np
            import sounddevice as sd
        except (ImportError, OSError) as exc:
            raise AudioUnavailable("Registrazione non disponibile: installa 'sounddevice' e 'numpy' "
                                   f"(pip install sounddevice numpy). Dettaglio: {exc}") from exc
        if self.recording:
            return
        path.parent.mkdir(parents=True, exist_ok=True)

        def callback(indata, frames, time_info, status):
            self._queue.put(bytes(indata))
            peak = float(np.abs(indata).max()) / 32768.0 if frames else 0.0
            self.level = max(peak, self.level * 0.85)

        stream, rate = None, self.preferred_rate
        for candidate in (self.preferred_rate, None):
            try:
                if candidate is None:  # il dispositivo non supporta 16 kHz: usa la sua frequenza
                    rate = int(sd.query_devices(kind="input")["default_samplerate"])
                stream = sd.InputStream(samplerate=rate, channels=1, dtype="int16", callback=callback)
                break
            except Exception as exc:  # noqa: BLE001 - errori PortAudio eterogenei
                last_error = exc
        if stream is None:
            raise AudioUnavailable(f"Impossibile aprire il microfono: {last_error}")

        wav = wave.open(str(path), "wb")
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)

        def writer():
            while True:
                chunk = self._queue.get()
                if chunk is None:
                    break
                wav.writeframes(chunk)
            wav.close()

        self._queue = queue.Queue()
        self._writer = threading.Thread(target=writer, daemon=True)
        self._writer.start()
        self.path, self.started_at, self._stream = path, time.monotonic(), stream
        stream.start()

    def stop(self) -> tuple[Path, float]:
        """Ferma la registrazione e restituisce (file, durata in secondi)."""
        if not self.recording:
            raise RuntimeError("Nessuna registrazione in corso")
        duration = self.elapsed
        self._stream.stop()
        self._stream.close()
        self._stream = None
        self._queue.put(None)
        self._writer.join(timeout=10)
        self.started_at, self.level = None, 0.0
        return self.path, duration


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


WHISPER_RATE = 16000


def load_wav(path: Path):
    """Legge un WAV PCM 16-bit come array float32 mono a 16 kHz, il formato atteso da Whisper.

    Evita la decodifica tramite PyAV di faster-whisper, che con alcune versioni di PyAV
    fallisce ("open() got an unexpected keyword argument 'metadata_errors'").
    """
    import numpy as np

    with wave.open(str(path), "rb") as wav:
        channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
        raw = wav.readframes(wav.getnframes())
    if width != 2:
        raise ValueError(f"WAV a {width * 8} bit non supportato (serve PCM 16-bit)")
    audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != WHISPER_RATE and audio.size:
        n_out = int(round(audio.size * WHISPER_RATE / rate))
        audio = np.interp(np.linspace(0, audio.size - 1, n_out), np.arange(audio.size), audio)
        audio = audio.astype(np.float32)
    return audio


class Transcriber:
    """Trascrizione locale: l'audio non lascia il computer.

    Il modello viene scaricato da Hugging Face al primo utilizzo e poi resta in cache.
    """

    def __init__(self, model_size: str = "small", language: str = "it"):
        self.model_size = model_size
        self.language = language or None
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise AudioUnavailable("Trascrizione non disponibile: installa 'faster-whisper' "
                                       "(pip install faster-whisper).") from exc
            self._model = WhisperModel(self.model_size, device="auto", compute_type="int8")
        return self._model

    def transcribe(self, path: Path, progress: Callable[[float], None] | None = None,
                   block_seconds: float = 60.0) -> str:
        """Restituisce il testo a paragrafi, ciascuno preceduto da [mm:ss]."""
        with self._lock:
            model = self._load()
            try:
                source = load_wav(path)
            except (wave.Error, ValueError, EOFError):
                source = str(path)  # formato diverso: lascia decodificare a faster-whisper
            segments, info = model.transcribe(source, language=self.language, vad_filter=True,
                                              beam_size=5)
            paragraphs, current, block_start = [], [], None
            for seg in segments:
                if block_start is None:
                    block_start = seg.start
                current.append(seg.text.strip())
                if seg.end - block_start >= block_seconds:
                    paragraphs.append(f"[{format_duration(block_start)}] " + " ".join(current))
                    current, block_start = [], None
                if progress and info.duration:
                    progress(min(seg.end / info.duration, 1.0))
            if current:
                paragraphs.append(f"[{format_duration(block_start)}] " + " ".join(current))
            return "\n\n".join(paragraphs)
