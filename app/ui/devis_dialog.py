"""Dialogue de création / modification d'un devis."""
from __future__ import annotations

import tempfile
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from PySide6.QtCore import QDate, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    DatePicker,
    ComboBox,
    DoubleSpinBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    TextEdit,
)

from app.models.devis import Chantier, Client, Devis, Ligne, Lot
from app.services.branding import resolve_logo_str
from app.services.export_docx import DOCXExporter
from app.services.export_pdf import PDFExporter
from app.services.storage_sqlite import StorageSQLite
from app.ui.feedback import show_error, show_loading, show_success
from app.ui.ligne_dialog import LigneDialog
from app.ui.lot_dialog import LotDialog


_STATUTS = ["Brouillon", "Envoyé", "Accepté", "Refusé"]


class DevisDialog(QDialog):
    """Modal complète pour créer ou modifier un devis."""

    def __init__(
        self,
        storage: StorageSQLite,
        devis: Devis | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.storage = storage
        self._devis = deepcopy(devis) if devis else Devis()
        self._lots: list[Lot] = []
        self._lignes_directes: list[Ligne] = []
        self._saved = False

        is_new = self._devis.id is None
        self.setWindowTitle("Nouveau devis" if is_new else f"Devis {self._devis.numero}")
        self.setMinimumWidth(860)
        self.setMinimumHeight(720)
        self.setModal(True)

        self._build_ui()
        self._load()
        self._update_totals()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setSpacing(18)
        il.setContentsMargins(24, 24, 24, 20)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # ── En-tête ───────────────────────────────────────────────────────────
        header_box = QGroupBox("Informations générales")
        hf = QFormLayout(header_box)
        hf.setVerticalSpacing(14)
        hf.setHorizontalSpacing(18)

        num_statut_row = QHBoxLayout()
        self.numero_edit = LineEdit()
        self.numero_edit.setPlaceholderText("Auto — ex. 2026-0001")
        self.statut_combo = ComboBox()
        self.statut_combo.addItems(_STATUTS)
        self.statut_combo.setMinimumWidth(150)
        num_statut_row.addWidget(self.numero_edit, 2)
        num_statut_row.addWidget(QLabel("  Statut :"))
        num_statut_row.addWidget(self.statut_combo)
        hf.addRow("N° devis", num_statut_row)

        date_valid_row = QHBoxLayout()
        self.date_edit = DatePicker()
        self.date_edit.setDate(QDate.currentDate())
        self.validite_spin = SpinBox()
        self.validite_spin.setRange(1, 365)
        self.validite_spin.setValue(30)
        self.validite_spin.setSuffix(" jours")
        self.validite_spin.setMinimumWidth(130)
        date_valid_row.addWidget(self.date_edit)
        date_valid_row.addWidget(QLabel("  Validité :"))
        date_valid_row.addWidget(self.validite_spin)
        date_valid_row.addStretch()
        hf.addRow("Date", date_valid_row)

        self.affaire_edit = LineEdit()
        self.affaire_edit.setPlaceholderText("ex. Rénovation salle de bain — M. Dupont")
        hf.addRow("Nom affaire", self.affaire_edit)

        il.addWidget(header_box)

        # ── Client ────────────────────────────────────────────────────────────
        client_box = QGroupBox("Client")
        cf = QFormLayout(client_box)
        cf.setVerticalSpacing(14)
        cf.setHorizontalSpacing(18)

        self.client_nom_edit = LineEdit()
        self.client_nom_edit.setPlaceholderText("Nom ou raison sociale *")
        cf.addRow("Nom *", self.client_nom_edit)

        self.client_adresse_edit = LineEdit()
        cf.addRow("Adresse", self.client_adresse_edit)

        cp_ville_row = QHBoxLayout()
        self.client_cp_edit = LineEdit()
        self.client_cp_edit.setMaximumWidth(90)
        self.client_ville_edit = LineEdit()
        cp_ville_row.addWidget(self.client_cp_edit)
        cp_ville_row.addWidget(self.client_ville_edit, 1)
        cf.addRow("CP / Ville", cp_ville_row)

        self.client_tel_edit = LineEdit()
        self.client_email_edit = LineEdit()
        cf.addRow("Téléphone", self.client_tel_edit)
        cf.addRow("Email", self.client_email_edit)

        il.addWidget(client_box)

        # ── Mode de saisie ────────────────────────────────────────────────────
        mode_row = QHBoxLayout()
        mode_row.setSpacing(16)
        mode_lbl = QLabel("Mode de saisie :")
        self.radio_avec_lots = QRadioButton("Avec lots")
        self.radio_sans_lots = QRadioButton("Sans lots (lignes directes)")
        self.radio_avec_lots.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self.radio_avec_lots, 0)
        self._mode_group.addButton(self.radio_sans_lots, 1)
        mode_row.addWidget(mode_lbl)
        mode_row.addWidget(self.radio_avec_lots)
        mode_row.addWidget(self.radio_sans_lots)
        mode_row.addStretch()
        il.addLayout(mode_row)
        self.radio_avec_lots.toggled.connect(self._on_mode_changed)

        # ── Lots container ────────────────────────────────────────────────────
        self._lots_container = QWidget()
        lots_vl = QVBoxLayout(self._lots_container)
        lots_vl.setSpacing(8)
        lots_vl.setContentsMargins(0, 0, 0, 0)

        lots_header_row = QHBoxLayout()
        lots_lbl = QLabel("Prestations (lots)")
        lots_lbl.setProperty("variant", "title")
        btn_add_lot = PrimaryPushButton("+ Nouveau lot")
        btn_add_lot.clicked.connect(self._on_add_lot)
        lots_header_row.addWidget(lots_lbl)
        lots_header_row.addStretch()
        lots_header_row.addWidget(btn_add_lot)
        lots_vl.addLayout(lots_header_row)

        self.lots_table = QTableWidget(0, 3)
        self.lots_table.setHorizontalHeaderLabels(["Nom du lot", "Lignes", "Sous-total HT"])
        self.lots_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lots_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.lots_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lots_table.setAlternatingRowColors(False)
        self.lots_table.verticalHeader().setVisible(False)
        self.lots_table.verticalHeader().setDefaultSectionSize(48)
        self.lots_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.lots_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.lots_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.lots_table.setMinimumHeight(140)
        self.lots_table.itemDoubleClicked.connect(lambda _: self._on_edit_lot())
        lots_vl.addWidget(self.lots_table)

        lot_actions_row = QHBoxLayout()
        lot_actions_row.setSpacing(8)
        btn_edit_lot = PushButton("Modifier le lot")
        btn_edit_lot.clicked.connect(self._on_edit_lot)
        btn_del_lot = QPushButton("Supprimer le lot")
        btn_del_lot.setProperty("variant", "danger")
        btn_del_lot.clicked.connect(self._on_delete_lot)
        lot_actions_row.addStretch()
        lot_actions_row.addWidget(btn_edit_lot)
        lot_actions_row.addWidget(btn_del_lot)
        lots_vl.addLayout(lot_actions_row)

        il.addWidget(self._lots_container)

        # ── Lignes directes container (caché par défaut) ───────────────────────
        self._lignes_container = QWidget()
        self._lignes_container.setVisible(False)
        lignes_vl = QVBoxLayout(self._lignes_container)
        lignes_vl.setSpacing(8)
        lignes_vl.setContentsMargins(0, 0, 0, 0)

        lignes_header_row = QHBoxLayout()
        lignes_lbl = QLabel("Lignes de prestation")
        lignes_lbl.setProperty("variant", "title")
        btn_add_ligne = PrimaryPushButton("+ Ajouter une ligne")
        btn_add_ligne.clicked.connect(self._on_add_ligne_directe)
        lignes_header_row.addWidget(lignes_lbl)
        lignes_header_row.addStretch()
        lignes_header_row.addWidget(btn_add_ligne)
        lignes_vl.addLayout(lignes_header_row)

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
        self.lignes_table.setMinimumHeight(140)
        self.lignes_table.itemDoubleClicked.connect(lambda _: self._on_edit_ligne_directe())
        lignes_vl.addWidget(self.lignes_table)

        lignes_actions_row = QHBoxLayout()
        lignes_actions_row.setSpacing(8)
        btn_edit_ligne = PushButton("Modifier la ligne")
        btn_edit_ligne.clicked.connect(self._on_edit_ligne_directe)
        btn_del_ligne = QPushButton("Supprimer la ligne")
        btn_del_ligne.setProperty("variant", "danger")
        btn_del_ligne.clicked.connect(self._on_delete_ligne_directe)
        lignes_actions_row.addStretch()
        lignes_actions_row.addWidget(btn_edit_ligne)
        lignes_actions_row.addWidget(btn_del_ligne)
        lignes_vl.addLayout(lignes_actions_row)

        il.addWidget(self._lignes_container)

        # ── TVA + Totaux ──────────────────────────────────────────────────────
        totals_box = QGroupBox("TVA & Totaux")
        tl = QHBoxLayout(totals_box)
        tl.setSpacing(24)

        tva_col = QFormLayout()
        tva_col.setVerticalSpacing(8)
        tva_col.setHorizontalSpacing(12)
        self.tva_spin = DoubleSpinBox()
        self.tva_spin.setRange(0, 100)
        self.tva_spin.setDecimals(2)
        self.tva_spin.setSuffix(" %")
        self.tva_spin.setValue(20.0)
        self.tva_spin.setMaximumWidth(140)
        self.tva_spin.valueChanged.connect(self._update_totals)
        tva_col.addRow("TVA globale :", self.tva_spin)
        tl.addLayout(tva_col)
        tl.addStretch()

        recap_col = QFormLayout()
        recap_col.setVerticalSpacing(8)
        recap_col.setHorizontalSpacing(18)
        self.lbl_ht = QLabel("0,00 €")
        self.lbl_ht.setAlignment(Qt.AlignRight)
        self.lbl_tva_amt = QLabel("0,00 €")
        self.lbl_tva_amt.setAlignment(Qt.AlignRight)
        self.lbl_ttc = QLabel("0,00 €")
        self.lbl_ttc.setObjectName("KpiValue")
        self.lbl_ttc.setAlignment(Qt.AlignRight)
        recap_col.addRow("Total HT :", self.lbl_ht)
        recap_col.addRow("Montant TVA :", self.lbl_tva_amt)
        recap_col.addRow("Total TTC :", self.lbl_ttc)
        tl.addLayout(recap_col)

        il.addWidget(totals_box)

        # ── Conditions ────────────────────────────────────────────────────────
        cond_box = QGroupBox("Conditions")
        cf2 = QFormLayout(cond_box)
        cf2.setVerticalSpacing(14)
        cf2.setHorizontalSpacing(18)

        self.delais_edit = LineEdit()
        self.delais_edit.setPlaceholderText("ex. 4 semaines après acceptation")
        self.remarques_edit = TextEdit()
        self.remarques_edit.setPlaceholderText("Observations, conditions particulières…")
        self.remarques_edit.setMinimumHeight(90)

        cf2.addRow("Délais", self.delais_edit)
        cf2.addRow("Remarques", self.remarques_edit)
        il.addWidget(cond_box)

        il.addSpacerItem(QSpacerItem(0, 8))

        # ── Barre de boutons ──────────────────────────────────────────────────
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(24, 10, 24, 18)
        btn_bar.setSpacing(10)

        btn_cancel = PushButton("Annuler")
        btn_cancel.setMinimumHeight(42)
        btn_cancel.setMinimumWidth(110)
        btn_cancel.clicked.connect(self.reject)

        btn_preview = PushButton("Aperçu PDF")
        btn_preview.setMinimumHeight(42)
        btn_preview.clicked.connect(self._on_preview)

        btn_pdf = PushButton("Export PDF")
        btn_pdf.setObjectName("ExportPdfButton")
        btn_pdf.setMinimumHeight(42)
        btn_pdf.clicked.connect(self._on_export_pdf)

        btn_docx = PushButton("Export DOCX")
        btn_docx.setObjectName("ExportDocxButton")
        btn_docx.setMinimumHeight(42)
        btn_docx.clicked.connect(self._on_export_docx)

        self.btn_save = PrimaryPushButton("Enregistrer le devis")
        self.btn_save.setMinimumHeight(42)
        self.btn_save.setMinimumWidth(210)
        self.btn_save.clicked.connect(self._on_save)

        btn_bar.addWidget(btn_cancel)
        btn_bar.addStretch()
        btn_bar.addWidget(btn_preview)
        btn_bar.addWidget(btn_pdf)
        btn_bar.addWidget(btn_docx)
        btn_bar.addWidget(self.btn_save)
        root.addLayout(btn_bar)

    # ── Mode toggle ───────────────────────────────────────────────────────────

    def _on_mode_changed(self, checked: bool) -> None:
        avec_lots = self.radio_avec_lots.isChecked()
        self._lots_container.setVisible(avec_lots)
        self._lignes_container.setVisible(not avec_lots)
        self._update_totals()

    # ── Chargement ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        d = self._devis
        self.numero_edit.setText(d.numero or "")

        if d.date_devis:
            self.date_edit.setDate(QDate(d.date_devis.year, d.date_devis.month, d.date_devis.day))
        self.validite_spin.setValue(d.validite_jours or 30)

        idx = self.statut_combo.findText(d.statut or "Brouillon")
        if idx >= 0:
            self.statut_combo.setCurrentIndex(idx)

        affaire = (d.reference_affaire or d.chantier.adresse or "").strip()
        self.affaire_edit.setText(affaire)

        self.client_nom_edit.setText(d.client.nom)
        self.client_adresse_edit.setText(d.client.adresse)
        self.client_cp_edit.setText(d.client.code_postal)
        self.client_ville_edit.setText(d.client.ville)
        self.client_tel_edit.setText(d.client.telephone)
        self.client_email_edit.setText(d.client.email)

        self.tva_spin.setValue(float(d.tva_pourcent_global or 20))
        self.delais_edit.setText(d.delais or "")
        self.remarques_edit.setPlainText(d.remarques or "")

        # Mode: avec lots ou lignes directes
        utiliser_lots = d.utiliser_lots if d.utiliser_lots is not None else True
        self.radio_avec_lots.setChecked(utiliser_lots)
        self.radio_sans_lots.setChecked(not utiliser_lots)
        self._lots_container.setVisible(utiliser_lots)
        self._lignes_container.setVisible(not utiliser_lots)

        if utiliser_lots:
            self._lots = deepcopy(d.lots) if d.lots else [Lot(nom="")]
            self._refresh_lots()
        else:
            first_lot = d.lots[0] if d.lots else None
            self._lignes_directes = deepcopy(first_lot.lignes) if first_lot else []
            self._lots = []
            self._refresh_lignes_directes()

    # ── Lots ─────────────────────────────────────────────────────────────────

    def _refresh_lots(self) -> None:
        self.lots_table.setRowCount(len(self._lots))
        for i, lot in enumerate(self._lots):
            st = lot.calculer_sous_total_ht()

            nom_item = QTableWidgetItem(lot.nom or f"Lot {i + 1}")
            self.lots_table.setItem(i, 0, nom_item)

            nb_item = QTableWidgetItem(str(len(lot.lignes)))
            nb_item.setTextAlignment(Qt.AlignCenter)
            self.lots_table.setItem(i, 1, nb_item)

            total_item = QTableWidgetItem(self._fmt(st))
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.lots_table.setItem(i, 2, total_item)

        self._update_totals()

    def _selected_lot_index(self) -> int | None:
        row = self.lots_table.currentRow()
        return row if 0 <= row < len(self._lots) else None

    def _on_add_lot(self) -> None:
        dlg = LotDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._lots.append(dlg.get_lot())
            self._refresh_lots()

    def _on_edit_lot(self) -> None:
        idx = self._selected_lot_index()
        if idx is None:
            return
        dlg = LotDialog(lot=self._lots[idx], parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._lots[idx] = dlg.get_lot()
            self._refresh_lots()

    def _on_delete_lot(self) -> None:
        idx = self._selected_lot_index()
        if idx is None:
            return
        if len(self._lots) <= 1:
            self._lots[0] = Lot(nom="")
        else:
            del self._lots[idx]
        self._refresh_lots()

    # ── Lignes directes ───────────────────────────────────────────────────────

    def _refresh_lignes_directes(self) -> None:
        self.lignes_table.setRowCount(len(self._lignes_directes))
        for i, ligne in enumerate(self._lignes_directes):
            ht = ligne.calculer_total_ht()

            desc_item = QTableWidgetItem(ligne.designation or "—")
            self.lignes_table.setItem(i, 0, desc_item)

            unite_str = (
                "1 Forfait" if ligne.unite.lower() == "forfait"
                else f"{ligne.quantite} {ligne.unite}"
            )
            qty_item = QTableWidgetItem(unite_str)
            qty_item.setTextAlignment(Qt.AlignCenter)
            self.lignes_table.setItem(i, 1, qty_item)

            pu_item = QTableWidgetItem(f"{ligne.prix_unitaire_ht:.2f} €")
            pu_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.lignes_table.setItem(i, 2, pu_item)

            total_item = QTableWidgetItem(self._fmt(ht))
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.lignes_table.setItem(i, 3, total_item)

        self._update_totals()

    def _selected_ligne_index(self) -> int | None:
        row = self.lignes_table.currentRow()
        return row if 0 <= row < len(self._lignes_directes) else None

    def _on_add_ligne_directe(self) -> None:
        dlg = LigneDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._lignes_directes.append(dlg.get_ligne())
            self._refresh_lignes_directes()

    def _on_edit_ligne_directe(self) -> None:
        idx = self._selected_ligne_index()
        if idx is None:
            return
        dlg = LigneDialog(ligne=deepcopy(self._lignes_directes[idx]), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._lignes_directes[idx] = dlg.get_ligne()
            self._refresh_lignes_directes()

    def _on_delete_ligne_directe(self) -> None:
        idx = self._selected_ligne_index()
        if idx is None:
            return
        del self._lignes_directes[idx]
        self._refresh_lignes_directes()

    # ── Totaux ───────────────────────────────────────────────────────────────

    def _update_totals(self) -> None:
        try:
            if self.radio_avec_lots.isChecked():
                ht = sum(lot.calculer_sous_total_ht() for lot in self._lots)
            else:
                ht = sum(ligne.calculer_total_ht() for ligne in self._lignes_directes)
            tva_pct = Decimal(str(self.tva_spin.value()))
            tva_amt = ht * tva_pct / Decimal("100")
            ttc = ht + tva_amt
            self.lbl_ht.setText(self._fmt(ht))
            self.lbl_tva_amt.setText(self._fmt(tva_amt))
            self.lbl_ttc.setText(self._fmt(ttc))
        except (InvalidOperation, ValueError):
            pass

    @staticmethod
    def _fmt(v: Decimal) -> str:
        return f"{v:,.2f} €".replace(",", "\u202f").replace(".", ",")

    # ── Construction du Devis depuis l'UI ────────────────────────────────────

    def _build_devis(self) -> Devis:
        d = self._devis
        numero = self.numero_edit.text().strip()
        if numero:
            d.numero = numero

        qdate = self.date_edit.getDate()
        if qdate is None:
            qdate = QDate.currentDate()
        d.date_devis = date(qdate.year(), qdate.month(), qdate.day())
        d.validite_jours = self.validite_spin.value()
        d.statut = self.statut_combo.currentText()

        affaire = self.affaire_edit.text().strip()
        d.reference_affaire = affaire
        d.chantier = Chantier(adresse=affaire)

        d.client = Client(
            nom=self.client_nom_edit.text().strip(),
            adresse=self.client_adresse_edit.text().strip(),
            code_postal=self.client_cp_edit.text().strip(),
            ville=self.client_ville_edit.text().strip(),
            telephone=self.client_tel_edit.text().strip(),
            email=self.client_email_edit.text().strip(),
        )

        d.tva_pourcent_global = Decimal(str(self.tva_spin.value()))

        if self.radio_avec_lots.isChecked():
            d.utiliser_lots = True
            d.lots = deepcopy(self._lots)
        else:
            d.utiliser_lots = False
            d.lots = [Lot(nom="Prestations", lignes=deepcopy(self._lignes_directes))]

        d.delais = self.delais_edit.text().strip()
        d.remarques = self.remarques_edit.toPlainText().strip()
        return d

    def _check_client(self) -> bool:
        if not self.client_nom_edit.text().strip():
            show_error(self, "Client requis", "Le nom du client est obligatoire.")
            return False
        return True

    # ── Aperçu / Export ───────────────────────────────────────────────────────

    def _on_preview(self) -> None:
        if not self._check_client():
            return
        devis = self._build_devis()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        loading = show_loading(self, "Aperçu PDF", "Génération en cours…")
        try:
            PDFExporter(logo_path=resolve_logo_str()).export(devis, tmp.name)
            loading.close()
            QDesktopServices.openUrl(QUrl.fromLocalFile(tmp.name))
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Aperçu impossible :\n{exc}")

    def _on_export_pdf(self) -> None:
        if not self._check_client():
            return
        devis = self._build_devis()
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", f"devis_{devis.numero or 'nouveau'}.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return
        loading = show_loading(self, "Export PDF", "Export en cours…")
        try:
            PDFExporter(logo_path=resolve_logo_str()).export(devis, path)
            loading.close()
            show_success(self, "Succès", f"PDF exporté :\n{path}")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Export PDF impossible :\n{exc}")

    def _on_export_docx(self) -> None:
        if not self._check_client():
            return
        devis = self._build_devis()
        path, _ = QFileDialog.getSaveFileName(
            self, "Export DOCX", f"devis_{devis.numero or 'nouveau'}.docx", "DOCX Files (*.docx)"
        )
        if not path:
            return
        loading = show_loading(self, "Export DOCX", "Export en cours…")
        try:
            DOCXExporter().export(devis, path)
            loading.close()
            show_success(self, "Succès", f"DOCX exporté :\n{path}")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Export DOCX impossible :\n{exc}")

    # ── Sauvegarde ───────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        if not self._check_client():
            return
        devis = self._build_devis()
        try:
            if devis.id is None:
                self._devis = self.storage.create(devis)
            else:
                self._devis = self.storage.update(devis)
            self._saved = True
            self.accept()
        except Exception as exc:
            show_error(self, "Erreur", f"Impossible d'enregistrer le devis :\n{exc}")

    # ── Accesseurs publics ────────────────────────────────────────────────────

    def get_devis(self) -> Devis:
        """Retourne le devis sauvegardé après accept()."""
        return self._devis

    def was_saved(self) -> bool:
        return self._saved
