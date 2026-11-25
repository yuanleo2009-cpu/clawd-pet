"""開機 / 登入時自動啟動（都不需要系統管理員權限）。

- Windows：寫入目前使用者的「執行」登錄機碼 HKCU\\...\\Run。
- macOS：在 ~/Library/LaunchAgents 放一個 LaunchAgent（.plist），登入時由系統啟動。
"""
from __future__ import annotations

import plistlib
import sys
from pathlib import Path

from . import paths

NAME = "ClawdPet"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MAC_LABEL = "io.github.yuanleo2009-cpu.clawdpet"


# ---------------- 要執行的指令 ----------------
def command() -> str:
    """Windows：登錄機碼裡的那一行指令。"""
    if paths.is_frozen():
        return f'"{Path(sys.executable).resolve()}"'
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")  # 不跳出黑色主控台視窗
    if not pythonw.exists():
        pythonw = exe
    main = paths.bundle_dir() / "main.py"
    return f'"{pythonw}" "{main}"'


def mac_program_arguments() -> list[str]:
    """macOS：LaunchAgent 要執行的指令（陣列，不經過 shell，所以路徑有空白也沒問題）。"""
    if paths.is_frozen():
        exe = Path(sys.executable).resolve()
        app = next((p for p in exe.parents if p.suffix == ".app"), None)
        if app is not None:  # 用 open 開 .app，和從「應用程式」資料夾點開一樣
            return ["/usr/bin/open", str(app)]
        return [str(exe)]
    return [str(Path(sys.executable).resolve()), str(paths.bundle_dir() / "main.py")]


def mac_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


# ---------------- 對外的三個函式 ----------------
def is_enabled() -> bool:
    if sys.platform == "darwin":
        return mac_plist_path().is_file()
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, NAME)
            return True
    except OSError:
        return False


def set_enabled(on: bool) -> None:
    if sys.platform == "darwin":
        p = mac_plist_path()
        if on:
            p.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "Label": MAC_LABEL,
                "ProgramArguments": mac_program_arguments(),
                "RunAtLoad": True,           # 登入時執行一次
                "ProcessType": "Interactive",
            }
            with open(p, "wb") as f:
                plistlib.dump(data, f)
        else:
            p.unlink(missing_ok=True)
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except FileNotFoundError:
                pass


def refresh() -> None:
    """程式被搬到別的地方時，更新自動啟動的路徑（只在打包版執行）。"""
    if paths.is_frozen() and is_enabled():
        set_enabled(True)
