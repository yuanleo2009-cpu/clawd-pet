# -*- mode: python ; coding: utf-8 -*-
# macOS 打包設定（由 build_mac.sh 呼叫）：產生 dist/ClawdPet.app
# - LSUIElement：不在 Dock 顯示圖示（和 Windows 版不佔工作列一樣），只在選單列有圖示
# - 拿掉用不到的 Qt 外掛與加密函式庫，讓 App 小一點
import os
import re

spec_dir = os.path.dirname(os.path.abspath(SPEC))  # noqa: F821  (PyInstaller 提供 SPEC)
with open(os.path.join(spec_dir, "services", "version.py"), encoding="utf-8") as f:
    VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)

DROP_NAMES = ("libqoffscreen", "libqminimal", "libcrypto", "libssl", "_ssl.", "_hashlib.")
DROP_PARTS = ("/plugins/tls/", "/plugins/imageformats/", "/plugins/iconengines/",
              "/plugins/networkinformation/", "/plugins/generic/", "/translations/")


def keep(dest: str) -> bool:
    d = "/" + dest.replace("\\", "/").lower()
    name = os.path.basename(d)
    if any(name.startswith(n) for n in DROP_NAMES):
        return False
    return not any(part in d for part in DROP_PARTS)


a = Analysis(  # noqa: F821
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

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ClawdPet",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    # universal2 = 一個 App 同時包含 Apple 晶片（arm64）和 Intel（x86_64）兩種程式碼
    target_arch=os.environ.get("CLAWDPET_TARGET_ARCH") or None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ClawdPet")  # noqa: F821
app = BUNDLE(  # noqa: F821
    coll,
    name="ClawdPet.app",
    icon="assets/icon.png",                      # PyInstaller 會用 Pillow 轉成 .icns
    bundle_identifier="io.github.yuanleo2009-cpu.clawdpet",
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": "Clawd 桌寵",
        "CFBundleName": "ClawdPet",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSUIElement": True,                     # 不在 Dock 顯示
        "LSMinimumSystemVersion": "14.0",          # PySide6 6.12 需要 macOS 14 以上
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Unofficial fan project. Clawd and Claude belong to Anthropic.",
    },
)
