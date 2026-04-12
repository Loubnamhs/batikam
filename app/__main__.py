# -*- coding: utf-8 -*-
"""Point d'entrée pour l'exécution en mode module."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_APP_KEY = "BatikamRenove_SingleInstance_v1"


def _try_raise_existing() -> bool:
    socket = QLocalSocket()
    socket.connectToServer(_APP_KEY)
    if socket.waitForConnected(500):
        socket.write(b"raise")
        socket.flush()
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        return True
    return False


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Batikam Rénove")
    app.setOrganizationName("Batikam")

    if _try_raise_existing():
        sys.exit(0)

    server = QLocalServer()
    QLocalServer.removeServer(_APP_KEY)
    server.listen(_APP_KEY)

    # Tous les imports lourds APRÈS QApplication()
    from app.services.branding import resolve_logo_path
    from app.ui.theme import apply_theme
    from app.ui.main_window import MainWindow
    from qfluentwidgets import setTheme, Theme, setThemeColor

    logo_path = resolve_logo_path()
    if logo_path is not None and logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    apply_theme(app)
    setTheme(Theme.LIGHT)
    setThemeColor('#1F6FEB')

    window = MainWindow()

    def _on_new_connection() -> None:
        conn = server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(1000)
            state = window.windowState() & ~Qt.WindowMinimized
            window.setWindowState(state | Qt.WindowActive)
            window.raise_()
            window.activateWindow()

    server.newConnection.connect(_on_new_connection)
    window.show()

    result = app.exec()
    server.close()
    sys.exit(result)


if __name__ == "__main__":
    main()
