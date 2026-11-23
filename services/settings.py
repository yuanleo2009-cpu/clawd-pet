"""設定檔：%APPDATA%\\ClawdPet\\settings.json

載入時逐欄檢查型別與允許值，手改壞掉的欄位會改用預設值，程式不會因此開不起來。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import paths

DEFAULTS = {
    "pos": None,            # 視窗左上角 [x, y]
    "size": 4,              # 大小檔位（3 小 / 4 中 / 5 大 / 6 特大）
    "project_dir": "",      # 終端機版 Claude Code（右鍵 → 進階）使用的專案資料夾
    "recent_dirs": [],      # 最近使用的專案資料夾
    "bubbles": True,        # 點擊時冒對話泡泡
    "chatter": True,        # 偶爾自言自語
    "skin": "crab",         # crab = 內建 Clawd；custom = assets/clawd.png
    "fps": 120,             # 幀率；0 = 跟隨螢幕更新率
    "smooth": True,         # 抗鋸齒（平滑）繪製
    "dock": "always",       # 吸附底部：always = 放開後總是落到底部；near = 靠近時吸附；off = 關閉
}
CHOICES = {                 # 只能是這幾個值的欄位
    "size": {3, 4, 5, 6},
    "skin": {"crab", "custom"},
    "dock": {"always", "near", "off"},
}
MAX_RECENT = 6


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _clean(key: str, value):
    """回傳合法的值；不合法就回傳預設值。"""
    default = DEFAULTS[key]
    if key == "pos":
        if isinstance(value, list) and len(value) == 2 and all(_is_number(v) for v in value):
            return [int(value[0]), int(value[1])]
        return None
    if key == "fps":
        ok = isinstance(value, int) and not isinstance(value, bool) and (value == 0 or 15 <= value <= 360)
        return value if ok else default
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    if isinstance(default, int):
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif isinstance(default, list):
        return [v for v in value if isinstance(v, str) and v][:MAX_RECENT] if isinstance(value, list) else []
    else:
        ok = isinstance(value, str)
    if ok and key in CHOICES and value not in CHOICES[key]:
        ok = False
    return value if ok else default


class Settings:
    def __init__(self, path: Path, data: dict):
        self.path = path
        self.data = {k: _clean(k, data.get(k, v)) for k, v in DEFAULTS.items()}

    @classmethod
    def load(cls) -> "Settings":
        path = paths.data_dir() / "settings.json"
        data = {}
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            pass
        return cls(path, data)

    def __getitem__(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self.data[key] = _clean(key, value) if key in DEFAULTS else value

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
