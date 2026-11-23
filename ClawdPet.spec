# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包設定（由 build.ps1 呼叫）。
# 除了一般打包，還會拿掉 Clawd 用不到的大型元件，讓 exe / 安裝包小很多。
import os

# 用不到的檔案（檔名開頭比對）
DROP_FILES = (
    "opengl32sw.dll",      # 軟體 OpenGL 備援（約 20MB），我們只用 CPU 繪圖
    "qdirect2d.dll",       # 其他繪圖平台外掛，只需要 qwindows.dll
    "qoffscreen.dll",
    "qminimal.dll",
    "libcrypto", "libssl",  # HTTPS 加密函式庫，Clawd 不用連網
    "_ssl.", "_hashlib.",
)
# 用不到的 Qt 外掛資料夾
DROP_DIRS = (
    "pyside6\\plugins\\tls",
    "pyside6\\plugins\\imageformats",   # PNG 是 Qt 內建，不需要額外外掛
    "pyside6\\plugins\\iconengines",
    "pyside6\\plugins\\networkinformation",
    "pyside6\\plugins\\generic",
    "pyside6\\translations",
)


def keep(dest: str) -> bool:
    d = dest.replace("/", "\\").lower()
    name = os.path.basename(d)
    if any(name.startswith(f) for f in DROP_FILES):
        return False
    return not any(d.startswith(x + "\\") or d == x for x in DROP_DIRS)


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("assets/sprites", "assets/sprites"),
        ("assets/icon.png", "assets"),
        ("assets/phrases.txt", "assets"),
    ],
    hiddenimports=[],
    excludes=["ssl", "_ssl", "_hashlib", "tkinter", "unittest", "pydoc", "xmlrpc"],
    noarchive=False,
)
before = len(a.binaries) + len(a.datas)
a.binaries = [b for b in a.binaries if keep(b[0])]
a.datas = [d for d in a.datas if keep(d[0])]
print(f"[ClawdPet] removed {before - len(a.binaries) - len(a.datas)} unused files")

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ClawdPet",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/icon.ico",
)
