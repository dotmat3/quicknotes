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


def to_recycle_bin(path: Path) -> bool:
    """Sposta un file nel Cestino di Windows. False se il Cestino non c'è (altri sistemi, cartelle di rete):
    lì Windows eliminerebbe il file per sempre senza dirlo, quindi non ci si prova nemmeno."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    full = str(path.resolve())
    drive = os.path.splitdrive(full)[0]
    if not drive or drive.startswith("\\\\"):
        return False
    kernel32 = ctypes.windll.kernel32
    kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    if kernel32.GetDriveTypeW(drive + "\\") != 3:  # DRIVE_FIXED: dischi del PC, dove il Cestino esiste
        return False

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 0x4, 0x10, 0x40, 0x400
    op = SHFILEOPSTRUCTW(wFunc=FO_DELETE, pFrom=full + "\0",
                         fFlags=FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI)
    shell32 = ctypes.windll.shell32
    shell32.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    return shell32.SHFileOperationW(ctypes.byref(op)) == 0 and not op.fAnyOperationsAborted and not path.exists()


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
