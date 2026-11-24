"""設定檔的單元測試：手改壞掉的值要自動改回預設，不能讓程式開不起來。"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.settings import DEFAULTS, Settings  # noqa: E402

NOWHERE = Path(os.devnull)


class SettingsTests(unittest.TestCase):
    def test_broken_values_fall_back_to_defaults(self):
        s = Settings(NOWHERE, {
            "size": "大", "fps": "fast", "pos": ["a", 1], "recent_dirs": None,
            "dock": "sideways", "skin": 3, "smooth": 1, "bubbles": "yes", "project_dir": 42,
        })
        for key in ("size", "fps", "dock", "skin", "smooth", "bubbles", "project_dir"):
            self.assertEqual(s[key], DEFAULTS[key], key)
        self.assertIsNone(s["pos"])
        self.assertEqual(s["recent_dirs"], [])

    def test_valid_values_are_kept(self):
        s = Settings(NOWHERE, {"size": 6, "fps": 0, "pos": [10.7, -20], "dock": "off",
                               "recent_dirs": ["C:\\a", 5, "", "C:\\b"]})
        self.assertEqual(s["size"], 6)
        self.assertEqual(s["fps"], 0)            # 0 = 跟隨螢幕
        self.assertEqual(s["pos"], [10, -20])
        self.assertEqual(s["dock"], "off")
        self.assertEqual(s["recent_dirs"], ["C:\\a", "C:\\b"])

    def test_out_of_range_numbers_are_rejected(self):
        s = Settings(NOWHERE, {"size": 99, "fps": 5000, "pos": [True, 3]})
        self.assertEqual(s["size"], DEFAULTS["size"])
        self.assertEqual(s["fps"], DEFAULTS["fps"])
        self.assertIsNone(s["pos"])

    def test_reminder_and_chase_settings(self):
        s = Settings(NOWHERE, {"water_minutes": 45, "chime": True, "chase": True})
        self.assertEqual(s["water_minutes"], 45)
        self.assertTrue(s["chime"])
        self.assertTrue(s["chase"])
        bad = Settings(NOWHERE, {"water_minutes": 7, "chime": "yes", "chase": 1})
        self.assertEqual(bad["water_minutes"], 0)      # 不在選項裡 → 關閉
        self.assertFalse(bad["chime"])
        self.assertFalse(bad["chase"])

    def test_not_a_dict_and_unknown_keys(self):
        s = Settings(NOWHERE, {"something_else": 1})
        self.assertNotIn("something_else", s.data)
        self.assertEqual(set(s.data), set(DEFAULTS))

    def test_setitem_also_validates(self):
        s = Settings(NOWHERE, {})
        s["size"] = "huge"
        self.assertEqual(s["size"], DEFAULTS["size"])
        s["size"] = 5
        self.assertEqual(s["size"], 5)


if __name__ == "__main__":
    unittest.main()
