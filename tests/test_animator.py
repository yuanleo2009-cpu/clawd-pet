"""動畫狀態機的單元測試：時間全部由測試傳入，不需要真的等。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet.animator import ACTIONS, SLEEP_AFTER, Animator  # noqa: E402


def run(anim: Animator, start: float, end: float, step: float = 1 / 60):
    """從 start 到 end 逐幀更新，回傳最後一個 pose。"""
    t, pose = start, None
    while t <= end:
        pose = anim.update(t)
        t += step
    return pose


class AnimatorTests(unittest.TestCase):
    def test_falls_asleep_after_idle_time(self):
        a = Animator(now=0.0)
        run(a, 0, SLEEP_AFTER - 1, step=0.5)
        self.assertFalse(a.sleeping)
        pose = run(a, SLEEP_AFTER - 0.5, SLEEP_AFTER + 1, step=0.5)
        self.assertTrue(a.sleeping)
        self.assertEqual(pose.sprite, "sleep")

    def test_poke_wakes_up_and_reports_it(self):
        a = Animator(now=0.0)
        run(a, 0, SLEEP_AFTER + 1, step=0.5)
        self.assertTrue(a.poke(SLEEP_AFTER + 2))
        self.assertFalse(a.sleeping)
        self.assertFalse(a.poke(SLEEP_AFTER + 3))  # 已經醒著

    def test_jump_shows_happy_then_returns_to_idle(self):
        a = Animator(now=0.0)
        a.play("jump", 10.0)
        self.assertEqual(a.update(10.3).sprite, "happy")
        self.assertLess(a.update(10.33).dy, -5)  # 在空中
        run(a, 10.4, 10.0 + ACTIONS["jump"] + 0.1)
        self.assertIsNone(a.action)

    def test_idle_bob_never_sinks_below_the_floor(self):
        a = Animator(now=0.0)
        for i in range(600):
            pose = a.update(i / 60)
            self.assertLessEqual(pose.dy, 1e-9, f"t={i / 60:.2f}s dy={pose.dy}")

    def test_drag_then_fall_then_land(self):
        a = Animator(now=0.0)
        a.start_drag(1.0)
        pose = a.update(1.1)
        self.assertEqual(pose.sprite, "lifted")
        self.assertTrue(pose.anchor_top)
        self.assertGreater(pose.sy, 1.0)  # 被拎起來會拉長
        a.end_drag(fall=True, now=1.5)
        self.assertEqual(a.update(1.6).sprite, "lifted")
        a.land(2.0)
        self.assertFalse(a.falling)
        self.assertEqual(a.action, "land")

    def test_talk_alternates_mouth_frames(self):
        a = Animator(now=0.0)
        a.talk(1.0, 5.0)
        sprites = {a.update(5.0 + i * 0.05).sprite for i in range(15)}
        self.assertIn("talk", sprites)


if __name__ == "__main__":
    unittest.main()
