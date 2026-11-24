"""特效：落地的灰塵 / 火花 / 衝擊線，以及愛心、音符、點心、汗滴、驚嘆號等小圖案。

座標都是桌寵視窗內的邏輯像素；`unit` = 素材 1 個原始像素在螢幕上的大小，
所以 Clawd 調大調小時，特效也跟著等比例縮放。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

DUST_COLORS = [QColor(240, 231, 220), QColor(222, 208, 194), QColor(250, 245, 238)]
SPARK_COLOR = QColor(255, 226, 150)
LINE_COLOR = QColor(255, 255, 255)
HEART_COLOR = QColor(255, 107, 139)
NOTE_COLORS = [QColor(127, 209, 255), QColor(255, 211, 110), QColor(180, 155, 255), QColor(140, 230, 170)]
STAR_COLOR = QColor(255, 222, 89)

# 像素小圖案（X = 有顏色）
HEART = [".X.X.", "XXXXX", "XXXXX", ".XXX.", "..X.."]
NOTE = ["..XXX", "..X.X", "..X..", "XXX..", "XXX.."]
STAR = [".X.", "XXX", ".X."]
BANG = ["XX", "XX", "XX", "..", "XX"]                                   # 驚嘆號
COOKIE = [".XXX.", "XXoXX", "XoXXX", "XXXoX", ".XXX."]                  # 餅乾（o = 巧克力豆）
COOKIE_COLOR = QColor(214, 158, 92)
CHIP_COLOR = QColor(110, 66, 32)
CRUMB_COLOR = QColor(198, 142, 80)
SWEAT_COLOR = QColor(140, 205, 255)
BANG_COLOR = QColor(255, 84, 84)
PATTERNS = {"heart": HEART, "note": NOTE, "bang": BANG, "snack": COOKIE}


def paint_pattern(p: QPainter, pattern: list[str], cx: float, cy: float, px: float, color: QColor) -> None:
    """以 (cx, cy) 為中心畫像素小圖案，每格 px 大小。"""
    h, w = len(pattern), len(pattern[0])
    x0, y0 = cx - w * px / 2, cy - h * px / 2
    for r, row in enumerate(pattern):
        for c, ch in enumerate(row):
            if ch == "X":
                p.fillRect(QRectF(x0 + c * px, y0 + r * px, px + 0.3, px + 0.3), color)
            elif ch == "o":      # 第二種顏色（餅乾上的巧克力豆），透明度跟著主色
                chip = QColor(CHIP_COLOR)
                chip.setAlphaF(color.alphaF())
                p.fillRect(QRectF(x0 + c * px, y0 + r * px, px + 0.3, px + 0.3), chip)


def paint_dizzy_stars(p: QPainter, cx: float, cy: float, radius: float, unit: float, t: float,
                      alpha: float = 1.0) -> None:
    """暈頭轉向：三顆星星繞著頭頂轉（扁橢圓軌道，後面那顆小一點、淡一點）。"""
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(3):
        ang = t * 4.2 + i * 2 * math.pi / 3
        depth = (math.sin(ang) + 1) / 2          # 0 = 後面，1 = 前面
        c = QColor(STAR_COLOR)
        c.setAlphaF(alpha * (0.45 + 0.55 * depth))
        paint_pattern(p, STAR, cx + math.cos(ang) * radius, cy + math.sin(ang) * radius * 0.28,
                      unit * (0.85 + 0.4 * depth), c)
    p.restore()


@dataclass
class Particle:
    kind: str          # dust / spark
    x: float
    y: float
    vx: float
    vy: float
    life: float
    size: float
    color: QColor
    age: float = 0.0
    ay: float = 0.0    # 額外的垂直加速度（點心掉下來用）


@dataclass
class Ring:
    """貼著地面擴散的衝擊波（扁橢圓）。"""
    x: float
    y: float
    radius: float
    life: float
    age: float = 0.0


@dataclass
class ImpactLine:
    x: float
    y: float
    angle: float       # 弧度；0 = 往右，-π/2 = 往上
    length: float
    life: float
    age: float = 0.0


class Effects:
    def __init__(self):
        self.particles: list[Particle] = []
        self.lines: list[ImpactLine] = []
        self.rings: list[Ring] = []
        self._unit = 4.0

    @property
    def active(self) -> bool:
        return bool(self.particles or self.lines or self.rings)

    def clear(self) -> None:
        self.particles.clear()
        self.lines.clear()
        self.rings.clear()

    # ---------- 產生 ----------
    def landing(self, x: float, y: float, unit: float, width: float, strength: float = 1.0) -> None:
        """重重落地：地面衝擊波、往兩側噴出的灰塵、彈起的小火花、放射狀衝擊線。"""
        self._unit = unit
        s = max(0.4, min(strength, 1.6))
        self.rings.append(Ring(x, y, width * (0.75 + 0.35 * s), 0.32))
        for _ in range(round(14 + 16 * s)):
            side = random.choice((-1, 1))
            self.particles.append(Particle(
                "dust",
                x + side * random.uniform(0.1, 0.45) * width,
                y - random.uniform(0, 1.5) * unit,
                side * random.uniform(15, 55) * s * unit,   # 沿著地面往兩邊噴
                -random.uniform(1, 12) * s * unit,
                random.uniform(0.5, 1.0),
                random.uniform(1.8, 3.6) * unit,
                random.choice(DUST_COLORS),
            ))
        if s >= 0.7:
            for _ in range(round(3 + 4 * s)):
                side = random.choice((-1, 1))
                self.particles.append(Particle(
                    "spark",
                    x + side * random.uniform(0.15, 0.45) * width,
                    y - unit,
                    side * random.uniform(6, 20) * unit,
                    -random.uniform(16, 26) * unit,
                    random.uniform(0.4, 0.65),
                    unit * 1.1,
                    SPARK_COLOR,
                ))
            for side in (-1, 1):
                for deg in (25, 50, 72):        # 從腳邊往斜上方放射
                    up = math.radians(deg) if side > 0 else math.radians(180 - deg)
                    self.lines.append(ImpactLine(
                        x + side * 0.5 * width, y - unit, -up,
                        random.uniform(3.5, 5.5) * unit * s, 0.24))

    def heart(self, x: float, y: float, unit: float) -> None:
        """被摸摸：頭上冒出一顆愛心，晃著往上飄。"""
        self._unit = unit
        self.particles.append(Particle(
            "heart", x + random.uniform(-6, 6) * unit, y,
            random.uniform(-3, 3) * unit, -random.uniform(10, 15) * unit,
            random.uniform(1.0, 1.3), unit * random.uniform(0.95, 1.15), HEART_COLOR))

    def note(self, x: float, y: float, unit: float) -> None:
        """跳舞：飄出一個彩色音符。"""
        self._unit = unit
        side = random.choice((-1, 1))
        self.particles.append(Particle(
            "note", x + side * random.uniform(6, 10) * unit, y,
            side * random.uniform(3, 7) * unit, -random.uniform(9, 14) * unit,
            random.uniform(1.2, 1.5), unit * 0.95, random.choice(NOTE_COLORS)))

    def snack(self, x: float, y_from: float, y_to: float, unit: float, seconds: float) -> None:
        """餵點心：一塊餅乾從上面掉到嘴邊，剛好在 seconds 秒後抵達（然後被吃掉）。"""
        self._unit = unit
        dist = y_to - y_from
        v0 = 0.4 * dist / seconds                      # 一開始慢、越掉越快
        self.particles.append(Particle("snack", x, y_from, 0.0, v0, seconds, unit * 1.3, COOKIE_COLOR,
                                       ay=1.2 * dist / seconds ** 2))

    def crumbs(self, x: float, y: float, unit: float) -> None:
        """吃東西掉屑屑。"""
        self._unit = unit
        for _ in range(3):
            side = random.choice((-1, 1))
            self.particles.append(Particle(
                "spark", x + side * random.uniform(1, 5) * unit, y,
                side * random.uniform(4, 14) * unit, -random.uniform(4, 12) * unit,
                random.uniform(0.35, 0.55), unit * random.uniform(0.7, 1.0), CRUMB_COLOR))

    def sweat(self, x: float, y: float, unit: float, width: float) -> None:
        """運動流汗：從頭的兩側甩出汗滴。"""
        self._unit = unit
        side = random.choice((-1, 1))
        for _ in range(2):
            self.particles.append(Particle(
                "spark", x + side * 0.42 * width, y + random.uniform(0, 3) * unit,
                side * random.uniform(8, 16) * unit, -random.uniform(8, 14) * unit,
                random.uniform(0.4, 0.6), unit * 1.1, SWEAT_COLOR))

    def emote(self, x: float, y: float, unit: float) -> None:
        """嚇一跳：頭上冒出驚嘆號。"""
        self._unit = unit
        self.particles.append(Particle("bang", x, y, 0.0, -9 * unit, 0.8, unit * 1.2, BANG_COLOR))

    def puff(self, x: float, y: float, unit: float, width: float) -> None:
        """小跳一下落地：腳邊冒一點點灰。"""
        self._unit = unit
        for side in (-1, 1):
            for _ in range(3):
                self.particles.append(Particle(
                    "dust",
                    x + side * random.uniform(0.15, 0.38) * width,
                    y - random.uniform(0, 0.8) * unit,
                    side * random.uniform(8, 20) * unit,
                    -random.uniform(2, 7) * unit,
                    random.uniform(0.3, 0.5),
                    random.uniform(1.0, 1.8) * unit,
                    random.choice(DUST_COLORS),
                ))

    # ---------- 每幀 ----------
    def step(self, dt: float) -> None:
        if not self.active:
            return
        u = self._unit
        alive = []
        for p in self.particles:
            p.age += dt
            if p.age >= p.life:
                continue
            if p.kind == "dust":
                drag = math.exp(-3.2 * dt)      # 灰塵很快就慢下來、往上飄散
                p.vx *= drag
                p.vy = p.vy * drag - 2 * u * dt
            elif p.kind in ("heart", "note"):   # 輕飄飄往上、左右晃
                p.vx = p.vx * math.exp(-1.5 * dt) + math.sin(p.age * 6) * 8 * u * dt
                p.vy *= math.exp(-0.8 * dt)
            elif p.kind == "bang":              # 驚嘆號：往上彈一下就停住
                p.vy *= math.exp(-6 * dt)
            elif p.kind == "snack":             # 點心：加速往下掉
                p.vy += p.ay * dt
            else:
                p.vy += 60 * u * dt             # 火花會掉回來
            p.x += p.vx * dt
            p.y += p.vy * dt
            alive.append(p)
        self.particles = alive
        for ln in self.lines:
            ln.age += dt
        self.lines = [ln for ln in self.lines if ln.age < ln.life]
        for r in self.rings:
            r.age += dt
        self.rings = [r for r in self.rings if r.age < r.life]

    def paint(self, p: QPainter) -> None:
        if not self.active:
            return
        p.save()
        for r in self.rings:                     # 衝擊波：快速擴散、變淡
            k = r.age / r.life
            ease = 1 - (1 - k) ** 3
            c = QColor(LINE_COLOR)
            c.setAlphaF(0.75 * (1 - k))
            p.setPen(QPen(c, max(1.0, self._unit * 0.7 * (1 - 0.5 * k))))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rx = r.radius * (0.35 + 0.65 * ease)
            p.drawEllipse(QPointF(r.x, r.y), rx, rx * 0.16)
        p.setPen(Qt.PenStyle.NoPen)
        for q in self.particles:
            k = q.age / q.life
            c = QColor(q.color)
            if q.kind == "snack":                            # 點心：一路清楚到被吃掉
                paint_pattern(p, COOKIE, q.x, q.y, q.size, c)
                continue
            if q.kind in PATTERNS:
                pop = min(1.0, q.age / 0.15)                 # 一開始「啵」地放大出現
                c.setAlphaF(1.0 if k < 0.6 else (1 - k) / 0.4)
                paint_pattern(p, PATTERNS[q.kind], q.x, q.y, q.size * (0.5 + 0.5 * pop), c)
                continue
            if q.kind == "dust":
                c.setAlphaF(0.95 * (1 - k) ** 1.2)
                size = q.size * (1 + 0.7 * k)    # 灰塵越散越大
            else:
                c.setAlphaF(1 - k)
                size = q.size
            p.fillRect(QRectF(q.x - size / 2, q.y - size / 2, size, size), c)
        for ln in self.lines:
            k = ln.age / ln.life
            c = QColor(LINE_COLOR)
            c.setAlphaF(0.85 * (1 - k))
            pen = QPen(c, max(1.0, self._unit * 0.6))
            p.setPen(pen)
            r0 = ln.length * (0.2 + 0.9 * k)
            r1 = ln.length * (0.7 + 0.9 * k)
            dx, dy = math.cos(ln.angle), math.sin(ln.angle)
            p.drawLine(QPointF(ln.x + dx * r0, ln.y + dy * r0), QPointF(ln.x + dx * r1, ln.y + dy * r1))
        p.restore()
