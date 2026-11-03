"""Integrazione con Windows che non riguarda la finestra: link e cartelle, avvio con Windows, percorsi."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "QuickNotes"
HIDDEN_ARG = "--nascosta"


def open_external(target: str) -> None:
    """Un indirizzo web nel browser o una cartella in Esplora risorse."""
    if sys.platform == "win32":
        os.startfile(target)  # noqa: S606 - solo http(s) o la cartella delle note, controllati dal chiamante
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


def _sibling(name: str) -> str:
    exe = Path(sys.executable)
    candidate = exe.with_name(name)
    return str(candidate if candidate.exists() else exe)


def console_python() -> str:
    """python.exe accanto a quello in uso: il server MCP parla su stdio, quindi non può essere pythonw."""
    return _sibling("python.exe") if sys.platform == "win32" else sys.executable


def window_python() -> str:
    """pythonw.exe accanto a quello in uso: l'app senza finestra di console."""
    return _sibling("pythonw.exe") if sys.platform == "win32" else sys.executable


def autostart_command() -> str:
    return f'"{window_python()}" -m quicknotes {HIDDEN_ARG}'


def autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value = winreg.QueryValueEx(k, RUN_NAME)[0]
    except OSError:
        return False
    # Se la cartella è stata spostata, la voce punta a un Python che non c'è più: vale come spenta.
    return isinstance(value, str) and value == autostart_command()


def set_autostart(on: bool) -> None:
    """L'app parte nascosta nell'area di notifica all'accesso a Windows. Solo per l'utente: niente permessi
    di amministratore."""
    if sys.platform != "win32":
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


def system_is_dark() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False
