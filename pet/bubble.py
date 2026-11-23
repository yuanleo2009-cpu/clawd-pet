"""對話泡泡：獨立的小透明視窗，浮在桌寵頭上，不會擋住滑鼠。"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

PAD_X, PAD_Y, TAIL, RADIUS, MAX_W = 12, 8, 9, 10, 220
BORDER = QColor("#D97757")
FILL = QColor("#FFFBF7")
TEXT = QColor("#3A2A22")


class Bubble(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.NoDropShadowWindowHint
                         | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._text = ""
        self._tail_x = 0.0
        self._font = QFont("Microsoft JhengHei UI", 10)
        self._font.setBold(True)
        self._timer = QTimer(self, singleShot=True)
        self._timer.timeout.connect(self.hide)

    def say(self, text: str, anchor: QPoint, ms: int) -> None:
        self._text = text
        fm = QFontMetrics(self._font)
        r = fm.boundingRect(QRect(0, 0, MAX_W, 1000),
                            Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter, text)
        self.setFixedSize(r.width() + PAD_X * 2 + 6, r.height() + PAD_Y * 2 + TAIL + 6)
        self.follow(anchor, force=True)
        self.show()
        self.raise_()
        self.update()
        self._timer.start(ms)

    def hide_now(self) -> None:
        self._timer.stop()
        self.hide()

    def follow(self, anchor: QPoint, force: bool = False) -> None:
        if not force and not self.isVisible():
            return
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        x = anchor.x() - self.width() // 2
        y = anchor.y() - self.height()
        x = max(g.left() + 2, min(x, g.right() - self.width() - 2))
        y = max(g.top() + 2, y)
        self._tail_x = max(RADIUS + 8, min(anchor.x() - x, self.width() - RADIUS - 8))
        if self.pos() != QPoint(x, y):
            self.move(x, y)
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        body = QRectF(3, 3, w - 6, h - 6 - TAIL)
        path = QPainterPath()
        path.addRoundedRect(body, RADIUS, RADIUS)
        tail = QPainterPath()
        tx = self._tail_x
        tail.addPolygon(QPolygonF([QPointF(tx - 7, body.bottom() - 2),
                                   QPointF(tx + 7, body.bottom() - 2),
                                   QPointF(tx, h - 3)]))
        path = path.united(tail)
        p.setPen(QPen(BORDER, 2.5))
        p.setBrush(FILL)
        p.drawPath(path)
        p.setPen(TEXT)
        p.setFont(self._font)
        p.drawText(body.adjusted(PAD_X, PAD_Y, -PAD_X, -PAD_Y),
                   Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter, self._text)
