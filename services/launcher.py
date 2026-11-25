"""開啟 Claude。

- 桌面版 Claude 應用程式（雙擊 Clawd）：open_desktop_app()
- 終端機版 Claude Code（右鍵 → 進階）：launch()
  Windows：優先使用 Windows Terminal (wt.exe)，沒有的話直接開 PowerShell 視窗。
    要執行的指令用 -EncodedCommand 傳遞，資料夾路徑也只出現在編碼後的指令裡，
    所以路徑中有空白、引號、分號都不會出問題（wt 會把分號當成指令分隔）。
  macOS：寫一個 .command 小腳本，交給「終端機」打開（不需要「自動化」權限）。
"""
from __future__ import annotations

import base64
import os
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

IS_MAC = sys.platform == "darwin"

# macOS 的 Claude 桌面版
MAC_BUNDLE_ID = "com.anthropic.claudefordesktop"
MAC_APP_PATHS = (Path("/Applications/Claude.app"), Path.home() / "Applications" / "Claude.app")


# ---------------- 桌面版 Claude 應用程式 ----------------
# 官方 MSIX 套件名稱（Microsoft Store 與官網下載都是這個，不隨版本改變）
STORE_FAMILY = "Claude_pzs8sxrjxfjjc"
STORE_AUMID = f"{STORE_FAMILY}!Claude"


def _protocol_exe() -> str | None:
    """從 claude:// 協定的登錄設定找出桌面版 exe（一般安裝版）。"""
    import winreg
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_CLASSES_ROOT):
        sub = r"Software\Classes\claude\shell\open\command" if root == winreg.HKEY_CURRENT_USER \
            else r"claude\shell\open\command"
        try:
            with winreg.OpenKey(root, sub) as k:
                cmd, _ = winreg.QueryValueEx(k, "")
        except OSError:
            continue
        if cmd.startswith('"'):
            exe = cmd[1:].split('"', 1)[0]
        else:
            exe = cmd.split(" ", 1)[0]
        if exe and Path(exe).is_file():
            return exe
    return None


DOWNLOAD_URL = "https://claude.ai/download"


def _store_installed() -> bool:
    """官方 MSIX 版是否已安裝。只認已知的套件名稱，其他名稱交給後面的 claude:// 協定處理。"""
    return (Path(os.environ.get("LOCALAPPDATA", "")) / "Packages" / STORE_FAMILY).is_dir()


