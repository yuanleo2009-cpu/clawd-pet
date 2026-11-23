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
    "dance": 3.6,    # 左右搖擺、手舉高放下（視窗會飄出音符）
    "spin": 1.0,     # 跳起來在空中翻一圈
    "dizzy": 2.6,    # 被搖暈：X X 眼、東倒西歪（視窗畫繞圈的星星）
    "pet": 1.4,      # 被摸摸：開心地扭來扭去（視窗冒愛心）
    "wave": 1.6,     # 揮手打招呼
}
WALK_STEPS = 7.0     # 走路時每秒換幾次腳


@dataclass
class Pose:
    sprite: str = "idle"
    dx: float = 0.0           # 水平位移
    dy: float = 0.0           # 垂直位移（負數往上）
    sx: float = 1.0           # 水平縮放（負數 = 左右翻轉）
    sy: float = 1.0           # 垂直縮放
    rot: float = 0.0          # 旋轉角度
    anchor_top: bool = False  # True = 以頭頂為支點（被拎起來時）


def _now(now: float | None) -> float:
    return time.perf_counter() if now is None else now


def _ease(p: float) -> float:
    p = min(max(p, 0.0), 1.0)
    return p * p * (3 - 2 * p)


class Animator:
    def __init__(self, now: float | None = None):
        # 所有時間都可以從外部傳入（測試時用假時間）；不傳就用目前時間
        now = time.perf_counter() if now is None else now
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
        self.fall_spin = 0.0               # 被丟出去時在空中的旋轉速度（度/秒），由視窗設定
        self._fall_rot = 0.0
        self._land_strength = 1.0          # 落地力道：越大壓得越扁
        # 給視窗的一次性事件（例如跳躍落地 → 揚起一點灰塵），由 pop_events() 取走
        self._events: list[str] = []
        self._sent: set = set()
        # 走路（0 = 沒在走；1 = 往右；-1 = 往左）、看著滑鼠
        self.walking = 0
        self._watch_until = 0.0
        # 睡覺
        self._last_interaction = now
        self.sleeping = False

    # ---------- 外部呼叫 ----------
    def poke(self, now: float | None = None) -> bool:
        """有互動：重設睡眠計時。回傳原本是否在睡覺。"""
        was = self.sleeping
        self.sleeping = False
        self._last_interaction = _now(now)
        return was

    def play(self, name: str, now: float | None = None, interaction: bool = True) -> None:
        """做一個動作。interaction=False：自己閒著表演的，不算互動（不會重設睡覺倒數）。"""
        now = _now(now)
        if interaction:
            self.poke(now)
        self._action = name
        self._action_start = now
        self._sent.clear()
        self.walking = 0  # 做動作時先停下腳步

    def talk(self, seconds: float, now: float | None = None) -> None:
        now = _now(now)
        self.poke(now)
        self._talk_until = now + seconds

    def start_drag(self, now: float | None = None) -> None:
        self.poke(now)
        self.dragging = True
        self.walking = 0
        self.falling = False
        self.fall_spin = self._fall_rot = 0.0
        self._action = None
        self._vx = self._sway = self._sway_v = 0.0

    def drag_velocity(self, vx: float) -> None:
        self._vx = self._vx * 0.6 + vx * 0.4  # 平滑一點，避免抖動

    def end_drag(self, fall: bool = False, now: float | None = None) -> None:
        self.dragging = False
        if fall:
            self.falling = True
        else:
            self.play("land", now)

    def land(self, now: float | None = None, strength: float = 1.0) -> None:
        """落地。strength 約 0.4（輕輕放下）～1.6（從高處摔下來）。"""
        self.falling = False
        self.fall_spin = 0.0
        self._fall_rot = 0.0
        self._land_strength = max(0.3, min(strength, 1.8))
        self.play("land", now)

    def walk(self, direction: int, now: float | None = None) -> None:
        """開始橫著走（1 = 往右、-1 = 往左）。走路是待機行為，不算互動，所以不會阻止睡覺。"""
        now = _now(now)
        self.walking = 1 if direction > 0 else -1
        if self.facing != self.walking:
            self._turn(now, float(self.walking))

    def stop_walk(self) -> None:
        self.walking = 0

    def sleep_now(self) -> None:
        """馬上去睡（右鍵 → 動作 → 睡覺）。"""
        self._action = None
        self.walking = 0
        self.sleeping = True

    def watch(self, direction: int, now: float | None = None) -> None:
        """滑鼠在附近：轉向滑鼠那邊看一下。"""
        now = _now(now)
        d = 1.0 if direction > 0 else -1.0
        if d != self.facing and now >= self._turn_start + 0.6:  # 不要一直轉來轉去
            self._turn(now, d)
        self._watch_until = now + 0.3
        self._next_look = max(self._next_look, now + 4)       # 看滑鼠時不要自己亂張望

    @property
    def busy(self) -> bool:
        """正在做某個動作 / 被拖 / 往下掉（不適合開始走路或跳舞）。"""
        return self._action is not None or self.dragging or self.falling

    def pop_events(self) -> list[str]:
        ev, self._events = self._events, []
        return ev

    @property
    def action(self) -> str | None:
        return self._action

    def action_elapsed(self, now: float) -> float:
        return now - self._action_start

    # ---------- 每幀更新 ----------
    def update(self, now: float) -> Pose:
        dt = min(now - self._last, 0.1)
        self._last = now
        t = now - self.t0
        pose = Pose()

        if self.dragging:
            return self._drag_pose(pose, t, dt, now)

        if self.falling:  # 往下掉：手舉高、身體被風拉長一點；被丟出去時會在空中轉
            self._fall_rot += self.fall_spin * dt
            pose.sprite = "lifted"
            pose.sy = 1.08
            pose.sx = 0.94 * self._facing_value(now)
            pose.rot = self._fall_rot
            return pose

        if (not self.sleeping and self._action is None and now >= self._talk_until
                and now - self._last_interaction > SLEEP_AFTER):
            self.sleeping = True

        if self.sleeping:
            self.walking = 0
            breath = math.sin(t * 2 * math.pi / 3.6)
            pose.sprite = "sleep"
            pose.sy = 1 + 0.035 * breath
            pose.sx = (1 - 0.02 * breath) * self._facing_value(now)
            return pose

        # 緩慢上下浮動（只往上浮，站在工作列上時腳不會陷進去）
        pose.dy = (math.sin(t * 2 * math.pi / 2.8) - 1) * 1.1
        sprite = "idle"

        if self.walking and self._action is None:
            # 橫著走：兩組腳交替，每一步身體輕輕彈一下、左右擺
            step = t * WALK_STEPS
            sprite = "walk_a" if int(step) % 2 == 0 else "walk_b"
            pose.dy = -abs(math.sin(step * math.pi)) * 0.9
            pose.rot = 2.5 * math.sin(step * math.pi) * self.walking
        elif now < self._watch_until and self._action is None:
            sprite = "look"                      # 盯著滑鼠看
        else:
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

    def _emit_once(self, name: str, tag: object = None) -> None:
        """同一次動作只送出一次事件（例如落地揚塵）；tag 不同就可以再送一次（例如每拍一個音符）。"""
        key = (name, tag, self._action_start)
        if key not in self._sent:
            self._sent.add(key)
            self._events.append(name)

    def _apply_action(self, name: str, pose: Pose, a: float, sprite: str) -> str:
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
            self._emit_once("jump_land")         # 落地 → 視窗揚起一點灰塵
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

        if name == "land":                       # 落地回彈：摔得越重壓得越扁
            k = self._land_strength
            d = math.exp(-5 * a) * math.cos(a * 16)
            pose.sy *= 1 - min(0.42, 0.25 * k) * d
            pose.sx *= 1 + min(0.34, 0.2 * k) * d
            if k > 1.0 and a < 0.14:             # 重重落地：先閉眼縮一下
                return "blink"
            return "happy" if a < 0.3 else sprite

        if name == "idea":                       # 頭上冒燈泡，小跳一下
            if a < 0.4:
                q = a / 0.4
                pose.dy += -4 * 4 * q * (1 - q)
            return "idea"

        if name == "dance":                      # 跳舞：每拍彈一下、左右搖擺、手舉高放下
            beat = 0.3
            k = a / beat
            fade = min(1.0, (ACTIONS["dance"] - a) / 0.3)   # 最後 0.3 秒收回來
            pose.dy += -abs(math.sin(k * math.pi)) * 2.4 * fade
            pose.rot += 11 * math.sin(k * math.pi / 2) * fade
            pose.sy *= 1 - 0.07 * abs(math.cos(k * math.pi)) * fade
            if int(k) % 2 == 0:
                self._emit_once("note", int(k))  # 每兩拍飄出一個音符
            return "happy" if int(k) % 2 == 0 else "talk"

        if name == "spin":                       # 跳起來翻一圈
            if a < 0.1:
                k = a / 0.1
                pose.sy *= 1 - 0.18 * k
                pose.sx *= 1 + 0.12 * k
                return sprite
            if a < 0.8:
                q = (a - 0.1) / 0.7
                pose.dy += -14 * 4 * q * (1 - q)
                pose.rot += 360 * _ease(q)
                return "happy"
            self._emit_once("jump_land")
            r = (a - 0.8) / 0.2
            d = math.exp(-4 * r) * math.cos(r * math.pi * 3)
            pose.sy *= 1 - 0.18 * d
            pose.sx *= 1 + 0.14 * d
            return "happy"

        if name == "dizzy":                      # 暈頭轉向：東倒西歪
            fade = min(1.0, (ACTIONS["dizzy"] - a) / 0.5)
            pose.rot += 7 * math.sin(a * 6.5) * fade
            pose.dx += 1.3 * math.sin(a * 3.2) * fade
            return "dizzy" if a < ACTIONS["dizzy"] - 0.25 else "blink"

        if name == "pet":                        # 被摸摸：開心地扭來扭去
            fade = 1 - a / ACTIONS["pet"]
            pose.sy *= 1 - 0.06 * abs(math.sin(a * 11)) * fade
            pose.sx *= 1 + 0.05 * abs(math.sin(a * 11)) * fade
            pose.rot += 4 * math.sin(a * 9) * fade
            self._emit_once("heart", int(a / 0.35))
            return "happy"

        if name == "wave":                       # 揮手打招呼
            pose.rot += 3 * math.sin(a * 10)
            return "talk" if int(a / 0.16) % 2 == 0 else "idle"

        return sprite
