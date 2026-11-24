"""提醒（喝水、番茄鐘、整點報時）的單元測試：時間由測試傳入。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.reminders import BREAK_MINUTES, FOCUS_MINUTES, Reminders  # noqa: E402

MIN = 60.0


class RemindersTests(unittest.TestCase):
    def test_nothing_happens_by_default(self):
        r = Reminders(0.0, hour=9)
        for t in range(0, 4 * 3600, 60):
            self.assertEqual(r.poll(float(t), hour=9), [])

    def test_water_reminder_repeats(self):
        r = Reminders(0.0, hour=9, water_minutes=30)
        self.assertEqual(r.poll(29 * MIN, 9), [])
        self.assertEqual(r.poll(30 * MIN, 9), [("water",)])
        self.assertEqual(r.poll(31 * MIN, 9), [])            # 提醒過就重新計時
        self.assertEqual(r.poll(60 * MIN + 1, 9), [("water",)])

    def test_water_can_be_turned_off_and_rejects_odd_values(self):
        r = Reminders(0.0, hour=9, water_minutes=30)
        r.set_water(0, 10 * MIN)
        self.assertEqual(r.poll(500 * MIN, 9), [])
        r.set_water(7, 0.0)                                  # 不在選項裡 → 當成關閉
        self.assertEqual(r.water_minutes, 0)

    def test_pomodoro_focus_then_break(self):
        r = Reminders(0.0, hour=9)
        r.start_pomodoro(100.0)
        self.assertEqual(r.phase, "focus")
        self.assertAlmostEqual(r.seconds_left(100.0 + 10 * MIN), 15 * MIN)
        self.assertEqual(r.poll(100.0 + FOCUS_MINUTES * MIN - 1, 9), [])
        self.assertEqual(r.poll(100.0 + FOCUS_MINUTES * MIN, 9), [("focus_done",)])
        self.assertEqual(r.phase, "break")
        end = 100.0 + (FOCUS_MINUTES + BREAK_MINUTES) * MIN
        self.assertEqual(r.poll(end - 1, 9), [])
        self.assertEqual(r.poll(end, 9), [("break_done",)])
        self.assertIsNone(r.phase)
        self.assertEqual(r.seconds_left(end + 1), 0.0)

    def test_pomodoro_cancel(self):
        r = Reminders(0.0, hour=9)
        r.start_pomodoro(0.0)
        r.cancel_pomodoro()
        self.assertEqual(r.poll(100 * MIN, 9), [])

    def test_hourly_chime_only_when_enabled_and_not_at_startup(self):
        r = Reminders(0.0, hour=9, chime=True)
        self.assertEqual(r.poll(1.0, 9), [])                 # 啟動的那個小時不報
        self.assertEqual(r.poll(2.0, 10), [("chime", 10)])
        self.assertEqual(r.poll(3.0, 10), [])                # 同一個小時只報一次
        self.assertEqual(r.poll(4.0, 0), [("chime", 0)])     # 跨日
        quiet = Reminders(0.0, hour=9, chime=False)
        self.assertEqual(quiet.poll(1.0, 10), [])
        quiet.chime = True                                   # 中途打開：下個整點才報
        self.assertEqual(quiet.poll(2.0, 10), [])
        self.assertEqual(quiet.poll(3.0, 11), [("chime", 11)])


if __name__ == "__main__":
    unittest.main()
