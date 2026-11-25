"""主視窗整合測試：用離屏模式（不顯示在螢幕上）建立真的 PetWindow 來測。

Windows 和 macOS 都會跑（GitHub Actions 兩邊都跑），確認介面相關的程式在兩個系統上都正常。
不會讀寫使用者真正的設定檔。
"""
import os
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from services.settings import Settings  # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv)


def _touches_edge(img: QImage) -> bool:
    a = img.convertToFormat(QImage.Format.Format_Alpha8)
    w, h, bpl = a.width(), a.height(), a.bytesPerLine()
    data = bytes(a.constBits())
    lines = [data[0:w], data[(h - 1) * bpl:(h - 1) * bpl + w],
             bytes(data[y * bpl] for y in range(h)), bytes(data[y * bpl + w - 1] for y in range(h))]
    return any(any(v > 8 for v in line) for line in lines)


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._load, cls._save = Settings.load, Settings.save
        Settings.load = classmethod(lambda c: c(Path(os.devnull), {}))
        Settings.save = lambda self: None
        from pet.window import PetWindow
        cls.w = w = PetWindow()
        for t in (w._tick, w._idle, w._chatter):
            t.stop()
        w.tray.hide()
        w.show()
        g = w._screen_rect()
        fo = w._feet_offset()
        w.move(g.center().x() - fo.x(), g.bottom() - fo.y())

    @classmethod
    def tearDownClass(cls):
        cls.w.bubble.close()
        cls.w.close()
        Settings.load, Settings.save = cls._load, cls._save

    def setUp(self):
        from pet.animator import Animator
        self.w.anim = Animator()
        self.w._fall = None
        self.w.fx.clear()
        g = self.w._screen_rect()
        fo = self.w._feet_offset()
        self.w.move(g.center().x() - fo.x(), g.bottom() - fo.y())

    def test_starts_on_the_floor_and_paints(self):
        self.assertTrue(self.w._on_floor())
        self.w._on_tick()
        img = self.w.grab().toImage()
        self.assertFalse(img.isNull())
        self.assertGreater(img.width(), 0)

    def test_menu_has_every_section(self):
        texts = []

        def walk(m):
            for a in m.actions():
                if a.text():
                    texts.append(a.text())
                if a.menu():
                    walk(a.menu())
        walk(self.w._build_menu())
        for needle in ("開啟 Claude", "動作", "提醒", "大小", "畫面", "吸附底部", "造型", "說話", "結束"):
            self.assertTrue(any(needle in t for t in texts), needle)

    def test_thrown_pet_lands_on_the_floor(self):
        w = self.w
        g = w._screen_rect()
        w.move(w.x(), g.top() + 50)
        w.anim.end_drag(fall=True)
        w._start_fall(1800, -600)
        for _ in range(1200):
            if w._fall is None:
                break
            w._step_fall(1 / 120)
        self.assertIsNone(w._fall)
        self.assertTrue(w._on_floor())

    def test_no_animation_is_cut_off_by_the_window(self):
        from pet.animator import ACTIONS, Animator
        w = self.w
        for act in ACTIONS:
            w.anim = Animator(now=0.0)
            w.anim.play(act, 0.0)
            for i in range(0, int(ACTIONS[act] * 60), 3):
                w.pose = w.anim.update(i / 60)
                self.assertFalse(_touches_edge(w.grab().toImage()), f"{act} t={i / 60:.2f}")
        for deg in range(0, 360, 15):                       # 被丟出去時在空中旋轉
            w.anim = Animator(now=0.0)
            w.anim.end_drag(fall=True, now=0.0)
            w.anim._fall_rot = deg
            w.pose = w.anim.update(0.0)
            self.assertFalse(_touches_edge(w.grab().toImage()), f"throw {deg}")

    def test_feed_and_hide(self):
        w = self.w
        w.feed()
        kinds = set()
        end = time.perf_counter() + 2.7
        while time.perf_counter() < end:
            w._on_tick()
            kinds.update(p.kind for p in w.fx.particles)
            time.sleep(1 / 120)
        w._tick.stop()
        self.assertTrue({"snack", "heart"} <= kinds, kinds)
        w.anim._action = None
        w.play_hide()
        self.assertEqual(w.anim.action, "hide")

    def test_wheel_resizes(self):
        w = self.w

        class Wheel:
            def __init__(self, dy):
                self.dy = dy

            def angleDelta(self):
                return QPoint(0, self.dy)

            def accept(self):
                pass
        start = w.settings["size"]
        w._last_wheel = 0
        w.wheelEvent(Wheel(-120))
        self.assertEqual(w.settings["size"], start - 1)
        w._last_wheel = 0
        w.wheelEvent(Wheel(120))
        self.assertEqual(w.settings["size"], start)

    def test_menu_wording_matches_the_system(self):
        from services import osinfo
        texts = []

        def walk(m):
            for a in m.actions():
                texts.append(a.text())
                if a.menu():
                    walk(a.menu())
        walk(self.w._build_menu())
        self.assertTrue(any(osinfo.AUTOSTART_LABEL in t for t in texts))
        if osinfo.IS_MAC:
            self.assertFalse(any("開機" in t or "檔案總管" in t for t in texts))


if __name__ == "__main__":
    unittest.main()
