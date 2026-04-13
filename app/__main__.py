# -*- coding: utf-8 -*-
"""Point d'entrée — splash screen puis chargement dans le thread UI."""

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
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Batikam Rénove")
    qt_app.setOrganizationName("Batikam")

    if _try_raise_existing():
        sys.exit(0)

    server = QLocalServer()
    QLocalServer.removeServer(_APP_KEY)
    server.listen(_APP_KEY)

    # Import léger du logo uniquement
    from app.services.branding import resolve_logo_path
    logo_path = resolve_logo_path()
    logo_str = str(logo_path) if logo_path is not None and logo_path.exists() else None
    if logo_str:
        qt_app.setWindowIcon(QIcon(logo_str))

    # Splash affiché immédiatement
    from app.ui.splash import SplashScreen
    splash = SplashScreen(logo_str)
    splash.show()
    qt_app.processEvents()

    # Étape 1 — thème
    splash.set_status("Initialisation du thème…")
    qt_app.processEvents()
    from app.ui.theme import apply_theme
    from qfluentwidgets import setTheme, Theme, setThemeColor
    apply_theme(qt_app)
    setTheme(Theme.LIGHT)
    setThemeColor("#1F6FEB")
    qt_app.processEvents()

    # Étape 2 — base de données
    splash.set_status("Chargement de la base de données…")
    qt_app.processEvents()
    from app.services import storage_sqlite as _  # noqa: F401
    qt_app.processEvents()

    # Étape 3 — interface principale
    splash.set_status("Démarrage de l'interface…")
    qt_app.processEvents()
    from app.ui.main_window import MainWindow
    window = MainWindow()
    qt_app.processEvents()

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
    splash.finish(window)

    result = qt_app.exec()
    server.close()
    sys.exit(result)


if __name__ == "__main__":
    main()
