"""開機自動啟動：寫入目前使用者的「執行」登錄機碼（不需要系統管理員權限）。"""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

from . import paths

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "ClawdPet"


def command() -> str:
    if paths.is_frozen():
        return f'"{Path(sys.executable).resolve()}"'
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")  # 不跳出黑色主控台視窗
    if not pythonw.exists():
        pythonw = exe
    main = paths.bundle_dir() / "main.py"
    return f'"{pythonw}" "{main}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, NAME)
            return True
    except OSError:
        return False


def set_enabled(on: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except FileNotFoundError:
                pass


def refresh() -> None:
    """exe 被搬到別的地方時，更新自啟動路徑（只在打包版執行）。"""
    if paths.is_frozen() and is_enabled():
        set_enabled(True)
