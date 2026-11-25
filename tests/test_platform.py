"""跨平台部分的測試：macOS 終端機腳本、登入自動啟動、資料夾位置。"""
import os
import plistlib
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import autostart, launcher, paths  # noqa: E402

IS_MAC = sys.platform == "darwin"


class MacCommandScriptTests(unittest.TestCase):
    """開終端機版 Claude Code 的 .command 腳本（純文字產生，任何系統都能測）。"""

    def test_paths_with_spaces_quotes_and_semicolons_are_quoted(self):
        folder = "/Users/a b/proj; rm -rf ~ $(x) 'q'"
        text = launcher.mac_command_script(folder, "/opt/homebrew/bin/claude", ["--continue"])
        self.assertTrue(text.startswith("#!/bin/zsh -l\n"))
        self.assertIn(f"cd {shlex.quote(folder)} || exit 1\n", text)
        self.assertIn("/opt/homebrew/bin/claude --continue\n", text)
        cd_line = [ln for ln in text.splitlines() if ln.startswith("cd ")][0]
        self.assertEqual(shlex.split(cd_line), ["cd", folder, "||", "exit", "1"])

    @unittest.skipUnless(IS_MAC, "只有 macOS 有 zsh 可以實際執行")
    def test_script_really_cds_into_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "a b; c 'd'"
            folder.mkdir()
            script = launcher.mac_command_script(str(folder), "/bin/pwd")
            script = script.replace("exec /bin/zsh -l\n", "")      # 測試時不要留在 shell 裡
            out = subprocess.run(["/bin/zsh", "-c", script], capture_output=True, text=True, timeout=20)
            self.assertEqual(out.stdout.strip().splitlines()[-1], str(folder.resolve()))


class AutostartTests(unittest.TestCase):
    @unittest.skipUnless(IS_MAC, "macOS LaunchAgent")
    def test_mac_launch_agent_roundtrip(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home}):
            self.assertFalse(autostart.is_enabled())
            autostart.set_enabled(True)
            p = Path(home) / "Library" / "LaunchAgents" / f"{autostart.MAC_LABEL}.plist"
            self.assertTrue(p.is_file())
            data = plistlib.loads(p.read_bytes())
            self.assertEqual(data["Label"], autostart.MAC_LABEL)
            self.assertTrue(data["RunAtLoad"])
            self.assertTrue(data["ProgramArguments"][-1].endswith("main.py"))
            self.assertTrue(autostart.is_enabled())
            autostart.set_enabled(False)
            self.assertFalse(p.exists())

    @unittest.skipUnless(IS_MAC, "macOS 路徑格式")
    def test_mac_arguments_for_a_bundled_app(self):
        exe = "/Applications/ClawdPet.app/Contents/MacOS/ClawdPet"
        with mock.patch.object(paths, "is_frozen", return_value=True), \
                mock.patch.object(sys, "executable", exe), \
                mock.patch.object(Path, "resolve", lambda self: self):
            self.assertEqual(autostart.mac_program_arguments(),
                             ["/usr/bin/open", "/Applications/ClawdPet.app"])


class PathsTests(unittest.TestCase):
    def test_data_dir_location(self):
        d = paths.data_dir()
        self.assertTrue(d.is_dir())
        self.assertEqual(d.name, "ClawdPet")
        if IS_MAC:
            self.assertEqual(d.parent, Path.home() / "Library" / "Application Support")


class LauncherTests(unittest.TestCase):
    """macOS 開 Claude 桌面版：依序試 App 路徑 → bundle id → App 名稱；全部失敗要回報 missing。"""

    def test_mac_open_reports_missing_when_every_attempt_fails(self):
        with mock.patch.object(launcher, "_mac_app_path", return_value=None), \
                mock.patch.object(launcher.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 1)
            self.assertEqual(launcher._mac_open_desktop_app(), (False, "missing"))
            tried = [c.args[0] for c in run.call_args_list]
            self.assertEqual(tried, [["open", "-b", launcher.MAC_BUNDLE_ID], ["open", "-a", "Claude"]])

    def test_mac_open_uses_the_app_path_first(self):
        app = Path("/Applications/Claude.app")
        with mock.patch.object(launcher, "_mac_app_path", return_value=app), \
                mock.patch.object(launcher.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0)
            self.assertEqual(launcher._mac_open_desktop_app(), (True, "mac"))
            self.assertEqual(run.call_args_list[0].args[0], ["open", str(app)])
            self.assertEqual(run.call_count, 1)

    @unittest.skipUnless(IS_MAC, "macOS")
    def test_real_mac_detection_does_not_crash(self):
        self.assertIsInstance(launcher.is_desktop_app_installed(), bool)


if __name__ == "__main__":
    unittest.main()
