"""桌寵主視窗：透明、無邊框、置頂、不佔工作列；處理繪製、滑鼠與右鍵選單。"""
from __future__ import annotations

import math
import os
import random
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import (QActionGroup, QColor, QDesktopServices, QFont, QGuiApplication, QIcon,
                           QPainter)
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon, QWidget

from services import autostart, launcher, paths
from services.settings import Settings
from services.version import __version__
from .animator import Animator
from .bubble import Bubble
from .phrases import Phrases
from .sprites import BASE_W, SpriteSet

SIZE_PRESETS = [("小", 3), ("中", 4), ("大", 5), ("特大", 6)]
WAKE_LINES = ["嗯…？我醒了！", "呼啊～睡得好飽", "有什麼事嗎？"]
LAUNCH_LINES = ["有點子了！開工囉", "Claude 出動！", "一起把 bug 抓光吧！"]

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
        self._fall: tuple[int, float, float] | None = None  # (目標 y, 目前速度, 目前 y（浮點數）)
        self._last_tick = time.perf_counter()
        self._was_sleeping = False

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
        win_w = math.ceil(lw * 1.35)
        win_h = math.ceil(lh + 8 * u)
        self.setFixedSize(win_w, win_h)
        self._center_x = win_w / 2
        self._baseline = win_h - 6 * u
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

    def _start_fall(self) -> None:
        target = self._floor_y() - self._feet_offset().y()
        if target <= self.y():
            self._fall = None
            self.anim.land()
            self._save_position()
            return
        self._fall = (target, 0.0, float(self.y()))
        self.anim.falling = True

    def _step_fall(self, dt: float) -> None:
        # y 用浮點數累積：每幀從整數座標重算的話，小數被捨去，幀率越高掉得越慢
        target, v, y = self._fall
        v += 4200 * dt                     # 重力加速度（像素/秒²）
        y += v * dt
        if y >= target:
            self.move(self.x(), target)
            self._fall = None
            self.anim.land()
            self._save_position()
        else:
            self.move(self.x(), round(y))
            self._fall = (target, v, y)

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
        now = time.perf_counter()
        dt, self._last_tick = min(now - self._last_tick, 0.05), now
        if self._fall is not None:
            self._step_fall(dt)
        self.pose = self.anim.update(now)
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
        else:
            y = snap(self._baseline + pose.dy * u)
            rect = QRectF(-sw / 2, -sh, sw, sh)

        p.save()
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

    # ================= 說話 =================
    def say(self, text: str, force: bool = False) -> None:
        if not (force or self.settings["bubbles"]):
            return
        ms = 2200 + 90 * len(text)
        self.bubble.say(text, self._head_global(), ms)
        self.anim.talk(min(ms / 1000, 2.0))

    def _schedule_chatter(self) -> None:
        self._chatter.start(random.randint(240, 480) * 1000)

    def _on_chatter(self) -> None:
        if (self.settings["chatter"] and self.settings["bubbles"]
                and not self.anim.sleeping and not self.anim.dragging):
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
            self._pressed = True
            self._dragging = False
            self._press_global = e.globalPosition().toPoint()
            self._win_start = self.pos()
            self._last_mouse = (self._press_global, time.perf_counter())
        e.accept()

    def mouseMoveEvent(self, e):
        if not self._pressed:
            return
        g = e.globalPosition().toPoint()
        if not self._dragging:
            if (g - self._press_global).manhattanLength() < 6:
                return
            self._dragging = True
            self._click_timer.stop()
            self.bubble.hide_now()
            self.anim.start_drag()
        self.move(self._win_start + (g - self._press_global))
        now = time.perf_counter()
        lp, lt = self._last_mouse
        self.anim.drag_velocity((g.x() - lp.x()) / max(now - lt, 1e-3))
        self._last_mouse = (g, now)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        was_pressed, self._pressed = self._pressed, False
        if self._ignore_release:
            self._ignore_release = False
            return
        if self._dragging:
            self._dragging = False
            self._keep_on_screen()
            if self._should_dock():
                self.anim.end_drag(fall=True)
                self._start_fall()
            else:
                self.anim.end_drag()
                self._save_position()
            return
        if was_pressed:
            self._click_timer.start(QApplication.styleHints().mouseDoubleClickInterval())

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
        choices = ["jump", "squish", "shake"]
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

        # 大小
        size = self._menu("📏  大小", menu)
        group = QActionGroup(size)
        for label, v in SIZE_PRESETS:
            a = size.addAction(label)
            a.setCheckable(True)
            a.setChecked(int(s["size"]) == v)
            group.addAction(a)
            a.triggered.connect(lambda _=False, v=v: self._set_size(v))
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
