"""提醒：喝水提醒、番茄鐘、整點報時。

純邏輯，不碰介面：時間（秒）和現在幾點都由外部傳入，方便測試。
視窗每秒呼叫一次 poll()，拿到要顯示的事件。
"""
from __future__ import annotations

FOCUS_MINUTES = 25
BREAK_MINUTES = 5
WATER_CHOICES = (0, 30, 45, 60, 90)   # 0 = 關閉


class Reminders:
    def __init__(self, now: float, hour: int, water_minutes: int = 0, chime: bool = False):
        self.water_minutes = 0
        self._water_at: float | None = None
        self.chime = chime
        self._last_hour = hour            # 啟動的那個小時不報時
        self._phase: str | None = None    # None / "focus" / "break"
        self._phase_end = 0.0
        self.set_water(water_minutes, now)

    # ---------- 喝水 ----------
    def set_water(self, minutes: int, now: float) -> None:
        self.water_minutes = minutes if minutes in WATER_CHOICES else 0
        self._water_at = now + self.water_minutes * 60 if self.water_minutes else None

    # ---------- 番茄鐘 ----------
    def start_pomodoro(self, now: float, minutes: float = FOCUS_MINUTES) -> None:
        self._phase = "focus"
        self._phase_end = now + minutes * 60

    def cancel_pomodoro(self) -> None:
        self._phase = None

    @property
    def phase(self) -> str | None:
        return self._phase

    def seconds_left(self, now: float) -> float:
        """番茄鐘目前階段還剩幾秒；沒在跑就是 0。"""
        return max(0.0, self._phase_end - now) if self._phase else 0.0

    # ---------- 每秒檢查 ----------
    def poll(self, now: float, hour: int) -> list[tuple]:
        """回傳這一刻要提醒的事件：
        ("water",)、("focus_done",)、("break_done",)、("chime", 幾點)
        """
        events: list[tuple] = []
        if self._water_at is not None and now >= self._water_at:
            events.append(("water",))
            self._water_at = now + self.water_minutes * 60
        if self._phase == "focus" and now >= self._phase_end:
            events.append(("focus_done",))
            self._phase = "break"                      # 專注完自動接著休息
            self._phase_end = now + BREAK_MINUTES * 60
        elif self._phase == "break" and now >= self._phase_end:
            events.append(("break_done",))
            self._phase = None
        if hour != self._last_hour:
            self._last_hour = hour
            if self.chime:
                events.append(("chime", hour))
        return events
