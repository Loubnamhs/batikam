"""Dialogue de création / modification d'un lot et de ses lignes."""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from qfluentwidgets import LineEdit, PrimaryPushButton, PushButton

from app.models.devis import Ligne, Lot
from app.ui.ligne_dialog import LigneDialog


class LotDialog(QDialog):
    """Popup pour créer ou modifier un lot et ses lignes de prestation."""

    def __init__(self, lot: Lot | None = None, parent=None) -> None:
        super().__init__(parent)
        is_new = lot is None
        self.setWindowTitle("Nouveau lot" if is_new else "Modifier le lot")
        self.setMinimumWidth(720)
        self.setMinimumHeight(540)
        self.setModal(True)
        self._lot = deepcopy(lot) if lot else Lot(nom="")
        self._build_ui()
        self._refresh_lignes()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(24, 24, 24, 24)

        # Nom du lot
        form = QFormLayout()
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(18)
        self.nom_edit = LineEdit()
        self.nom_edit.setText(self._lot.nom)
        self.nom_edit.setPlaceholderText("ex. Maçonnerie, Peinture, Électricité…")
        form.addRow("Nom du lot", self.nom_edit)
        root.addLayout(form)

        # Lignes
        grp = QGroupBox("Lignes de prestation")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setSpacing(8)
        grp_layout.setContentsMargins(12, 14, 12, 12)

        self.lignes_table = QTableWidget(0, 4)
        self.lignes_table.setHorizontalHeaderLabels(["Description", "Qté / Unité", "PU HT", "Total HT"])
        self.lignes_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lignes_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.lignes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lignes_table.setAlternatingRowColors(False)
        self.lignes_table.verticalHeader().setVisible(False)
        self.lignes_table.verticalHeader().setDefaultSectionSize(52)
        self.lignes_table.setWordWrap(True)
        self.lignes_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.lignes_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.lignes_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.lignes_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.lignes_table.itemDoubleClicked.connect(self._on_edit_ligne)
        grp_layout.addWidget(self.lignes_table, 1)

        # Actions lignes
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_add = PrimaryPushButton("+ Ajouter une ligne")
        btn_add.clicked.connect(self._on_add_ligne)
        self.btn_edit_ligne = PushButton("Modifier")
        self.btn_edit_ligne.clicked.connect(self._on_edit_ligne)
        self.btn_del_ligne = QPushButton("Supprimer")
        self.btn_del_ligne.setProperty("variant", "danger")
        self.btn_del_ligne.clicked.connect(self._on_delete_ligne)
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_edit_ligne)
        btn_row.addWidget(self.btn_del_ligne)
        grp_layout.addLayout(btn_row)

        # Sous-total
        self.lbl_sous_total = QLabel("Sous-total HT : 0,00 €")
        self.lbl_sous_total.setObjectName("KpiValue")
        self.lbl_sous_total.setAlignment(Qt.AlignRight)
        grp_layout.addWidget(self.lbl_sous_total)

        root.addWidget(grp, 1)

        # Boutons OK / Annuler
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)
        btn_bar.addStretch()
        btn_cancel = PushButton("Annuler")
        btn_cancel.setMinimumWidth(110)
        btn_cancel.clicked.connect(self.reject)
        btn_ok = PrimaryPushButton("Valider le lot")
        btn_ok.setMinimumWidth(150)
        btn_ok.clicked.connect(self._on_accept)
        btn_bar.addWidget(btn_cancel)
        btn_bar.addWidget(btn_ok)
        root.addLayout(btn_bar)

    # ── Données ───────────────────────────────────────────────────────────────

    def _refresh_lignes(self) -> None:
        self.lignes_table.setRowCount(len(self._lot.lignes))
        for i, ligne in enumerate(self._lot.lignes):
            ht = ligne.calculer_total_ht()

            desc_item = QTableWidgetItem(ligne.designation or "—")
            self.lignes_table.setItem(i, 0, desc_item)

            unite_str = "1 Forfait" if ligne.unite.lower() == "forfait" else f"{ligne.quantite} {ligne.unite}"
            qty_item = QTableWidgetItem(unite_str)
            qty_item.setTextAlignment(Qt.AlignCenter)
            self.lignes_table.setItem(i, 1, qty_item)

            pu_item = QTableWidgetItem(f"{ligne.prix_unitaire_ht:.2f} €")
            pu_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.lignes_table.setItem(i, 2, pu_item)

            total_item = QTableWidgetItem(self._fmt(ht))
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.lignes_table.setItem(i, 3, total_item)

        st = self._lot.calculer_sous_total_ht()
        self.lbl_sous_total.setText(f"Sous-total HT : {self._fmt(st)}")

    @staticmethod
    def _fmt(v) -> str:
        from decimal import Decimal
        return f"{v:,.2f} €".replace(",", "\u202f").replace(".", ",")

    def _selected_index(self) -> int | None:
        row = self.lignes_table.currentRow()
        return row if 0 <= row < len(self._lot.lignes) else None

    # ── Actions lignes ────────────────────────────────────────────────────────

    def _on_add_ligne(self) -> None:
        dlg = LigneDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._lot.lignes.append(dlg.get_ligne())
            self._refresh_lignes()

    def _on_edit_ligne(self, _=None) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        dlg = LigneDialog(ligne=deepcopy(self._lot.lignes[idx]), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._lot.lignes[idx] = dlg.get_ligne()
            self._refresh_lignes()

    def _on_delete_ligne(self) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        del self._lot.lignes[idx]
        self._refresh_lignes()

    # ── Validation ────────────────────────────────────────────────────────────

    def _on_accept(self) -> None:
        self._lot.nom = self.nom_edit.text().strip()
        self.accept()

    def get_lot(self) -> Lot:
        """Retourne le lot avec les valeurs saisies."""
        self._lot.nom = self.nom_edit.text().strip()
        return deepcopy(self._lot)
