"""ClawdPet 桌面寵物 — 程式入口。

開發時執行：  .venv\\Scripts\\pythonw.exe main.py
結束執行中的 Clawd（安裝程式會用到）：  ClawdPet.exe --quit
"""
from __future__ import annotations

import datetime
import getpass
import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from services import paths
from services.version import __version__


def _log_crash(exc_type, exc, tb) -> None:
    """打包版沒有主控台：把未處理的錯誤寫到資料夾裡的 error.log
    （Windows：%APPDATA%\\ClawdPet；macOS：~/Library/Application Support/ClawdPet）。"""
    try:
        with open(paths.data_dir() / "error.log", "a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S}  v{__version__} =====\n")
            traceback.print_exception(exc_type, exc, tb, file=f)
    except OSError:
        pass
    sys.__excepthook__(exc_type, exc, tb)


def main() -> int:
    sys.excepthook = _log_crash
    quit_requested = "--quit" in sys.argv

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("ClawdPet")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(str(paths.assets_dir() / "icon.png")))

    # 只允許一隻：已經在執行的話，叫原本那隻出來打招呼（或請它正常結束）
    name = f"ClawdPet-{getpass.getuser()}"
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(300):
        sock.write(b"quit" if quit_requested else b"hello")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.waitForDisconnected(2000)
        return 0
    if quit_requested:  # 本來就沒在執行
        return 0

    from pet.window import PetWindow  # 放在這裡：只送訊息的那次執行不用載入整個介面

    QLocalServer.removeServer(name)
    server = QLocalServer()
    server.listen(name)

    pet = PetWindow()
    pet.show()

    def on_connection():
        conn = server.nextPendingConnection()
        if conn is None:
            return
        conn.waitForReadyRead(500)
        msg = bytes(conn.readAll())
        conn.disconnectFromServer()
        if msg == b"quit":
            pet.quit()
        else:
            pet.hello_again()

    server.newConnection.connect(on_connection)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
