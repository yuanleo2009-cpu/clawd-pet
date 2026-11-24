"""桌寵主視窗：透明、無邊框、置頂、不佔工作列；處理繪製、滑鼠與右鍵選單。"""
from __future__ import annotations

import math
import os
import random
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, QUrl
from dataclasses import dataclass

from PySide6.QtGui import (QActionGroup, QColor, QCursor, QDesktopServices, QFont, QGuiApplication,
                           QIcon, QPainter, QPen)
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon, QWidget

from services import autostart, launcher, paths
from services.reminders import Reminders
from services.settings import Settings
from services.version import __version__
from .animator import Animator
from .bubble import Bubble
from .effects import Effects, paint_dizzy_stars
from .phrases import Phrases
from .sprites import BASE_W, SpriteSet

SIZE_PRESETS = [("小", 3), ("中", 4), ("大", 5), ("特大", 6)]
WAKE_LINES = ["嗯…？我醒了！", "呼啊～睡得好飽", "有什麼事嗎？"]
LAUNCH_LINES = ["有點子了！開工囉", "Claude 出動！", "一起把 bug 抓光吧！"]

PET_LINES = ["好舒服～", "嘿嘿 💕", "再摸一下！", "最喜歡你了～"]
DIZZY_LINES = ["頭好暈…", "天旋地轉～", "不要再搖了啦 @_@"]
EAT_LINES = ["好好吃！謝謝 🍪", "再來一塊！", "嗝～吃飽了"]
WOKE_LINES = ["睡飽了～", "呼啊～起床！", "精神滿滿！"]
# 自己做動作的頻率：設定值 → 間隔秒數範圍（None = 不做）
IDLE_INTERVALS = {"off": None, "rare": (180, 360), "normal": (60, 120), "often": (25, 50)}
IDLE_TRICKS = ["dance", "spin", "wave", "exercise", "hide", "jump", "idea"]
GRAVITY = 4200          # 重力加速度（像素/秒²）


@dataclass
class Flight:
    """往下掉 / 被丟出去時的狀態（視窗左上角座標，浮點數）。"""
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    bounces: int = 0


MENU_QSS = """
QMenu {
    background: #FFFBF7; border: 2px solid #D97757; border-radius: 10px; padding: 6px;
    font-family: "Microsoft JhengHei UI"; font-size: 10pt; color: #3A2A22;
}
QMenu::item { padding: 6px 28px 6px 14px; border-radius: 6px; }
QMenu::item:selected { background: #F6D3C4; }
QMenu::item:disabled { color: #A08A80; }
QMenu::separator { height: 1px; background: #EBC8B8; margin: 4px 8px; }
QMenu::indicator { width: 14px; height: 14px; left: 6px; }
"""


class PetWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("ClawdPet")

        self.settings = Settings.load()
        self.sprites = SpriteSet.load(self.settings["skin"])
        self.anim = Animator()
        self.bubble = Bubble()
        self.phrases = Phrases()
        self.fx = Effects()
        self.pose = self.anim.update(time.perf_counter())

        # 幾何資訊（_rebuild 會填）
        self._geo_key = None
        self._pixmaps = {}
        self._dpr = 1.0
        self._unit = 1.0
        self._sprite_w = self._sprite_h = 1.0
        self._center_x = self._baseline = 0.0

        # 滑鼠狀態
        self._pressed = False
        self._dragging = False
        self._ignore_release = False
        self._press_global = QPoint()
        self._win_start = QPoint()
        self._last_mouse = (QPoint(), 0.0)
        self._click_timer = QTimer(self, singleShot=True)
        self._click_timer.timeout.connect(self._on_single_click)
        self._fall: Flight | None = None
        self._last_tick = self._now = time.perf_counter()
        self._was_sleeping = False
        self._drag_v = (0.0, 0.0)          # 拖曳時的速度（像素/秒），放開時用來把牠丟出去
        self._shakes: list[float] = []     # 拖曳時左右急轉的時間點（搖太多會暈）
        self._shake_dir = 0
        self._dizzy_pending = False
        self._hover = (0, 0, 0.0)          # 摸摸偵測：(上次 x, 方向, 累積移動)
        self._rubs: list[float] = []
        # 待機小行為：走路、偶爾表演
        now = time.perf_counter()
        self._walk_x = 0.0
        self._walk_until = 0.0
        self._next_walk = now + random.uniform(8, 15)
        self._next_trick = now + random.uniform(30, 60)   # 啟動後第一次早一點
        self._last_trick = ""
        self.anim.nap_wakes = self.settings["idle_actions"] != "off"
        self._next_watch_check = 0.0
        self._last_night_note = 0.0
        self._idle = QTimer(self)
        self._idle.timeout.connect(self._on_idle)
        self._idle.start(1000)
        self._chasing = False              # 正在朝滑鼠走過去
        self._last_wheel = 0.0
        self.reminders = Reminders(now, time.localtime().tm_hour,
                                   self.settings["water_minutes"], self.settings["chime"])
        self.setMouseTracking(True)        # 不按鍵也能收到滑鼠移動（摸摸用）
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        # 動畫計時器（幀率可在右鍵 → 畫面 調整）
        self._tick = QTimer(self)
        self._tick.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick.timeout.connect(self._on_tick)
        self._debug = bool(os.environ.get("CLAWDPET_DEBUG"))
        self._frames = 0
        self._fps_t = time.perf_counter()
        self._apply_fps()

        # 偶爾自言自語
        self._chatter = QTimer(self, singleShot=True)
        self._chatter.timeout.connect(self._on_chatter)
        self._schedule_chatter()

        self.winId()  # 先建立原生視窗，才能取得螢幕 DPI
        self._rebuild(keep_anchor=False)
        self._restore_position()
        if self.settings["dock"] == "always":  # 直接站在工作列上
            self.move(self.x(), self._floor_y() - self._feet_offset().y())
        self.windowHandle().screenChanged.connect(lambda _s: (self._rebuild(), self._apply_fps()))
        autostart.refresh()
        self._setup_tray()
        QTimer.singleShot(1500, self._greet)

    # ================= 幾何 =================
    def _rebuild(self, keep_anchor: bool = True, force: bool = False) -> None:
        handle = self.windowHandle()
        screen = handle.screen() if handle else None
        dpr = screen.devicePixelRatio() if screen else self.devicePixelRatioF()
        preset = int(self.settings["size"])
        smooth = bool(self.settings["smooth"])
        key = (dpr, preset, id(self.sprites), smooth)
        if key == self._geo_key and not force:
            return
        anchor = self._feet_global() if (keep_anchor and self._geo_key) else None
        self._geo_key = key

        self._pixmaps, (lw, lh) = self.sprites.pixmaps(BASE_W * preset, dpr, ss=2 if smooth else 1)
        self._dpr = dpr
        self._sprite_w, self._sprite_h = lw, lh
        self._unit = u = lw / BASE_W
        self.fx.clear()
        # 視窗大小：Clawd 以身體中心旋轉時，轉到任何角度都要完整放得下（含被拎起時的長手長腳、
        # 擠壓伸長、轉一圈時跳起來的高度）；兩側再多留空間給落地灰塵。
        # 多出來的地方都是透明的，滑鼠會直接穿透，不影響操作底下的視窗。
        b0, bl = self.sprites.bounds["idle"], self.sprites.bounds["lifted"]
        radius = 1.12 * max(math.hypot(b.width() * lw, b.height() * lh) for b in (b0, bl)) / 2
        above = b0.center().y() * lh            # 身體中心到素材頂端
        below = lh - above                       # 身體中心到素材底端
        spin_jump = 14 * u                       # 「轉一圈」跳起來的最高高度
        top_margin = max(2 * u, radius + spin_jump - above + u)
        bottom_margin = max(6 * u, radius - below + 2 * u)
        win_w = math.ceil(max(lw * 2.1, 2 * radius + 4 * u))
        win_h = math.ceil(top_margin + lh + bottom_margin)
        self.setFixedSize(win_w, win_h)
        self._center_x = win_w / 2
        self._baseline = win_h - bottom_margin
        if anchor is not None:
            self.move(anchor - self._feet_offset())
            self._keep_on_screen()
        self.update()

    def _snap(self, v: float) -> float:
        """對齊到實體像素，避免像素圖出現忽粗忽細的線。"""
        return round(v * self._dpr) / self._dpr

    def _feet_offset(self) -> QPoint:
        """腳底（素材最下面有顏色的地方）相對於視窗左上角的位置。"""
        gap = (1 - self.sprites.bounds["idle"].bottom()) * self._sprite_h
        return QPoint(round(self._center_x), round(self._baseline - gap))

    def _feet_global(self) -> QPoint:
        return self.pos() + self._feet_offset()

    def _head_y(self) -> float:
        """待機時頭頂（不含燈泡）在視窗中的 y。"""
        top = self.sprites.bounds["idle"].top()
        return self._baseline - self._sprite_h + top * self._sprite_h

    def _head_global(self) -> QPoint:
        return self.mapToGlobal(QPoint(round(self._center_x), round(self._head_y() - 2 * self._unit)))

    def _keep_on_screen(self) -> None:
        feet = self._feet_global()
        screen = QGuiApplication.screenAt(feet) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        b = self.sprites.bounds["idle"]
        half = b.width() * self._sprite_w / 2
        height = (1 - b.top()) * self._sprite_h
        fx = min(max(feet.x(), g.left() + half), g.right() - half)
        fy = min(max(feet.y(), g.top() + height), g.bottom())
        self.move(QPoint(round(fx), round(fy)) - self._feet_offset())

    def _restore_position(self) -> None:
        pos = self.settings["pos"]
        if isinstance(pos, list) and len(pos) == 2:
            self.move(int(pos[0]), int(pos[1]))
            self._keep_on_screen()
        else:
            self.reset_position()

    def reset_position(self) -> None:
        g = QGuiApplication.primaryScreen().availableGeometry()
        feet = QPoint(g.right() - round(self._sprite_w), g.bottom())  # 站在工作列上
        self._fall = None
        self.anim.falling = False
        self.move(feet - self._feet_offset())
        self._save_position()

    # ================= 吸附底部 =================
    def _floor_y(self) -> int:
        """目前所在螢幕的「地板」：工作列上緣（工作區域底部）。"""
        feet = self._feet_global()
        screen = QGuiApplication.screenAt(feet) or self.screen() or QGuiApplication.primaryScreen()
        return screen.availableGeometry().bottom()

    def _should_dock(self) -> bool:
        mode = self.settings["dock"]
        if mode == "always":
            return True
        if mode == "near":
            dist = self._floor_y() - self._feet_global().y()
            return 0 < dist < self._sprite_h * 1.5  # 離底部不到 1.5 隻 Clawd 高就吸過去
        return False

    def _screen_rect(self):
        feet = self._feet_global()
        screen = QGuiApplication.screenAt(feet) or self.screen() or QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def _start_fall(self, vx: float = 0.0, vy: float = 0.0) -> None:
        """開始受重力往下掉。vx / vy 是放開時甩動的速度（像素/秒）：用力甩就會被丟出去。"""
        vx = max(-2600.0, min(vx, 2600.0))
        vy = max(-2200.0, min(vy, 1500.0))
        floor = self._floor_y() - self._feet_offset().y()
        if self.y() >= floor and abs(vx) < 150 and vy >= 0:
            self._fall = None
            self.anim.land()
            self._after_landing()
            return
        self._fall = Flight(float(self.x()), float(self.y()), vx, vy)
        self.anim.falling = True
        # 甩得越用力，在空中轉得越快
        self.anim.fall_spin = max(-900.0, min(vx * 0.4, 900.0)) if abs(vx) > 350 else 0.0

    def _step_fall(self, dt: float) -> None:
        # 位置用浮點數累積：每幀從整數座標重算的話，小數被捨去，幀率越高掉得越慢
        f = self._fall
        f.vy += GRAVITY * dt
        f.vx *= math.exp(-0.35 * dt)                       # 空氣阻力
        f.x += f.vx * dt
        f.y += f.vy * dt

        g = self._screen_rect()
        fo = self._feet_offset()
        half = self.sprites.bounds["idle"].width() * self._sprite_w / 2
        left, right = g.left() + half - fo.x(), g.right() - half - fo.x()
        if f.x < left or f.x > right:                       # 撞到螢幕左右邊緣：彈回來
            f.x = left if f.x < left else right
            f.vx = -f.vx * 0.55
            self.anim.fall_spin *= -0.6
        top = g.top() - (self._head_y() - 2 * self._unit)
        if f.y < top:                                       # 撞到螢幕上緣
            f.y, f.vy = top, abs(f.vy) * 0.3

        floor = g.bottom() - fo.y()
        if f.y >= floor:
            f.y = floor
            strength = f.vy / 1400       # 掉越快摔越重（約 0.4 輕放 ～ 1.6 從高處摔下）
            if f.vy > 1150 and f.bounces < 2:               # 摔很重：在地上彈一兩下
                self._spawn_landing(strength * 0.7)
                f.vy = -f.vy * 0.32
                f.vx *= 0.6
                f.bounces += 1
                self.anim.fall_spin *= 0.4
            else:
                self.move(round(f.x), round(f.y))
                self._fall = None
                self.anim.land(strength=strength)
                self._spawn_landing(strength)
                self._after_landing()
                return
        self.move(round(f.x), round(f.y))

    def _after_landing(self) -> None:
        self._save_position()
        if self._dizzy_pending:                             # 被搖暈了：落地後才開始暈
            self._dizzy_pending = False
            QTimer.singleShot(450, self._become_dizzy)

    def _become_dizzy(self) -> None:
        self.anim.play("dizzy")
        self.say(random.choice(DIZZY_LINES))

    # ================= 落地特效 =================
    def _spawn_landing(self, strength: float) -> None:
        if self.settings["effects"]:
            feet = self._feet_offset()
            self.fx.landing(feet.x(), feet.y(), self._unit, self._sprite_w * 0.8, strength)

    def _spawn_puff(self) -> None:
        if self.settings["effects"]:
            feet = self._feet_offset()
            self.fx.puff(feet.x(), feet.y(), self._unit, self._sprite_w * 0.8)

    def _paint_speed_lines(self, p: QPainter) -> None:
        """往下掉時，頭上拖著幾條速度線。"""
        if self._fall is None or not self.settings["effects"]:
            return
        u, v = self._unit, self._fall.vy
        if v < 300:          # 往上飛或還很慢的時候不畫
            return
        length = min(14.0, 3 + v / 260) * u
        top = self._head_y() - 2 * u
        c = QColor(255, 255, 255, 150)
        p.save()
        p.setPen(QPen(c, max(1.0, u * 0.6)))
        t = time.perf_counter()
        for i, off in enumerate((-0.32, -0.1, 0.14, 0.34)):
            x = self._center_x + off * self._sprite_w
            jitter = (math.sin(t * 23 + i * 1.7) + 1) * 1.5 * u
            p.drawLine(QPointF(x, top - jitter), QPointF(x, top - jitter - length * (0.6 + 0.4 * (i % 2))))
        p.restore()

    def _save_position(self) -> None:
        self.settings["pos"] = [self.x(), self.y()]
        self.settings.save()

    # ================= 動畫 =================
    def target_fps(self) -> float:
        fps = int(self.settings["fps"] or 0)
        if fps <= 0:  # 跟隨螢幕更新率
            screen = self.screen() or QGuiApplication.primaryScreen()
            fps = round(screen.refreshRate()) if screen else 60
        return max(15, min(fps, 360))

    def _apply_fps(self) -> None:
        """依設定啟動計時器。睡著時只有呼吸和 z，降到 30 FPS 省電（筆電續航）。"""
        fps = self.target_fps()
        if self.anim.sleeping:
            fps = min(fps, 30)
        self._tick.start(max(1, round(1000 / fps)))

    def _on_tick(self) -> None:
        now = self._now = time.perf_counter()
        dt, self._last_tick = min(now - self._last_tick, 0.05), now
        if self._fall is not None:
            self._step_fall(dt)
        if self.anim.walking:
            self._step_walk(now, dt)
        elif now >= self._next_watch_check:
            self._next_watch_check = now + 0.1
            self._watch_cursor(now)
            self._maybe_chase(now)
        self.pose = self.anim.update(now)
        self._handle_anim_events()
        self.fx.step(dt)
        if self.anim.sleeping != self._was_sleeping:  # 睡著 / 醒來 → 切換幀率
            self._was_sleeping = self.anim.sleeping
            if self.isVisible():
                self._apply_fps()
        self.repaint()  # 立即重繪，不等事件佇列合併，幀率才準
        self.bubble.follow(self._head_global())
        if self._debug:
            self._frames += 1
            if now - self._fps_t >= 2:
                print(f"fps={self._frames / (now - self._fps_t):.1f}", flush=True)
                self._frames, self._fps_t = 0, now

    def _handle_anim_events(self) -> None:
        """動畫送出的一次性事件 → 對應的特效（灰塵、愛心、音符、點心、屑屑、汗滴）。"""
        u, fx_on = self._unit, self.settings["effects"]
        head = self._head_y()
        for ev in self.anim.pop_events():
            if ev == "jump_land":
                self._spawn_puff()
            elif ev == "woke":       # 自己睡醒了
                if random.random() < 0.5:
                    self.say(random.choice(WOKE_LINES))
            elif ev == "heart":
                self.fx.heart(self._center_x, head - 2 * u, u)
            elif ev == "note" and fx_on:
                self.fx.note(self._center_x, head, u)
            elif ev == "snack":      # 點心從上面掉到臉前面，0.6 秒後剛好被吃掉
                self.fx.snack(self._center_x, max(2 * u, head - 30 * u), head + 5 * u, u, 0.6)
            elif ev == "crumb" and fx_on:
                self.fx.crumbs(self._center_x, head + 7 * u, u)
            elif ev == "sweat" and fx_on:
                self.fx.sweat(self._center_x, head + 2 * u, u, self._sprite_w * 0.6)

    def paintEvent(self, _):
        p = QPainter(self)
        smooth = bool(self.settings["smooth"])
        # 平滑模式：從 2 倍超取樣圖平滑縮放 → 旋轉/擠壓/移動時邊緣有抗鋸齒，且可以次像素移動
        # 銳利模式：最近鄰 + 對齊實體像素 → 最「像素風」，但動起來會有鋸齒
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, smooth)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, smooth)
        snap = (lambda v: v) if smooth else self._snap
        pose, u = self.pose, self._unit
        pm = self._pixmaps.get(pose.sprite) or self._pixmaps.get("idle")
        if pm is None:
            return
        sw, sh = self._sprite_w, self._sprite_h
        x = snap(self._center_x + pose.dx * u)
        if pose.anchor_top:
            # 被拎起來：支點在頭頂
            pivot = self.sprites.bounds["idle"].top() * sh
            y = snap(self._baseline - sh + pivot + pose.dy * u)
            rect = QRectF(-sw / 2, -pivot, sw, sh)
        elif pose.pivot_center:
            # 被丟出去 / 轉一圈：以身體中心為軸原地旋轉，轉到哪個角度都不會甩出視窗
            c = self.sprites.bounds["idle"].center()
            cx, cy = c.x() * sw, c.y() * sh
            x = snap(self._center_x - sw / 2 + cx + pose.dx * u)
            y = snap(self._baseline - sh + cy + pose.dy * u)
            rect = QRectF(-cx, -cy, sw, sh)
        else:
            y = snap(self._baseline + pose.dy * u)
            rect = QRectF(-sw / 2, -sh, sw, sh)

        self._paint_speed_lines(p)
        p.save()
        if pose.clip_floor:  # 躲貓貓：腳底線以下不畫，看起來像沉進工作列裡
            p.setClipRect(QRectF(0, 0, self.width(), self._feet_offset().y()))
        p.translate(x, y)
        if pose.rot:
            p.rotate(pose.rot)
        p.scale(pose.sx, pose.sy)
        # 幾乎透明的點擊區：讓腳之間的空隙也點得到（完全透明的地方滑鼠會穿透）
        b = self.sprites.bounds.get(pose.sprite, self.sprites.bounds["idle"])
        hit = QRectF(rect.x() + b.x() * sw, rect.y() + b.y() * sh, b.width() * sw, b.height() * sh)
        p.fillRect(hit, QColor(0, 0, 0, 1))
        p.drawPixmap(rect, pm, QRectF(0, 0, pm.width(), pm.height()))
        p.restore()
        self.fx.paint(p)  # 灰塵、愛心、音符畫在 Clawd 前面

        if self.anim.action == "dizzy":
            a = self.anim.action_elapsed(self._now)
            fade = max(0.0, min(1.0, (2.6 - a) / 0.5))
            paint_dizzy_stars(p, x, self._head_y() - 1.5 * u, self._sprite_w * 0.3, u, self._now, fade)

        if self.anim.sleeping:
            self._paint_zzz(p)

    def _paint_zzz(self, p: QPainter) -> None:
        u = self._unit
        t = time.perf_counter()
        base_x = self._center_x + self._sprite_w * 0.22
        base_y = self._head_y()
        for i in range(3):
            phase = (t * 0.35 + i / 3) % 1.0
            alpha = int(255 * math.sin(phase * math.pi))
            f = QFont("Consolas")
            f.setBold(True)
            f.setPixelSize(max(8, round(u * (3.5 + phase * 3))))
            p.setFont(f)
            p.setPen(QColor(217, 119, 87, alpha))
            p.drawText(QPointF(base_x + phase * 5 * u, base_y - phase * 10 * u), "z")

    # ================= 待機小行為 =================
    def _on_floor(self) -> bool:
        return abs(self._feet_global().y() - self._floor_y()) <= 3

    def _free(self) -> bool:
        """閒著：沒被拖、沒在掉、沒在做動作、沒睡覺、看得見。"""
        return (self.isVisible() and not self._pressed and self._fall is None
                and not self.anim.busy and not self.anim.sleeping)

    def _on_idle(self) -> None:
        """每秒檢查一次：閒著的時候偶爾走一走，或表演一下。"""
        now = time.perf_counter()
        for ev in self.reminders.poll(now, time.localtime().tm_hour):
            self._on_reminder(ev)
        if not self._free() or self.anim.walking or self.bubble.isVisible():
            return
        if self.settings["wander"] and self._on_floor() and now >= self._next_walk:
            self._next_walk = now + random.uniform(12, 30)
            if random.random() < 0.7:
                self.start_walk(duration=random.uniform(1.8, 4.5))
                return
        interval = IDLE_INTERVALS[self.settings["idle_actions"]]
        if interval and now >= self._next_trick:
            self._next_trick = now + random.uniform(*interval)
            self.do_random_trick()

    def do_random_trick(self) -> str:
        """自己隨機做一個動作（不會連續兩次做同一個；不算互動，所以不影響睡覺）。"""
        pool = [t for t in IDLE_TRICKS if t != self._last_trick
                and (t != "hide" or self._on_floor())]
        trick = self._last_trick = random.choice(pool)
        self.anim.play(trick, interaction=False)
        return trick

    def _set_idle_actions(self, v: str) -> None:
        self.settings["idle_actions"] = v
        self.settings.save()
        self.anim.nap_wakes = v != "off"
        interval = IDLE_INTERVALS[v]
        if interval:
            self._next_trick = time.perf_counter() + random.uniform(*interval)

    # ================= 提醒 =================
    def _on_reminder(self, ev: tuple) -> None:
        kind = ev[0]
        if kind == "water":
            self._remind("該喝水囉 💧 起來倒杯水吧", "wave")
        elif kind == "focus_done":
            self._remind("專注時間結束！🎉 休息 5 分鐘吧", "dance")
        elif kind == "break_done":
            self._remind("休息結束，繼續加油 💪", "wave")
        elif kind == "chime":
            self._remind(f"{ev[1]} 點整囉 🕐", "wave")

    def _remind(self, text: str, action: str) -> None:
        """提醒一定要讓人看到：Clawd 被隱藏時改用系統通知；睡著的話先醒來。"""
        if not self.isVisible():
            self.tray.showMessage("Clawd 桌寵", text, self.tray.icon(), 6000)
            return
        self.anim.poke()
        if self._fall is None and not self._pressed:
            self.anim.play(action)
        self.say(text, force=True, min_ms=6000)

    def start_pomodoro(self) -> None:
        self.reminders.start_pomodoro(time.perf_counter())
        self.anim.play("wave")
        self.say("開始專注 25 分鐘，加油！🍅", force=True)

    def cancel_pomodoro(self) -> None:
        self.reminders.cancel_pomodoro()
        self.say("番茄鐘結束了", force=True)

    def _set_water(self, minutes: int) -> None:
        self.settings["water_minutes"] = minutes
        self.settings.save()
        self.reminders.set_water(minutes, time.perf_counter())
        self.say(f"每 {minutes} 分鐘提醒你喝水 💧" if minutes else "喝水提醒已關閉", force=True)

    def _set_chime(self, on: bool) -> None:
        self.settings["chime"] = on
        self.settings.save()
        self.reminders.chime = on

    # ================= 餵食、躲貓貓、跟著滑鼠 =================
    def feed(self) -> None:
        if self._fall is not None or self._pressed:
            return
        self.anim.poke()
        self.anim.play("eat")
        QTimer.singleShot(2150, self._after_eat)

    def _after_eat(self) -> None:
        if self.anim.action == "eat":
            self.say(random.choice(EAT_LINES))

    def play_hide(self) -> None:
        if self._fall is not None or self._pressed:
            return
        if self._on_floor():
            self.anim.play("hide")
        else:
            self.say("要站在工作列上才能躲貓貓啦", force=True)

    def _maybe_chase(self, now: float) -> None:
        """「跟著滑鼠走」：滑鼠離得遠時，沿著工作列朝它走過去。"""
        if not self.settings["chase"] or not self._free() or not self._on_floor():
            return
        dx = QCursor.pos().x() - self._feet_global().x()
        if abs(dx) > self._sprite_w * 1.1:
            self._chasing = True
            self._walk_x = float(self.x())
            self._walk_until = now + 20
            self.anim.walk(1 if dx > 0 else -1, now)

    def start_walk(self, direction: int = 0, duration: float = 3.0) -> None:
        if not self._on_floor() or self._fall is not None:
            return
        if direction == 0:  # 往空間比較大的那邊走
            g = self._screen_rect()
            cx = self._feet_global().x()
            direction = 1 if (g.right() - cx) > (cx - g.left()) else -1
            if random.random() < 0.35:
                direction = -direction
        self._chasing = False
        self._walk_x = float(self.x())
        self._walk_until = time.perf_counter() + duration
        self.anim.walk(direction)

    def _step_walk(self, now: float, dt: float) -> None:
        if now >= self._walk_until or not self._free():
            self._end_walk()
            return
        if self._chasing:                                        # 朝滑鼠走：隨時修正方向，走到就停
            dx = QCursor.pos().x() - self._feet_global().x()
            if not self.settings["chase"] or abs(dx) < self._sprite_w * 0.45:
                self._end_walk()
                return
            d = 1 if dx > 0 else -1
            if d != self.anim.walking:
                self.anim.walk(d, now)
        speed = (22 if self._chasing else 11) * self._unit      # 追滑鼠時走快一點
        self._walk_x += self.anim.walking * speed * dt
        g = self._screen_rect()
        fo = self._feet_offset()
        half = self.sprites.bounds["idle"].width() * self._sprite_w / 2
        left, right = g.left() + half - fo.x(), g.right() - half - fo.x()
        if self._walk_x <= left or self._walk_x >= right:        # 走到邊緣
            self._walk_x = max(left, min(self._walk_x, right))
            if self._chasing:                                    # 追滑鼠：到邊緣就停下來等
                self.move(round(self._walk_x), self.y())
                self._end_walk()
                return
            self.anim.walk(-self.anim.walking, now)              # 散步：轉身往回走
        self.move(round(self._walk_x), self.y())

    def _end_walk(self) -> None:
        self.anim.stop_walk()
        self._chasing = False
        self._save_position()

    def _watch_cursor(self, now: float) -> None:
        """滑鼠在附近時轉過去看它（太近、太遠都不理）。"""
        if not self.settings["follow_cursor"] or not self._free():
            return
        c = QCursor.pos()
        me = self.mapToGlobal(QPoint(round(self._center_x), round(self._head_y() + self._sprite_h * 0.3)))
        dx, dy = c.x() - me.x(), c.y() - me.y()
        dist = math.hypot(dx, dy)
        if self._sprite_w * 0.6 < dist < self._sprite_w * 2.6 and abs(dx) > self._sprite_w * 0.3:
            self.anim.watch(1 if dx > 0 else -1, now)

    def _greet(self) -> None:
        hour = time.localtime().tm_hour
        if 5 <= hour < 11:
            text = "早安！今天也一起加油 ☀️"
        elif 11 <= hour < 14:
            text = "午安～吃飯了嗎？"
        elif 14 <= hour < 18:
            text = "下午好！要不要喝杯茶？"
        elif 18 <= hour < 23:
            text = "晚上好～今天辛苦了"
        else:
            text = "這麼晚還沒睡？我陪你 🌙"
        self.anim.play("wave")
        self.say(text)

    # ================= 說話 =================
    def say(self, text: str, force: bool = False, min_ms: int = 0) -> None:
        if not (force or self.settings["bubbles"]):
            return
        ms = max(min_ms, 2200 + 90 * len(text))
        self.bubble.say(text, self._head_global(), ms)
        self.anim.talk(min(ms / 1000, 2.0))

    def _schedule_chatter(self) -> None:
        self._chatter.start(random.randint(240, 480) * 1000)

    def _on_chatter(self) -> None:
        if (self.settings["chatter"] and self.settings["bubbles"]
                and not self.anim.sleeping and not self.anim.dragging):
            now = time.perf_counter()
            hour = time.localtime().tm_hour
            if hour < 5 and now - self._last_night_note > 3600:   # 深夜：每小時最多提醒一次
                self._last_night_note = now
                self.say(f"已經 {hour} 點了，早點睡吧 💤")
            else:
                self.say(self.phrases.random())
        self._schedule_chatter()

    def hello_again(self) -> None:
        """有人又執行了一次程式：跳出來打招呼，而不是開第二隻。"""
        self.set_pet_visible(True)
        self.raise_()
        self._keep_on_screen()
        self.anim.play("jump")
        self.say("我在這裡！", force=True)

    # ================= 工作列右下角圖示 =================
    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon(str(paths.assets_dir() / "icon.png")), self)
        self.tray.setToolTip("Clawd 桌寵（左鍵：顯示/隱藏，右鍵：選單）")
        self._tray_menu = self._menu()
        self._tray_menu.aboutToShow.connect(lambda: self._build_menu(self._tray_menu, tray=True))
        self.tray.setContextMenu(self._tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # 左鍵單擊
            self.set_pet_visible(not self.isVisible())

    def set_pet_visible(self, on: bool) -> None:
        if on:
            self.show()
            self._apply_fps()
            self.anim.play("jump")
        else:
            self.bubble.hide_now()
            self.hide()
            self._tick.stop()  # 隱藏時不耗 CPU

    # ================= 滑鼠 =================
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self._fall is not None:  # 掉落中被接住
                self._fall = None
                self.anim.falling = False
            self.anim.stop_walk()
            self._pressed = True
            self._dragging = False
            self._press_global = e.globalPosition().toPoint()
            self._win_start = self.pos()
            self._last_mouse = (self._press_global, time.perf_counter())
            self._drag_v = (0.0, 0.0)
            self._shakes.clear()
            self._shake_dir = 0
        e.accept()

    def mouseMoveEvent(self, e):
        g = e.globalPosition().toPoint()
        if not self._pressed:
            self._detect_petting(g.x())
            return
        if not self._dragging:
            if (g - self._press_global).manhattanLength() < 6:
                return
            self._dragging = True
            self._click_timer.stop()
            self.bubble.hide_now()
            self.anim.start_drag()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if self.settings["effects"]:                         # 被抓起來嚇一跳：頭上冒「!」
                self.fx.emote(self._center_x, self._head_y() - 5 * self._unit, self._unit)
        self.move(self._win_start + (g - self._press_global))
        now = time.perf_counter()
        lp, lt = self._last_mouse
        dt = max(now - lt, 1e-3)
        vx, vy = (g.x() - lp.x()) / dt, (g.y() - lp.y()) / dt
        ovx, ovy = self._drag_v
        self._drag_v = (ovx * 0.5 + vx * 0.5, ovy * 0.5 + vy * 0.5)   # 平滑：放開時拿來丟
        self.anim.drag_velocity(vx)
        self._last_mouse = (g, now)
        # 搖晃偵測：快速左右來回 5 次以上 → 落地後會暈
        if abs(vx) > 900:
            d = 1 if vx > 0 else -1
            if self._shake_dir and d != self._shake_dir:
                self._shakes = [t for t in self._shakes if now - t < 1.5] + [now]
                if len(self._shakes) >= 5:
                    self._dizzy_pending = True
            self._shake_dir = d

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        was_pressed, self._pressed = self._pressed, False
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if self._ignore_release:
            self._ignore_release = False
            return
        if self._dragging:
            self._dragging = False
            # 放開前停住超過 0.1 秒就不算甩，直接掉下去
            vx, vy = self._drag_v if time.perf_counter() - self._last_mouse[1] < 0.1 else (0.0, 0.0)
            self._keep_on_screen()
            if self._should_dock():
                self.anim.end_drag(fall=True)
                self._start_fall(vx, vy)
            else:
                self.anim.end_drag()
                self._after_landing()
            return
        if was_pressed:
            self._click_timer.start(QApplication.styleHints().mouseDoubleClickInterval())

    def _detect_petting(self, x: int) -> None:
        """滑鼠在 Clawd 身上來回滑（不按鍵）= 摸摸頭。"""
        last_x, last_dir, travel = self._hover
        dx = x - last_x
        now = time.perf_counter()
        if abs(dx) < 2:
            return
        d = 1 if dx > 0 else -1
        travel = travel + abs(dx) if last_dir else 0.0                  # 剛移進來的第一下不算
        if last_dir and d != last_dir and travel > self._unit * 3:   # 換方向 = 摸了一下
            self._rubs = [t for t in self._rubs if now - t < 1.2] + [now]
            travel = 0
            if len(self._rubs) >= 3 and self.anim.action != "pet" and self._fall is None:
                self._rubs.clear()
                woke = self.anim.poke()
                self.anim.play("pet")
                if woke:
                    self.say("嗯～被摸醒了 💕")
                elif random.random() < 0.4:
                    self.say(random.choice(PET_LINES))
        self._hover = (x, d, travel)

    def wheelEvent(self, e):
        """在 Clawd 身上滾動滑鼠滾輪：往上變大、往下變小。"""
        now = time.perf_counter()
        delta = e.angleDelta().y()
        if delta == 0 or now - self._last_wheel < 0.25:
            return
        self._last_wheel = now
        sizes = [v for _, v in SIZE_PRESETS]
        i = sizes.index(int(self.settings["size"])) + (1 if delta > 0 else -1)
        if 0 <= i < len(sizes):
            self._set_size(sizes[i])
        e.accept()

    def leaveEvent(self, e):
        self._hover = (0, 0, 0.0)
        self._rubs.clear()
        super().leaveEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._click_timer.stop()
        self._pressed = False
        self._ignore_release = True
        self.open_claude_app()

    def _on_single_click(self) -> None:
        if self.anim.poke():  # 原本在睡覺 → 被吵醒
            self.anim.play("squish")
            self.say(random.choice(WAKE_LINES))
            return
        choices = ["jump", "squish", "shake", "spin"]
        if self.settings["bubbles"]:
            choices += ["talk", "talk"]
        c = random.choice(choices)
        if c == "talk":
            self.say(self.phrases.random())
        else:
            self.anim.play(c)

    # ================= Claude =================
    def open_claude_app(self) -> None:
        """雙擊：開啟桌面版 Claude（已經開著的話會叫到前面）。"""
        ok, _ = launcher.open_desktop_app()
        if ok:
            self.anim.play("idea")
            self.say(random.choice(LAUNCH_LINES))
            return
        self.anim.play("shake")
        self.say("找不到 Claude 桌面版…", force=True)
        ans = QMessageBox.question(
            None, "ClawdPet",
            "這台電腦還沒有安裝 Claude 桌面版。\n\n要現在打開下載頁面嗎？\n（安裝好之後，雙擊 Clawd 就能直接開啟 Claude）")
        if ans == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(launcher.DOWNLOAD_URL))

    def _launch_folder(self) -> tuple[str, bool]:
        """決定在哪裡開 Claude：設定的專案 → 最近用過的 → 使用者資料夾。回傳 (資料夾, 是否為預設)。"""
        for d in [self.settings["project_dir"], *self.settings["recent_dirs"]]:
            if d and os.path.isdir(d):
                return d, False
        return os.path.expanduser("~"), True

    def launch_claude(self, cont: bool = False) -> None:
        folder, is_default = self._launch_folder()
        ok, msg = launcher.launch(folder, ["--continue"] if cont else [])
        if ok:
            self.anim.play("idea")
            if is_default:
                self.say("在使用者資料夾開啟 Claude～\n右鍵可以設定專案資料夾", force=True)
            else:
                self.say(f"{random.choice(LAUNCH_LINES)}\n📁 {os.path.basename(folder) or folder}")
        else:
            self.anim.play("shake")
            self.say(msg, force=True)
            QMessageBox.warning(None, "ClawdPet", msg)

    def choose_folder(self) -> str:
        start = self.settings["project_dir"] or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(None, "選擇 Claude 專案資料夾", start)
        if folder:
            self.settings.set_project(folder)
            self.say(f"專案設定為：{os.path.basename(folder) or folder}")
        return folder

    # ================= 右鍵選單 =================
    def _menu(self, title: str = "", parent: QWidget | None = None) -> QMenu:
        m = QMenu(title, parent)
        m.setWindowFlags(m.windowFlags() | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        m.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        m.setStyleSheet(MENU_QSS)
        m.setToolTipsVisible(True)
        return m

    def contextMenuEvent(self, e):
        self._click_timer.stop()
        self.bubble.hide_now()
        self.anim.poke()
        menu = self._build_menu()
        menu.exec(e.globalPos())
        menu.deleteLater()

    def _build_menu(self, menu: QMenu | None = None, tray: bool = False) -> QMenu:
        s = self.settings
        if menu is None:
            menu = self._menu(parent=self)
        else:  # 重複使用（工作列圖示的選單）：清掉上次的內容與子選單
            menu.clear()
            for child in menu.findChildren(QMenu):
                child.deleteLater()

        if tray:
            if self.isVisible():
                menu.addAction("🙈  隱藏 Clawd", lambda: self.set_pet_visible(False))
            else:
                menu.addAction("🦀  顯示 Clawd", lambda: self.set_pet_visible(True))
            menu.addSeparator()

        menu.addAction("🚀  開啟 Claude（雙擊）", self.open_claude_app)
        menu.addSeparator()

        # 進階：終端機版 Claude Code
        adv = self._menu("💻  進階：終端機版 Claude Code", menu)
        adv.addAction("在專案資料夾中開啟", lambda: self.launch_claude())
        adv.addAction("繼續上次的對話", lambda: self.launch_claude(cont=True))
        adv.addSeparator()
        proj = adv
        current = s["project_dir"]
        cur = proj.addAction(f"📁 專案：{os.path.basename(current) or current}" if current else "📁 專案：尚未設定")
        cur.setEnabled(False)
        if current:
            cur.setToolTip(current)
        proj.addAction("選擇專案資料夾…", self.choose_folder)
        if current and os.path.isdir(current):
            proj.addAction("在檔案總管中開啟", lambda: os.startfile(current))
        recent = [d for d in s["recent_dirs"] if os.path.isdir(d)]
        if recent:
            proj.addSeparator()
            for d in recent:
                a = proj.addAction(os.path.basename(d) or d)
                a.setToolTip(d)
                a.setCheckable(True)
                a.setChecked(os.path.normcase(d) == os.path.normcase(current))
                a.triggered.connect(lambda _=False, d=d: self._set_project(d))
        menu.addMenu(adv)

        # 動作
        act = self._menu("🎭  動作", menu)
        act.addAction("💃 跳舞", lambda: self.anim.play("dance"))
        act.addAction("🔄 轉一圈", lambda: self.anim.play("spin"))
        act.addAction("👋 揮手打招呼", self._greet)
        act.addAction("🦀 走一走", lambda: self.start_walk(duration=4.0))
        act.addAction("🍪 餵點心", self.feed)
        act.addAction("🤸 開合跳", lambda: self.anim.play("exercise"))
        act.addAction("🙈 躲貓貓", self.play_hide)
        act.addAction("😴 睡覺", lambda: self.anim.sleep_now())
        act.addSeparator()
        freq = self._menu("自己做動作的頻率", act)
        fgp = QActionGroup(freq)
        for label, v in (("關閉", "off"), ("偶爾（3～6 分鐘一次）", "rare"),
                         ("普通（1～2 分鐘一次）", "normal"), ("常常（約半分鐘一次）", "often")):
            a = freq.addAction(label)
            a.setCheckable(True)
            a.setChecked(s["idle_actions"] == v)
            fgp.addAction(a)
            a.triggered.connect(lambda _=False, v=v: self._set_idle_actions(v))
        act.addMenu(freq)
        wd = act.addAction("閒著時到處走走")
        wd.setCheckable(True)
        wd.setChecked(bool(s["wander"]))
        wd.toggled.connect(lambda on: self._set_flag("wander", on))
        fc = act.addAction("滑鼠靠近時轉頭看")
        fc.setCheckable(True)
        fc.setChecked(bool(s["follow_cursor"]))
        fc.toggled.connect(lambda on: self._set_flag("follow_cursor", on))
        ch = act.addAction("跟著滑鼠走")
        ch.setCheckable(True)
        ch.setChecked(bool(s["chase"]))
        ch.setToolTip("滑鼠離得遠時，Clawd 會沿著工作列朝滑鼠走過去")
        ch.toggled.connect(lambda on: self._set_flag("chase", on))
        menu.addMenu(act)

        # 提醒
        rem = self._menu("⏰  提醒", menu)
        r = self.reminders
        left = math.ceil(r.seconds_left(time.perf_counter()) / 60)
        if r.phase == "focus":
            rem.addAction(f"🍅 專注中：剩 {left} 分鐘（點此取消）", self.cancel_pomodoro)
        elif r.phase == "break":
            rem.addAction(f"☕ 休息中：剩 {left} 分鐘（點此結束）", self.cancel_pomodoro)
        else:
            rem.addAction("🍅 開始番茄鐘（專注 25 分鐘 → 休息 5 分鐘）", self.start_pomodoro)
        water = self._menu("💧 喝水提醒", rem)
        wg = QActionGroup(water)
        for label, v in (("關閉", 0), ("每 30 分鐘", 30), ("每 45 分鐘", 45), ("每 60 分鐘", 60), ("每 90 分鐘", 90)):
            a = water.addAction(label)
            a.setCheckable(True)
            a.setChecked(int(s["water_minutes"]) == v)
            wg.addAction(a)
            a.triggered.connect(lambda _=False, v=v: self._set_water(v))
        rem.addMenu(water)
        cm = rem.addAction("🕐 整點報時")
        cm.setCheckable(True)
        cm.setChecked(bool(s["chime"]))
        cm.toggled.connect(self._set_chime)
        menu.addMenu(rem)

        # 大小
        size = self._menu("📏  大小", menu)
        group = QActionGroup(size)
        for label, v in SIZE_PRESETS:
            a = size.addAction(label)
            a.setCheckable(True)
            a.setChecked(int(s["size"]) == v)
            group.addAction(a)
            a.triggered.connect(lambda _=False, v=v: self._set_size(v))
        size.addSeparator()
        tip = size.addAction("也可以在 Clawd 身上滾動滑鼠滾輪")
        tip.setEnabled(False)
        menu.addMenu(size)

        # 畫面：幀率 + 抗鋸齒
        gfx = self._menu("🎞  畫面", menu)
        fg = QActionGroup(gfx)
        cur_fps = int(s["fps"] or 0)
        screen = self.screen() or QGuiApplication.primaryScreen()
        hz = round(screen.refreshRate()) if screen else 60
        for label, v in ((f"跟隨螢幕（{hz} Hz）", 0), ("30 FPS", 30), ("60 FPS", 60),
                         ("120 FPS", 120), ("144 FPS", 144), ("240 FPS", 240)):
            a = gfx.addAction(label)
            a.setCheckable(True)
            a.setChecked(cur_fps == v)
            fg.addAction(a)
            a.triggered.connect(lambda _=False, v=v: self._set_fps(v))
        gfx.addSeparator()
        sm = gfx.addAction("抗鋸齒（平滑）")
        sm.setCheckable(True)
        sm.setChecked(bool(s["smooth"]))
        sm.setToolTip("關閉 = 像素銳利模式：靜止時最清晰，但旋轉、擠壓時會有鋸齒")
        sm.toggled.connect(self._set_smooth)
        ef = gfx.addAction("落地特效（灰塵粒子）")
        ef.setCheckable(True)
        ef.setChecked(bool(s["effects"]))
        ef.toggled.connect(lambda on: self._set_flag("effects", on))
        menu.addMenu(gfx)

        # 吸附底部
        dock = self._menu("🧲  吸附底部", menu)
        dg = QActionGroup(dock)
        for label, v in (("放開後總是落到底部", "always"), ("靠近底部時吸附", "near"), ("關閉", "off")):
            a = dock.addAction(label)
            a.setCheckable(True)
            a.setChecked(s["dock"] == v)
            dg.addAction(a)
            a.triggered.connect(lambda _=False, v=v: self._set_dock(v))
        dock.addSeparator()
        dock.addAction("立刻落到底部", self._drop_now)
        menu.addMenu(dock)

        # 造型
        skin = self._menu("🎨  造型", menu)
        sg = QActionGroup(skin)
        a1 = skin.addAction("Clawd（內建多動作）")
        a2 = skin.addAction("自訂圖片 assets\\clawd.png")
        for a, v in ((a1, "crab"), (a2, "custom")):
            a.setCheckable(True)
            a.setChecked(s["skin"] == v)
            sg.addAction(a)
            a.triggered.connect(lambda _=False, v=v: self._set_skin(v))
        if not paths.custom_image():
            a2.setEnabled(False)
            a2.setToolTip(f"把圖片放到 {paths.app_dir() / 'assets' / 'clawd.png'} 就能使用")
        menu.addMenu(skin)

        # 說話
        talk = self._menu("💬  說話", menu)
        b = talk.addAction("點擊時冒泡泡")
        b.setCheckable(True)
        b.setChecked(bool(s["bubbles"]))
        b.toggled.connect(lambda on: self._set_flag("bubbles", on))
        c = talk.addAction("偶爾自言自語")
        c.setCheckable(True)
        c.setChecked(bool(s["chatter"]))
        c.toggled.connect(lambda on: self._set_flag("chatter", on))
        talk.addSeparator()
        talk.addAction("編輯台詞…", lambda: os.startfile(self.phrases.path))
        menu.addMenu(talk)

        menu.addSeparator()
        auto = menu.addAction("⚙  開機自動啟動")
        auto.setCheckable(True)
        auto.setChecked(autostart.is_enabled())
        auto.toggled.connect(self._set_autostart)
        menu.addAction("📍  重設位置", self.reset_position)
        menu.addSeparator()
        menu.addAction("👋  結束", self.quit)
        ver = menu.addAction(f"Clawd 桌寵 v{__version__}")
        ver.setEnabled(False)
        return menu

    def _set_project(self, folder: str) -> None:
        self.settings.set_project(folder)
        self.say(f"專案設定為：{os.path.basename(folder) or folder}")

    def _set_size(self, v: int) -> None:
        self.settings["size"] = v
        self._rebuild(keep_anchor=True)
        self._save_position()
        self.anim.play("squish")

    def _set_dock(self, v: str) -> None:
        self.settings["dock"] = v
        self.settings.save()
        if v == "always":
            self._drop_now()

    def _drop_now(self) -> None:
        if not self.isVisible():
            self.set_pet_visible(True)
        self._start_fall()

    def _set_fps(self, v: int) -> None:
        self.settings["fps"] = v
        self.settings.save()
        self._apply_fps()
        self.say(f"畫面更新：{round(self.target_fps())} FPS", force=True)

    def _set_smooth(self, on: bool) -> None:
        self.settings["smooth"] = on
        self.settings.save()
        self._rebuild(keep_anchor=True, force=True)

    def _set_skin(self, v: str) -> None:
        self.settings["skin"] = v
        self.settings.save()
        self.sprites = SpriteSet.load(v)
        self._rebuild(keep_anchor=True, force=True)
        self.anim.play("jump")

    def _set_flag(self, key: str, on: bool) -> None:
        self.settings[key] = on
        self.settings.save()

    def _set_autostart(self, on: bool) -> None:
        try:
            autostart.set_enabled(on)
            self.say("開機後我會自己出現！" if on else "好，開機時不自動啟動", force=True)
        except OSError as e:
            QMessageBox.warning(None, "ClawdPet", f"設定開機自動啟動失敗：{e}")

    def quit(self) -> None:
        self._save_position()
        self.bubble.close()
        self.tray.hide()
        QApplication.quit()
