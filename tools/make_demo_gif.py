"""
產生 README 用的示範動畫 docs/demo.gif（離屏繪製，不需要真的錄螢幕）。

用法：
    .venv\\Scripts\\python.exe tools\\make_demo_gif.py

需要 Pillow（在 requirements-dev.txt 裡）。不會讀寫你的設定檔。
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFontDatabase, QImage, QLinearGradient, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from services.settings import Settings  # noqa: E402

# 用預設設定、而且不存檔，避免動到使用者的 settings.json
Settings.load = classmethod(lambda cls: cls(Path(os.devnull), {}))
Settings.save = lambda self: None

from pet.animator import Animator  # noqa: E402
from pet.window import Flight, PetWindow  # noqa: E402

OUT = ROOT / "docs" / "demo.gif"
FPS = 25
W, H = 460, 300
TASKBAR = 34
FLOOR = H - TASKBAR


def background() -> QImage:
    bg = QImage(W, H, QImage.Format.Format_RGB32)
    p = QPainter(bg)
    g = QLinearGradient(0, 0, W, H)
    g.setColorAt(0, QColor("#3B4BB8"))
    g.setColorAt(1, QColor("#1E2257"))
    p.fillRect(0, 0, W, H, g)
    p.fillRect(0, FLOOR, W, TASKBAR, QColor("#5E3A78"))
    p.end()
    return bg


def to_pil(img: QImage) -> Image.Image:
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombuffer("RGBA", (img.width(), img.height()), bytes(img.constBits()),
                            "raw", "RGBA", img.bytesPerLine(), 1).convert("RGB")


def main():
    random.seed(7)
    app = QApplication(sys.argv)  # noqa: F841
    # 離屏模式看不到系統字型，手動載入泡泡用的微軟正黑體
    fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in ("msjh.ttc", "msjhbd.ttc", "seguiemj.ttf"):
        if (fonts / name).exists():
            QFontDatabase.addApplicationFont(str(fonts / name))
    w = PetWindow()
    for timer in (w._tick, w._chatter, w._idle):
        timer.stop()
    w.tray.hide()
    w.anim = anim = Animator(now=0.0)
    anim._next_look = 99  # 不要自己亂張望
    bg = background()
    feet = w._feet_offset()
    u = w._unit

    frames: list[Image.Image] = []
    lift = 0.0          # 被拎起的高度
    shift = -60.0       # 水平位置（相對畫面中央）
    fall_v = 0.0
    bubble_img: QImage | None = None
    bubble_until = 0.0

    def say(text: str, t: float, seconds: float):
        nonlocal bubble_img, bubble_until
        w.bubble.say(text, QPoint(0, 0), 10_000)
        bubble_img = w.bubble.grab().toImage()
        bubble_until = t + seconds

    # 時間軸（秒）：打招呼 → 橫著走 → 被摸摸 → 被拎起來猛搖 → 摔下來暈 → 跳舞
    script = [
        (0.5, lambda t: (anim.play("wave", t), say("嗨！今天也一起寫程式吧", t, 1.8))),
        (2.6, lambda t: anim.walk(1, t)),
        (4.3, lambda t: anim.stop_walk()),
        (4.6, lambda t: anim.play("pet", t)),
        (6.3, lambda t: anim.start_drag(t)),
        (7.5, "drop"),
        (10.9, lambda t: anim.play("dance", t)),
    ]
    total = 14.8
    events = list(script)
    falling = False

    for i in range(int(total * FPS)):
        t = i / FPS
        dt = 1 / FPS
        w._now = t
        while events and events[0][0] <= t:
            _, ev = events.pop(0)
            if ev == "drop":
                anim.end_drag(fall=True, now=t)
                falling = True
            else:
                ev(t)
        if bubble_img is not None and t > bubble_until:
            bubble_img = None

        if anim.walking:
            shift += anim.walking * 11 * u * dt
        if anim.dragging:  # 拎起來、左右猛搖
            lift = min(110.0, lift + 300 * dt)
            v = 1600 if int(t * 5) % 2 == 0 else -1600
            shift += v * dt * 0.06
            anim.drag_velocity(v)
        elif falling:      # 放開：受重力掉回工作列
            fall_v += 4200 * dt
            lift -= fall_v * dt
            w._fall = Flight(0, 0, 0, fall_v)   # 讓視窗畫出速度線
            if lift <= 0:
                lift, fall_v, falling = 0.0, 0.0, False
                w._fall = None
                anim.land(t, strength=1.3)       # 示範用：當成從高處摔下來
                w._spawn_landing(1.3)
                events.insert(0, (t + 0.45, lambda t: (anim.play("dizzy", t), say("頭好暈…", t, 1.6))))

        w.pose = anim.update(t)
        head = w._head_y()
        for ev in anim.pop_events():
            if ev == "jump_land":
                w._spawn_puff()
            elif ev == "heart":
                w.fx.heart(w._center_x, head - 2 * u, u)
            elif ev == "note":
                w.fx.note(w._center_x, head, u)
        w.fx.step(dt)
        pet = w.grab().toImage()

        frame = QImage(bg)
        p = QPainter(frame)
        x = round(W / 2 + shift) - feet.x()
        y = round(FLOOR - feet.y() - lift)
        p.drawImage(x, y, pet)
        if bubble_img is not None:
            p.drawImage(round(W / 2 + shift) - bubble_img.width() // 2,
                        round(y + head - 2 * u - bubble_img.height()), bubble_img)
        p.end()
        frames.append(to_pil(frame))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=round(1000 / FPS),
                   loop=0, optimize=True, disposal=1)
    print(f"wrote {OUT} ({len(frames)} frames, {OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
