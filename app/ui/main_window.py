"""Fenêtre principale de l'application Batikam Renov."""

from copy import deepcopy
from decimal import Decimal
from html import escape as html_escape
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    ComboBox as FComboBox,
    DoubleSpinBox as FDoubleSpinBox,
    LineEdit as FLineEdit,
    PrimaryPushButton,
    PushButton as FPushButton,
)

import json

from app.models.devis import Devis
from app.services.branding import resolve_logo_path, resolve_logo_str
from app.services.export_docx import DOCXExporter
from app.services.export_pdf import PDFExporter
from app.services.storage_sqlite import StorageSQLite
from app.ui.client_dialog import ClientDialog
from app.ui.depense_dialog import DepenseDialog
from app.ui.devis_dialog import DevisDialog
from app.ui.facture_dialog import FactureDialog
from app.ui.feedback import show_confirm, show_error, show_loading, show_success
from app.ui.theme import add_shadow, make_card


# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DES FACTURES
# ═══════════════════════════════════════════════════════════════════════════════

class FacturesWidget(QWidget):
    """Module de gestion des factures — vue client-centrique, indépendant du devis."""

    def __init__(
        self,
        storage: StorageSQLite,
        on_data_changed: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.storage = storage
        self.on_data_changed = on_data_changed
        self._selected_client_id: Optional[int] = None
        self._client_row_map: dict[int, int] = {}
        self._facture_row_map: dict[int, int] = {}
        self._build_ui()
        self.refresh()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Splitter principal
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)

        # ── Panneau CLIENTS (gauche) ──────────────────────────────────────────
        client_card = make_card("SideListCard")
        client_card.setMinimumWidth(240)
        client_card.setMaximumWidth(300)
        add_shadow(client_card, blur=22, y_offset=4, color="#0F172A1F")
        cl = QVBoxLayout(client_card)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(8)

        cl_title = QLabel("Clients")
        cl_title.setProperty("variant", "title")
        cl.addWidget(cl_title)

        self.client_search = QLineEdit()
        self.client_search.setPlaceholderText("Rechercher un client…")
        self.client_search.textChanged.connect(self._on_client_search)
        cl.addWidget(self.client_search)

        self.client_table = QTableWidget(0, 1)
        self.client_table.setHorizontalHeaderLabels(["Nom"])
        self.client_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.client_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.client_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.client_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.client_table.setAlternatingRowColors(True)
        self.client_table.verticalHeader().setVisible(False)
        self.client_table.verticalHeader().setDefaultSectionSize(38)
        self.client_table.itemSelectionChanged.connect(self._on_client_selected)
        cl.addWidget(self.client_table, 1)

        client_actions = QHBoxLayout()
        client_actions.setSpacing(6)
        btn_new_client = QPushButton("+ Client")
        btn_new_client.setProperty("variant", "primary")
        btn_new_client.clicked.connect(self._on_new_client)
        btn_edit_client = QPushButton("Modifier")
        btn_edit_client.clicked.connect(self._on_edit_client)
        btn_del_client = QPushButton("Suppr.")
        btn_del_client.setProperty("variant", "danger")
        btn_del_client.clicked.connect(self._on_delete_client)
        client_actions.addWidget(btn_new_client)
        client_actions.addWidget(btn_edit_client)
        client_actions.addWidget(btn_del_client)
        cl.addLayout(client_actions)
        split.addWidget(client_card)

        # ── Panneau FACTURES (droite) ─────────────────────────────────────────
        facture_card = make_card("SectionCard")
        fl = QVBoxLayout(facture_card)
        fl.setContentsMargins(12, 12, 12, 12)
        fl.setSpacing(8)

        fact_header = QHBoxLayout()
        self.factures_title = QLabel("Toutes les factures")
        self.factures_title.setProperty("variant", "title")
        fact_header.addWidget(self.factures_title, 1)
        fl.addLayout(fact_header)

        self.facture_table = QTableWidget(0, 6)
        self.facture_table.setHorizontalHeaderLabels(
            ["N°", "Date", "Affaire / Projet", "HT", "TTC", "Statut"]
        )
        self.facture_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.facture_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.facture_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.facture_table.setAlternatingRowColors(True)
        self.facture_table.verticalHeader().setVisible(False)
        self.facture_table.verticalHeader().setDefaultSectionSize(40)
        self.facture_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.facture_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.facture_table.itemDoubleClicked.connect(self._on_facture_double_clicked)
        fl.addWidget(self.facture_table, 1)

        fact_actions = QHBoxLayout()
        fact_actions.setSpacing(8)
        self.btn_edit_facture = QPushButton("Modifier")
        self.btn_edit_facture.setProperty("variant", "primary")
        self.btn_edit_facture.clicked.connect(self._on_edit_facture)
        self.btn_export_pdf = QPushButton("Export PDF")
        self.btn_export_pdf.setObjectName("ExportPdfButton")
        self.btn_export_pdf.clicked.connect(self._on_export_pdf)
        self.btn_export_docx = QPushButton("Export DOCX")
        self.btn_export_docx.setObjectName("ExportDocxButton")
        self.btn_export_docx.clicked.connect(self._on_export_docx)
        self.btn_delete_facture = QPushButton("Supprimer")
        self.btn_delete_facture.setProperty("variant", "danger")
        self.btn_delete_facture.clicked.connect(self._on_delete_facture)
        fact_actions.addWidget(self.btn_edit_facture)
        fact_actions.addWidget(self.btn_export_pdf)
        fact_actions.addWidget(self.btn_export_docx)
        fact_actions.addStretch()
        fact_actions.addWidget(self.btn_delete_facture)
        fl.addLayout(fact_actions)

        split.addWidget(facture_card)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 10)

    # ── Données ───────────────────────────────────────────────────────────────

    def refresh(self, select_facture_id: Optional[int] = None) -> None:
        self._refresh_clients()
        self._refresh_factures(select_facture_id)

    def _refresh_clients(self) -> None:
        search = self.client_search.text().lower()
        self._client_row_map.clear()
        rows = self.storage.list_clients()
        filtered = [r for r in rows if search in r["nom"].lower()] if search else rows
        self.client_table.setRowCount(len(filtered))
        for i, row in enumerate(filtered):
            cid = int(row["id"])
            item = QTableWidgetItem(row["nom"])
            item.setData(Qt.UserRole, cid)
            self.client_table.setItem(i, 0, item)
            self._client_row_map[cid] = i
        if self._selected_client_id in self._client_row_map:
            self.client_table.selectRow(self._client_row_map[self._selected_client_id])

    def _refresh_factures(self, select_id: Optional[int] = None) -> None:
        if self._selected_client_id is not None:
            rows = self.storage.list_factures_by_client_id(self._selected_client_id)
            client_row = self.storage.read_client(self._selected_client_id)
            nom = client_row["nom"] if client_row else "client"
            self.factures_title.setText(f"Factures — {nom}")
        else:
            rows = self.storage.list_factures()
            self.factures_title.setText("Toutes les factures")

        self._facture_row_map.clear()
        self.facture_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            fid = int(row["id"])
            numero_item = QTableWidgetItem(row["numero"])
            numero_item.setData(Qt.UserRole, fid)
            self.facture_table.setItem(i, 0, numero_item)
            self.facture_table.setItem(i, 1, QTableWidgetItem(row["date_facture"]))
            self.facture_table.setItem(i, 2, QTableWidgetItem(row["projet"] or "—"))
            self.facture_table.setItem(i, 3, QTableWidgetItem(f"{Decimal(row['montant_ht']):.2f} €"))
            self.facture_table.setItem(i, 4, QTableWidgetItem(f"{Decimal(row['montant_ttc']):.2f} €"))
            self.facture_table.setItem(i, 5, QTableWidgetItem(row["statut"]))
            self._facture_row_map[fid] = i

        if select_id is not None and select_id in self._facture_row_map:
            self.facture_table.selectRow(self._facture_row_map[select_id])

    # ── Clients ───────────────────────────────────────────────────────────────

    def _on_client_search(self, _: str) -> None:
        self._refresh_clients()

    def _on_client_selected(self) -> None:
        row = self.client_table.currentRow()
        item = self.client_table.item(row, 0) if row >= 0 else None
        self._selected_client_id = int(item.data(Qt.UserRole)) if item else None
        self._refresh_factures()

    def _on_new_client(self) -> None:
        from PySide6.QtWidgets import QDialog
        dlg = ClientDialog(parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_data()
        try:
            self.storage.create_client_direct(**data)
            self.refresh()
        except Exception as exc:
            show_error(self, "Erreur", f"Impossible de créer le client :\n{exc}")

    def _on_edit_client(self) -> None:
        from PySide6.QtWidgets import QDialog
        if self._selected_client_id is None:
            show_error(self, "Client requis", "Sélectionnez un client dans la liste.")
            return
        row = self.storage.read_client(self._selected_client_id)
        if row is None:
            return
        existing = {"nom": row["nom"], **json.loads(row["data_json"] or "{}")}
        dlg = ClientDialog(data=existing, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_data()
        try:
            self.storage.update_client_direct(self._selected_client_id, **data)
            self.refresh()
        except Exception as exc:
            show_error(self, "Erreur", f"Impossible de modifier le client :\n{exc}")

    def _on_delete_client(self) -> None:
        if self._selected_client_id is None:
            show_error(self, "Client requis", "Sélectionnez un client.")
            return
        row = self.storage.read_client(self._selected_client_id)
        nom = row["nom"] if row else f"#{self._selected_client_id}"
        if not show_confirm(self, "Supprimer le client", f"Supprimer le client « {nom} » ?"):
            return
        self.storage.delete_client_direct(self._selected_client_id)
        self._selected_client_id = None
        self.refresh()

    # ── Factures ──────────────────────────────────────────────────────────────

    def _on_new_facture(self) -> None:
        from PySide6.QtWidgets import QDialog
        dlg = FactureDialog(
            storage=self.storage,
            preselect_client_id=self._selected_client_id,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            self.refresh(select_facture_id=dlg.get_facture_id())
            if self.on_data_changed:
                self.on_data_changed()

    def _on_edit_facture(self) -> None:
        from PySide6.QtWidgets import QDialog
        fid = self._selected_facture_id()
        if fid is None:
            show_error(self, "Facture requise", "Sélectionnez une facture dans la liste.")
            return
        dlg = FactureDialog(storage=self.storage, facture_id=fid, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh(select_facture_id=fid)
            if self.on_data_changed:
                self.on_data_changed()

    def _on_facture_double_clicked(self, _) -> None:
        self._on_edit_facture()

    def _on_delete_facture(self) -> None:
        fid = self._selected_facture_id()
        if fid is None:
            show_error(self, "Facture requise", "Sélectionnez une facture.")
            return
        facture = self.storage.read_facture(fid)
        if facture is None:
            return
        if not show_confirm(self, "Supprimer la facture", f"Supprimer la facture {facture['numero']} ?"):
            return
        self.storage.delete_facture(fid)
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()

    def _selected_facture_id(self) -> Optional[int]:
        row = self.facture_table.currentRow()
        item = self.facture_table.item(row, 0) if row >= 0 else None
        if item is None:
            return None
        val = item.data(Qt.UserRole)
        return int(val) if val is not None else None

    # ── Export ────────────────────────────────────────────────────────────────

    def _on_export_pdf(self) -> None:
        fid = self._selected_facture_id()
        if fid is None:
            show_error(self, "Facture requise", "Sélectionnez une facture.")
            return
        devis = self.storage.read_facture_devis(fid)
        if devis is None:
            return
        devis.statut = "Facture"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter en PDF", f"facture_{devis.numero or 'sans_numero'}.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return
        loading = show_loading(self, "Export PDF", "Export en cours…")
        try:
            PDFExporter().export(devis, path)
            loading.close()
            show_success(self, "Succès", f"PDF exporté :\n{path}")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Export PDF impossible :\n{exc}")

    def _on_export_docx(self) -> None:
        fid = self._selected_facture_id()
        if fid is None:
            show_error(self, "Facture requise", "Sélectionnez une facture.")
            return
        devis = self.storage.read_facture_devis(fid)
        if devis is None:
            return
        devis.statut = "Facture"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter en DOCX", f"facture_{devis.numero or 'sans_numero'}.docx", "DOCX Files (*.docx)"
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

    # ── Conversion depuis devis ────────────────────────────────────────────────

    def convert_from_devis(self, devis: Devis) -> bool:
        loading = show_loading(self, "Facturation", "Conversion du devis en facture…")
        try:
            facture_id = self.storage.create_facture_from_devis(devis)
            loading.close()
            self.refresh(select_facture_id=facture_id)
            if self.on_data_changed:
                self.on_data_changed()
            show_success(
                self,
                "Facture créée",
                f"Le devis {devis.numero} a été converti en facture.\n"
                "Vous pouvez maintenant l'exporter en PDF ou DOCX.",
            )
            return True
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Impossible de créer la facture :\n{exc}")
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# SUIVI PROJET
# ═══════════════════════════════════════════════════════════════════════════════

class SuiviProjetWidget(QWidget):
    """Module de suivi des dépenses par facture/projet/client."""

    ACOMPTE_MODE_PERCENT = "percent"
    ACOMPTE_MODE_TTC = "ttc"

    def __init__(self, storage: StorageSQLite, on_data_changed: Optional[Callable[[], None]] = None):
        super().__init__()
        self.storage = storage
        self.on_data_changed = on_data_changed
        self._client_id_map: dict[str, int] = {}   # label → client_id
        self._facture_id_map: dict[str, int] = {}  # label → facture_id
        self._build_ui()
        self.refresh_factures()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)

        # ── Toolbar : Client + Facture + Seuil (pleine largeur) ─────────────
        toolbar = make_card("MatCard")
        add_shadow(toolbar, blur=8, y_offset=2, color="#0F172A10")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(20, 14, 20, 14)
        tb.setSpacing(24)

        def _labeled(parent_layout: QHBoxLayout, text: str, widget: QWidget, stretch: int = 1) -> None:
            col = QVBoxLayout()
            col.setSpacing(5)
            lbl = QLabel(text)
            lbl.setObjectName("MatFieldLabel")
            col.addWidget(lbl)
            col.addWidget(widget)
            parent_layout.addLayout(col, stretch)

        self.client_combo = FComboBox()
        self.client_combo.currentTextChanged.connect(self._on_client_changed)
        _labeled(tb, "Client", self.client_combo, 2)

        self.facture_combo = FComboBox()
        self.facture_combo.currentTextChanged.connect(self._on_facture_changed)
        _labeled(tb, "Facture / N°", self.facture_combo, 3)

        self.seuil_spin = FDoubleSpinBox()
        self.seuil_spin.setRange(0, 100)
        self.seuil_spin.setValue(70)
        self.seuil_spin.setSuffix(" %")
        self.seuil_spin.valueChanged.connect(self._refresh_status)
        _labeled(tb, "Seuil d'alerte", self.seuil_spin, 1)

        root.addWidget(toolbar)

        # ── Corps : 2 colonnes 50 / 50 ───────────────────────────────────────
        body = QHBoxLayout()
        body.setSpacing(12)

        # ══ COLONNE GAUCHE : Dépenses ════════════════════════════════════════
        left_col = QVBoxLayout()
        left_col.setSpacing(0)
        left_col.setContentsMargins(0, 0, 0, 0)

        dep_card = make_card("MatCard")
        add_shadow(dep_card, blur=14, y_offset=4, color="#0F172A16")
        dl = QVBoxLayout(dep_card)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(0)

        dep_topbar = QWidget()
        dep_topbar.setObjectName("MatTableTopBar")
        dtb = QHBoxLayout(dep_topbar)
        dtb.setContentsMargins(20, 14, 14, 14)
        dtb.setSpacing(8)
        dep_title = QLabel("Dépenses")
        dep_title.setObjectName("MatTableTitle")
        dtb.addWidget(dep_title, 1)
        btn_add_dep = PrimaryPushButton("+ Ajouter")
        btn_add_dep.clicked.connect(self._on_open_add_depense)
        btn_del_dep = FPushButton("Supprimer")
        btn_del_dep.setProperty("variant", "danger")
        btn_del_dep.clicked.connect(self._on_delete_depense)
        dtb.addWidget(btn_add_dep)
        dtb.addWidget(btn_del_dep)
        dl.addWidget(dep_topbar)

        _div_dep = QFrame()
        _div_dep.setObjectName("MatDivider")
        _div_dep.setFixedHeight(1)
        dl.addWidget(_div_dep)

        self.depenses_table = QTableWidget(0, 4)
        self.depenses_table.setHorizontalHeaderLabels(["Date", "Catégorie", "Montant", "Notes"])
        self.depenses_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.depenses_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.depenses_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.depenses_table.verticalHeader().setVisible(False)
        self.depenses_table.verticalHeader().setDefaultSectionSize(48)
        self.depenses_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.depenses_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        # hauteur min pour afficher 5 lignes : header ~42 + 5×48 = 282
        self.depenses_table.setMinimumHeight(282)
        dl.addWidget(self.depenses_table, 1)

        left_col.addWidget(dep_card, 1)
        body.addLayout(left_col, 1)

        # ══ COLONNE DROITE : KPIs + Budget + Acompte ════════════════════════
        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        right_col.setContentsMargins(0, 0, 0, 0)

        # KPIs 2×2
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(10)
        self.kpi_ttc = self._kpi_card("Montant TTC", "—", "#1565C0")
        self.kpi_depenses = self._kpi_card("Dépenses", "—", "#C62828")
        self.kpi_reste = self._kpi_card("Reste", "—", "#2E7D32")
        self.kpi_ratio = self._kpi_card("Consommation", "—", "#E65100")
        kpi_grid.addWidget(self.kpi_ttc[0], 0, 0)
        kpi_grid.addWidget(self.kpi_depenses[0], 0, 1)
        kpi_grid.addWidget(self.kpi_reste[0], 1, 0)
        kpi_grid.addWidget(self.kpi_ratio[0], 1, 1)
        kpi_grid.setColumnStretch(0, 1)
        kpi_grid.setColumnStretch(1, 1)
        right_col.addLayout(kpi_grid)

        # Barre budget + statut
        prog_card = make_card("MatCard")
        add_shadow(prog_card, blur=10, y_offset=3, color="#0F172A12")
        pi = QVBoxLayout(prog_card)
        pi.setContentsMargins(20, 16, 20, 16)
        pi.setSpacing(12)
        prog_row = QHBoxLayout()
        prog_lbl = QLabel("BUDGET CONSOMMÉ")
        prog_lbl.setObjectName("MatSectionLabel")
        self.prog_pct_label = QLabel("—")
        self.prog_pct_label.setObjectName("MatProgressPct")
        prog_row.addWidget(prog_lbl, 1)
        prog_row.addWidget(self.prog_pct_label)
        pi.addLayout(prog_row)
        self.budget_progress = QProgressBar()
        self.budget_progress.setObjectName("MatBudgetProgress")
        self.budget_progress.setRange(0, 100)
        self.budget_progress.setValue(0)
        self.budget_progress.setTextVisible(False)
        self.budget_progress.setProperty("zone", "ok")
        pi.addWidget(self.budget_progress)
        self.status_label = QLabel("Sélectionnez un client puis une facture.")
        self.status_label.setObjectName("SuiviStatus")
        self.status_label.setProperty("zone", "neutral")
        self.status_label.setWordWrap(True)
        pi.addWidget(self.status_label)
        right_col.addWidget(prog_card)

        # Acompte
        acompte_card = make_card("MatCard")
        add_shadow(acompte_card, blur=10, y_offset=3, color="#0F172A12")
        ai = QVBoxLayout(acompte_card)
        ai.setContentsMargins(20, 16, 20, 16)
        ai.setSpacing(12)
        aco_lbl = QLabel("GÉNÉRATION D'ACOMPTE")
        aco_lbl.setObjectName("MatSectionLabel")
        ai.addWidget(aco_lbl)

        aco_top = QHBoxLayout()
        aco_top.setSpacing(10)
        self.acompte_mode_combo = FComboBox()
        self.acompte_mode_combo.addItem("Pourcentage (%)", self.ACOMPTE_MODE_PERCENT)
        self.acompte_mode_combo.addItem("Montant TTC (€)", self.ACOMPTE_MODE_TTC)
        self.acompte_mode_combo.currentIndexChanged.connect(self._on_acompte_mode_changed)
        self.acompte_value_spin = FDoubleSpinBox()
        self.acompte_value_spin.setDecimals(2)
        self.acompte_value_spin.setRange(0.01, 100.0)
        self.acompte_value_spin.setValue(30.0)
        self.acompte_value_spin.setSuffix(" %")
        self.acompte_value_spin.valueChanged.connect(self._refresh_acompte_preview)
        self.btn_generate_acompte = PrimaryPushButton("Générer l'acompte")
        self.btn_generate_acompte.clicked.connect(self._on_generate_acompte_facture)
        self.btn_generate_acompte.setEnabled(False)
        aco_top.addWidget(self.acompte_mode_combo, 1)
        aco_top.addWidget(self.acompte_value_spin, 1)
        aco_top.addWidget(self.btn_generate_acompte)
        ai.addLayout(aco_top)

        self.acompte_preview_label = QLabel("Sélectionnez une facture pour générer un acompte.")
        self.acompte_preview_label.setObjectName("PageSubtitle")
        self.acompte_preview_label.setWordWrap(True)
        ai.addWidget(self.acompte_preview_label)
        right_col.addWidget(acompte_card)

        right_col.addStretch(1)
        body.addLayout(right_col, 1)

        root.addLayout(body, 1)

    def _kpi_card(self, label: str, value: str, accent: str = "#1565C0") -> tuple[QFrame, QLabel]:
        card = make_card("MatKpiCard")
        add_shadow(card, blur=8, y_offset=2, color="#0F172A10")
        lo = QVBoxLayout(card)
        lo.setContentsMargins(16, 12, 16, 14)
        lo.setSpacing(6)
        accent_bar = QFrame()
        accent_bar.setFixedHeight(3)
        accent_bar.setStyleSheet(f"background: {accent}; border-radius: 2px; border: none;")
        kpi_label = QLabel(label)
        kpi_label.setObjectName("MatKpiLabel")
        kpi_value = QLabel(value)
        kpi_value.setObjectName("MatKpiValue")
        kpi_value.setStyleSheet(f"color: {accent};")
        lo.addWidget(accent_bar)
        lo.addWidget(kpi_label)
        lo.addWidget(kpi_value)
        return card, kpi_value

    # ── Données ───────────────────────────────────────────────────────────────

    def refresh_factures(self) -> None:
        """Recharge le combo client (point d'entrée principal)."""
        prev_client = self.client_combo.currentText()
        self._client_id_map.clear()
        self.client_combo.blockSignals(True)
        self.client_combo.clear()
        self.client_combo.addItem("— Sélectionner —")
        for row in self.storage.list_clients():
            label = row["nom"]
            self._client_id_map[label] = int(row["id"])
            self.client_combo.addItem(label)
        self.client_combo.blockSignals(False)
        # Restaurer la sélection précédente si possible
        if prev_client in self._client_id_map:
            self.client_combo.setCurrentText(prev_client)
        else:
            self._on_client_changed(self.client_combo.currentText())

    def _on_client_changed(self, text: str) -> None:
        client_id = self._client_id_map.get(text)
        self._facture_id_map.clear()
        self.facture_combo.blockSignals(True)
        self.facture_combo.clear()
        self.facture_combo.addItem("— Sélectionner —")
        if client_id is not None:
            for row in self.storage.list_factures_by_client_id(client_id):
                projet = row["projet"] or ""
                label = f"{row['numero']}" + (f"  —  {projet}" if projet else "")
                self._facture_id_map[label] = int(row["id"])
                self.facture_combo.addItem(label)
        self.facture_combo.blockSignals(False)
        self._on_facture_changed(self.facture_combo.currentText())

    def _on_facture_changed(self, _: str) -> None:
        facture_id = self._current_facture_id()
        self.depenses_table.setRowCount(0)
        if facture_id is None:
            self._reset_dashboard()
            return
        self._sync_acompte_controls()
        self._refresh_acompte_preview()
        self._refresh_depenses()
        self._refresh_status()

    def _current_facture_id(self) -> Optional[int]:
        return self._facture_id_map.get(self.facture_combo.currentText())

    def _reset_dashboard(self) -> None:
        self._set_kpis(Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))
        self.status_label.setProperty("zone", "neutral")
        self.status_label.setText("Sélectionnez un client puis une facture.")
        self._restyle_status()
        self.acompte_preview_label.setText("Sélectionnez une facture pour générer un acompte.")
        self.btn_generate_acompte.setEnabled(False)
        self.acompte_mode_combo.setEnabled(False)
        self.acompte_value_spin.setEnabled(False)

    def _refresh_depenses(self) -> None:
        facture_id = self._current_facture_id()
        if facture_id is None:
            return
        rows = self.storage.list_depenses(facture_id=facture_id)
        self.depenses_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            date_item = QTableWidgetItem(row["date_depense"])
            date_item.setData(Qt.UserRole, int(row["id"]))
            self.depenses_table.setItem(r, 0, date_item)
            self.depenses_table.setItem(r, 1, QTableWidgetItem(row["categorie"]))
            montant = f"{Decimal(row['montant']):,.2f} €".replace(",", " ").replace(".", ",")
            self.depenses_table.setItem(r, 2, QTableWidgetItem(montant))
            self.depenses_table.setItem(r, 3, QTableWidgetItem(row["notes"] or ""))

    def _set_kpis(self, ttc: Decimal, depenses: Decimal, reste: Decimal, ratio: Decimal) -> None:
        fmt = lambda v: f"{v:,.2f} €".replace(",", " ").replace(".", ",")
        self.kpi_ttc[1].setText(fmt(ttc))
        self.kpi_depenses[1].setText(fmt(depenses))
        self.kpi_reste[1].setText(fmt(reste))
        self.kpi_ratio[1].setText(f"{ratio:.1f} %")
        pct = min(100, max(0, int(ratio)))
        self.budget_progress.setValue(pct)
        self.prog_pct_label.setText(f"{ratio:.1f} %" if ttc > 0 else "—")
        zone = "warning" if pct >= int(self.seuil_spin.value()) else "ok"
        self.budget_progress.setProperty("zone", zone)
        self.budget_progress.style().unpolish(self.budget_progress)
        self.budget_progress.style().polish(self.budget_progress)

    def _restyle_status(self) -> None:
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.update()

    def _refresh_status(self) -> None:
        facture_id = self._current_facture_id()
        if facture_id is None:
            return
        facture = self.storage.read_facture(facture_id)
        if facture is None:
            return
        total_ttc = Decimal(facture["montant_ttc"])
        total_dep = self.storage.total_depenses_facture(facture_id)
        reste = total_ttc - total_dep
        ratio = (total_dep / total_ttc * Decimal("100")) if total_ttc > 0 else Decimal("0")
        self._set_kpis(total_ttc, total_dep, reste, ratio)
        seuil = Decimal(str(self.seuil_spin.value()))
        zone = "warning" if ratio >= seuil else "ok"
        label = "ZONE ORANGE" if zone == "warning" else "Zone normale"
        self.status_label.setProperty("zone", zone)
        self.status_label.setText(
            f"{label} | TTC: {total_ttc:.2f} EUR | Dépenses: {total_dep:.2f} EUR | "
            f"Reste: {reste:.2f} EUR | Taux: {ratio:.1f}%"
        )
        self._restyle_status()

    # ── Dépenses (popup) ──────────────────────────────────────────────────────

    def _on_open_add_depense(self) -> None:
        from PySide6.QtWidgets import QDialog
        facture_id = self._current_facture_id()
        if facture_id is None:
            show_error(self, "Facture requise", "Sélectionnez d'abord une facture.")
            return
        facture = self.storage.read_facture(facture_id)
        client_nom = facture["client_nom"] if facture else ""
        projet = facture["projet"] if facture else ""
        dlg = DepenseDialog(client_nom=client_nom, projet=projet, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_data()
        self.storage.add_depense(
            facture_id=facture_id,
            client_nom=data["client_nom"],
            projet=data["projet"],
            categorie=data["categorie"],
            montant=data["montant"],
            notes=data["notes"],
        )
        self._refresh_depenses()
        self._refresh_status()
        if self.on_data_changed:
            self.on_data_changed()

    def _on_delete_depense(self) -> None:
        row = self.depenses_table.currentRow()
        if row < 0:
            show_error(self, "Dépense requise", "Sélectionnez une dépense à supprimer.")
            return
        item = self.depenses_table.item(row, 0)
        if item is None:
            return
        dep_id = item.data(Qt.UserRole)
        if dep_id is None:
            return
        if not show_confirm(self, "Supprimer la dépense", "Supprimer cette dépense ?"):
            return
        with self.storage._connect() as conn:
            conn.execute("DELETE FROM depenses WHERE id = ?", (int(dep_id),))
            conn.commit()
        self._refresh_depenses()
        self._refresh_status()
        if self.on_data_changed:
            self.on_data_changed()

    # ── Acompte ───────────────────────────────────────────────────────────────

    def _on_acompte_mode_changed(self, _: int) -> None:
        self._sync_acompte_controls()
        self._refresh_acompte_preview()

    def _sync_acompte_controls(self) -> None:
        facture_id = self._current_facture_id()
        facture = self.storage.read_facture(facture_id) if facture_id is not None else None
        has_facture = facture is not None
        self.acompte_mode_combo.setEnabled(has_facture)
        self.acompte_value_spin.setEnabled(has_facture)
        self.btn_generate_acompte.setEnabled(has_facture)
        if not has_facture:
            self.acompte_preview_label.setText("Sélectionnez une facture pour générer un acompte.")
            return
        total_ttc = Decimal(str(facture["montant_ttc"] or "0"))
        mode = self.acompte_mode_combo.currentData()
        if mode == self.ACOMPTE_MODE_TTC:
            max_value = float(total_ttc if total_ttc > 0 else Decimal("0.01"))
            self.acompte_value_spin.blockSignals(True)
            self.acompte_value_spin.setRange(0.01, max(0.01, max_value))
            self.acompte_value_spin.setSingleStep(max(1.0, round(max_value / 20, 2)))
            self.acompte_value_spin.setSuffix(" EUR TTC")
            if self.acompte_value_spin.value() > max_value:
                self.acompte_value_spin.setValue(max_value)
            self.acompte_value_spin.blockSignals(False)
        else:
            self.acompte_value_spin.blockSignals(True)
            self.acompte_value_spin.setRange(0.01, 100.0)
            self.acompte_value_spin.setSingleStep(5.0)
            self.acompte_value_spin.setSuffix(" %")
            if self.acompte_value_spin.value() > 100:
                self.acompte_value_spin.setValue(30.0)
            self.acompte_value_spin.blockSignals(False)

    def _compute_acompte_ttc(self, total_ttc: Decimal) -> Decimal:
        value = Decimal(str(self.acompte_value_spin.value()))
        mode = self.acompte_mode_combo.currentData()
        if mode == self.ACOMPTE_MODE_PERCENT:
            return (total_ttc * value / Decimal("100")).quantize(Decimal("0.01"))
        return value.quantize(Decimal("0.01"))

    def _refresh_acompte_preview(self) -> None:
        facture_id = self._current_facture_id()
        facture = self.storage.read_facture(facture_id) if facture_id is not None else None
        if facture is None:
            self.acompte_preview_label.setText("Sélectionnez une facture pour générer un acompte.")
            return
        total_ttc = Decimal(str(facture["montant_ttc"] or "0"))
        if total_ttc <= 0:
            self.acompte_preview_label.setText("Montant TTC nul.")
            return
        acompte_ttc = self._compute_acompte_ttc(total_ttc)
        self.acompte_preview_label.setText(
            f"Acompte prévu : {acompte_ttc:.2f} EUR TTC sur {facture['numero']} (base {total_ttc:.2f} EUR TTC)."
        )

    def _select_facture_by_id(self, facture_id: int) -> None:
        for label, fid in self._facture_id_map.items():
            if fid == facture_id:
                self.facture_combo.setCurrentText(label)
                return

    def _on_generate_acompte_facture(self) -> None:
        source_facture_id = self._current_facture_id()
        if source_facture_id is None:
            show_error(self, "Facture requise", "Sélectionnez d'abord une facture source.")
            return
        source_facture = self.storage.read_facture(source_facture_id)
        if source_facture is None:
            show_error(self, "Facture introuvable", "Impossible de lire la facture source.")
            return
        total_ttc = Decimal(str(source_facture["montant_ttc"] or "0"))
        if total_ttc <= 0:
            show_error(self, "Montant invalide", "La facture source doit avoir un montant TTC positif.")
            return
        mode = self.acompte_mode_combo.currentData()
        value = Decimal(str(self.acompte_value_spin.value()))
        if mode == self.ACOMPTE_MODE_PERCENT:
            if value <= 0 or value > Decimal("100"):
                show_error(self, "Acompte invalide", "Le pourcentage doit être entre 0 et 100.")
                return
        else:
            if value <= 0 or value > total_ttc:
                show_error(self, "Acompte invalide", "Le montant TTC d'acompte est invalide.")
                return
        saved_client_text = self.client_combo.currentText()
        loading = show_loading(self, "Acompte", "Génération de la facture d'acompte…")
        try:
            new_facture_id = self.storage.create_facture_acompte_from_facture(
                source_facture_id=source_facture_id, mode=str(mode), value=value
            )
            self.refresh_factures()
            if saved_client_text in self._client_id_map:
                self.client_combo.setCurrentText(saved_client_text)
            self._select_facture_by_id(new_facture_id)
            loading.close()
            if self.on_data_changed:
                self.on_data_changed()
            new_row = self.storage.read_facture(new_facture_id)
            new_numero = new_row["numero"] if new_row is not None else str(new_facture_id)
            show_success(self, "Succès", f"Facture d'acompte générée : {new_numero}")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Impossible de générer la facture d'acompte :\n{exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# FENÊTRE PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """Fenêtre principale."""

    def __init__(self):
        super().__init__()
        self.storage = StorageSQLite()

        self.setWindowTitle("Batikam Renove — Gestion")
        self.setGeometry(90, 80, 1440, 900)
        self.setMinimumSize(1200, 720)

        logo_path = resolve_logo_path()
        if logo_path:
            self.setWindowIcon(QIcon(str(logo_path)))

        central = QWidget()
        central.setObjectName("AppRoot")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        root.addWidget(self._build_navigation())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._build_top_header())

        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages, 1)

        self.home_page = self._build_home_page()
        self.devis_page = self._build_devis_page()
        self.factures_widget = FacturesWidget(self.storage, on_data_changed=self._refresh_dashboard)
        self.suivi_widget = SuiviProjetWidget(self.storage, on_data_changed=self._refresh_dashboard)

        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.devis_page)
        self.pages.addWidget(self.factures_widget)
        self.pages.addWidget(self.suivi_widget)

        root.addWidget(content, 1)

        self._refresh_devis_list()
        self._refresh_dashboard()
        self._switch_page("home")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _build_navigation(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("NavSidebar")
        panel.setMinimumWidth(260)
        panel.setMaximumWidth(290)
        add_shadow(panel, blur=26, y_offset=4, color="#0F172A26")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        logo_shell = QFrame()
        logo_shell.setObjectName("NavLogoShell")
        logo_shell.setMinimumHeight(110)
        logo_shell.setMaximumHeight(140)
        shell_layout = QVBoxLayout(logo_shell)
        shell_layout.setContentsMargins(8, 8, 8, 8)
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_path = resolve_logo_path()
        if logo_path:
            pixmap = QPixmap(str(logo_path)).scaled(200, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        shell_layout.addWidget(logo_label)
        layout.addWidget(logo_shell)

        nav_title = QLabel("Navigation")
        nav_title.setProperty("variant", "muted")
        layout.addWidget(nav_title)

        self.btn_nav_home = self._nav_button("Tableau de bord", lambda: self._switch_page("home"))
        self.btn_nav_devis = self._nav_button("Gestion des devis", lambda: self._switch_page("devis"))
        self.btn_nav_factures = self._nav_button("Gestion des factures", self._open_factures)
        self.btn_nav_suivi = self._nav_button("Suivi projet", self._open_suivi)

        layout.addWidget(self.btn_nav_home)
        layout.addWidget(self.btn_nav_devis)
        layout.addWidget(self.btn_nav_factures)
        layout.addWidget(self.btn_nav_suivi)
        layout.addStretch()

        footer = QLabel("Batikam Renov\nBâtir avec talent, innovation, qualité")
        footer.setObjectName("NavFooter")
        footer.setWordWrap(True)
        layout.addWidget(footer)

        return panel

    def _nav_button(self, text: str, on_click: Callable[[], None]) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        btn.clicked.connect(on_click)
        return btn

    # ── Top header ────────────────────────────────────────────────────────────

    def _build_top_header(self) -> QWidget:
        top = make_card("TopHeader")
        add_shadow(top, blur=18, y_offset=2, color="#0F172A1A")
        layout = QHBoxLayout(top)
        layout.setContentsMargins(16, 7, 16, 7)
        layout.setSpacing(10)
        title_col = QVBoxLayout()
        self.top_title = QLabel("Tableau de bord")
        self.top_title.setObjectName("TopHeaderTitle")
        self.top_subtitle = QLabel("Pilotage global de l'activité")
        self.top_subtitle.setObjectName("TopHeaderSubtitle")
        title_col.addWidget(self.top_title)
        title_col.addWidget(self.top_subtitle)
        layout.addLayout(title_col)
        layout.addStretch()
        self.btn_top_new_devis = QPushButton("+ Nouveau devis")
        self.btn_top_new_devis.setObjectName("ToFactureBtn")
        self.btn_top_new_devis.setMinimumHeight(34)
        self.btn_top_new_devis.clicked.connect(self._on_new_devis)
        self.btn_top_new_devis.hide()
        layout.addWidget(self.btn_top_new_devis)
        self.btn_top_new_facture = QPushButton("+ Nouvelle facture")
        self.btn_top_new_facture.setObjectName("ToFactureBtn")
        self.btn_top_new_facture.setMinimumHeight(34)
        self.btn_top_new_facture.clicked.connect(self._on_new_facture_from_header)
        self.btn_top_new_facture.hide()
        layout.addWidget(self.btn_top_new_facture)
        btn_refresh = QPushButton("Rafraîchir données")
        btn_refresh.clicked.connect(self._refresh_all_views)
        layout.addWidget(btn_refresh)
        return top

    # ── Page Accueil ──────────────────────────────────────────────────────────

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(12)
        kpi_grid.setVerticalSpacing(12)

        self.kpi_devis = self._dashboard_kpi("Devis en cours", "0")
        self.kpi_factures = self._dashboard_kpi("Factures", "0")
        self.kpi_attente = self._dashboard_kpi("Factures en attente", "0")
        self.kpi_depenses = self._dashboard_kpi("Dépenses du mois", "0,00 EUR")
        self.kpi_ca = self._dashboard_kpi("CA facturé", "0,00 EUR")

        kpi_grid.addWidget(self.kpi_devis[0], 0, 0)
        kpi_grid.addWidget(self.kpi_factures[0], 0, 1)
        kpi_grid.addWidget(self.kpi_attente[0], 0, 2)
        kpi_grid.addWidget(self.kpi_depenses[0], 1, 0)
        kpi_grid.addWidget(self.kpi_ca[0], 1, 1)

        quick_actions = make_card("DashboardKpi")
        qa_layout = QVBoxLayout(quick_actions)
        qa_layout.setContentsMargins(14, 12, 14, 12)
        qa_layout.setSpacing(8)
        qa_title = QLabel("Actions rapides")
        qa_title.setObjectName("KpiLabel")
        qa_layout.addWidget(qa_title)
        btn_new = QPushButton("Nouveau devis")
        btn_new.setProperty("variant", "primary")
        btn_new.clicked.connect(self._on_new_devis)
        btn_devis = QPushButton("Aller aux devis")
        btn_devis.clicked.connect(lambda: self._switch_page("devis"))
        btn_fact = QPushButton("Aller aux factures")
        btn_fact.clicked.connect(self._open_factures)
        qa_layout.addWidget(btn_new)
        qa_layout.addWidget(btn_devis)
        qa_layout.addWidget(btn_fact)
        qa_layout.addStretch()
        kpi_grid.addWidget(quick_actions, 1, 2)

        root.addLayout(kpi_grid)

        bottom = QSplitter(Qt.Horizontal)
        bottom.setChildrenCollapsible(False)
        root.addWidget(bottom, 1)

        recent_card = make_card("SectionCard")
        rl = QVBoxLayout(recent_card)
        rl.setContentsMargins(12, 12, 12, 12)
        rl.setSpacing(8)
        rl.addWidget(self._section_title("Devis récents"))
        self.dashboard_devis_table = QTableWidget(0, 4)
        self.dashboard_devis_table.setHorizontalHeaderLabels(["N°", "Client", "Date", "TTC"])
        self.dashboard_devis_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dashboard_devis_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dashboard_devis_table.verticalHeader().setVisible(False)
        self.dashboard_devis_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.dashboard_devis_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        rl.addWidget(self.dashboard_devis_table)
        bottom.addWidget(recent_card)

        fact_card = make_card("SectionCard")
        fll = QVBoxLayout(fact_card)
        fll.setContentsMargins(12, 12, 12, 12)
        fll.setSpacing(8)
        fll.addWidget(self._section_title("Factures récentes"))
        self.dashboard_factures_table = QTableWidget(0, 4)
        self.dashboard_factures_table.setHorizontalHeaderLabels(["N°", "Client", "Projet", "TTC"])
        self.dashboard_factures_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dashboard_factures_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dashboard_factures_table.verticalHeader().setVisible(False)
        self.dashboard_factures_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.dashboard_factures_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        fll.addWidget(self.dashboard_factures_table)
        bottom.addWidget(fact_card)

        alert_card = make_card("SectionCard")
        all_ = QVBoxLayout(alert_card)
        all_.setContentsMargins(12, 12, 12, 12)
        all_.setSpacing(8)
        all_.addWidget(self._section_title("Alertes"))
        self.alerts_box = QTextEdit()
        self.alerts_box.setReadOnly(True)
        self.alerts_box.setObjectName("AlertsBox")
        all_.addWidget(self.alerts_box)
        bottom.addWidget(alert_card)

        bottom.setStretchFactor(0, 3)
        bottom.setStretchFactor(1, 3)
        bottom.setStretchFactor(2, 2)

        return page

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("variant", "title")
        return lbl

    def _dashboard_kpi(self, label: str, value: str) -> tuple[QFrame, QLabel]:
        card = make_card("DashboardKpi")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        lbl = QLabel(label)
        lbl.setObjectName("KpiLabel")
        val = QLabel(value)
        val.setObjectName("KpiValue")
        layout.addWidget(lbl)
        layout.addWidget(val)
        return card, val

    # ── Page Devis ────────────────────────────────────────────────────────────

    def _build_devis_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Barre de recherche
        search_card = make_card("ToolbarCard")
        sl = QHBoxLayout(search_card)
        sl.setContentsMargins(14, 8, 14, 8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher N°, client, affaire…")
        self.search_input.textChanged.connect(self._on_search_changed)
        sl.addWidget(self.search_input)
        root.addWidget(search_card)

        # Table + actions
        content_card = make_card("SectionCard")
        add_shadow(content_card, blur=18, y_offset=3, color="#0F172A18")
        cl = QVBoxLayout(content_card)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(10)

        self.devis_table = QTableWidget(0, 6)
        self.devis_table.setHorizontalHeaderLabels(["N°", "Client", "Affaire", "Date", "TTC", "Statut"])
        self.devis_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.devis_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.devis_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.devis_table.setAlternatingRowColors(True)
        self.devis_table.verticalHeader().setVisible(False)
        self.devis_table.verticalHeader().setDefaultSectionSize(44)
        self.devis_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.devis_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.devis_table.itemDoubleClicked.connect(self._on_devis_double_clicked)
        cl.addWidget(self.devis_table, 1)

        # Barre d'actions
        actions = QHBoxLayout()
        actions.setSpacing(8)

        btn_open = QPushButton("Ouvrir / Modifier")
        btn_open.setProperty("variant", "primary")
        btn_open.clicked.connect(self._on_open_devis)

        btn_dup = QPushButton("Dupliquer")
        btn_dup.clicked.connect(self._on_duplicate_devis)

        btn_del = QPushButton("Supprimer")
        btn_del.setProperty("variant", "danger")
        btn_del.clicked.connect(self._on_delete_devis)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)

        btn_pdf = QPushButton("Export PDF")
        btn_pdf.setObjectName("ExportPdfButton")
        btn_pdf.clicked.connect(self._on_export_pdf)

        btn_docx = QPushButton("Export DOCX")
        btn_docx.setObjectName("ExportDocxButton")
        btn_docx.clicked.connect(self._on_export_docx)

        btn_validate = QPushButton("Valider prospect")
        btn_validate.clicked.connect(self._on_validate_prospect)

        btn_to_facture = QPushButton("Créer facture →")
        btn_to_facture.setObjectName("ToFactureBtn")
        btn_to_facture.clicked.connect(self._on_convert_to_facture)

        actions.addWidget(btn_open)
        actions.addWidget(btn_dup)
        actions.addWidget(btn_del)
        actions.addWidget(sep)
        actions.addWidget(btn_pdf)
        actions.addWidget(btn_docx)
        actions.addWidget(btn_validate)
        actions.addStretch()
        actions.addWidget(btn_to_facture)
        cl.addLayout(actions)

        root.addWidget(content_card, 1)
        return page

    # ── Routing ───────────────────────────────────────────────────────────────

    def _switch_page(self, page: str) -> None:
        titles = {
            "home": ("Tableau de bord", "Vue synthèse de l'activité Batikam Renov"),
            "devis": ("Gestion des devis", "Créez, éditez et exportez vos devis professionnels"),
            "factures": ("Gestion des factures", "Facturation complète — création ou depuis devis"),
            "suivi": ("Suivi projet", "Pilotage dépenses, marge et seuils d'alerte"),
        }
        widgets = {
            "home": self.home_page,
            "devis": self.devis_page,
            "factures": self.factures_widget,
            "suivi": self.suivi_widget,
        }
        self.pages.setCurrentWidget(widgets[page])
        title, subtitle = titles[page]
        self.top_title.setText(title)
        self.top_subtitle.setText(subtitle)
        self.btn_top_new_devis.setVisible(page == "devis")
        self.btn_top_new_facture.setVisible(page == "factures")
        self.btn_nav_home.setChecked(page == "home")
        self.btn_nav_devis.setChecked(page == "devis")
        self.btn_nav_factures.setChecked(page == "factures")
        self.btn_nav_suivi.setChecked(page == "suivi")

    def _open_factures(self) -> None:
        self.factures_widget.refresh()
        self._switch_page("factures")

    def _open_suivi(self) -> None:
        self.suivi_widget.refresh_factures()
        self._switch_page("suivi")

    def _refresh_all_views(self) -> None:
        self._refresh_devis_list()
        self.factures_widget.refresh()
        self.suivi_widget.refresh_factures()
        self._refresh_dashboard()

    # ── CRUD Devis ────────────────────────────────────────────────────────────

    def _selected_devis_id(self) -> Optional[int]:
        row = self.devis_table.currentRow()
        if row < 0:
            return None
        item = self.devis_table.item(row, 0)
        if item is None:
            return None
        val = item.data(Qt.UserRole)
        return int(val) if val is not None else None

    def _refresh_devis_list(self) -> None:
        search = self.search_input.text() if hasattr(self, "search_input") else ""
        devis_list = self.storage.list_all(search=search)
        self.devis_table.setSortingEnabled(False)
        self.devis_table.setRowCount(len(devis_list))
        for row, devis in enumerate(devis_list):
            numero_item = QTableWidgetItem(devis.numero)
            numero_item.setData(Qt.UserRole, devis.id)
            self.devis_table.setItem(row, 0, numero_item)
            self.devis_table.setItem(row, 1, QTableWidgetItem(devis.client.nom))
            affaire = (devis.reference_affaire or "").strip() or "—"
            self.devis_table.setItem(row, 2, QTableWidgetItem(affaire))
            self.devis_table.setItem(row, 3, QTableWidgetItem(devis.date_devis.strftime("%d/%m/%Y")))
            self.devis_table.setItem(row, 4, QTableWidgetItem(f"{devis.calculer_total_ttc():.2f} €"))
            self.devis_table.setItem(row, 5, QTableWidgetItem(devis.statut))
        self.devis_table.setSortingEnabled(True)

    def _on_search_changed(self, _: str) -> None:
        self._refresh_devis_list()

    def _on_devis_double_clicked(self, _) -> None:
        self._on_open_devis()

    def _on_new_facture_from_header(self) -> None:
        self.factures_widget._on_new_facture()

    def _on_new_devis(self) -> None:
        from PySide6.QtWidgets import QDialog
        dlg = DevisDialog(storage=self.storage, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_devis_list()
            self._refresh_dashboard()
        self._switch_page("devis")

    def _on_open_devis(self) -> None:
        from PySide6.QtWidgets import QDialog
        devis_id = self._selected_devis_id()
        if devis_id is None:
            show_error(self, "Attention", "Sélectionnez un devis.")
            return
        devis = self.storage.read(devis_id)
        if devis is None:
            show_error(self, "Attention", "Devis introuvable.")
            return
        dlg = DevisDialog(storage=self.storage, devis=devis, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_devis_list()
            self._refresh_dashboard()

    def _on_duplicate_devis(self) -> None:
        from PySide6.QtWidgets import QDialog
        devis_id = self._selected_devis_id()
        if devis_id is None:
            show_error(self, "Attention", "Sélectionnez un devis.")
            return
        source = self.storage.read(devis_id)
        if source is None:
            show_error(self, "Attention", "Devis introuvable.")
            return
        duplicated = deepcopy(source)
        duplicated.id = None
        duplicated.numero = ""
        duplicated.statut = "Brouillon"
        dlg = DevisDialog(storage=self.storage, devis=duplicated, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_devis_list()
            self._refresh_dashboard()

    def _on_delete_devis(self) -> None:
        devis_id = self._selected_devis_id()
        if devis_id is None:
            show_error(self, "Attention", "Sélectionnez un devis.")
            return
        devis = self.storage.read(devis_id)
        if devis is None:
            show_error(self, "Attention", "Devis introuvable.")
            return
        if not show_confirm(self, "Confirmation", f"Supprimer le devis {devis.numero} ?"):
            return
        if self.storage.delete(devis_id):
            self._refresh_devis_list()
            self._refresh_dashboard()

    def _on_validate_prospect(self) -> None:
        devis_id = self._selected_devis_id()
        if devis_id is None:
            show_error(self, "Prospect requis", "Sélectionnez un devis/prospect.")
            return
        devis = self.storage.read(devis_id)
        if devis is None:
            show_error(self, "Introuvable", "Devis introuvable.")
            return
        loading = show_loading(self, "Validation", "Conversion prospect vers client/projet…")
        try:
            self.storage.validate_prospect_to_client_project(devis)
            loading.close()
            self._refresh_devis_list()
            self._refresh_dashboard()
            show_success(self, "Succès", "Prospect validé en client avec projet actif.")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Validation impossible :\n{exc}")

    def _on_convert_to_facture(self) -> None:
        devis_id = self._selected_devis_id()
        if devis_id is None:
            show_error(self, "Aucun devis sélectionné", "Sélectionnez un devis dans la liste.")
            return
        devis = self.storage.read(devis_id)
        if devis is None:
            show_error(self, "Introuvable", "Devis introuvable.")
            return
        if not show_confirm(
            self,
            "Créer une facture",
            f"Convertir le devis {devis.numero} ({devis.client.nom}) en facture ?",
        ):
            return
        self.factures_widget.refresh()
        if self.factures_widget.convert_from_devis(devis):
            self._switch_page("factures")

    def _on_export_pdf(self) -> None:
        devis_id = self._selected_devis_id()
        if devis_id is None:
            show_error(self, "Attention", "Sélectionnez un devis.")
            return
        devis = self.storage.read(devis_id)
        if devis is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", f"devis_{devis.numero or 'sans_numero'}.pdf", "PDF Files (*.pdf)"
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
        devis_id = self._selected_devis_id()
        if devis_id is None:
            show_error(self, "Attention", "Sélectionnez un devis.")
            return
        devis = self.storage.read(devis_id)
        if devis is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export DOCX", f"devis_{devis.numero or 'sans_numero'}.docx", "DOCX Files (*.docx)"
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

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _refresh_dashboard(self) -> None:
        devis_list = self.storage.list_all()
        factures = self.storage.list_factures()
        depenses = self.storage.list_depenses()

        devis_count = len(devis_list)
        factures_count = len(factures)
        attente_count = sum(1 for r in factures if (r["statut"] or "").lower() in {"brouillon", "en attente"})
        depenses_total = sum(Decimal(r["montant"]) for r in depenses) if depenses else Decimal("0")
        ca_total = sum(Decimal(r["montant_ttc"]) for r in factures) if factures else Decimal("0")

        self.kpi_devis[1].setText(str(devis_count))
        self.kpi_factures[1].setText(str(factures_count))
        self.kpi_attente[1].setText(str(attente_count))
        self.kpi_depenses[1].setText(f"{depenses_total:.2f} EUR")
        self.kpi_ca[1].setText(f"{ca_total:.2f} EUR")

        self.dashboard_devis_table.setRowCount(min(8, len(devis_list)))
        for i, devis in enumerate(devis_list[:8]):
            self.dashboard_devis_table.setItem(i, 0, QTableWidgetItem(devis.numero))
            self.dashboard_devis_table.setItem(i, 1, QTableWidgetItem(devis.client.nom))
            self.dashboard_devis_table.setItem(i, 2, QTableWidgetItem(devis.date_devis.strftime("%d/%m/%Y")))
            self.dashboard_devis_table.setItem(i, 3, QTableWidgetItem(f"{devis.calculer_total_ttc():.2f} €"))

        self.dashboard_factures_table.setRowCount(min(8, len(factures)))
        for i, row in enumerate(factures[:8]):
            self.dashboard_factures_table.setItem(i, 0, QTableWidgetItem(row["numero"]))
            self.dashboard_factures_table.setItem(i, 1, QTableWidgetItem(row["client_nom"]))
            self.dashboard_factures_table.setItem(i, 2, QTableWidgetItem(row["projet"]))
            self.dashboard_factures_table.setItem(i, 3, QTableWidgetItem(f"{Decimal(row['montant_ttc']):.2f} €"))

        # Alertes
        critical_alerts: list[dict[str, str]] = []
        warning_alerts: list[dict[str, str]] = []
        info_alerts: list[dict[str, str]] = []

        for row in factures:
            facture_id = int(row["id"])
            numero = row["numero"]
            client = row["client_nom"] or "Client non renseigné"
            ttc = Decimal(row["montant_ttc"])
            dep = self.storage.total_depenses_facture(facture_id)
            if ttc > 0:
                ratio = (dep / ttc) * Decimal("100")
                alert = {"title": f"{numero} • {client}", "summary": f"Dépenses à {ratio:.1f}% ({dep:.2f}/{ttc:.2f} EUR).", "action": ""}
                if ratio >= Decimal("90"):
                    alert["action"] = "Vérifier la marge immédiatement."
                    critical_alerts.append(alert)
                elif ratio >= Decimal("70"):
                    alert["action"] = "Surveiller les prochains coûts."
                    warning_alerts.append(alert)

        if not factures:
            info_alerts.append({"title": "Aucune facture", "summary": "Le suivi d'alertes est actif.", "action": "Créez une facture pour démarrer."})
        if not critical_alerts and not warning_alerts and not info_alerts:
            info_alerts.append({"title": "Aucun risque financier détecté", "summary": "Situation saine.", "action": "Maintenir le suivi actuel."})

        def _card(level: str, title: str, summary: str, action: str, bg: str, border: str, badge_bg: str, badge_fg: str) -> str:
            return (
                f"<div style='margin:0 0 14px 0; padding:13px; background:{bg}; border:1px solid {border}; border-radius:14px;'>"
                f"<div style='margin-bottom:6px;'><span style='background:{badge_bg}; color:{badge_fg}; font-weight:700; font-size:11px; padding:3px 9px; border-radius:10px;'>{html_escape(level)}</span></div>"
                f"<div style='font-weight:700; color:#0F172A; margin-bottom:4px;'>{html_escape(title)}</div>"
                f"<div style='color:#334155; line-height:1.45; margin-bottom:4px;'>{html_escape(summary)}</div>"
                f"<div style='color:#0F172A; font-weight:600;'>Action : {html_escape(action)}</div>"
                "</div>"
            )

        html_parts = ["<div style='font-family:Segoe UI,Arial; font-size:13px; padding:2px;'>"]
        for a in critical_alerts[:4]:
            html_parts.append(_card("CRITIQUE", a["title"], a["summary"], a["action"], "#FEF2F2", "#FCA5A5", "#B91C1C", "#FFFFFF"))
        for a in warning_alerts[:6]:
            html_parts.append(_card("ATTENTION", a["title"], a["summary"], a["action"], "#FFFBEB", "#FCD34D", "#B45309", "#FFFFFF"))
        for a in info_alerts[:4]:
            html_parts.append(_card("INFO", a["title"], a["summary"], a["action"], "#EFF6FF", "#BFDBFE", "#1D4ED8", "#FFFFFF"))
        html_parts.append("</div>")
        self.alerts_box.setHtml("".join(html_parts))
