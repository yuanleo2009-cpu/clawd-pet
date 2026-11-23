"""設定檔：%APPDATA%\\ClawdPet\\settings.json"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import paths

DEFAULTS = {
    "pos": None,            # 視窗左上角 [x, y]
    "size": 4,              # 大小檔位（3 小 / 4 中 / 5 大 / 6 特大）
    "project_dir": "",      # 雙擊時開啟的專案資料夾
    "recent_dirs": [],      # 最近使用的專案資料夾
    "bubbles": True,        # 點擊時冒對話泡泡
    "chatter": True,        # 偶爾自言自語
    "skin": "crab",         # crab = 內建小螃蟹；custom = assets/clawd.png
    "fps": 120,             # 幀率；0 = 跟隨螢幕更新率
    "smooth": True,         # 抗鋸齒（平滑）繪製
    "dock": "always",       # 吸附底部：always = 放開後總是落到底部；near = 靠近時吸附；off = 關閉
}
MAX_RECENT = 6


class Settings:
    def __init__(self, path: Path, data: dict):
        self.path = path
        self.data = {**DEFAULTS, **data}

    @classmethod
    def load(cls) -> "Settings":
        path = paths.data_dir() / "settings.json"
        data = {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            pass
        return cls(path, data)

    def __getitem__(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self.data[key] = value

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def set_project(self, folder: str) -> None:
        folder = str(Path(folder))
        self["project_dir"] = folder
        recent = [d for d in self["recent_dirs"] if os.path.normcase(d) != os.path.normcase(folder)]
        recent.insert(0, folder)
        self["recent_dirs"] = recent[:MAX_RECENT]
        self.save()
