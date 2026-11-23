"""落地特效：灰塵粒子、小火花、衝擊線。

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
