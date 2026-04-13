# -*- coding: utf-8 -*-
"""Splash screen non-bloquant style Discord — card flottante sans fond sombre."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap, QPainterPath, QBrush
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication


class _Dots(QWidget):
    """Trois points animés façon chargement Discord."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(48, 14)
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(380)

    def _tick(self) -> None:
        self._phase = (self._phase + 1) % 3
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = 5
        gap = 11
        for i in range(3):
            alpha = 220 if i == self._phase else 70
            p.setBrush(QBrush(QColor(179, 186, 193, alpha)))   # #B3BAC1
            p.setPen(Qt.NoPen)
            cx = r + i * (r * 2 + gap)
            p.drawEllipse(cx - r, 2, r * 2, r * 2)
        p.end()


class SplashScreen(QWidget):
    """
    Card centrée à l'écran, fond #2B2D31, coins arrondis.
    Non-bloquant : pas de fond sombre, fenêtre déplaçable, fermable.
    """

    CARD_W = 340
    CARD_H = 290

    def __init__(self, logo_path: str | None = None) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool              # n'apparaît pas dans la barre des tâches
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedSize(self.CARD_W, self.CARD_H)

        self._logo_path = logo_path
        self._drag_pos = None
        self._build_ui()
        self._center_on_screen()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 36, 32, 28)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignHCenter)

        # Logo
        if self._logo_path:
            px = QPixmap(self._logo_path)
            if not px.isNull():
                px = px.scaledToHeight(70, Qt.SmoothTransformation)
                lbl_logo = QLabel()
                lbl_logo.setPixmap(px)
                lbl_logo.setAlignment(Qt.AlignHCenter)
                lbl_logo.setStyleSheet("background: transparent;")
                layout.addWidget(lbl_logo)

        layout.addSpacing(18)

        # Titre
        lbl_title = QLabel("Batikam Rénove")
        lbl_title.setAlignment(Qt.AlignHCenter)
        lbl_title.setStyleSheet(
            "color:#FFFFFF; font-size:17px; font-weight:700;"
            "font-family:'Segoe UI',sans-serif; background:transparent;"
        )
        layout.addWidget(lbl_title)

        layout.addSpacing(8)

        # Statut (mis à jour dynamiquement)
        self._lbl_status = QLabel("Veuillez patienter…")
        self._lbl_status.setAlignment(Qt.AlignHCenter)
        self._lbl_status.setStyleSheet(
            "color:#B5BAC1; font-size:12px;"
            "font-family:'Segoe UI',sans-serif; background:transparent;"
        )
        layout.addWidget(self._lbl_status)

        layout.addSpacing(22)

        # Points animés centrés
        dots_wrap = QWidget()
        dots_wrap.setStyleSheet("background:transparent;")
        dw_layout = QVBoxLayout(dots_wrap)
        dw_layout.setContentsMargins(0, 0, 0, 0)
        dw_layout.setAlignment(Qt.AlignHCenter)
        dw_layout.addWidget(_Dots())
        layout.addWidget(dots_wrap)

        layout.addStretch()

        # Hint fermeture
        lbl_hint = QLabel("Cliquez pour fermer")
        lbl_hint.setAlignment(Qt.AlignHCenter)
        lbl_hint.setStyleSheet(
            "color:#4E5058; font-size:10px;"
            "font-family:'Segoe UI',sans-serif; background:transparent;"
        )
        layout.addWidget(lbl_hint)

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.x() + (screen.width()  - self.CARD_W) // 2,
            screen.y() + (screen.height() - self.CARD_H) // 2,
        )

    # ── Rendu — card arrondie ─────────────────────────────────────────────────

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.CARD_W, self.CARD_H, 16, 16)
        p.fillPath(path, QColor("#2B2D31"))
        p.end()

    # ── Drag pour déplacer la card ────────────────────────────────────────────

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e) -> None:
        if self._drag_pos and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e) -> None:
        self._drag_pos = None

    # ── API publique ──────────────────────────────────────────────────────────

    def set_status(self, text: str) -> None:
        self._lbl_status.setText(text)
        QApplication.processEvents()

    def finish(self, window: QWidget) -> None:  # noqa: ARG002
        self.close()
