#!/bin/bash
# macOS 一鍵打包：dist/ClawdPet.app + dist/ClawdPet-<版本>-mac-<架構>.dmg（附 .sha256）
# 用法：在專案資料夾執行  ./build_mac.sh
# 通用版（Apple 晶片 + Intel 都能原生執行）：
#   PYTHON=<python.org 的 universal2 Python> CLAWDPET_TARGET_ARCH=universal2 ./build_mac.sh
# GitHub Actions（.github/workflows/release.yml）也是呼叫這個腳本。
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if [ ! -x .venv/bin/python ]; then
    echo "建立虛擬環境並安裝套件…"
    "$PY" -m venv .venv
    .venv/bin/python -m pip install -r requirements-dev.txt
fi

VERSION="$(.venv/bin/python -c 'from services.version import __version__; print(__version__)')"
if [ "${CLAWDPET_TARGET_ARCH:-}" = "universal2" ]; then
    ARCH="universal"                     # 一個檔案兩種 Mac 都能用
else
    ARCH="$(uname -m)"                   # arm64（Apple 晶片）或 x86_64（Intel）
fi
echo "版本：$VERSION  架構：$ARCH"

# 重新產生素材
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/make_sprites.py > /dev/null

# 先請正在執行的 ClawdPet 正常結束，否則無法覆蓋
if [ -x dist/ClawdPet.app/Contents/MacOS/ClawdPet ]; then
    dist/ClawdPet.app/Contents/MacOS/ClawdPet --quit || true
fi

.venv/bin/pyinstaller --noconfirm --clean ClawdPet-mac.spec

APP="dist/ClawdPet.app"
# PyInstaller 會做「臨時簽章」（ad-hoc）；Apple 晶片的 Mac 一定要有簽章才能執行，這裡確認一下
codesign --verify --deep --strict "$APP"
echo "簽章檢查通過（ad-hoc）"

# 做成 DMG：裡面放 App 和「應用程式」資料夾捷徑，打開後拖過去就安裝好了
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/應用程式"
cp "docs/mac-安裝說明.txt" "$STAGE/安裝說明.txt"
DMG="dist/ClawdPet-$VERSION-mac-$ARCH.dmg"
rm -f "$DMG"
hdiutil create -volname "Clawd 桌寵" -srcfolder "$STAGE" -ov -format UDZO "$DMG" > /dev/null
rm -rf "$STAGE"

( cd dist && shasum -a 256 "$(basename "$DMG")" | awk '{print toupper($1) "  " $2}' > "$(basename "$DMG").sha256" )
echo ""
echo "完成：$APP"
echo "安裝檔：$DMG  ($(du -h "$DMG" | cut -f1))"
cat "$DMG.sha256"
