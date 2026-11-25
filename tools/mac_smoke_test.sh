#!/bin/bash
# macOS 實機啟動測試（GitHub Actions 的 Mac 上執行）：
# 真的打開 ClawdPet.app → 確認有在跑、沒有錯誤紀錄、有存設定 → 截圖 → 請它正常結束。
# 用法：tools/mac_smoke_test.sh <ClawdPet.app 路徑> <截圖輸出路徑>
set -uo pipefail
APP="$1"
SHOT="${2:-screenshot.png}"
DATA="$HOME/Library/Application Support/ClawdPet"
fail() { echo "❌ $*"; exit 1; }

echo "== App 資訊"
/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP/Contents/Info.plist"
[ "$(/usr/libexec/PlistBuddy -c 'Print :LSUIElement' "$APP/Contents/Info.plist")" = "true" ] \
    || fail "LSUIElement 不是 true（Dock 會出現圖示）"
lipo -archs "$APP/Contents/MacOS/ClawdPet"
codesign --verify --deep --strict "$APP" || fail "簽章檢查失敗"

rm -rf "$DATA"
echo "== 打開 App"
open "$APP" || fail "open 失敗"
for _ in $(seq 1 40); do pgrep -x ClawdPet > /dev/null && break; sleep 1; done
pgrep -x ClawdPet > /dev/null || fail "App 沒有啟動"
sleep 12                                   # 讓打招呼、待機動畫、提醒檢查都跑過一輪
pgrep -x ClawdPet > /dev/null || fail "App 啟動後自己關掉了（閃退）"
echo "✅ App 持續執行中（PID $(pgrep -x ClawdPet | tr '\n' ' ')）"

screencapture -x "$SHOT" && echo "✅ 已截圖：$SHOT" || echo "⚠️ 截圖失敗（不影響測試結果）"

if [ -f "$DATA/error.log" ]; then
    cat "$DATA/error.log"
    fail "出現錯誤紀錄"
fi
echo "✅ 沒有錯誤紀錄"
[ -f "$DATA/settings.json" ] || fail "沒有建立設定檔（$DATA/settings.json）"
echo "✅ 設定檔已建立：$(tr -d '\n' < "$DATA/settings.json" | cut -c1-120)…"

echo "== 第二次打開（應該只叫原本那隻出來打招呼，不會開第二隻）"
open -n "$APP"
sleep 6
COUNT="$(pgrep -x ClawdPet | wc -l | tr -d ' ')"
[ "$COUNT" = "1" ] || fail "同時有 $COUNT 隻在跑"
echo "✅ 只有一隻"

echo "== 請它正常結束（解除安裝 / 更新時用的 --quit）"
"$APP/Contents/MacOS/ClawdPet" --quit
for _ in $(seq 1 15); do pgrep -x ClawdPet > /dev/null || break; sleep 1; done
pgrep -x ClawdPet > /dev/null && fail "--quit 之後還在執行"
echo "✅ 已正常結束"
[ -f "$DATA/error.log" ] && { cat "$DATA/error.log"; fail "結束時出現錯誤紀錄"; }
echo "🎉 macOS 實機啟動測試全部通過"
