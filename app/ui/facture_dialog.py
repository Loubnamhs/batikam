"""Dialogue de création / modification d'une facture indépendante."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from PySide6.QtCore import QDate, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QAbstractItemView,
    QButtonGroup,
    QDialog,
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
    TextEdit,
)

from app.models.devis import Chantier, Client, Devis, Ligne, Lot
from app.services.branding import resolve_logo_str
from app.services.export_docx import DOCXExporter
from app.services.export_pdf import PDFExporter
from app.services.storage_sqlite import StorageSQLite
from app.ui.client_dialog import ClientDialog
from app.ui.feedback import show_error, show_loading, show_success
from app.ui.ligne_dialog import LigneDialog
from app.ui.lot_dialog import LotDialog


_STATUTS = ["Brouillon", "Envoyée", "Validée", "Payée", "Annulée"]


class FactureDialog(QDialog):
    """Dialogue complet pour créer ou modifier une facture, indépendant du devis."""

    def __init__(
        self,
        storage: StorageSQLite,
        facture_id: int | None = None,
        preselect_client_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.storage = storage
        self.facture_id = facture_id
        self._lots: list[Lot] = []
        self._lignes_directes: list[Ligne] = []

        is_new = facture_id is None
        self.setWindowTitle("Nouvelle facture" if is_new else "Modifier la facture")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.setModal(True)

        self._build_ui()
        self._load_clients(preselect_client_id)

        if not is_new:
            self._load_facture(facture_id)
        else:
            self._lots = [Lot(nom="")]
            self._refresh_lots()

        self._update_totals()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Zone scrollable principale
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(18)
        inner_layout.setContentsMargins(24, 24, 24, 20)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # ── Informations générales ────────────────────────────────────────────
        header_box = QGroupBox("Informations générales")
        header_form = QFormLayout(header_box)
        header_form.setVerticalSpacing(14)
        header_form.setHorizontalSpacing(18)

        client_row = QHBoxLayout()
        self.client_combo = ComboBox()
        self.client_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_new_client = PushButton("+ Nouveau client")
        btn_new_client.clicked.connect(self._on_new_client)
        client_row.addWidget(self.client_combo, 1)
        client_row.addWidget(btn_new_client)
        header_form.addRow("Client *", client_row)

        self.affaire_edit = LineEdit()
        self.affaire_edit.setPlaceholderText("ex. Rénovation cuisine, Extension terrasse…")
        header_form.addRow("Affaire / Projet", self.affaire_edit)

        date_statut_row = QHBoxLayout()
        self.date_edit = DatePicker()
        self.date_edit.setDate(QDate.currentDate())
        self.statut_combo = ComboBox()
        self.statut_combo.addItems(_STATUTS)
        date_statut_row.addWidget(self.date_edit)
        date_statut_row.addWidget(QLabel("  Statut :"))
        date_statut_row.addWidget(self.statut_combo)
        date_statut_row.addStretch()
        header_form.addRow("Date", date_statut_row)

        self.tva_spin = DoubleSpinBox()
        self.tva_spin.setRange(0, 100)
        self.tva_spin.setDecimals(2)
        self.tva_spin.setSuffix(" %")
        self.tva_spin.setValue(20)
        self.tva_spin.setMaximumWidth(140)
        self.tva_spin.valueChanged.connect(self._update_totals)
        header_form.addRow("TVA globale", self.tva_spin)

        inner_layout.addWidget(header_box)

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
        inner_layout.addLayout(mode_row)
        self.radio_avec_lots.toggled.connect(self._on_mode_changed)

        # ── Lots container ────────────────────────────────────────────────────
        self._lots_container = QWidget()
        lots_vl = QVBoxLayout(self._lots_container)
        lots_vl.setSpacing(8)
        lots_vl.setContentsMargins(0, 0, 0, 0)

        lots_header = QHBoxLayout()
        lots_lbl = QLabel("Prestations (lots)")
        lots_lbl.setProperty("variant", "title")
        btn_add_lot = PrimaryPushButton("+ Nouveau lot")
        btn_add_lot.clicked.connect(self._on_add_lot)
        lots_header.addWidget(lots_lbl)
        lots_header.addStretch()
        lots_header.addWidget(btn_add_lot)
        lots_vl.addLayout(lots_header)

        self.lots_table = QTableWidget(0, 3)
        self.lots_table.setHorizontalHeaderLabels(["Nom du lot", "Nb lignes", "Sous-total HT"])
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

        lot_actions = QHBoxLayout()
        lot_actions.setSpacing(8)
        btn_edit_lot = PushButton("Modifier le lot")
        btn_edit_lot.clicked.connect(self._on_edit_lot)
        self.btn_del_lot = QPushButton("Supprimer le lot")
        self.btn_del_lot.setProperty("variant", "danger")
        self.btn_del_lot.clicked.connect(self._on_delete_lot)
        lot_actions.addStretch()
        lot_actions.addWidget(btn_edit_lot)
        lot_actions.addWidget(self.btn_del_lot)
        lots_vl.addLayout(lot_actions)

        inner_layout.addWidget(self._lots_container)

        # ── Lignes directes container (caché par défaut) ───────────────────────
        self._lignes_container = QWidget()
        self._lignes_container.setVisible(False)
        lignes_vl = QVBoxLayout(self._lignes_container)
        lignes_vl.setSpacing(8)
        lignes_vl.setContentsMargins(0, 0, 0, 0)

        lignes_header = QHBoxLayout()
        lignes_lbl = QLabel("Lignes de prestation")
        lignes_lbl.setProperty("variant", "title")
        btn_add_ligne = PrimaryPushButton("+ Ajouter une ligne")
        btn_add_ligne.clicked.connect(self._on_add_ligne_directe)
        lignes_header.addWidget(lignes_lbl)
        lignes_header.addStretch()
        lignes_header.addWidget(btn_add_ligne)
        lignes_vl.addLayout(lignes_header)

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

        lignes_actions = QHBoxLayout()
        lignes_actions.setSpacing(8)
        btn_edit_ligne = PushButton("Modifier la ligne")
        btn_edit_ligne.clicked.connect(self._on_edit_ligne_directe)
        btn_del_ligne = QPushButton("Supprimer la ligne")
        btn_del_ligne.setProperty("variant", "danger")
        btn_del_ligne.clicked.connect(self._on_delete_ligne_directe)
        lignes_actions.addStretch()
        lignes_actions.addWidget(btn_edit_ligne)
        lignes_actions.addWidget(btn_del_ligne)
        lignes_vl.addLayout(lignes_actions)

        inner_layout.addWidget(self._lignes_container)

        # ── Totaux ───────────────────────────────────────────────────────────
        totals_box = QGroupBox("Totaux")
        totals_form = QFormLayout(totals_box)
        totals_form.setVerticalSpacing(8)
        totals_form.setHorizontalSpacing(18)

        self.lbl_ht = QLabel("0,00 €")
        self.lbl_ht.setAlignment(Qt.AlignRight)
        self.lbl_tva = QLabel("0,00 €")
        self.lbl_tva.setAlignment(Qt.AlignRight)
        self.lbl_ttc = QLabel("0,00 €")
        self.lbl_ttc.setObjectName("KpiValue")
        self.lbl_ttc.setAlignment(Qt.AlignRight)

        totals_form.addRow("Total HT :", self.lbl_ht)
        totals_form.addRow("TVA :", self.lbl_tva)
        totals_form.addRow("Total TTC :", self.lbl_ttc)
        inner_layout.addWidget(totals_box)

        # ── Notes ────────────────────────────────────────────────────────────
        notes_box = QGroupBox("Notes / Remarques")
        notes_layout = QVBoxLayout(notes_box)
        self.notes_edit = TextEdit()
        self.notes_edit.setPlaceholderText("Conditions de paiement, délais, observations…")
        self.notes_edit.setMaximumHeight(110)
        notes_layout.addWidget(self.notes_edit)
        inner_layout.addWidget(notes_box)

        inner_layout.addSpacerItem(QSpacerItem(0, 10))

        # ── Barre de boutons ─────────────────────────────────────────────────
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(24, 12, 24, 18)
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

        self.btn_save = PrimaryPushButton("Enregistrer la facture")
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

    def _load_clients(self, preselect_id: int | None = None) -> None:
        self.client_combo.blockSignals(True)
        self.client_combo.clear()
        self.client_combo.addItem("— Sélectionner un client —", userData=None)
        selected_idx = 0
        for row in self.storage.list_clients():
            cid = int(row["id"])
            self.client_combo.addItem(row["nom"], userData=cid)
            if preselect_id is not None and cid == preselect_id:
                selected_idx = self.client_combo.count() - 1
        self.client_combo.setCurrentIndex(selected_idx)
        self.client_combo.blockSignals(False)

    def _load_facture(self, facture_id: int) -> None:
        devis = self.storage.read_facture_devis(facture_id)
        if devis is None:
            return
        row = self.storage.read_facture(facture_id)

        if row and row["client_id"]:
            idx = self.client_combo.findData(int(row["client_id"]))
            if idx >= 0:
                self.client_combo.setCurrentIndex(idx)

        self.affaire_edit.setText(devis.reference_affaire or "")

        d = devis.date_devis
        self.date_edit.setDate(QDate(d.year, d.month, d.day))

        statut = row["statut"] if row else "Brouillon"
        idx_s = self.statut_combo.findText(statut)
        if idx_s >= 0:
            self.statut_combo.setCurrentIndex(idx_s)

        self.tva_spin.setValue(float(devis.tva_pourcent_global))

        if row:
            self.notes_edit.setPlainText(row["notes"] or "")

        # Mode: avec lots ou lignes directes
        utiliser_lots = devis.utiliser_lots if devis.utiliser_lots is not None else True
        self.radio_avec_lots.setChecked(utiliser_lots)
        self.radio_sans_lots.setChecked(not utiliser_lots)
        self._lots_container.setVisible(utiliser_lots)
        self._lignes_container.setVisible(not utiliser_lots)

        if utiliser_lots:
            self._lots = deepcopy(devis.lots) if devis.lots else [Lot(nom="")]
            self._refresh_lots()
        else:
            first_lot = devis.lots[0] if devis.lots else None
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

    # ── Clients ──────────────────────────────────────────────────────────────

    def _on_new_client(self) -> None:
        dlg = ClientDialog(parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_data()
        try:
            cid = self.storage.create_client_direct(
                nom=data["nom"],
                adresse=data.get("adresse", ""),
                code_postal=data.get("code_postal", ""),
                ville=data.get("ville", ""),
                telephone=data.get("telephone", ""),
                email=data.get("email", ""),
            )
            self._load_clients(preselect_id=cid)
            idx = self.client_combo.findData(cid)
            if idx >= 0:
                self.client_combo.setCurrentIndex(idx)
        except Exception as exc:
            show_error(self, "Erreur", f"Impossible de créer le client :\n{exc}")

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
            self.lbl_tva.setText(self._fmt(tva_amt))
            self.lbl_ttc.setText(self._fmt(ttc))
        except (InvalidOperation, ValueError):
            pass

    @staticmethod
    def _fmt(v: Decimal) -> str:
        return f"{v:,.2f} €".replace(",", "\u202f").replace(".", ",")

    # ── Aperçu / Export ───────────────────────────────────────────────────────

    def _build_devis_for_export(self) -> Devis | None:
        """Construit un objet Devis depuis l'UI pour l'export — retourne None si client manquant."""
        import json
        client_id: int | None = self.client_combo.currentData()
        if client_id is None:
            show_error(self, "Client requis", "Veuillez sélectionner un client avant l'export.")
            return None
        affaire = self.affaire_edit.text().strip()
        qdate = self.date_edit.getDate()
        if qdate is None:
            qdate = QDate.currentDate()
        facture_date = date(qdate.year(), qdate.month(), qdate.day())
        tva_pct = Decimal(str(self.tva_spin.value()))
        notes = self.notes_edit.toPlainText().strip()
        client_row = self.storage.read_client(client_id)
        if client_row:
            cdata = json.loads(client_row["data_json"] or "{}")
            client = Client(
                nom=client_row["nom"],
                adresse=cdata.get("adresse", ""),
                code_postal=cdata.get("code_postal", ""),
                ville=cdata.get("ville", ""),
                telephone=cdata.get("telephone", ""),
                email=cdata.get("email", ""),
            )
        else:
            client = Client(nom=self.client_combo.currentText())

        if self.radio_avec_lots.isChecked():
            utiliser_lots = True
            lots = deepcopy(self._lots)
        else:
            utiliser_lots = False
            lots = [Lot(nom="Prestations", lignes=deepcopy(self._lignes_directes))]

        return Devis(
            date_devis=facture_date,
            reference_affaire=affaire,
            client=client,
            chantier=Chantier(adresse=affaire),
            statut="Facture",
            tva_pourcent_global=tva_pct,
            utiliser_lots=utiliser_lots,
            lots=lots,
            remarques=notes,
        )

    def _on_preview(self) -> None:
        import tempfile
        devis = self._build_devis_for_export()
        if devis is None:
            return
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
        devis = self._build_devis_for_export()
        if devis is None:
            return
        affaire = (devis.reference_affaire or "facture").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", f"facture_{affaire}.pdf", "PDF Files (*.pdf)"
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
        devis = self._build_devis_for_export()
        if devis is None:
            return
        affaire = (devis.reference_affaire or "facture").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export DOCX", f"facture_{affaire}.docx", "DOCX Files (*.docx)"
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
        import json

        client_id: int | None = self.client_combo.currentData()
        if client_id is None:
            show_error(self, "Client requis", "Veuillez sélectionner ou créer un client.")
            return

        affaire = self.affaire_edit.text().strip()
        qdate = self.date_edit.getDate()
        if qdate is None:
            qdate = QDate.currentDate()
        facture_date = date(qdate.year(), qdate.month(), qdate.day())
        statut = self.statut_combo.currentText()
        tva_pct = Decimal(str(self.tva_spin.value()))
        notes = self.notes_edit.toPlainText().strip()

        client_row = self.storage.read_client(client_id)
        if client_row:
            cdata = json.loads(client_row["data_json"] or "{}")
            client = Client(
                nom=client_row["nom"],
                adresse=cdata.get("adresse", ""),
                code_postal=cdata.get("code_postal", ""),
                ville=cdata.get("ville", ""),
                telephone=cdata.get("telephone", ""),
                email=cdata.get("email", ""),
            )
        else:
            client = Client(nom=self.client_combo.currentText())

        if self.radio_avec_lots.isChecked():
            utiliser_lots = True
            lots = deepcopy(self._lots)
        else:
            utiliser_lots = False
            lots = [Lot(nom="Prestations", lignes=deepcopy(self._lignes_directes))]

        devis = Devis(
            date_devis=facture_date,
            reference_affaire=affaire,
            client=client,
            chantier=Chantier(adresse=affaire),
            statut="Facture",
            tva_pourcent_global=tva_pct,
            utiliser_lots=utiliser_lots,
            lots=lots,
            remarques=notes,
        )

        try:
            if self.facture_id is None:
                fid = self.storage.create_facture_empty()
                self.storage.update_facture_devis(fid, devis, statut=statut, notes=notes)
                self.facture_id = fid
            else:
                self.storage.update_facture_devis(
                    self.facture_id, devis, statut=statut, notes=notes
                )
            self.accept()
        except Exception as exc:
            show_error(self, "Erreur", f"Impossible d'enregistrer la facture :\n{exc}")

    def get_facture_id(self) -> int | None:
        """Retourne l'ID de la facture créée ou modifiée après accept()."""
        return self.facture_id
