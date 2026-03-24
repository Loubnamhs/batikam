# -*- coding: utf-8 -*-
"""Small status popups with logo footer."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.branding import resolve_logo_path


class StatusPopup(QDialog):
    def __init__(self, parent: QWidget, kind: str, title: str, message: str):
        super().__init__(parent)
        self.setObjectName("StatusPopup")
        self.setWindowTitle(title)
        self.setModal(kind != "loading")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(360)
        self.setStyleSheet(
            """
            #StatusPopup { background: #FFFFFF; color: #111827; border: 1px solid #E5E7EB; border-radius: 14px; }
            #StatusTitle { color: #111827; font-size: 15px; font-weight: 700; }
            #StatusMessage { color: #4B5563; }
            #StatusPowered { color: #9CA3AF; font-size: 11px; }
            #StatusProgress { border: 1px solid #E5E7EB; border-radius: 8px; background: #F3F4F6; }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("StatusTitle")
        root.addWidget(title_label)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setObjectName("StatusMessage")
        root.addWidget(message_label)

        if kind == "loading":
            bar = QProgressBar()
            bar.setRange(0, 0)
            bar.setObjectName("StatusProgress")
            root.addWidget(bar)
        else:
            actions = QHBoxLayout()
            actions.addStretch()
            ok_btn = QPushButton("OK")
            ok_btn.clicked.connect(self.accept)
            actions.addWidget(ok_btn)
            root.addLayout(actions)

        footer = QFrame()
        footer.setObjectName("StatusFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 6, 0, 0)
        footer_layout.setSpacing(8)
        footer_layout.addStretch()
        powered = QLabel("Powered by")
        powered.setObjectName("StatusPowered")
        footer_layout.addWidget(powered)

        logo_label = QLabel()
        logo_label.setObjectName("StatusLogo")
        logo_path = resolve_logo_path()
        if logo_path:
            pixmap = QPixmap(str(logo_path)).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        footer_layout.addWidget(logo_label)
        root.addWidget(footer)


def show_loading(parent: QWidget, title: str, message: str) -> StatusPopup:
    popup = StatusPopup(parent, "loading", title, message)
    popup.show()
    QApplication.processEvents()
    return popup


def show_success(parent: QWidget, title: str, message: str) -> None:
    popup = StatusPopup(parent, "success", title, message)
    popup.exec()


def show_error(parent: QWidget, title: str, message: str) -> None:
    popup = StatusPopup(parent, "error", title, message)
    popup.exec()


def show_confirm(parent: QWidget, title: str, message: str) -> bool:
    dialog = QDialog(parent)
    dialog.setObjectName("StatusPopup")
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    dialog.setMinimumWidth(380)
    dialog.setStyleSheet(
        """
        #StatusPopup { background: #FFFFFF; color: #111827; border: 1px solid #E5E7EB; border-radius: 14px; }
        """
    )
    root = QVBoxLayout(dialog)
    root.setContentsMargins(18, 16, 18, 14)
    title_label = QLabel(title)
    title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #111827;")
    msg = QLabel(message)
    msg.setWordWrap(True)
    msg.setStyleSheet("color: #4B5563;")
    root.addWidget(title_label)
    root.addWidget(msg)
    actions = QHBoxLayout()
    actions.addStretch()
    no_btn = QPushButton("Annuler")
    yes_btn = QPushButton("Confirmer")
    yes_btn.setProperty("variant", "primary")
    no_btn.clicked.connect(dialog.reject)
    yes_btn.clicked.connect(dialog.accept)
    actions.addWidget(no_btn)
    actions.addWidget(yes_btn)
    root.addLayout(actions)
    return dialog.exec() == QDialog.Accepted
