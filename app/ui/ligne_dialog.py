"""Dialogue de saisie / modification d'une ligne de prestation."""
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from qfluentwidgets import ComboBox, DoubleSpinBox, PrimaryPushButton, PushButton, TextEdit

from app.models.devis import Ligne


class LigneDialog(QDialog):
    """Popup confortable pour créer ou modifier une ligne de prestation."""

    UNITES = ["U", "m²", "m", "ml", "Forfait"]

    def __init__(self, ligne: Ligne | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ajouter une ligne" if ligne is None else "Modifier la ligne")
        self.setMinimumWidth(620)
        self.setModal(True)
        self._source = ligne or Ligne()
        self._build_ui()
        self._load(self._source)
        self._update_total()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(24, 24, 24, 24)

        # ── Formulaire principal ─────────────────────────────────────────────
        form = QFormLayout()
        form.setVerticalSpacing(14)
        form.setHorizontalSpacing(18)

        self.designation_edit = TextEdit()
        self.designation_edit.setPlaceholderText("Description détaillée de la prestation…")
        self.designation_edit.setMinimumHeight(80)
        self.designation_edit.setMaximumHeight(420)
        self.designation_edit.textChanged.connect(self._auto_resize_text)
        self.designation_edit.textChanged.connect(self._update_total)
        form.addRow("Description *", self.designation_edit)

        unite_row = QHBoxLayout()
        self.unite_combo = ComboBox()
        self.unite_combo.addItems(self.UNITES)
        self.unite_combo.setMinimumWidth(130)
        self.unite_combo.currentTextChanged.connect(self._on_unite_changed)
        unite_row.addWidget(self.unite_combo)
        unite_row.addStretch()
        form.addRow("Unité", unite_row)

        self.qte_spin = DoubleSpinBox()
        self.qte_spin.setRange(0, 9_999_999)
        self.qte_spin.setDecimals(3)
        self.qte_spin.setSingleStep(1)
        self.qte_spin.setValue(1)
        self.qte_spin.setMinimumWidth(160)
        self.qte_spin.valueChanged.connect(self._update_total)
        form.addRow("Quantité", self.qte_spin)

        self.pu_spin = DoubleSpinBox()
        self.pu_spin.setRange(0, 9_999_999)
        self.pu_spin.setDecimals(2)
        self.pu_spin.setSuffix(" €")
        self.pu_spin.setMinimumWidth(160)
        self.pu_spin.valueChanged.connect(self._update_total)
        form.addRow("Prix unitaire HT", self.pu_spin)

        self.remise_spin = DoubleSpinBox()
        self.remise_spin.setRange(0, 100)
        self.remise_spin.setDecimals(2)
        self.remise_spin.setSuffix(" %")
        self.remise_spin.setMinimumWidth(160)
        self.remise_spin.valueChanged.connect(self._update_total)
        form.addRow("Remise", self.remise_spin)

        self.tva_spin = DoubleSpinBox()
        self.tva_spin.setRange(0, 100)
        self.tva_spin.setDecimals(2)
        self.tva_spin.setSuffix(" %")
        self.tva_spin.setValue(20)
        self.tva_spin.setMinimumWidth(160)
        self.tva_spin.valueChanged.connect(self._update_total)
        form.addRow("TVA", self.tva_spin)

        root.addLayout(form)

        # ── Récapitulatif live ───────────────────────────────────────────────
        recap = QGroupBox("Récapitulatif")
        recap_form = QFormLayout(recap)
        recap_form.setVerticalSpacing(8)
        recap_form.setHorizontalSpacing(18)

        self.label_ht = QLabel("0,00 €")
        self.label_ht.setObjectName("KpiValue")
        self.label_ht.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.label_tva_amt = QLabel("0,00 €")
        self.label_tva_amt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.label_ttc = QLabel("0,00 €")
        self.label_ttc.setObjectName("KpiValue")
        self.label_ttc.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        recap_form.addRow("Total HT :", self.label_ht)
        recap_form.addRow("Montant TVA :", self.label_tva_amt)
        recap_form.addRow("Total TTC :", self.label_ttc)
        root.addWidget(recap)

        # ── Boutons ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        btn_cancel = PushButton("Annuler")
        btn_cancel.setMinimumWidth(110)
        btn_cancel.clicked.connect(self.reject)
        btn_ok = PrimaryPushButton("Valider")
        btn_ok.setMinimumWidth(130)
        btn_ok.clicked.connect(self._on_accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    # ── Logique ──────────────────────────────────────────────────────────────

    def _auto_resize_text(self) -> None:
        doc = self.designation_edit.document()
        doc.setTextWidth(self.designation_edit.viewport().width())
        h = int(doc.size().height()) + 24
        h = max(80, min(h, 420))
        if self.designation_edit.height() != h:
            self.designation_edit.setFixedHeight(h)
            self.adjustSize()

    def _on_unite_changed(self, unite: str) -> None:
        is_forfait = unite.lower() == "forfait"
        self.qte_spin.setEnabled(not is_forfait)
        if is_forfait:
            self.qte_spin.setValue(1)
        self._update_total()

    def _update_total(self) -> None:
        try:
            unite = self.unite_combo.currentText()
            qte = Decimal("1") if unite.lower() == "forfait" else Decimal(str(self.qte_spin.value()))
            pu = Decimal(str(self.pu_spin.value()))
            remise = Decimal(str(self.remise_spin.value()))
            tva_pct = Decimal(str(self.tva_spin.value()))
            ht = qte * pu * (Decimal("1") - remise / Decimal("100"))
            tva_amt = ht * tva_pct / Decimal("100")
            ttc = ht + tva_amt
            self.label_ht.setText(f"{ht:,.2f} €".replace(",", " ").replace(".", ","))
            self.label_tva_amt.setText(f"{tva_amt:,.2f} €".replace(",", " ").replace(".", ","))
            self.label_ttc.setText(f"{ttc:,.2f} €".replace(",", " ").replace(".", ","))
        except (InvalidOperation, ValueError):
            pass

    def _load(self, ligne: Ligne) -> None:
        self.designation_edit.setPlainText(ligne.designation)
        idx = self.unite_combo.findText(ligne.unite)
        if idx >= 0:
            self.unite_combo.setCurrentIndex(idx)
        self.qte_spin.setValue(float(ligne.quantite))
        self.pu_spin.setValue(float(ligne.prix_unitaire_ht))
        self.remise_spin.setValue(float(ligne.remise_pourcent))
        self.tva_spin.setValue(float(ligne.tva_pourcent))

    def _on_accept(self) -> None:
        if not self.designation_edit.toPlainText().strip():
            from app.ui.feedback import show_error
            show_error(self, "Champ requis", "La description de la ligne est obligatoire.")
            return
        self.accept()

    # ── Résultat ─────────────────────────────────────────────────────────────

    def get_ligne(self) -> Ligne:
        """Retourne la Ligne avec les valeurs saisies dans le dialogue."""
        unite = self.unite_combo.currentText()
        return Ligne(
            designation=self.designation_edit.toPlainText().strip(),
            unite=unite,
            quantite=Decimal("1") if unite.lower() == "forfait" else Decimal(str(self.qte_spin.value())),
            mesure=Decimal("1"),
            prix_unitaire_ht=Decimal(str(self.pu_spin.value())),
            remise_pourcent=Decimal(str(self.remise_spin.value())),
            tva_pourcent=Decimal(str(self.tva_spin.value())),
        )
