# -*- coding: utf-8 -*-
"""Theme helpers and QSS loader for Batikam Renove UI."""

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QFrame, QWidget

from app.services.paths import resolve_resource_path


def _theme_path() -> Path:
    return resolve_resource_path("app", "ui", "theme.qss")


def apply_theme(target: QWidget | QApplication) -> None:
    """Apply global theme: palette, font, and QSS."""
    app = target if isinstance(target, QApplication) else QApplication.instance()
    if app is None:
        return

    app.setStyle("Fusion")
    app.setFont(QFont("Helvetica Neue", 10))

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#F4F6FB"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F8FAFC"))
    palette.setColor(QPalette.Text, QColor("#0F172A"))
    palette.setColor(QPalette.WindowText, QColor("#0F172A"))
    palette.setColor(QPalette.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ButtonText, QColor("#0F172A"))
    palette.setColor(QPalette.Highlight, QColor("#1F6FEB"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)

    qss_path = _theme_path()
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def make_card(object_name: str = "Card") -> QFrame:
    """Create a reusable card container with object name for QSS targeting."""
    frame = QFrame()
    frame.setObjectName(object_name)
    return frame


def add_shadow(widget: QWidget, blur: int = 28, y_offset: int = 6, color: str = "#00000022") -> None:
    """Add a subtle drop shadow to a widget."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setXOffset(0)
    shadow.setYOffset(y_offset)
    shadow.setColor(QColor(color))
    widget.setGraphicsEffect(shadow)
