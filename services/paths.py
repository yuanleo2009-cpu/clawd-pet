"""所有路徑集中在這裡：開發模式和打包成 exe 後都能正確找到檔案。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """是否為 PyInstaller 打包後的 exe。"""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """程式內建資源的根目錄（exe 執行時是解壓出來的暫存資料夾）。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    return bundle_dir() / "assets"


def app_dir() -> Path:
    """exe 所在資料夾；開發模式下是專案根目錄。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return bundle_dir()


def data_dir() -> Path:
    """使用者資料（設定、台詞）：%APPDATA%\\ClawdPet"""
    base = os.environ.get("APPDATA") or str(Path.home())
    d = Path(base) / "ClawdPet"
    d.mkdir(parents=True, exist_ok=True)
    return d


def custom_image() -> Path | None:
    """使用者自訂的單張圖片（assets/clawd.png），找不到則回傳 None。"""
    for c in (app_dir() / "assets" / "clawd.png", data_dir() / "clawd.png"):
        if c.is_file():
            return c
    return None
