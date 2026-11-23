"""台詞：存在 %APPDATA%\\ClawdPet\\phrases.txt，可以自己編輯，存檔後立即生效。"""
from __future__ import annotations

import random
import shutil

from services import paths


class Phrases:
    def __init__(self):
        self.path = paths.data_dir() / "phrases.txt"
        if not self.path.exists():
            src = paths.assets_dir() / "phrases.txt"
            try:
                shutil.copyfile(src, self.path)
            except OSError:
                self.path.write_text("嗨！\n", encoding="utf-8")
        self._mtime = None
        self._lines: list[str] = []
        self._last = ""

    def _reload(self) -> None:
        try:
            m = self.path.stat().st_mtime
            if m == self._mtime:
                return
            self._mtime = m
            text = self.path.read_text(encoding="utf-8-sig")
        except OSError:
            return
        self._lines = [s.strip() for s in text.splitlines()
                       if s.strip() and not s.strip().startswith("#")]

    def random(self) -> str:
        self._reload()
        if not self._lines:
            return "🦀"
        choices = [s for s in self._lines if s != self._last] or self._lines
        self._last = random.choice(choices)
        return self._last
