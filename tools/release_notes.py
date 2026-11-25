"""
從 CHANGELOG.md 取出某個版本的更新內容，組成 GitHub Release 的說明。

用法：
    # 只檢查 CHANGELOG.md 有沒有寫這個版本（沒有就失敗）
    python tools/release_notes.py 1.1.0 --check

    # 產生完整的 Release 說明
    python tools/release_notes.py 1.1.0 --setup dist/ClawdPet-Setup-1.1.0.exe \
        --run-url https://github.com/.../actions/runs/123 --out notes.md
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"


def changelog_section(version: str) -> str:
    """回傳 `## [版本]` 底下到下一個 `## ` 之前的內容；找不到回傳空字串。"""
    version = version.lstrip("v")
    text = CHANGELOG.read_text(encoding="utf-8")
    head = re.compile(rf"^##\s+\[?v?{re.escape(version)}\]?(\s|$)")
    lines, out, inside = text.splitlines(), [], False
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = bool(head.match(line))
            continue
        if inside:
            out.append(line)
    return "\n".join(out).strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


MAC_ARCH_LABEL = {"arm64": "Apple 晶片（M1、M2、M3、M4…）", "x86_64": "Intel 處理器",
                  "universal": "所有 Mac（Apple 晶片和 Intel 都能原生執行）"}


def build_notes(version: str, setup: Path | None, run_url: str | None,
                repo: str = "yuanleo2009-cpu/clawd-pet", macs: list[Path] | None = None) -> str:
    changes = changelog_section(version)
    parts = ["## 更新內容", "", changes, ""]
    name = setup.name if setup else f"ClawdPet-Setup-{version.lstrip('v')}.exe"
    parts += [
        "## 下載與安裝", "",
        "### Windows", "",
        f"下載下面的 **{name}**，雙擊安裝即可（Windows 10/11，64 位元，不需要系統管理員權限）。",
        "",
        "安裝檔沒有數位簽章，Windows 可能顯示「Windows 已保護你的電腦」：點「其他資訊」→「仍要執行」。",
        "",
    ]
    if setup:
        parts += [
            f"**SHA-256**：`{sha256(setup)}`",
            f"（PowerShell 驗證：`Get-FileHash .\\{name} -Algorithm SHA256`）",
            "",
        ]
    if macs:
        parts += ["### macOS（14 Sonoma 以上）", ""]
        if len(macs) > 1:
            parts += ["依你的 Mac 下載對應的檔案（不知道的話：左上角  →「關於這台 Mac」看「晶片」或「處理器」）：", ""]
        for dmg in macs:
            arch = dmg.stem.rsplit("-", 1)[-1]
            parts.append(f"- **{dmg.name}**：{MAC_ARCH_LABEL.get(arch, arch)}　SHA-256 `{sha256(dmg)}`")
        parts += [
            "",
            "打開 DMG 後，把 ClawdPet 拖進「應用程式」資料夾。App 沒有向 Apple 付費簽章，第一次打開會被擋下："
            "請對 ClawdPet 按右鍵 →「打開」→「打開」；若沒有「打開」按鈕，到「系統設定 → 隱私權與安全性」"
            "按「強制打開」。之後就能直接打開。DMG 裡也附了「安裝說明.txt」。",
            "",
        ]
    if run_url:
        parts += [f"這些安裝檔由 GitHub Actions 從這個 tag 的原始碼自動打包：{run_url}", ""]
    parts += [
        f"完整的歷次更新紀錄見 [CHANGELOG.md](https://github.com/{repo}/blob/main/CHANGELOG.md)。",
        "",
        "> 非官方的粉絲作品，與 Anthropic 無關。程式碼為 MIT 授權；Clawd 形象與 Claude 商標歸 Anthropic 所有，不在授權範圍內。",
    ]
    return "\n".join(parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--check", action="store_true", help="只檢查 CHANGELOG.md 有沒有這個版本")
    ap.add_argument("--setup", type=Path, help="安裝檔路徑（會算 SHA-256）")
    ap.add_argument("--run-url", help="GitHub Actions 打包紀錄的網址")
    ap.add_argument("--repo", default="yuanleo2009-cpu/clawd-pet", help="owner/name，用來產生連結")
    ap.add_argument("--mac", type=Path, nargs="*", default=[], help="macOS 的 DMG 路徑（可多個）")
    ap.add_argument("--out", type=Path, help="輸出檔（UTF-8）；不給就印出來")
    args = ap.parse_args()

    if not changelog_section(args.version):
        print(f"CHANGELOG.md 裡沒有 {args.version} 的更新內容，請先補上 `## [{args.version.lstrip('v')}] - 日期`。",
              file=sys.stderr)
        return 1
    if args.check:
        print(f"CHANGELOG.md 有 {args.version} 的更新內容 ✓")
        return 0
    notes = build_notes(args.version, args.setup, args.run_url, args.repo, sorted(args.mac))
    if args.out:
        args.out.write_text(notes, encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
