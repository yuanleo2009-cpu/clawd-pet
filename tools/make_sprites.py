"""
產生 Clawd 桌寵素材（扁平橘色像素風，透明背景）。

座標單位是「格」，每格 = 2 個實際像素（子像素），
所以眼睛、燈泡等細節可以用半格來畫。

用法：
    .venv\\Scripts\\python.exe tools\\make_sprites.py [預覽圖輸出路徑]

輸出：
    assets/sprites/<動作>.png   1 倍原始像素圖（40 x 38）
    assets/icon.ico / icon.png   程式圖示
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "sprites"

SUB = 2                 # 每格幾個像素
GW, GH = 20, 19         # 畫布大小（格）
W, H = GW * SUB, GH * SUB

BODY = "#D97757"        # Clawd 橘
EYE = "#000000"
BULB = {
    "Y": "#F2A93B",     # 燈泡外圈
    "L": "#FCD38D",     # 燈泡亮面
    "W": "#FFF6E0",     # 發光
    "G": "#BDB7AE",     # 燈座淺灰
    "D": "#8C8780",     # 燈座深灰
}

# 燈泡（子像素，10 x 13）
BULB_ART = [
    "...YYYY...",
    ".YYLLLLYY.",
    ".YLWLLWLY.",
    "YLLLWWLLLY",
    "YLLLLLLLLY",
    "YLYLLLLYLY",
    ".YLYLLYLY.",
    ".YYLYYLYY.",
    "..YYLLYY..",
    "...GGGG...",
    "...DDDD...",
    "...GGGG...",
    "....DD....",
]

# ---- Clawd 的身體結構（格）----
BODY_X, BODY_Y, BODY_W, BODY_H = 4, 8, 12, 8      # 身體
LEGS_X = (5, 7, 12, 14)                           # 四隻腳
EYE_L, EYE_R, EYE_Y = 6, 13, 10                   # 眼睛位置


class Canvas:
    def __init__(self):
        self.img = QImage(W, H, QImage.Format.Format_ARGB32)
        self.img.fill(Qt.GlobalColor.transparent)

    def rect(self, x, y, w, h, color):
        """以「格」為單位畫矩形（可用 0.5 格）。"""
        c = QColor(color)
        x0, y0 = round(x * SUB), round(y * SUB)
        x1, y1 = round((x + w) * SUB), round((y + h) * SUB)
        for py in range(max(0, y0), min(H, y1)):
            for px in range(max(0, x0), min(W, x1)):
                self.img.setPixelColor(px, py, c)

    def sub(self, px, py, color):
        """畫單一子像素。"""
        if 0 <= px < W and 0 <= py < H:
            self.img.setPixelColor(px, py, QColor(color))


def mirror_x(x, w=1):
    return GW - x - w


# ---------------- 部件 ----------------
def body(c: Canvas):
    c.rect(BODY_X, BODY_Y, BODY_W, BODY_H, BODY)


def legs(c: Canvas, length=2):
    """length 可以是一個數字，或四隻腳各自的長度（走路時腳會一長一短交替）。"""
    lengths = length if isinstance(length, tuple) else (length,) * len(LEGS_X)
    for x, n in zip(LEGS_X, lengths):
        c.rect(x, BODY_Y + BODY_H, 1, n, BODY)


def arms(c: Canvas, style="normal"):
    for side in ("L", "R"):
        def r(x, y, w, h):
            c.rect(x if side == "L" else mirror_x(x, w), y, w, h, BODY)

        s = style if isinstance(style, str) else style[0 if side == "L" else 1]
        if s == "normal":          # 平舉
            r(2, 12, 2, 2)
        elif s == "up":            # 舉手
            r(2, 10, 2, 2)
            r(2, 8, 1, 2)
        elif s == "wave":          # 揮手（抬高一點）
            r(2, 10, 2, 2)
        elif s == "low":           # 放鬆垂下
            r(2, 13, 2, 2)


def eyes(c: Canvas, style="open"):
    if style == "open":
        for x in (EYE_L, EYE_R):
            c.rect(x, EYE_Y, 1, 2, EYE)
    elif style == "look":          # 往右看：眼睛偏半格
        for x in (EYE_L, EYE_R):
            c.rect(x + 0.5, EYE_Y, 1, 2, EYE)
    elif style == "blink":
        for x in (EYE_L, EYE_R):
            c.rect(x, EYE_Y + 1.5, 1, 0.5, EYE)
    elif style == "sleep":         # 橫線眼
        c.rect(EYE_L - 0.5, EYE_Y + 1, 2, 0.5, EYE)
        c.rect(mirror_x(EYE_L - 0.5, 2), EYE_Y + 1, 2, 0.5, EYE)
    elif style == "happy":         # > <（3 x 5 子像素）
        lx, y = EYE_L * SUB, EYE_Y * SUB
        for dx, dy in ((0, 0), (1, 1), (2, 2), (1, 3), (0, 4)):
            c.sub(lx + dx, y + dy, EYE)
            c.sub(W - 1 - (lx + dx), y + dy, EYE)
    elif style == "dizzy":         # X X（3 x 3 子像素）：被搖暈了
        lx, y = EYE_L * SUB, EYE_Y * SUB + 1
        for dx, dy in ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2)):
            c.sub(lx + dx, y + dy, EYE)
            c.sub(W - 1 - (lx + dx), y + dy, EYE)


def bulb(c: Canvas):
    bw = len(BULB_ART[0])
    ox = W // 2 - bw // 2
    oy = 1
    for r, row in enumerate(BULB_ART):
        for col, ch in enumerate(row):
            if ch in BULB:
                c.sub(ox + col, oy + r, BULB[ch])


# ---------------- 動作幀 ----------------
def frame(arm="normal", eye="open", leg=2, extra=None) -> QImage:
    c = Canvas()
    arms(c, arm)
    body(c)
    legs(c, leg)
    eyes(c, eye)
    if extra:
        extra(c)
    return c.img


FRAMES = {
    "idle":   lambda: frame(),
    "blink":  lambda: frame(eye="blink"),
    "look":   lambda: frame(eye="look"),
    "talk":   lambda: frame(arm=("normal", "wave")),
    "happy":  lambda: frame(arm="up", eye="happy"),
    "lifted": lambda: frame(arm="up", leg=3),
    "sleep":  lambda: frame(arm="low", eye="sleep"),
    "idea":   lambda: frame(arm=("normal", "up"), extra=bulb),
    # 橫著走：兩組腳一長一短交替，手也一高一低
    "walk_a": lambda: frame(arm=("normal", "wave"), leg=(2, 1, 2, 1)),
    "walk_b": lambda: frame(arm=("wave", "normal"), leg=(1, 2, 1, 2)),
    "dizzy":  lambda: frame(arm="low", eye="dizzy"),
}


def main():
    QGuiApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    images = {}
    for name, make in FRAMES.items():
        img = make()
        img.save(str(OUT / f"{name}.png"))
        images[name] = img
        print("wrote", OUT / f"{name}.png")

    # 圖示：只取螃蟹本體（不含上方空白），放大置中到 256x256
    crab = images["idle"].copy(0, 7 * SUB, W, (GH - 7) * SUB)
    k = 256 // max(crab.width(), crab.height())
    big = crab.scaled(crab.width() * k, crab.height() * k,
                      Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
    icon = QImage(256, 256, QImage.Format.Format_ARGB32)
    icon.fill(Qt.GlobalColor.transparent)
    p = QPainter(icon)
    p.drawImage((256 - big.width()) // 2, (256 - big.height()) // 2, big)
    p.end()
    icon.save(str(ROOT / "assets" / "icon.png"))
    ok = icon.save(str(ROOT / "assets" / "icon.ico"))
    print("icon.ico", "ok" if ok else "FAILED")

    if len(sys.argv) > 1:  # 預覽圖
        s = 8
        names = list(images)
        sheet = QImage(len(names) * (W * s + 16) + 16, H * s + 32, QImage.Format.Format_ARGB32)
        sheet.fill(QColor("#2B2F38"))
        p = QPainter(sheet)
        for i, n in enumerate(names):
            im = images[n].scaled(W * s, H * s, Qt.AspectRatioMode.IgnoreAspectRatio,
                                  Qt.TransformationMode.FastTransformation)
            p.drawImage(16 + i * (W * s + 16), 16, im)
        p.end()
        sheet.save(sys.argv[1])
        print("preview", sys.argv[1])


if __name__ == "__main__":
    main()
