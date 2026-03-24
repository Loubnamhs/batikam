"""Fenetre principale de l'application."""


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
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.devis import Devis
from app.services.branding import resolve_logo_path
from app.services.export_docx import DOCXExporter
from app.services.export_pdf import PDFExporter
from app.services.storage_sqlite import StorageSQLite
from app.ui.devis_editor import DevisEditorWidget
from app.ui.feedback import show_confirm, show_error, show_loading, show_success
from app.ui.theme import add_shadow, make_card


class FacturesWidget(QWidget):
    """Module de gestion des factures."""

    def __init__(
        self,
        storage: StorageSQLite,
        selected_devis_provider: Callable[[], Optional[Devis]],
        on_data_changed: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.storage = storage
        self.selected_devis_provider = selected_devis_provider
        self.on_data_changed = on_data_changed
        self.current_facture_id: Optional[int] = None
        self.current_facture_devis: Optional[Devis] = None
        self._client_map: dict[str, int] = {}
        self._project_map: dict[str, int] = {}
        self._facture_map: dict[str, int] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        header_card = make_card("PageHeaderCard")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(10)
        title_box = QVBoxLayout()
        title = QLabel("Gestion des factures")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Créer, éditer, exporter et suivre les statuts des factures")
        subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        self.btn_import_devis = QPushButton("Importer devis ouvert")
        self.btn_import_devis.setProperty("variant", "primary")
        self.btn_import_devis.clicked.connect(self._on_create_from_open_devis)
        self.btn_refresh = QPushButton("Rafraîchir")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_save_facture = QPushButton("Sauvegarder facture")
        self.btn_save_facture.setProperty("variant", "primary")
        self.btn_save_facture.clicked.connect(self._on_save_facture)
        self.btn_delete_facture = QPushButton("Supprimer facture")
        self.btn_delete_facture.setProperty("variant", "danger")
        self.btn_delete_facture.clicked.connect(self._on_delete_facture)
        header_layout.addWidget(self.btn_refresh)
        header_layout.addWidget(self.btn_import_devis)
        header_layout.addWidget(self.btn_save_facture)
        header_layout.addWidget(self.btn_delete_facture)
        root.addWidget(header_card)

        filters_card = make_card("ToolbarCard")
        filters_layout = QHBoxLayout(filters_card)
        filters_layout.setContentsMargins(14, 10, 14, 10)
        filters_layout.setSpacing(10)
        self.client_combo = QComboBox()
        self.client_combo.currentTextChanged.connect(self._on_client_changed)
        self.projet_combo = QComboBox()
        self.projet_combo.currentTextChanged.connect(self._on_project_changed)
        self.facture_combo = QComboBox()
        self.facture_combo.currentTextChanged.connect(self._on_facture_combo_changed)
        filters_layout.addWidget(QLabel("Client"))
        filters_layout.addWidget(self.client_combo, 1)
        filters_layout.addWidget(QLabel("Projet"))
        filters_layout.addWidget(self.projet_combo, 1)
        filters_layout.addWidget(QLabel("Facture"))
        filters_layout.addWidget(self.facture_combo, 1)
        root.addWidget(filters_card)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)

        table_card = make_card("SectionCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(10)
        table_title = QLabel("Liste des factures")
        table_title.setProperty("variant", "title")
        table_layout.addWidget(table_title)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["N°", "Date", "Client", "Projet", "TTC", "Statut"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        table_layout.addWidget(self.table)
        split.addWidget(table_card)

        editor_card = make_card("SectionCard")
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(10, 10, 10, 10)
        editor_layout.setSpacing(8)
        editor_title = QLabel("Édition facture")
        editor_title.setProperty("variant", "title")
        editor_layout.addWidget(editor_title)

        self.btn_export_pdf = QPushButton("Export PDF")
        self.btn_export_pdf.clicked.connect(self._on_export_pdf)
        self.btn_export_docx = QPushButton("Export DOCX")
        self.btn_export_docx.clicked.connect(self._on_export_docx)

        self.editor = DevisEditorWidget()
        self.editor.set_number_label("N° facture")
        self.editor.set_export_buttons(self.btn_export_pdf, self.btn_export_docx)
        editor_layout.addWidget(self.editor)
        split.addWidget(editor_card)

        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 9)

        add_shadow(header_card, blur=20, y_offset=2, color="#0F172A22")
        add_shadow(filters_card, blur=16, y_offset=2, color="#0F172A18")

    def _selected_facture_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.UserRole)
        return int(value) if value is not None else None

    def refresh(self, select_facture_id: Optional[int] = None) -> None:
        self._client_map.clear()
        self.client_combo.blockSignals(True)
        self.client_combo.clear()
        self.client_combo.addItem("-- Sélectionner --")
        for row in self.storage.list_clients():
            label = row["nom"]
            self._client_map[label] = int(row["id"])
            self.client_combo.addItem(label)
        self.client_combo.blockSignals(False)
        self._on_client_changed(self.client_combo.currentText())
        if select_facture_id is not None:
            self._select_facture_by_id(select_facture_id)

    def _on_client_changed(self, text: str) -> None:
        client_id = self._client_map.get(text)
        self._project_map.clear()
        self.projet_combo.blockSignals(True)
        self.projet_combo.clear()
        self.projet_combo.addItem("-- Sélectionner --")
        if client_id is not None:
            for row in self.storage.list_projets_by_client(client_id):
                label = row["nom"]
                self._project_map[label] = int(row["id"])
                self.projet_combo.addItem(label)
        self.projet_combo.blockSignals(False)
        self._on_project_changed(self.projet_combo.currentText())

    def _on_project_changed(self, text: str) -> None:
        projet_id = self._project_map.get(text)
        self._facture_map.clear()
        self.facture_combo.blockSignals(True)
        self.facture_combo.clear()
        self.facture_combo.addItem("-- Toutes --")
        rows = self.storage.list_factures_by_projet(projet_id) if projet_id is not None else []
        for row in rows:
            label = row["numero"]
            self._facture_map[label] = int(row["id"])
            self.facture_combo.addItem(label)
        self.facture_combo.blockSignals(False)
        self._fill_table(rows)

    def _on_facture_combo_changed(self, text: str) -> None:
        facture_id = self._facture_map.get(text)
        if facture_id is not None:
            self._select_facture_by_id(facture_id)

    def _fill_table(self, rows: list) -> None:
        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            numero = QTableWidgetItem(row["numero"])
            numero.setData(Qt.UserRole, row["id"])
            self.table.setItem(row_idx, 0, numero)
            self.table.setItem(row_idx, 1, QTableWidgetItem(row["date_facture"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(row["client_nom"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(row["projet"]))
            self.table.setItem(row_idx, 4, QTableWidgetItem(f"{Decimal(row['montant_ttc']):.2f} EUR"))
            self.table.setItem(row_idx, 5, QTableWidgetItem(row["statut"]))

    def _select_facture_by_id(self, facture_id: int) -> None:
        for row_idx in range(self.table.rowCount()):
            item = self.table.item(row_idx, 0)
            if item and item.data(Qt.UserRole) == facture_id:
                self.table.selectRow(row_idx)
                break

    def _current_facture_devis(self) -> Optional[Devis]:
        if self.current_facture_devis is not None:
            return self.current_facture_devis
        if self.current_facture_id is None:
            return None
        self.current_facture_devis = self.storage.read_facture_devis(self.current_facture_id)
        return self.current_facture_devis

    def _on_select(self) -> None:
        facture_id = self._selected_facture_id()
        if facture_id is None:
            return
        devis = self.storage.read_facture_devis(facture_id)
        if devis is None:
            return
        self.current_facture_id = facture_id
        self.current_facture_devis = devis
        self.editor.set_devis(devis)

    def _on_create_from_open_devis(self) -> None:
        devis = self.selected_devis_provider()
        if devis is None:
            show_error(self, "Devis requis", "Ouvrez d'abord un devis dans Gestion des devis.")
            return
        loading = show_loading(self, "Facturation", "Promotion du devis en facture...")
        try:
            facture_id = self.storage.create_facture_from_devis(devis)
            loading.close()
            self.refresh(select_facture_id=facture_id)
            if self.on_data_changed:
                self.on_data_changed()
            self._prompt_export_generated_facture(facture_id)
            show_success(self, "Succès", f"Le devis {devis.numero} a été converti en facture.")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Impossible de créer la facture:\n{exc}")

    def _prompt_export_generated_facture(self, facture_id: int) -> Optional[str]:
        facture_devis = self.storage.read_facture_devis(facture_id)
        if facture_devis is None:
            return None
        facture_devis.statut = "Facture"
        default_base = f"facture_{facture_devis.numero or 'sans_numero'}"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Choisir le chemin d'export de la facture",
            f"{default_base}.pdf",
            "PDF Files (*.pdf);;DOCX Files (*.docx)",
        )
        if not file_path:
            return None

        is_docx = "docx" in selected_filter.lower() or file_path.lower().endswith(".docx")
        if is_docx and not file_path.lower().endswith(".docx"):
            file_path = f"{file_path}.docx"
        if not is_docx and not file_path.lower().endswith(".pdf"):
            file_path = f"{file_path}.pdf"

        loading = show_loading(self, "Export", "Export de la facture générée...")
        try:
            if is_docx:
                DOCXExporter().export(facture_devis, file_path)
            else:
                PDFExporter(logo_path=self.editor.logo_path).export(facture_devis, file_path)
            loading.close()
            show_success(self, "Succès", f"Facture exportée:\n{file_path}")
            return file_path
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Export impossible:\n{exc}")
            return None

    def _on_save_facture(self) -> None:
        if self.current_facture_id is None:
            show_error(self, "Facture requise", "Sélectionnez ou créez une facture.")
            return
        devis = self.editor.get_devis_from_ui()
        if devis is None:
            show_error(self, "Erreur", "Impossible de lire les données facture.")
            return
        devis.statut = "Facture"
        loading = show_loading(self, "Facturation", "Enregistrement de la facture...")
        try:
            self.storage.update_facture_devis(self.current_facture_id, devis, statut="Brouillon")
            loading.close()
            self.refresh(select_facture_id=self.current_facture_id)
            if self.on_data_changed:
                self.on_data_changed()
            show_success(self, "Succès", "Facture enregistrée.")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Enregistrement impossible:\n{exc}")

    def _on_delete_facture(self) -> None:
        facture_id = self._selected_facture_id()
        if facture_id is None:
            show_error(self, "Facture requise", "Sélectionnez une facture.")
            return

        facture = self.storage.read_facture(facture_id)
        if facture is None:
            show_error(self, "Attention", "Facture introuvable.")
            return

        if not show_confirm(self, "Confirmation", f"Supprimer la facture {facture['numero']} ?"):
            return

        if self.storage.delete_facture(facture_id):
            if self.current_facture_id == facture_id:
                self.current_facture_id = None
                self.current_facture_devis = None
                self.editor.set_devis(None)
            self.refresh()
            if self.on_data_changed:
                self.on_data_changed()
            show_success(self, "Succès", "Facture supprimée.")

    def _on_export_pdf(self) -> None:
        devis = self._current_facture_devis()
        if devis is None:
            show_error(self, "Facture requise", "Sélectionnez une facture.")
            return
        devis = self.editor.get_devis_from_ui() or devis
        devis.statut = "Facture"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exporter facture en PDF", f"facture_{devis.numero or 'sans_numero'}.pdf", "PDF Files (*.pdf)"
        )
        if not file_path:
            return
        loading = show_loading(self, "Export PDF", "Export en cours...")
        try:
            PDFExporter(logo_path=self.editor.logo_path).export(devis, file_path)
            loading.close()
            show_success(self, "Succès", f"Facture PDF exportée:\n{file_path}")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Export PDF impossible:\n{exc}")

    def _on_export_docx(self) -> None:
        devis = self._current_facture_devis()
        if devis is None:
            show_error(self, "Facture requise", "Sélectionnez une facture.")
            return
        devis = self.editor.get_devis_from_ui() or devis
        devis.statut = "Facture"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exporter facture en DOCX", f"facture_{devis.numero or 'sans_numero'}.docx", "DOCX Files (*.docx)"
        )
        if not file_path:
            return
        loading = show_loading(self, "Export DOCX", "Export en cours...")
        try:
            DOCXExporter().export(devis, file_path)
            loading.close()
            show_success(self, "Succès", f"Facture DOCX exportée:\n{file_path}")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Export DOCX impossible:\n{exc}")


class SuiviProjetWidget(QWidget):
    """Module de suivi des dépenses par facture/projet/client."""

    CATEGORIES = ["Salaire", "Fourniture", "Produit", "Matérielle", "Main oeuvre", "Carburant", "Autre"]
    ACOMPTE_MODE_PERCENT = "percent"
    ACOMPTE_MODE_TTC = "ttc"

    def __init__(self, storage: StorageSQLite, on_data_changed: Optional[Callable[[], None]] = None):
        super().__init__()
        self.storage = storage
        self.on_data_changed = on_data_changed
        self._client_map: dict[str, int] = {}
        self._project_map: dict[str, int] = {}
        self._facture_map: dict[str, int] = {}
        self._build_ui()
        self.refresh_factures()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        header_card = make_card("PageHeaderCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(4)
        title = QLabel("Suivi projet et dépenses")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Contrôlez budget, marge et seuil d'alerte par facture/projet")
        subtitle.setObjectName("PageSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header_card)

        filters_card = make_card("ToolbarCard")
        filters = QHBoxLayout(filters_card)
        filters.setContentsMargins(14, 10, 14, 10)
        filters.setSpacing(10)
        self.client_combo = QComboBox()
        self.client_combo.currentTextChanged.connect(self._on_client_changed)
        self.projet_combo = QComboBox()
        self.projet_combo.currentTextChanged.connect(self._on_projet_changed)
        self.facture_combo = QComboBox()
        self.facture_combo.currentTextChanged.connect(self._on_facture_changed)
        self.seuil_spin = QDoubleSpinBox()
        self.seuil_spin.setRange(0, 100)
        self.seuil_spin.setValue(70)
        self.seuil_spin.setSuffix(" %")
        self.seuil_spin.valueChanged.connect(self._refresh_status)
        filters.addWidget(QLabel("Client"))
        filters.addWidget(self.client_combo, 1)
        filters.addWidget(QLabel("Projet"))
        filters.addWidget(self.projet_combo, 1)
        filters.addWidget(QLabel("Facture"))
        filters.addWidget(self.facture_combo, 1)
        filters.addWidget(QLabel("Seuil alerte"))
        filters.addWidget(self.seuil_spin)
        root.addWidget(filters_card)

        acompte_card = make_card("ToolbarCard")
        acompte_layout = QHBoxLayout(acompte_card)
        acompte_layout.setContentsMargins(14, 10, 14, 10)
        acompte_layout.setSpacing(10)
        self.acompte_mode_combo = QComboBox()
        self.acompte_mode_combo.addItem("Pourcentage (%)", self.ACOMPTE_MODE_PERCENT)
        self.acompte_mode_combo.addItem("Montant TTC (EUR)", self.ACOMPTE_MODE_TTC)
        self.acompte_mode_combo.currentIndexChanged.connect(self._on_acompte_mode_changed)
        self.acompte_value_spin = QDoubleSpinBox()
        self.acompte_value_spin.setDecimals(2)
        self.acompte_value_spin.setRange(0.01, 100.0)
        self.acompte_value_spin.setValue(30.0)
        self.acompte_value_spin.setSuffix(" %")
        self.acompte_value_spin.valueChanged.connect(self._refresh_acompte_preview)
        self.acompte_preview_label = QLabel("Sélectionnez une facture pour générer une facture d'acompte.")
        self.acompte_preview_label.setObjectName("PageSubtitle")
        self.btn_generate_acompte = QPushButton("Générer facture d'acompte")
        self.btn_generate_acompte.setProperty("variant", "primary")
        self.btn_generate_acompte.clicked.connect(self._on_generate_acompte_facture)
        self.btn_generate_acompte.setEnabled(False)
        acompte_layout.addWidget(QLabel("Acompte"))
        acompte_layout.addWidget(self.acompte_mode_combo)
        acompte_layout.addWidget(self.acompte_value_spin)
        acompte_layout.addWidget(self.acompte_preview_label, 1)
        acompte_layout.addWidget(self.btn_generate_acompte)
        root.addWidget(acompte_card)

        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(10)
        kpi_grid.setVerticalSpacing(10)
        self.kpi_ttc = self._kpi_card("Montant facture", "0,00 EUR")
        self.kpi_depenses = self._kpi_card("Dépenses", "0,00 EUR")
        self.kpi_reste = self._kpi_card("Reste", "0,00 EUR")
        self.kpi_ratio = self._kpi_card("Taux dépenses", "0,0%")
        kpi_grid.addWidget(self.kpi_ttc[0], 0, 0)
        kpi_grid.addWidget(self.kpi_depenses[0], 0, 1)
        kpi_grid.addWidget(self.kpi_reste[0], 0, 2)
        kpi_grid.addWidget(self.kpi_ratio[0], 0, 3)
        root.addLayout(kpi_grid)

        self.status_label = QLabel("Aucune facture sélectionnée.")
        self.status_label.setObjectName("SuiviStatus")
        self.status_label.setProperty("zone", "neutral")
        root.addWidget(self.status_label)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)

        table_card = make_card("SectionCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(10)
        table_title = QLabel("Dépenses")
        table_title.setProperty("variant", "title")
        table_layout.addWidget(table_title)

        self.depenses_table = QTableWidget(0, 6)
        self.depenses_table.setHorizontalHeaderLabels(["Date", "Client", "Projet", "Catégorie", "Montant", "Notes"])
        self.depenses_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.depenses_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.depenses_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.depenses_table.setAlternatingRowColors(True)
        self.depenses_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.depenses_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        table_layout.addWidget(self.depenses_table)
        split.addWidget(table_card)

        form_card = make_card("SectionCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(10)
        form_title = QLabel("Ajouter une dépense")
        form_title.setProperty("variant", "title")
        form_layout.addWidget(form_title)
        fields = QFormLayout()
        fields.setHorizontalSpacing(10)
        fields.setVerticalSpacing(10)
        self.dep_client = QLineEdit()
        self.dep_projet = QLineEdit()
        self.dep_cat = QComboBox()
        self.dep_cat.addItems(self.CATEGORIES)
        self.dep_montant = QDoubleSpinBox()
        self.dep_montant.setRange(0, 10_000_000)
        self.dep_montant.setDecimals(2)
        self.dep_montant.setSuffix(" EUR")
        self.dep_notes = QTextEdit()
        self.dep_notes.setMaximumHeight(110)
        fields.addRow("Client", self.dep_client)
        fields.addRow("Projet", self.dep_projet)
        fields.addRow("Catégorie", self.dep_cat)
        fields.addRow("Montant", self.dep_montant)
        fields.addRow("Notes", self.dep_notes)
        form_layout.addLayout(fields)
        self.add_dep_btn = QPushButton("Ajouter dépense")
        self.add_dep_btn.setProperty("variant", "primary")
        self.add_dep_btn.clicked.connect(self._on_add_depense)
        form_layout.addWidget(self.add_dep_btn)
        form_layout.addStretch()
        split.addWidget(form_card)

        split.setStretchFactor(0, 7)
        split.setStretchFactor(1, 4)

        add_shadow(header_card, blur=20, y_offset=2, color="#0F172A22")
        add_shadow(filters_card, blur=16, y_offset=2, color="#0F172A18")

    def _kpi_card(self, label: str, value: str) -> tuple[QFrame, QLabel]:
        card = make_card("DashboardKpi")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        kpi_label = QLabel(label)
        kpi_label.setObjectName("KpiLabel")
        kpi_value = QLabel(value)
        kpi_value.setObjectName("KpiValue")
        layout.addWidget(kpi_label)
        layout.addWidget(kpi_value)
        return card, kpi_value

    def refresh_factures(self) -> None:
        self._client_map.clear()
        self.client_combo.blockSignals(True)
        self.client_combo.clear()
        self.client_combo.addItem("-- Sélectionner --")
        for row in self.storage.list_clients():
            label = row["nom"]
            self._client_map[label] = int(row["id"])
            self.client_combo.addItem(label)
        self.client_combo.blockSignals(False)
        self._on_client_changed(self.client_combo.currentText())

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
            self.acompte_preview_label.setText("Sélectionnez une facture pour générer une facture d'acompte.")
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

    def _prompt_export_generated_facture(self, facture_id: int) -> Optional[str]:
        facture_devis = self.storage.read_facture_devis(facture_id)
        if facture_devis is None:
            return None
        facture_devis.statut = "Facture"
        default_base = f"facture_{facture_devis.numero or 'sans_numero'}"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Choisir le chemin d'export de la facture",
            f"{default_base}.pdf",
            "PDF Files (*.pdf);;DOCX Files (*.docx)",
        )
        if not file_path:
            return None

        is_docx = "docx" in selected_filter.lower() or file_path.lower().endswith(".docx")
        if is_docx and not file_path.lower().endswith(".docx"):
            file_path = f"{file_path}.docx"
        if not is_docx and not file_path.lower().endswith(".pdf"):
            file_path = f"{file_path}.pdf"

        loading = show_loading(self, "Export", "Export de la facture générée...")
        try:
            if is_docx:
                DOCXExporter().export(facture_devis, file_path)
            else:
                PDFExporter().export(facture_devis, file_path)
            loading.close()
            show_success(self, "Succès", f"Facture exportée:\n{file_path}")
            return file_path
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Export impossible:\n{exc}")
            return None

    def _refresh_acompte_preview(self) -> None:
        facture_id = self._current_facture_id()
        facture = self.storage.read_facture(facture_id) if facture_id is not None else None
        if facture is None:
            self.acompte_preview_label.setText("Sélectionnez une facture pour générer une facture d'acompte.")
            return
        total_ttc = Decimal(str(facture["montant_ttc"] or "0"))
        if total_ttc <= 0:
            self.acompte_preview_label.setText("La facture sélectionnée a un montant TTC nul.")
            return
        acompte_ttc = self._compute_acompte_ttc(total_ttc)
        self.acompte_preview_label.setText(
            f"Acompte prévu: {acompte_ttc:.2f} EUR TTC sur {facture['numero']} (base {total_ttc:.2f} EUR TTC)."
        )

    def _select_facture_by_id(self, facture_id: int) -> None:
        for label, mapped_id in self._facture_map.items():
            if mapped_id == facture_id:
                self.facture_combo.setCurrentText(label)
                return

    def _current_facture_id(self) -> Optional[int]:
        text = self.facture_combo.currentText()
        return self._facture_map.get(text)

    def _on_client_changed(self, text: str) -> None:
        client_id = self._client_map.get(text)
        self._project_map.clear()
        self.projet_combo.blockSignals(True)
        self.projet_combo.clear()
        self.projet_combo.addItem("-- Sélectionner --")
        if client_id is not None:
            for row in self.storage.list_projets_by_client(client_id):
                label = row["nom"]
                self._project_map[label] = int(row["id"])
                self.projet_combo.addItem(label)
        self.projet_combo.blockSignals(False)
        self._on_projet_changed(self.projet_combo.currentText())

    def _on_projet_changed(self, text: str) -> None:
        projet_id = self._project_map.get(text)
        self._facture_map.clear()
        self.facture_combo.blockSignals(True)
        self.facture_combo.clear()
        self.facture_combo.addItem("-- Sélectionner --")
        if projet_id is not None:
            for row in self.storage.list_factures_by_projet(projet_id):
                label = row["numero"]
                self._facture_map[label] = int(row["id"])
                self.facture_combo.addItem(label)
        self.facture_combo.blockSignals(False)
        self._on_facture_changed(self.facture_combo.currentText())

    def _on_facture_changed(self, _: str) -> None:
        facture_id = self._current_facture_id()
        self.depenses_table.setRowCount(0)
        if facture_id is None:
            self.status_label.setProperty("zone", "neutral")
            self.status_label.setText("Aucune facture sélectionnée.")
            self._restyle_status()
            self.dep_client.clear()
            self.dep_projet.clear()
            self._set_kpis(Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))
            self._sync_acompte_controls()
            return

        facture = self.storage.read_facture(facture_id)
        if facture is not None:
            self.dep_client.setText(facture["client_nom"])
            self.dep_projet.setText(facture["projet"])

        self._sync_acompte_controls()
        self._refresh_acompte_preview()
        self._refresh_depenses()
        self._refresh_status()

    def _refresh_depenses(self) -> None:
        facture_id = self._current_facture_id()
        if facture_id is None:
            return
        rows = self.storage.list_depenses(facture_id=facture_id)
        self.depenses_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.depenses_table.setItem(r, 0, QTableWidgetItem(row["date_depense"]))
            self.depenses_table.setItem(r, 1, QTableWidgetItem(row["client_nom"]))
            self.depenses_table.setItem(r, 2, QTableWidgetItem(row["projet"]))
            self.depenses_table.setItem(r, 3, QTableWidgetItem(row["categorie"]))
            self.depenses_table.setItem(r, 4, QTableWidgetItem(f"{Decimal(row['montant']):.2f} EUR"))
            self.depenses_table.setItem(r, 5, QTableWidgetItem(row["notes"] or ""))

    def _set_kpis(self, ttc: Decimal, depenses: Decimal, reste: Decimal, ratio: Decimal) -> None:
        self.kpi_ttc[1].setText(f"{ttc:.2f} EUR")
        self.kpi_depenses[1].setText(f"{depenses:.2f} EUR")
        self.kpi_reste[1].setText(f"{reste:.2f} EUR")
        self.kpi_ratio[1].setText(f"{ratio:.1f}%")

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
            f"Reste: {reste:.2f} EUR | Taux dépenses: {ratio:.1f}%"
        )
        self._restyle_status()

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
                show_error(self, "Acompte invalide", "Le pourcentage doit être compris entre 0 et 100.")
                return
        else:
            if value <= 0:
                show_error(self, "Acompte invalide", "Le montant TTC d'acompte doit être strictement positif.")
                return
            if value > total_ttc:
                show_error(
                    self,
                    "Acompte invalide",
                    "Le montant TTC d'acompte ne peut pas dépasser le TTC de la facture source.",
                )
                return

        client_text = self.client_combo.currentText()
        projet_text = self.projet_combo.currentText()
        loading = show_loading(self, "Acompte", "Génération de la facture d'acompte...")
        try:
            new_facture_id = self.storage.create_facture_acompte_from_facture(
                source_facture_id=source_facture_id,
                mode=str(mode),
                value=value,
            )
            self.refresh_factures()
            if client_text in self._client_map:
                self.client_combo.setCurrentText(client_text)
            if projet_text in self._project_map:
                self.projet_combo.setCurrentText(projet_text)
            self._select_facture_by_id(new_facture_id)
            loading.close()
            if self.on_data_changed:
                self.on_data_changed()
            self._prompt_export_generated_facture(new_facture_id)
            new_row = self.storage.read_facture(new_facture_id)
            new_numero = new_row["numero"] if new_row is not None else str(new_facture_id)
            show_success(self, "Succès", f"Facture d'acompte générée: {new_numero}")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Impossible de générer la facture d'acompte:\n{exc}")

    def _on_add_depense(self) -> None:
        facture_id = self._current_facture_id()
        if facture_id is None:
            show_error(self, "Facture requise", "Sélectionnez d'abord une facture.")
            return

        client = self.dep_client.text().strip()
        projet = self.dep_projet.text().strip()
        if not client or not projet:
            show_error(self, "Champs requis", "Client et projet sont obligatoires.")
            return

        self.storage.add_depense(
            facture_id=facture_id,
            client_nom=client,
            projet=projet,
            categorie=self.dep_cat.currentText(),
            montant=Decimal(str(self.dep_montant.value())),
            notes=self.dep_notes.toPlainText().strip(),
        )
        self.dep_montant.setValue(0)
        self.dep_notes.clear()
        self._refresh_depenses()
        self._refresh_status()
        if self.on_data_changed:
            self.on_data_changed()
        show_success(self, "Succès", "Dépense ajoutée.")


class MainWindow(QMainWindow):
    """Fenêtre principale."""

    def __init__(self):
        super().__init__()
        self.storage = StorageSQLite()
        self.current_devis: Optional[Devis] = None

        self.setWindowTitle("Batikam Renove - Gestion")
        self.setGeometry(90, 80, 1600, 940)
        self.setMinimumSize(1320, 800)

        logo_path = resolve_logo_path()
        if logo_path:
            self.setWindowIcon(QIcon(str(logo_path)))

        # Export buttons are reparented to preview tabs (devis/facture)
        self.btn_export_pdf = QPushButton("Export PDF")
        self.btn_export_docx = QPushButton("Export DOCX")
        self.btn_export_pdf.clicked.connect(self._on_export_pdf)
        self.btn_export_docx.clicked.connect(self._on_export_docx)

        central = QWidget()
        central.setObjectName("AppRoot")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        self.nav_panel = self._build_navigation()
        root.addWidget(self.nav_panel)

        self.content_panel = QWidget()
        content_layout = QVBoxLayout(self.content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        content_layout.addWidget(self._build_top_header())

        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages, 1)

        self.home_page = self._build_home_page()
        self.devis_page = self._build_devis_page()
        self.factures_widget = FacturesWidget(
            self.storage,
            self._current_devis_for_invoice,
            on_data_changed=self._refresh_dashboard,
        )
        self.suivi_widget = SuiviProjetWidget(self.storage, on_data_changed=self._refresh_dashboard)

        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.devis_page)
        self.pages.addWidget(self.factures_widget)
        self.pages.addWidget(self.suivi_widget)

        root.addWidget(self.content_panel, 1)

        self._refresh_devis_list()
        self._refresh_dashboard()
        self._switch_page("home")

    def _build_navigation(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("NavSidebar")
        panel.setMinimumWidth(270)
        panel.setMaximumWidth(300)
        add_shadow(panel, blur=26, y_offset=4, color="#0F172A26")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        logo_shell = QFrame()
        logo_shell.setObjectName("NavLogoShell")
        logo_shell.setMinimumHeight(180)
        shell_layout = QVBoxLayout(logo_shell)
        shell_layout.setContentsMargins(12, 12, 12, 12)
        shell_layout.setSpacing(8)
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_path = resolve_logo_path()
        if logo_path:
            pixmap = QPixmap(str(logo_path)).scaled(220, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
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

    def _build_top_header(self) -> QWidget:
        top = make_card("TopHeader")
        add_shadow(top, blur=18, y_offset=2, color="#0F172A1A")
        layout = QHBoxLayout(top)
        layout.setContentsMargins(18, 12, 18, 12)
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

        self.quick_refresh_btn = QPushButton("Rafraîchir données")
        self.quick_refresh_btn.clicked.connect(self._refresh_all_views)
        layout.addWidget(self.quick_refresh_btn)

        return top

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
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(12, 12, 12, 12)
        recent_layout.setSpacing(8)
        recent_title = QLabel("Devis récents")
        recent_title.setProperty("variant", "title")
        self.dashboard_devis_table = QTableWidget(0, 4)
        self.dashboard_devis_table.setHorizontalHeaderLabels(["N°", "Client", "Date", "TTC"])
        self.dashboard_devis_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dashboard_devis_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dashboard_devis_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.dashboard_devis_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        recent_layout.addWidget(recent_title)
        recent_layout.addWidget(self.dashboard_devis_table)
        bottom.addWidget(recent_card)

        fact_card = make_card("SectionCard")
        fact_layout = QVBoxLayout(fact_card)
        fact_layout.setContentsMargins(12, 12, 12, 12)
        fact_layout.setSpacing(8)
        fact_title = QLabel("Factures récentes")
        fact_title.setProperty("variant", "title")
        self.dashboard_factures_table = QTableWidget(0, 4)
        self.dashboard_factures_table.setHorizontalHeaderLabels(["N°", "Client", "Projet", "TTC"])
        self.dashboard_factures_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dashboard_factures_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dashboard_factures_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.dashboard_factures_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        fact_layout.addWidget(fact_title)
        fact_layout.addWidget(self.dashboard_factures_table)
        bottom.addWidget(fact_card)

        alert_card = make_card("SectionCard")
        alert_layout = QVBoxLayout(alert_card)
        alert_layout.setContentsMargins(12, 12, 12, 12)
        alert_layout.setSpacing(8)
        alert_title = QLabel("Alertes")
        alert_title.setProperty("variant", "title")
        self.alerts_box = QTextEdit()
        self.alerts_box.setReadOnly(True)
        self.alerts_box.setObjectName("AlertsBox")
        alert_layout.addWidget(alert_title)
        alert_layout.addWidget(self.alerts_box)
        bottom.addWidget(alert_card)

        bottom.setStretchFactor(0, 3)
        bottom.setStretchFactor(1, 3)
        bottom.setStretchFactor(2, 2)

        return page

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

    def _build_devis_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        header = make_card("PageHeaderCard")
        add_shadow(header, blur=20, y_offset=2, color="#0F172A22")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        title = QLabel("Gestion des devis")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Prospects, lots, lignes, aperçu et exports")
        subtitle.setObjectName("PageSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header)

        self.editor = DevisEditorWidget()
        self.editor.devis_changed.connect(self._on_devis_changed)
        self.editor.set_export_buttons(self.btn_export_pdf, self.btn_export_docx)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)

        split.addWidget(self._build_left_panel())

        editor_card = make_card("SectionCard")
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(10, 10, 10, 10)
        editor_layout.addWidget(self.editor)
        split.addWidget(editor_card)

        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 10)
        return page

    def _build_left_panel(self) -> QWidget:
        panel = make_card("SideListCard")
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(360)
        add_shadow(panel, blur=22, y_offset=4, color="#0F172A1F")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Liste des devis")
        title.setProperty("variant", "title")
        layout.addWidget(title)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher numéro, client, affaire...")
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        self.devis_table = QTableWidget(0, 6)
        self.devis_table.setHorizontalHeaderLabels(["N°", "Client", "Affaire", "Date", "TTC", "Statut"])
        self.devis_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.devis_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.devis_table.itemDoubleClicked.connect(self._on_devis_double_clicked)
        self.devis_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.devis_table.setAlternatingRowColors(True)
        self.devis_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.devis_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.devis_table, 1)

        actions_card = make_card("ToolbarCard")
        actions = QVBoxLayout(actions_card)
        actions.setContentsMargins(8, 8, 8, 8)
        actions.setSpacing(8)

        self.btn_new = QPushButton("Nouveau")
        self.btn_new.setProperty("variant", "primary")
        self.btn_new.clicked.connect(self._on_new_devis)
        self.btn_duplicate = QPushButton("Dupliquer")
        self.btn_duplicate.clicked.connect(self._on_duplicate_devis)
        self.btn_open = QPushButton("Ouvrir")
        self.btn_open.clicked.connect(self._on_open_devis)
        self.btn_validate = QPushButton("Valider prospect")
        self.btn_validate.clicked.connect(self._on_validate_prospect)
        self.btn_delete = QPushButton("Supprimer")
        self.btn_delete.setProperty("variant", "danger")
        self.btn_delete.clicked.connect(self._on_delete_devis)

        actions.addWidget(self.btn_new)
        actions.addWidget(self.btn_duplicate)
        actions.addWidget(self.btn_open)
        actions.addWidget(self.btn_validate)
        actions.addWidget(self.btn_delete)
        layout.addWidget(actions_card)

        return panel

    def _switch_page(self, page: str) -> None:
        titles = {
            "home": ("Tableau de bord", "Vue synthèse de l'activité Batikam Renov"),
            "devis": ("Gestion des devis", "Prospects, clients, lots, lignes et aperçu"),
            "factures": ("Gestion des factures", "Facturation complète depuis devis ou création manuelle"),
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

    def _refresh_dashboard(self) -> None:
        devis_list = self.storage.list_all()
        factures = self.storage.list_factures()
        depenses = self.storage.list_depenses()

        devis_count = len(devis_list)
        factures_count = len(factures)
        attente_count = sum(1 for row in factures if (row["statut"] or "").lower() in {"brouillon", "en attente"})
        depenses_total = sum(Decimal(row["montant"]) for row in depenses) if depenses else Decimal("0")
        ca_total = sum(Decimal(row["montant_ttc"]) for row in factures) if factures else Decimal("0")

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
            self.dashboard_devis_table.setItem(i, 3, QTableWidgetItem(f"{devis.calculer_total_ttc():.2f} EUR"))

        self.dashboard_factures_table.setRowCount(min(8, len(factures)))
        for i, row in enumerate(factures[:8]):
            self.dashboard_factures_table.setItem(i, 0, QTableWidgetItem(row["numero"]))
            self.dashboard_factures_table.setItem(i, 1, QTableWidgetItem(row["client_nom"]))
            self.dashboard_factures_table.setItem(i, 2, QTableWidgetItem(row["projet"]))
            self.dashboard_factures_table.setItem(i, 3, QTableWidgetItem(f"{Decimal(row['montant_ttc']):.2f} EUR"))

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
                if ratio >= Decimal("90"):
                    critical_alerts.append(
                        {
                            "title": f"{numero} • {client}",
                            "summary": f"Dépenses à {ratio:.1f}% ({dep:.2f}/{ttc:.2f} EUR).",
                            "action": "Vérifier la marge immédiatement.",
                        }
                    )
                elif ratio >= Decimal("70"):
                    warning_alerts.append(
                        {
                            "title": f"{numero} • {client}",
                            "summary": f"Dépenses à {ratio:.1f}% ({dep:.2f}/{ttc:.2f} EUR).",
                            "action": "Surveiller les prochains coûts.",
                        }
                    )

        if not factures:
            info_alerts.append(
                {
                    "title": "Aucune facture enregistrée",
                    "summary": "Le suivi d'alertes est actif.",
                    "action": "Créez une facture pour démarrer le monitoring financier.",
                }
            )

        if not critical_alerts and not warning_alerts and not info_alerts:
            info_alerts.append(
                {
                    "title": "Aucun risque financier détecté",
                    "summary": "Situation saine aujourd'hui.",
                    "action": "Maintenir le rythme de suivi actuel.",
                }
            )

        def _alert_card(level: str, title: str, summary: str, action: str, bg: str, border: str, badge_bg: str, badge_fg: str) -> str:
            return (
                f"<div style='margin:0 0 14px 0; padding:13px 13px; background:{bg}; border:1px solid {border}; border-radius:14px;'>"
                f"<div style='margin-bottom:6px;'><span style='display:inline-block; background:{badge_bg}; color:{badge_fg}; "
                f"font-weight:700; font-size:11px; padding:3px 9px; border-radius:10px;'>{html_escape(level)}</span></div>"
                f"<div style='font-weight:700; color:#0F172A; margin-bottom:4px;'>{html_escape(title)}</div>"
                f"<div style='color:#334155; line-height:1.45; margin-bottom:4px;'>{html_escape(summary)}</div>"
                f"<div style='color:#0F172A; font-weight:600;'>Action: {html_escape(action)}</div>"
                "</div>"
            )

        def _cards(items: list[dict[str, str]], sev: str) -> list[str]:
            out: list[str] = []
            for item in items:
                if sev == "critical":
                    out.append(
                        _alert_card(
                            "CRITIQUE",
                            item["title"],
                            item["summary"],
                            item["action"],
                            "#FEF2F2",
                            "#FCA5A5",
                            "#B91C1C",
                            "#FFFFFF",
                        )
                    )
                elif sev == "warning":
                    out.append(
                        _alert_card(
                            "ATTENTION",
                            item["title"],
                            item["summary"],
                            item["action"],
                            "#FFFBEB",
                            "#FCD34D",
                            "#B45309",
                            "#FFFFFF",
                        )
                    )
                else:
                    out.append(
                        _alert_card(
                            "INFO",
                            item["title"],
                            item["summary"],
                            item["action"],
                            "#EFF6FF",
                            "#BFDBFE",
                            "#1D4ED8",
                            "#FFFFFF",
                        )
                    )
            return out

        html_parts = [
            "<div style='font-family:Segoe UI, Arial; font-size:13px; padding:2px 2px 6px 2px;'>",
            "<div style='margin-bottom:14px; padding:12px 13px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:14px;'>",
            "<div style='font-size:12px; color:#475569; margin-bottom:4px;'>Synthèse alertes</div>",
            (
                "<div style='font-weight:700; color:#0F172A;'>"
                f"Critiques: {len(critical_alerts)} &nbsp;•&nbsp; "
                f"Attention: {len(warning_alerts)} &nbsp;•&nbsp; "
                f"Info: {len(info_alerts)}"
                "</div>"
            ),
            "</div>",
        ]

        html_parts.extend(_cards(critical_alerts[:4], "critical"))
        html_parts.extend(_cards(warning_alerts[:6], "warning"))
        html_parts.extend(_cards(info_alerts[:4], "info"))
        html_parts.append("</div>")
        self.alerts_box.setHtml("".join(html_parts))

    def _current_devis_for_invoice(self) -> Optional[Devis]:
        if self.current_devis:
            return self.current_devis
        devis_id = self._selected_devis_id()
        if devis_id is None:
            return None
        return self.storage.read(devis_id)

    def _selected_devis_id(self) -> Optional[int]:
        row = self.devis_table.currentRow()
        if row < 0:
            return None
        item = self.devis_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.UserRole)
        return int(value) if value is not None else None

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
            affaire = (devis.reference_affaire or "").strip() or "-"
            self.devis_table.setItem(row, 2, QTableWidgetItem(affaire))
            self.devis_table.setItem(row, 3, QTableWidgetItem(devis.date_devis.strftime("%d/%m/%Y")))
            self.devis_table.setItem(row, 4, QTableWidgetItem(f"{devis.calculer_total_ttc():.2f} EUR"))
            self.devis_table.setItem(row, 5, QTableWidgetItem(devis.statut))
        self.devis_table.setSortingEnabled(True)

    def _on_search_changed(self, _: str) -> None:
        self._refresh_devis_list()

    def _on_devis_double_clicked(self, _: QTableWidgetItem) -> None:
        self._on_open_devis()

    def _on_new_devis(self) -> None:
        self.current_devis = Devis()
        self.editor.set_devis(self.current_devis)
        self._switch_page("devis")

    def _on_duplicate_devis(self) -> None:
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
        self.current_devis = duplicated
        self.editor.set_devis(duplicated)
        self._switch_page("devis")

    def _on_open_devis(self) -> None:
        devis_id = self._selected_devis_id()
        if devis_id is None:
            show_error(self, "Attention", "Sélectionnez un devis.")
            return
        devis = self.storage.read(devis_id)
        if devis is None:
            show_error(self, "Attention", "Devis introuvable.")
            return
        self.current_devis = devis
        self.editor.set_devis(devis)
        self._switch_page("devis")

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
            if self.current_devis and self.current_devis.id == devis_id:
                self.current_devis = None
                self.editor.set_devis(None)
            self._refresh_devis_list()
            self._refresh_dashboard()

    def _on_validate_prospect(self) -> None:
        devis = self.current_devis
        if devis is None:
            devis_id = self._selected_devis_id()
            if devis_id is not None:
                devis = self.storage.read(devis_id)

        if devis is None:
            show_error(self, "Prospect requis", "Ouvrez d'abord un devis/prospect.")
            return

        loading = show_loading(self, "Validation", "Conversion prospect vers client/projet...")
        try:
            self.storage.validate_prospect_to_client_project(devis)
            loading.close()
            self._refresh_devis_list()
            self._refresh_dashboard()
            show_success(self, "Succès", "Prospect validé en client avec projet actif.")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Validation impossible:\n{exc}")

    def _on_export_pdf(self) -> None:
        if not self.current_devis:
            show_error(self, "Attention", "Aucun devis ouvert.")
            return
        # Always export latest UI state
        devis_ui = self.editor.get_devis_from_ui()
        if devis_ui is not None:
            self.current_devis = devis_ui
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter en PDF",
            f"devis_{self.current_devis.numero or 'sans_numero'}.pdf",
            "PDF Files (*.pdf)",
        )
        if not file_path:
            return

        loading = show_loading(self, "Export PDF", "Export en cours, veuillez patienter...")
        try:
            PDFExporter(logo_path=self.editor.logo_path).export(self.current_devis, file_path)
            loading.close()
            show_success(self, "Succès", f"PDF exporté:\n{file_path}")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Export PDF impossible:\n{exc}")

    def _on_export_docx(self) -> None:
        if not self.current_devis:
            show_error(self, "Attention", "Aucun devis ouvert.")
            return
        # Always export latest UI state
        devis_ui = self.editor.get_devis_from_ui()
        if devis_ui is not None:
            self.current_devis = devis_ui
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter en DOCX",
            f"devis_{self.current_devis.numero or 'sans_numero'}.docx",
            "DOCX Files (*.docx)",
        )
        if not file_path:
            return

        loading = show_loading(self, "Export DOCX", "Export en cours, veuillez patienter...")
        try:
            DOCXExporter().export(self.current_devis, file_path)
            loading.close()
            show_success(self, "Succès", f"DOCX exporté:\n{file_path}")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Export DOCX impossible:\n{exc}")

    def _on_devis_changed(self, devis: Devis) -> None:
        self.current_devis = devis
        if devis.id:
            self.storage.update(devis)
        else:
            self.storage.create(devis)
        self._refresh_devis_list()
        self._refresh_dashboard()
        self.editor.set_devis(devis)
