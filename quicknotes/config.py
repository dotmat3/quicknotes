"""Configurazione: ~/.quicknotes/config.json (creato al primo avvio).

La cartella delle note puo' essere forzata con la variabile d'ambiente
QUICKNOTES_DIR (utile per il server MCP e per i test).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("QUICKNOTES_CONFIG_DIR", Path.home() / ".quicknotes"))
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    notes_dir: str = str(Path.home() / "QuickNotes")
    # Modello faster-whisper: tiny, base, small, medium, large-v3, turbo...
    # "small" e' un buon compromesso velocita'/qualita' su CPU per l'italiano.
    whisper_model: str = "small"
    language: str = "it"  # "" = rilevamento automatico
    transcribe_after_recording: bool = True
    theme: str = "auto"  # "auto" (segue il sistema), "light", "dark"
    animations: bool = True  # false: interfaccia senza transizioni (tutto istantaneo)
    hotkeys: dict = field(default_factory=lambda: {
        "new_meeting": "<ctrl>+<alt>+n",
        "daily": "<ctrl>+<alt>+d",
        "toggle_recording": "<ctrl>+<alt>+r",
    })

    @property
    def notes_path(self) -> Path:
        env = os.environ.get("QUICKNOTES_DIR")
        return Path(env).expanduser() if env else Path(self.notes_dir).expanduser()


def load_config() -> Config:
    cfg = Config()
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for key, value in data.items():
                if hasattr(cfg, key):
                    setattr(cfg, key, value)
        except (OSError, ValueError):
            pass  # config illeggibile: si usano i default
    else:
        save_config(cfg)
    return cfg


def save_config(cfg: Config) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
