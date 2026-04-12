"""Dialogue d'ajout d'une dépense sur une facture."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
)

from qfluentwidgets import ComboBox, DoubleSpinBox, LineEdit, PrimaryPushButton, PushButton, TextEdit


_CATEGORIES = ["Salaire", "Fourniture", "Produit", "Matérielle", "Main oeuvre", "Carburant", "Autre"]


class DepenseDialog(QDialog):
    """Popup pour saisir une dépense liée à une facture."""

    def __init__(
        self,
        client_nom: str = "",
        projet: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ajouter une dépense")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._client_nom = client_nom
        self._projet = projet
        self._build_ui()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setVerticalSpacing(14)
        form.setHorizontalSpacing(18)

        self.client_edit = LineEdit()
        self.client_edit.setText(self._client_nom)
        form.addRow("Client", self.client_edit)

        self.projet_edit = LineEdit()
        self.projet_edit.setText(self._projet)
        form.addRow("Projet", self.projet_edit)

        self.cat_combo = ComboBox()
        self.cat_combo.addItems(_CATEGORIES)
        form.addRow("Catégorie", self.cat_combo)

        self.montant_spin = DoubleSpinBox()
        self.montant_spin.setRange(0, 10_000_000)
        self.montant_spin.setDecimals(2)
        self.montant_spin.setSuffix(" €")
        form.addRow("Montant", self.montant_spin)

        self.notes_edit = TextEdit()
        self.notes_edit.setPlaceholderText("Détails, références, observations…")
        self.notes_edit.setMaximumHeight(100)
        form.addRow("Notes", self.notes_edit)

        root.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        btn_cancel = PushButton("Annuler")
        btn_cancel.setMinimumWidth(110)
        btn_cancel.clicked.connect(self.reject)
        btn_ok = PrimaryPushButton("Ajouter la dépense")
        btn_ok.setMinimumWidth(160)
        btn_ok.clicked.connect(self._on_accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    # ── Validation ────────────────────────────────────────────────────────────

    def _on_accept(self) -> None:
        from app.ui.feedback import show_error
        if not self.client_edit.text().strip():
            show_error(self, "Champ requis", "Le client est obligatoire.")
            return
        if not self.projet_edit.text().strip():
            show_error(self, "Champ requis", "Le projet est obligatoire.")
            return
        self.accept()

    # ── Résultat ─────────────────────────────────────────────────────────────

    def get_data(self) -> dict:
        return {
            "client_nom": self.client_edit.text().strip(),
            "projet": self.projet_edit.text().strip(),
            "categorie": self.cat_combo.currentText(),
            "montant": Decimal(str(self.montant_spin.value())),
            "notes": self.notes_edit.toPlainText().strip(),
        }
