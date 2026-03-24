# -*- coding: utf-8 -*-
"""Point d'entrée de l'application Batikam Rénove."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme
from app.services.branding import resolve_logo_path


def main():
    """Lance l'application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Batikam Rénove")
    app.setOrganizationName("Batikam")

    logo_path = resolve_logo_path()
    if logo_path is not None and logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    # Theme global
    apply_theme(app)

    # Fenêtre principale
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
