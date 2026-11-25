"""Windows / macOS 差異集中在這裡：字型、檔案管理員名稱、開啟檔案的方式等。"""
from __future__ import annotations

import sys
from pathlib import Path

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform.startswith("win")

if IS_MAC:
    UI_FONT = "PingFang TC"            # macOS 內建的繁體中文字型
    MONO_FONT = "Menlo"
    FILE_MANAGER = "Finder"
    AUTOSTART_LABEL = "登入時自動啟動"
    AUTOSTART_ON = "登入 Mac 後我會自己出現！"
    AUTOSTART_OFF = "好，登入時不自動啟動"
else:
    UI_FONT = "Microsoft JhengHei UI"
    MONO_FONT = "Consolas"
    FILE_MANAGER = "檔案總管"
    AUTOSTART_LABEL = "開機自動啟動"
    AUTOSTART_ON = "開機後我會自己出現！"
    AUTOSTART_OFF = "好，開機時不自動啟動"


def open_path(path: str | Path) -> bool:
    """用系統預設的程式打開檔案或資料夾（Windows：檔案總管 / 記事本；macOS：Finder / 文字編輯）。"""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