def _mac_app_path() -> Path | None:
    for p in MAC_APP_PATHS:
        if p.is_dir():
            return p
    try:  # 裝在別的地方：用 Spotlight 依 bundle id 找
        out = subprocess.run(["mdfind", f"kMDItemCFBundleIdentifier == '{MAC_BUNDLE_ID}'"],
                             capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            if line.endswith(".app") and Path(line).is_dir():
                return Path(line)
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _mac_open_desktop_app() -> tuple[bool, str]:
    app = _mac_app_path()
    attempts = [["open", str(app)]] if app else []
    attempts += [["open", "-b", MAC_BUNDLE_ID], ["open", "-a", "Claude"]]
    for cmd in attempts:
        try:
            if subprocess.run(cmd, capture_output=True, timeout=10).returncode == 0:
                return True, "mac"
        except (OSError, subprocess.SubprocessError):
            pass
    return False, "missing"


def is_desktop_app_installed() -> bool:
    if IS_MAC:
        return _mac_app_path() is not None
    if _store_installed():
        return True
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    exe = _protocol_exe()
    return bool(exe and Path(exe).is_file()) or (local / "AnthropicClaude" / "claude.exe").is_file()


def open_desktop_app() -> tuple[bool, str]:
    """開啟（或叫到前面）桌面版 Claude。回傳 (是否成功, 說明)；找不到時說明為 "missing"。"""
    if IS_MAC:
        return _mac_open_desktop_app()
    # 1) MSIX 版（Microsoft Store 或官網下載）：用應用程式 ID 啟動，和從開始功能表點開一樣
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    if _store_installed():
        try:
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{STORE_AUMID}"])
            return True, "store"
        except OSError:
            pass
    # 2) 一般安裝版
    for exe in (_protocol_exe(), str(local / "AnthropicClaude" / "claude.exe")):
        if exe and Path(exe).is_file() and "WindowsApps" not in exe:
            try:
                subprocess.Popen([exe], close_fds=True)
                return True, "exe"
            except OSError:
                pass
    # 3) 最後手段：交給 claude:// 協定（沒有安裝時會丟出錯誤）
    try:
        os.startfile("claude://")
        return True, "protocol"
    except OSError:
        return False, "missing"


# ---------------- 終端機版 Claude Code ----------------
def find_claude() -> str | None:
    home = Path.home()
    if IS_MAC:  # 從 Finder 開的 App 拿不到使用者 shell 的 PATH，所以把常見位置都找一遍
        candidates = [
            shutil.which("claude"),
            str(home / ".local" / "bin" / "claude"),
            str(home / ".claude" / "local" / "claude"),
            "/opt/homebrew/bin/claude",
            "/usr/local/bin/claude",
            str(home / ".npm-global" / "bin" / "claude"),
        ]
    else:
        candidates = [
            shutil.which("claude"),
            str(home / ".local" / "bin" / "claude.exe"),
            str(Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd"),
        ]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return None


def find_wt() -> str | None:
    wt = shutil.which("wt")
    if wt:
        return wt
    p = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "wt.exe"
    return str(p) if p.exists() else None


def find_shell() -> str:
    for name in ("pwsh", "powershell"):
        p = shutil.which(name)
        if p:
            return p
    return r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"


def _ps_quote(s: str) -> str:
    return s.replace("'", "''")


def mac_command_script(folder: str, claude: str, args: list[str] | None = None) -> str:
    """macOS：給「終端機」執行的 .command 腳本內容。

    每個值都用 shlex.quote 包起來，資料夾路徑有空白、引號、分號、$ 都不會被 shell 誤解。
    用 zsh -l（登入 shell）跑，才讀得到使用者平常的 PATH。
    """
    cmd = " ".join(shlex.quote(a) for a in [claude, *(args or [])])
    return (
        "#!/bin/zsh -l\n"
        "printf '\\033]0;Claude Code\\007'\n"          # 視窗標題
        f"cd {shlex.quote(folder)} || exit 1\n"
        f"{cmd}\n"
        "exec /bin/zsh -l\n"                           # Claude 結束後留在 shell，視窗不會直接關掉
    )


def _mac_launch(folder: str, claude: str, args: list[str] | None) -> tuple[bool, str]:
    from . import paths
    script = paths.data_dir() / "open-claude.command"
    try:
        script.write_text(mac_command_script(folder, claude, args), encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        subprocess.Popen(["open", "-a", "Terminal", str(script)])
        return True, "Terminal"
    except OSError as e:
        return False, f"無法開啟終端機：{e}"


def launch(folder: str, args: list[str] | None = None) -> tuple[bool, str]:
    """回傳 (是否成功, 說明訊息)。"""
    folder = str(Path(folder))
    if not Path(folder).is_dir():
        return False, f"找不到資料夾：{folder}"
    claude = find_claude()
    if not claude:
        return False, "找不到 claude 指令，請先安裝 Claude Code"
    if IS_MAC:
        return _mac_launch(folder, claude, args)

    arg_str = " ".join(args or [])
    script = (
        "$Host.UI.RawUI.WindowTitle = 'Claude Code'; "
        # 重新讀取系統 PATH：桌寵比 Git / Claude 先啟動時，也找得到它們
        "$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + "
        "[Environment]::GetEnvironmentVariable('Path','User'); "
        f"Set-Location -LiteralPath '{_ps_quote(folder)}'; "
        f"& '{_ps_quote(claude)}' {arg_str}"
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    ps_cmd = [find_shell(), "-NoLogo", "-NoExit", "-EncodedCommand", encoded]

    wt = find_wt()
    if wt:
        # 不傳 -d：資料夾由腳本裡的 Set-Location 切換（wt 會把路徑裡的分號當成指令分隔）
        try:
            subprocess.Popen([wt] + ps_cmd, close_fds=True)
            return True, "Windows Terminal"
        except OSError:
            pass

    try:
        subprocess.Popen(ps_cmd, cwd=folder, creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True, "PowerShell"
    except OSError as e:
        return False, f"無法開啟終端機：{e}"
