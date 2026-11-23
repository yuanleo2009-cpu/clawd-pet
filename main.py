"""ClawdPet 桌面寵物 — 程式入口。

開發時執行：  .venv\\Scripts\\pythonw.exe main.py
"""
from __future__ import annotations

import getpass
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from pet.window import PetWindow
from services import paths


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("ClawdPet")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(str(paths.assets_dir() / "icon.png")))

    # 只允許一隻：已經在執行的話，叫原本那隻出來打招呼
    name = f"ClawdPet-{getpass.getuser()}"
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(300):
        sock.write(b"hello")
        sock.flush()
        sock.waitForBytesWritten(300)
        return 0

    QLocalServer.removeServer(name)
    server = QLocalServer()
    server.listen(name)

    pet = PetWindow()
    pet.show()

    def on_connection():
        conn = server.nextPendingConnection()
        if conn:
            conn.disconnectFromServer()
        pet.hello_again()

    server.newConnection.connect(on_connection)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
