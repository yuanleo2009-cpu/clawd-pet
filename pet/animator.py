"""動畫狀態機：每一幀算出要顯示哪張圖，以及位移、縮放、旋轉。

位移的單位是「素材原始像素」（內建素材寬 40），由視窗換算成螢幕像素。
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

SLEEP_AFTER = 180.0  # 幾秒沒互動就睡覺

ACTIONS = {          # 動作名稱: 持續秒數
    "jump": 0.8,
    "squish": 0.9,
    "shake": 0.8,
    "land": 0.7,
    "idea": 1.8,
}


@dataclass
class Pose:
    sprite: str = "idle"
    dx: float = 0.0           # 水平位移
    dy: float = 0.0           # 垂直位移（負數往上）
    sx: float = 1.0           # 水平縮放（負數 = 左右翻轉）
    sy: float = 1.0           # 垂直縮放
    rot: float = 0.0          # 旋轉角度
    anchor_top: bool = False  # True = 以頭頂為支點（被拎起來時）


def _ease(p: float) -> float:
    p = min(max(p, 0.0), 1.0)
    return p * p * (3 - 2 * p)


class Animator:
    def __init__(self):
        now = time.perf_counter()
        self.t0 = now
        self._last = now
        # 面向：1 = 原圖方向，-1 = 翻轉
        self.facing = 1.0
        self._turn_from = 1.0
        self._turn_start = -10.0
        # 待機小動作
        self._next_blink = now + random.uniform(2, 5)
        self._blink_until = 0.0
        self._next_look = now + random.uniform(5, 10)
        self._look_start = 0.0
        self._look_until = 0.0
        # 主動作
        self._action: str | None = None
        self._action_start = 0.0
        self._talk_until = 0.0
        # 拖曳
        self.dragging = False
        self._vx = 0.0
        self._sway = 0.0
        self._sway_v = 0.0
        # 往下掉（吸附到底部時）
        self.falling = False
        # 睡覺
        self._last_interaction = now
        self.sleeping = False

    # ---------- 外部呼叫 ----------
    def poke(self) -> bool:
        """有互動：重設睡眠計時。回傳原本是否在睡覺。"""
        was = self.sleeping
        self.sleeping = False
        self._last_interaction = time.perf_counter()
        return was

    def play(self, name: str) -> None:
        self.poke()
        self._action = name
        self._action_start = time.perf_counter()

    def talk(self, seconds: float) -> None:
        self.poke()
        self._talk_until = time.perf_counter() + seconds

    def start_drag(self) -> None:
        self.poke()
        self.dragging = True
        self._action = None
        self._vx = self._sway = self._sway_v = 0.0

    def drag_velocity(self, vx: float) -> None:
        self._vx = self._vx * 0.6 + vx * 0.4  # 平滑一點，避免抖動

    def end_drag(self, fall: bool = False) -> None:
        self.dragging = False
        if fall:
            self.falling = True
        else:
            self.play("land")

    def land(self) -> None:
        self.falling = False
        self.play("land")

    # ---------- 每幀更新 ----------
    def update(self, now: float) -> Pose:
        dt = min(now - self._last, 0.1)
        self._last = now
        t = now - self.t0
        pose = Pose()

        if self.dragging:
            return self._drag_pose(pose, t, dt, now)

        if self.falling:  # 往下掉：手舉高、身體被風拉長一點
            pose.sprite = "lifted"
            pose.sy = 1.08
            pose.sx = 0.94 * self._facing_value(now)
            return pose

        if (not self.sleeping and self._action is None and now >= self._talk_until
                and now - self._last_interaction > SLEEP_AFTER):
            self.sleeping = True

        if self.sleeping:
            breath = math.sin(t * 2 * math.pi / 3.6)
            pose.sprite = "sleep"
            pose.sy = 1 + 0.035 * breath
            pose.sx = (1 - 0.02 * breath) * self._facing_value(now)
            return pose

        # 緩慢上下浮動（只往上浮，站在工作列上時腳不會陷進去）
        pose.dy = (math.sin(t * 2 * math.pi / 2.8) - 1) * 1.1
        sprite = "idle"

        # 偶爾左右張望：轉身 + 看向那邊 + 稍微探頭
        if self._action is None and now >= self._next_look and now >= self._talk_until:
            self._look_start = now
            self._look_until = now + random.uniform(1.4, 2.6)
            self._turn(now, -self.facing)
            self._next_look = now + random.uniform(6, 14)
        if now < self._look_until:
            sprite = "look"
            p = (now - self._look_start) / (self._look_until - self._look_start)
            lean = math.sin(p * math.pi)
            pose.rot = 4 * lean * self.facing
            pose.dx = 1.0 * lean * self.facing

        # 眨眼
        if now >= self._next_blink:
            self._blink_until = now + 0.13
            self._next_blink = now + random.uniform(2.5, 6)
        if now < self._blink_until and sprite in ("idle", "look"):
            sprite = "blink"

        # 說話：一邊揮手
        if now < self._talk_until:
            sprite = "talk" if int(now * 1000 // 180) % 2 == 0 else "idle"

        # 主動作
        if self._action:
            a = now - self._action_start
            if a >= ACTIONS[self._action]:
                self._action = None
            else:
                sprite = self._apply_action(self._action, pose, a, sprite)

        pose.sprite = sprite
        pose.sx *= self._facing_value(now)
        return pose

    # ---------- 內部 ----------
    def _turn(self, now: float, to: float) -> None:
        self._turn_from = self._facing_value(now)
        self.facing = to
        self._turn_start = now

    def _facing_value(self, now: float) -> float:
        p = (now - self._turn_start) / 0.2
        if p >= 1:
            return self.facing
        v = self._turn_from + (self.facing - self._turn_from) * _ease(p)
        if abs(v) < 0.08:  # 轉身經過「側面」時不要完全消失
            v = 0.08 if self.facing > 0 else -0.08
        return v

    def _drag_pose(self, pose: Pose, t: float, dt: float, now: float) -> Pose:
        # 往右拖 → 身體往左甩，用彈簧讓它晃來晃去
        target = max(-20.0, min(20.0, -self._vx * 0.035))
        self._vx *= math.exp(-dt * 6)
        acc = (target - self._sway) * 120 - self._sway_v * 12
        self._sway_v += acc * dt
        self._sway += self._sway_v * dt
        wob = math.sin(t * 14) * 0.015
        pose.sprite = "lifted"
        pose.anchor_top = True
        pose.sy = 1.16 + wob          # 被拎起來：拉長
        pose.sx = (0.88 - wob) * self._facing_value(now)
        pose.rot = self._sway
        return pose

    @staticmethod
    def _apply_action(name: str, pose: Pose, a: float, sprite: str) -> str:
        if name == "jump":
            if a < 0.12:                         # 蹲下蓄力
                k = a / 0.12
                pose.sy *= 1 - 0.2 * k
                pose.sx *= 1 + 0.15 * k
                return sprite
            if a < 0.55:                         # 騰空
                q = (a - 0.12) / 0.43
                pose.dy += -10 * 4 * q * (1 - q)
                s = 1 - q
                pose.sy *= 1 + 0.14 * s
                pose.sx *= 1 - 0.09 * s
                return "happy"
            r = (a - 0.55) / 0.25                # 落地回彈
            d = math.exp(-4 * r) * math.cos(r * math.pi * 3)
            pose.sy *= 1 - 0.2 * d
            pose.sx *= 1 + 0.15 * d
            return "happy" if r < 0.5 else sprite

        if name == "squish":                     # 被戳：壓扁再彈回
            d = math.exp(-4.5 * a) * math.cos(a * 18)
            pose.sy *= 1 - 0.28 * d
            pose.sx *= 1 + 0.22 * d
            if a < 0.25:
                return "blink"
            return "happy" if a < 0.6 else sprite

        if name == "shake":                      # 左右搖晃
            pose.rot += 12 * math.exp(-3.5 * a) * math.sin(a * 30)
            return sprite

        if name == "land":                       # 放下後的回彈
            d = math.exp(-5 * a) * math.cos(a * 16)
            pose.sy *= 1 - 0.25 * d
            pose.sx *= 1 + 0.2 * d
            return "happy" if a < 0.3 else sprite

        if name == "idea":                       # 頭上冒燈泡，小跳一下
            if a < 0.4:
                q = a / 0.4
                pose.dy += -4 * 4 * q * (1 - q)
            return "idea"

        return sprite
