"""Configurazione: lo stesso ~/.quicknotes/config.json della versione Rust. Le chiavi sconosciute restano."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".")


def _arg(name: str) -> Path | None:
    for a in sys.argv[1:]:
        if a.startswith(name + "="):
            value = a[len(name) + 1:]
            if value:
                return Path(value)
    return None


def config_dir() -> Path:
    env = os.environ.get("QUICKNOTES_CONFIG_DIR")
    if env:
        return Path(env)
    return _arg("--cartella-config") or home() / ".quicknotes"


class Config:
    def __init__(self, path: Path):
        self.path = path
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            data = {}
        self.data: dict = data if isinstance(data, dict) else {}

    @classmethod
    def load(cls) -> Config:
        return cls(config_dir() / "config.json")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def _str(self, key: str, default: str) -> str:
        v = self.data.get(key)
        return v if isinstance(v, str) else default

    def _bool(self, key: str, default: bool) -> bool:
        v = self.data.get(key)
        return v if isinstance(v, bool) else default

    def notes_path(self) -> Path:
        env = os.environ.get("QUICKNOTES_DIR")
        if env:
            return Path(env)
        arg = _arg("--cartella-note")
        if arg:
            return arg
        d = self.data.get("notes_dir")
        if isinstance(d, str) and d.strip():
            d = d.strip()
            for prefix in ("~/", "~\\"):
                if d.startswith(prefix):
                    return home() / d[2:]
            return Path(d)
        return home() / "QuickNotes"

    def theme(self) -> str:
        return self._str("theme", "auto")

    def ui(self) -> dict:
        v = self.data.get("ui")
        return v if isinstance(v, dict) else {}

    def set_ui(self, ui: dict) -> None:
        self.data["ui"] = ui

    def whisper_model(self) -> str:
        return self._str("whisper_model", "small")

    def language(self) -> str:
        return self._str("language", "it")

    def keep_audio(self) -> bool:
        return self._bool("keep_audio", True)

    def transcript_timestamps(self) -> bool:
        return self._bool("transcript_timestamps", True)

    def set_recording(self, key: str, value) -> None:
        ok = {
            "whisper_model": lambda v: v in ("base", "small", "medium"),
            "language": lambda v: v in ("it", "en", "auto"),
            "keep_audio": lambda v: isinstance(v, bool),
            "transcript_timestamps": lambda v: isinstance(v, bool),
        }.get(key)
        if not ok or not ok(value):
            raise ValueError(f"Impostazione non valida: {key} = {value!r}")
        self.data[key] = value

    def hotkeys(self) -> dict[str, str]:
        """Azione → combinazione nel formato "Ctrl+Alt+D". Accetta anche il formato pynput."""
        out = {"quick_note": "Ctrl+Alt+N", "daily": "Ctrl+Alt+D", "toggle_recording": "Ctrl+Alt+R"}
        saved = self.data.get("hotkeys")
        if isinstance(saved, dict):
            for key, combo in saved.items():
                action = "quick_note" if key == "new_meeting" else key
                if action in out and isinstance(combo, str):
                    out[action] = convert_hotkey(combo)
        return out


def convert_hotkey(combo: str) -> str:
    names = {"ctrl": "Ctrl", "control": "Ctrl", "alt": "Alt", "shift": "Shift",
             "cmd": "Super", "win": "Super", "super": "Super", "meta": "Super"}
    parts = []
    for part in combo.split("+"):
        bare = part.strip().strip("<>")
        parts.append(names.get(bare.lower(), bare[:1].upper() + bare[1:]))
    return "+".join(parts)
