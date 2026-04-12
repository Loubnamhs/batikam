# -*- coding: utf-8 -*-
"""Point d'entrée de l'application Batikam Rénove."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket

# Clé unique pour identifier l'instance en cours
_APP_KEY = "BatikamRenove_SingleInstance_v1"


def _try_raise_existing() -> bool:
    """Tente de contacter une instance déjà ouverte.

    Retourne True si une instance existante a été trouvée et activée.
    L'appelant doit alors quitter immédiatement.
    """
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
    """Lance l'application (instance unique garantie)."""
    app = QApplication(sys.argv)
    app.setApplicationName("Batikam Rénove")
    app.setOrganizationName("Batikam")

    # --- Garde instance unique ---
    if _try_raise_existing():
        # Une fenêtre est déjà ouverte, on la réactive et on sort
        sys.exit(0)

    # Aucune instance active : on devient le serveur
    server = QLocalServer()
    QLocalServer.removeServer(_APP_KEY)  # Nettoie un éventuel socket stale
    server.listen(_APP_KEY)

    # --- Démarrage normal ---
    # Imports après QApplication pour éviter "Must construct a QApplication before a QWidget"
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
        """Quand un second clic ouvre une tentative de connexion : on remonte la fenêtre."""
        conn = server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(1000)
            # Retire la minimisation si présente, puis remonte au premier plan
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
