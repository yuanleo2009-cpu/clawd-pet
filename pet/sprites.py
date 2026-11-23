"""載入素材並以「整數倍、最近鄰」放大，確保像素風清晰不模糊。"""
from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPixmap

from services import paths

BASE_W = 40  # 內建素材的原始寬度；大小檔位與動畫幅度都以它為基準
FRAMES = ("idle", "blink", "look", "talk", "happy", "lifted", "sleep", "idea",
          "walk_a", "walk_b", "dizzy")

_FAST = Qt.TransformationMode.FastTransformation
_SMOOTH = Qt.TransformationMode.SmoothTransformation
_IGNORE = Qt.AspectRatioMode.IgnoreAspectRatio


class SpriteSet:
    def __init__(self, images: dict[str, QImage], has_frames: bool):
        self.images = images
        self.has_frames = has_frames  # False = 只有一張圖，全部動作靠變換
        # 每一幀實際有內容的範圍（0~1 的比例），用來決定點擊範圍與泡泡位置；同一張圖只算一次
        idle = _bounds(images["idle"])
        self.bounds = {n: _bounds(images[n]) if n in images and n != "idle" else idle for n in FRAMES}

    @property
    def size(self) -> tuple[int, int]:
        im = self.images["idle"]
        return im.width(), im.height()

    @classmethod
    def load(cls, skin: str = "crab") -> "SpriteSet":
        if skin == "custom":
            p = paths.custom_image()
            if p:
                img = QImage(str(p))
                if not img.isNull():
                    return cls({"idle": _prepare_custom(img)}, False)

        d = paths.assets_dir() / "sprites"
        images: dict[str, QImage] = {}
        for name in FRAMES:
            f = d / f"{name}.png"
            if f.is_file():
                im = QImage(str(f))
                if not im.isNull():
                    images[name] = im.convertToFormat(QImage.Format.Format_ARGB32)
        if "idle" not in images:
            images["idle"] = _fallback()
        return cls(images, True)

    def pixmaps(self, target_w: float, dpr: float, ss: int = 1) -> tuple[dict[str, QPixmap], tuple[float, float]]:
        """依目標寬度（邏輯像素）產生每個動作的點陣圖。

        放大一律用整數倍 + 最近鄰；圖片比目標還大時才平滑縮小。
        ss = 超取樣倍數：先做成 ss 倍大的清晰點陣圖，繪製時再平滑縮回，
             旋轉、擠壓、次像素移動時邊緣就會有漂亮的抗鋸齒。
        回傳 (點陣圖字典, (邏輯寬, 邏輯高))。
        """
        w, h = self.size
        s = target_w * dpr / w
        if s >= 1:
            k = max(1, round(s))
            pw, ph, mode = w * k * ss, h * k * ss, _FAST
        else:
            ss = 1
            pw, ph, mode = max(1, round(w * s)), max(1, round(h * s)), _SMOOTH
        out: dict[str, QPixmap] = {}
        for name in FRAMES:
            img = self.images.get(name, self.images["idle"])
            pm = QPixmap.fromImage(img.scaled(pw, ph, _IGNORE, mode))
            pm.setDevicePixelRatio(dpr * ss)
            out[name] = pm
        return out, (pw / (dpr * ss), ph / (dpr * ss))


def _bounds(img: QImage) -> QRectF:
    """有顏色（不透明）區域的範圍。整列處理透明度資料，大圖也很快。"""
    a = img.convertToFormat(QImage.Format.Format_Alpha8)
    w, h, bpl = a.width(), a.height(), a.bytesPerLine()
    if w == 0 or h == 0:
        return QRectF(0, 0, 1, 1)
    data = bytes(a.constBits())
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        row = data[y * bpl: y * bpl + w]
        left = w - len(row.lstrip(b"\0"))
        if left == w:  # 整列透明
            continue
        right = len(row.rstrip(b"\0")) - 1
        x0, x1 = min(x0, left), max(x1, right)
        y0 = min(y0, y)
        y1 = y
    if x1 < 0:
        return QRectF(0, 0, 1, 1)
    return QRectF(x0 / w, y0 / h, (x1 - x0 + 1) / w, (y1 - y0 + 1) / h)


# ---------- 自訂單張圖片 ----------
def _prepare_custom(img: QImage) -> QImage:
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    g = _detect_block(img)
    if g > 1:  # 已經被放大過的像素圖 → 還原成原始像素
        img = img.scaled(img.width() // g, img.height() // g, _IGNORE, _FAST)
    b = _bounds(img)  # 裁掉四周透明的邊（大圖也會裁）
    w, h = img.width(), img.height()
    return img.copy(round(b.x() * w), round(b.y() * h), round(b.width() * w), round(b.height() * h))


def _detect_block(img: QImage) -> int:
    """估計每個「像素點」實際佔幾個像素（所有同色連續長度的最大公因數）。

    只抽樣約 96 列、96 欄，並直接讀原始像素資料，不逐點呼叫 Qt。
    """
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    px = memoryview(bytes(img.constBits())).cast("I")  # ARGB32：每個像素 4 bytes
    stride = bpl // 4

    def runs_gcd(values, g):
        run, prev = 1, values[0]
        for v in values[1:]:
            if v == prev:
                run += 1
            else:
                g = math.gcd(g, run)
                if g == 1:
                    return 1
                run, prev = 1, v
        return g

    g = 0
    for y in range(0, h, max(1, h // 96)):
        g = runs_gcd(px[y * stride: y * stride + w].tolist(), g)
        if g == 1:
            return 1
    for x in range(0, w, max(1, w // 96)):
        g = runs_gcd(px[x: h * stride: stride].tolist(), g)
        if g == 1:
            return 1
    return max(g, 1)


def _fallback() -> QImage:
    img = QImage(BASE_W, 38, QImage.Format.Format_ARGB32)
    img.fill(QColor("#D97757"))
    return img
