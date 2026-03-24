"""Widget d'edition de devis."""

from pathlib import Path
from typing import Optional
import tempfile

from PySide6.QtCore import QDate, Qt, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStyledItemDelegate,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.devis import Devis, Ligne, Lot
from app.services.branding import resolve_logo_str
from app.services.calc import format_euro_fr, parse_decimal_fr
from app.services.company_info import CompanyInfo, get_company_info, save_company_info
from app.services.export_pdf import PDFExporter
from app.ui.theme import add_shadow
from app.ui.feedback import show_error, show_loading, show_success


class MultilineTextDelegate(QStyledItemDelegate):
    """Delegue d'edition multiline pour la description des lignes."""

    def createEditor(self, parent, option, index):
        editor = QTextEdit(parent)
        editor.setAcceptRichText(False)
        editor.setObjectName("TableEditor")
        editor.setFrameShape(QFrame.NoFrame)
        editor.setStyleSheet("background: #FFFFFF; color: #111827;")
        return editor

    def setEditorData(self, editor, index):
        editor.setPlainText(index.data(Qt.EditRole) or "")

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText(), Qt.EditRole)


class NumericEditorDelegate(QStyledItemDelegate):
    """Delegate for numeric edits with white input background."""

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setObjectName("TableNumericEditor")
        editor.setStyleSheet("background: #FFFFFF; color: #111827;")
        return editor


class DevisEditorWidget(QWidget):
    """Widget pour editer un devis."""

    devis_changed = Signal(Devis)
    LOT_ROW_BG = "#F6F1E6"
    LOT_ROW_ACCENT = "#C8A96B"
    SUBTOTAL_ROW_BG = "#EEF4FA"
    SUBTOTAL_ROW_ACCENT = "#D9E7F6"

    def __init__(self):
        super().__init__()
        self.current_devis: Optional[Devis] = None
        self.logo_path: Optional[str] = self._default_logo_path()
        self._export_pdf_button: Optional[QPushButton] = None
        self._export_docx_button: Optional[QPushButton] = None
        self._updating_table = False
        self._pdf_document = None
        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        self.current_client_bar = QFrame()
        self.current_client_bar.setObjectName("CurrentClientBar")
        bar_layout = QHBoxLayout(self.current_client_bar)
        bar_layout.setContentsMargins(10, 8, 10, 8)
        bar_layout.setSpacing(8)
        bar_title = QLabel("Client actuel:")
        bar_title.setProperty("variant", "muted")
        self.current_client_label = QLabel("Aucun client sélectionné")
        self.current_client_label.setObjectName("CurrentClientName")
        bar_layout.addWidget(bar_title)
        bar_layout.addWidget(self.current_client_label)
        bar_layout.addStretch()
        root.addWidget(self.current_client_bar)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.tabs.addTab(self._wrap_scroll(self._create_info_tab()), "Informations")
        self.tabs.addTab(self._wrap_scroll(self._create_lots_tab()), "Lots et lignes")
        self.tabs.addTab(self._wrap_scroll(self._create_preview_tab()), "Apercu")

        self.btn_save = QPushButton("Sauvegarder")
        self.btn_save.setProperty("variant", "primary")
        self.btn_save.setObjectName("SaveButton")
        self.btn_save.clicked.connect(self._on_save)
        root.addWidget(self.btn_save)

    def _wrap_scroll(self, inner: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(inner)
        return scroll

    def _create_info_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        header = QGroupBox("En-tete")
        f_header = QFormLayout(header)

        self.numero_edit = QLineEdit()
        self.numero_edit.setPlaceholderText("Auto")
        self.numero_label = QLabel("N° devis")
        f_header.addRow(self.numero_label, self.numero_edit)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        f_header.addRow("Date", self.date_edit)

        self.validite_spin = QSpinBox()
        self.validite_spin.setRange(1, 365)
        self.validite_spin.setValue(30)
        f_header.addRow("Validite (jours)", self.validite_spin)

        self.ref_affaire_edit = QLineEdit()
        f_header.addRow("Nom affaire", self.ref_affaire_edit)

        logo_layout = QHBoxLayout()
        self.logo_label = QLabel("Aucun logo")
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setMinimumSize(220, 140)
        self.logo_label.setMaximumSize(220, 140)
        self.logo_label.setScaledContents(False)

        logo_buttons = QVBoxLayout()
        self.btn_upload_logo = QPushButton("Choisir logo")
        self.btn_upload_logo.clicked.connect(self._on_upload_logo)
        self.btn_remove_logo = QPushButton("Supprimer logo")
        self.btn_remove_logo.clicked.connect(self._on_remove_logo)
        self.btn_remove_logo.setEnabled(False)
        logo_buttons.addWidget(self.btn_upload_logo)
        logo_buttons.addWidget(self.btn_remove_logo)
        logo_buttons.addStretch()

        logo_layout.addWidget(self.logo_label)
        logo_layout.addLayout(logo_buttons)
        # Logo section hidden: use application logo by default
        logo_container = QWidget(widget)
        logo_container.setVisible(False)
        logo_container.setLayout(logo_layout)

        layout.addWidget(header)

        company = QGroupBox("Entreprise")
        f_company = QFormLayout(company)
        self.company_forme_edit = QLineEdit()
        self.company_raison_edit = QLineEdit()
        self.company_adresse_edit = QLineEdit()
        self.company_cp_ville_edit = QLineEdit()
        self.company_siret_edit = QLineEdit()
        self.company_rcs_edit = QLineEdit()
        self.company_tva_edit = QLineEdit()
        self.company_tel_edit = QLineEdit()
        self.company_email_edit = QLineEdit()
        self.company_banque_nom_edit = QLineEdit()
        self.company_code_banque_edit = QLineEdit()
        self.company_code_guichet_edit = QLineEdit()
        self.company_iban_edit = QLineEdit()
        self.company_bic_edit = QLineEdit()
        f_company.addRow("Forme", self.company_forme_edit)
        f_company.addRow("Raison sociale", self.company_raison_edit)
        f_company.addRow("Adresse", self.company_adresse_edit)
        f_company.addRow("CP / Ville", self.company_cp_ville_edit)
        f_company.addRow("SIRET", self.company_siret_edit)
        f_company.addRow("RCS", self.company_rcs_edit)
        f_company.addRow("TVA", self.company_tva_edit)
        f_company.addRow("Telephone", self.company_tel_edit)
        f_company.addRow("Email", self.company_email_edit)
        f_company.addRow("Banque", self.company_banque_nom_edit)
        f_company.addRow("Code banque", self.company_code_banque_edit)
        f_company.addRow("Code guichet", self.company_code_guichet_edit)
        f_company.addRow("IBAN", self.company_iban_edit)
        f_company.addRow("BIC", self.company_bic_edit)
        layout.addWidget(company)

        client = QGroupBox("Client")
        f_client = QFormLayout(client)
        self.client_nom_edit = QLineEdit()
        self.client_adresse_edit = QLineEdit()
        self.client_cp_edit = QLineEdit()
        self.client_ville_edit = QLineEdit()
        self.client_tel_edit = QLineEdit()
        self.client_email_edit = QLineEdit()

        cp_ville_client = QHBoxLayout()
        cp_ville_client.addWidget(self.client_cp_edit)
        cp_ville_client.addWidget(self.client_ville_edit)

        f_client.addRow("Nom", self.client_nom_edit)
        f_client.addRow("Adresse", self.client_adresse_edit)
        f_client.addRow("CP / Ville", cp_ville_client)
        f_client.addRow("Telephone", self.client_tel_edit)
        f_client.addRow("Email", self.client_email_edit)
        layout.addWidget(client)

        # Champ chantier conservé uniquement pour compatibilite modele/stockage.
        self.chantier_adresse_edit = QLineEdit()
        self.chantier_cp_edit = QLineEdit()
        self.chantier_ville_edit = QLineEdit()
        self.chantier_adresse_edit.setVisible(False)
        self.chantier_cp_edit.setVisible(False)
        self.chantier_ville_edit.setVisible(False)

        conditions = QGroupBox("Conditions")
        f_conditions = QFormLayout(conditions)
        self.modalites_edit = QLineEdit("40% acompte + 60% fin")
        self.delais_edit = QLineEdit()
        self.remarques_edit = QTextEdit()
        self.remarques_edit.setMaximumHeight(100)
        f_conditions.addRow("Modalites", self.modalites_edit)
        f_conditions.addRow("Delais", self.delais_edit)
        f_conditions.addRow("Remarques", self.remarques_edit)
        layout.addWidget(conditions)

        layout.addStretch()
        self._load_default_logo_if_available()
        self._load_company_info_to_ui()
        self.client_nom_edit.textChanged.connect(self._on_client_changed)
        return widget

    def _create_lots_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        actions = QHBoxLayout()
        self.use_lots_check = QCheckBox("Structurer par lots")
        self.use_lots_check.setChecked(True)
        self.use_lots_check.toggled.connect(self._on_toggle_lots_mode)
        self.btn_add_lot = QPushButton("Ajouter lot")
        self.btn_add_lot.setProperty("variant", "primary")
        self.btn_add_lot.setObjectName("AddLotButton")
        self.btn_add_lot.clicked.connect(self._on_add_lot)
        self.btn_add_ligne = QPushButton("Ajouter ligne")
        self.btn_add_ligne.setObjectName("AddLineButton")
        self.btn_add_ligne.clicked.connect(self._on_add_ligne)
        self.btn_delete_ligne = QPushButton("Supprimer ligne")
        self.btn_delete_ligne.setProperty("variant", "danger")
        self.btn_delete_ligne.setObjectName("DeleteLineButton")
        self.btn_delete_ligne.clicked.connect(self._on_delete_ligne)
        actions.addWidget(self.use_lots_check)
        actions.addSpacing(10)
        actions.addWidget(self.btn_add_lot)
        actions.addWidget(self.btn_add_ligne)
        actions.addWidget(self.btn_delete_ligne)
        actions.addStretch()
        layout.addLayout(actions)

        self.lots_table = QTableWidget(0, 6)
        self.lots_table.setObjectName("LotsTable")
        self.lots_table.setHorizontalHeaderLabels(
            [
                "Lot",
                "Description des travaux",
                "Unite",
                "Qte",
                "PU HT",
                "Total HT",
            ]
        )
        self.lots_table.setWordWrap(True)
        self.lots_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lots_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.lots_table.setAlternatingRowColors(True)
        self.lots_table.verticalHeader().setDefaultSectionSize(40)
        self.lots_table.verticalHeader().setMinimumSectionSize(34)
        self.lots_table.setShowGrid(True)
        self.lots_table.setItemDelegateForColumn(1, MultilineTextDelegate(self.lots_table))
        self.lots_table.setItemDelegateForColumn(3, NumericEditorDelegate(self.lots_table))
        self.lots_table.setItemDelegateForColumn(4, NumericEditorDelegate(self.lots_table))
        self.lots_table.itemChanged.connect(self._on_table_item_changed)
        layout.addWidget(self.lots_table)

        return widget

    def _create_preview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(16)

        recap_card = QFrame()
        recap_card.setObjectName("Card")
        recap_card.setMinimumWidth(320)
        recap_card.setMaximumWidth(380)
        recap_layout = QVBoxLayout(recap_card)
        recap_layout.setContentsMargins(16, 16, 16, 16)
        recap_layout.setSpacing(12)
        add_shadow(recap_card, blur=22, y_offset=4, color="#0000001a")

        recap_title = QLabel("Recapitulatif")
        recap_title.setProperty("variant", "title")
        recap_layout.addWidget(recap_title)

        totals_form = QFormLayout()
        totals_form.setHorizontalSpacing(12)
        totals_form.setVerticalSpacing(8)
        self.label_total_ht = QLabel("0,00 €")
        self.label_total_tva = QLabel("0,00 €")
        self.label_total_ttc = QLabel("0,00 €")
        self.tva_spin = QDoubleSpinBox()
        self.tva_spin.setRange(0, 100)
        self.tva_spin.setSingleStep(0.5)
        self.tva_spin.setDecimals(2)
        self.tva_spin.setSuffix(" %")
        self.tva_spin.setValue(20.0)
        self.tva_spin.valueChanged.connect(self._on_tva_changed)
        totals_form.addRow(QLabel("Total HT"), self.label_total_ht)
        totals_form.addRow(QLabel("TVA"), self.tva_spin)
        totals_form.addRow(QLabel("Montant TVA"), self.label_total_tva)
        totals_form.addRow(QLabel("Total TTC"), self.label_total_ttc)
        recap_layout.addLayout(totals_form)

        self.preview_modalites_label = QLabel("")
        self.preview_modalites_label.setWordWrap(True)
        self.preview_modalites_label.setProperty("variant", "muted")
        self.preview_modalites_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        recap_layout.addWidget(self.preview_modalites_label)

        self.preview_signature_label = QLabel(
            "Signature: Acceptation du devis | Date et cachet | Signature (Bon pour accord)"
        )
        self.preview_signature_label.setWordWrap(True)
        self.preview_signature_label.setProperty("variant", "muted")
        self.preview_signature_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        recap_layout.addWidget(self.preview_signature_label)

        self.btn_generate_preview = QPushButton("Generer apercu PDF")
        self.btn_generate_preview.setProperty("variant", "primary")
        self.btn_generate_preview.setObjectName("GeneratePreviewButton")
        self.btn_generate_preview.clicked.connect(self._on_generate_preview)
        recap_layout.addStretch()
        recap_layout.addWidget(self.btn_generate_preview)

        exports_row = QHBoxLayout()
        exports_row.setSpacing(10)
        exports_row.addStretch()
        self._export_buttons_container = QFrame()
        exports_container_layout = QHBoxLayout(self._export_buttons_container)
        exports_container_layout.setContentsMargins(0, 0, 0, 0)
        exports_container_layout.setSpacing(10)
        exports_row.addWidget(self._export_buttons_container)
        recap_layout.addLayout(exports_row)

        preview_card = QFrame()
        preview_card.setObjectName("Card")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(12)
        add_shadow(preview_card, blur=22, y_offset=4, color="#0000001a")

        preview_title = QLabel("Apercu PDF")
        preview_title.setProperty("variant", "title")
        preview_layout.addWidget(preview_title)

        self.pdf_preview_area = QScrollArea()
        self.pdf_preview_area.setWidgetResizable(True)
        self.pdf_preview_label = QLabel("Generez un apercu pour visualiser le PDF")
        self.pdf_preview_label.setAlignment(Qt.AlignCenter)
        self.pdf_preview_area.setWidget(self.pdf_preview_label)
        preview_layout.addWidget(self.pdf_preview_area)

        layout.addWidget(recap_card, 1)
        layout.addWidget(preview_card, 2)
        return widget

    def set_devis(self, devis: Optional[Devis]) -> None:
        self.current_devis = devis
        if devis is None:
            self._clear_ui()
            return
        self._load_devis_to_ui(devis)

    def _clear_ui(self) -> None:
        self.numero_edit.clear()
        self.date_edit.setDate(QDate.currentDate())
        self.validite_spin.setValue(30)
        self.ref_affaire_edit.clear()

        self.client_nom_edit.clear()
        self.client_adresse_edit.clear()
        self.client_cp_edit.clear()
        self.client_ville_edit.clear()
        self.client_tel_edit.clear()
        self.client_email_edit.clear()

        self.chantier_adresse_edit.clear()
        self.chantier_cp_edit.clear()
        self.chantier_ville_edit.clear()

        self.modalites_edit.setText("40% acompte + 60% fin")
        self.delais_edit.clear()
        self.remarques_edit.clear()

        self.logo_path = self._default_logo_path()
        self.logo_label.clear()
        self.logo_label.setText("Aucun logo")
        self.btn_remove_logo.setEnabled(False)
        self._load_default_logo_if_available()

        self.lots_table.setRowCount(0)
        self.label_total_ht.setText("0,00 €")
        self.label_total_tva.setText("0,00 €")
        self.label_total_ttc.setText("0,00 €")
        self.tva_spin.setValue(20.0)
        self.use_lots_check.setChecked(True)
        self._load_company_info_to_ui()
        self._update_client_banner()
        self._update_actions_state()

    def _load_devis_to_ui(self, devis: Devis) -> None:
        self.numero_edit.setText(devis.numero)
        self.date_edit.setDate(QDate(devis.date_devis.year, devis.date_devis.month, devis.date_devis.day))
        self.validite_spin.setValue(devis.validite_jours)
        affaire_name = (devis.reference_affaire or devis.chantier.adresse or "").strip()
        self.ref_affaire_edit.setText(affaire_name)

        self.client_nom_edit.setText(devis.client.nom)
        self.client_adresse_edit.setText(devis.client.adresse)
        self.client_cp_edit.setText(devis.client.code_postal)
        self.client_ville_edit.setText(devis.client.ville)
        self.client_tel_edit.setText(devis.client.telephone)
        self.client_email_edit.setText(devis.client.email)

        self.chantier_adresse_edit.setText(affaire_name)
        self.chantier_cp_edit.clear()
        self.chantier_ville_edit.clear()

        self.modalites_edit.setText(devis.modalites_paiement)
        self.delais_edit.setText(devis.delais)
        self.remarques_edit.setPlainText(devis.remarques)
        self.tva_spin.setValue(float(devis.tva_pourcent_global))
        self.use_lots_check.setChecked(devis.utiliser_lots)

        self._rebuild_lots_table()
        self._update_totaux()
        self._update_client_banner()
        self._update_actions_state()

    def _rebuild_lots_table(self) -> None:
        self._updating_table = True
        self.lots_table.setRowCount(0)

        if not self.current_devis:
            self._updating_table = False
            return

        use_lots = self.current_devis.utiliser_lots
        source_lots = self.current_devis.lots if use_lots else self._ensure_flat_lot()

        for lot_index, lot in enumerate(source_lots):
            # Ligne separatrice de lot
            if use_lots:
                header_row = self.lots_table.rowCount()
                self.lots_table.insertRow(header_row)
                lot_item = self._readonly_item(f"Lot {lot_index + 1}", kind="lot_header", lot_index=lot_index)
                title_item = QTableWidgetItem(lot.nom)
                title_item.setData(Qt.UserRole, {"kind": "lot_header", "lot_index": lot_index})
                self.lots_table.setItem(header_row, 0, lot_item)
                self.lots_table.setItem(header_row, 1, title_item)
                for col in range(2, 6):
                    self.lots_table.setItem(
                        header_row, col, self._readonly_item("", kind="lot_header", lot_index=lot_index)
                    )
                self._style_special_row(header_row, "lot_header")

            # Lignes du lot
            for ligne_index, ligne in enumerate(lot.lignes):
                row = self.lots_table.rowCount()
                self.lots_table.insertRow(row)
                # m2/ml removed from UI: keep a neutral multiplier
                ligne.mesure = parse_decimal_fr("1")

                meta = {"kind": "line", "lot_index": lot_index, "line_index": ligne_index}
                self.lots_table.setItem(row, 0, self._readonly_item("", **meta))

                desc_item = QTableWidgetItem(ligne.designation)
                desc_item.setData(Qt.UserRole, meta)
                self.lots_table.setItem(row, 1, desc_item)

                unit_box = QComboBox()
                unit_box.addItems(["m2", "m", "ml", "U", "Forfait"])
                unit_box.setCurrentText(ligne.unite if ligne.unite in {"m2", "m", "ml", "U", "Forfait"} else "U")
                unit_box.currentTextChanged.connect(
                    lambda value, li=lot_index, ri=ligne_index: self._on_unite_changed(li, ri, value)
                )
                self.lots_table.setCellWidget(row, 2, unit_box)
                self.lots_table.setItem(row, 2, self._readonly_item("", **meta))

                qty_item = QTableWidgetItem(str(ligne.quantite))
                qty_item.setData(Qt.UserRole, meta)
                qty_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                self.lots_table.setItem(row, 3, qty_item)

                pu_item = QTableWidgetItem(str(ligne.prix_unitaire_ht))
                pu_item.setData(Qt.UserRole, meta)
                pu_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                self.lots_table.setItem(row, 4, pu_item)

                total_item = self._readonly_item(f"{ligne.calculer_total_ht():.2f}", **meta)
                total_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                self.lots_table.setItem(row, 5, total_item)

                if ligne.unite == "Forfait":
                    qty_item.setText("1")

            # Sous-total du lot
            if use_lots:
                subtotal_row = self.lots_table.rowCount()
                self.lots_table.insertRow(subtotal_row)
                label = self._readonly_item(f"Sous-total {lot.nom}".strip(), kind="subtotal", lot_index=lot_index)
                self.lots_table.setItem(subtotal_row, 0, self._readonly_item("", kind="subtotal", lot_index=lot_index))
                self.lots_table.setItem(subtotal_row, 1, label)
                for col in range(2, 5):
                    self.lots_table.setItem(
                        subtotal_row, col, self._readonly_item("", kind="subtotal", lot_index=lot_index)
                    )
                self.lots_table.setItem(
                    subtotal_row,
                    5,
                    self._readonly_item(f"{lot.calculer_sous_total_ht():.2f}", kind="subtotal", lot_index=lot_index),
                )
                self._style_special_row(subtotal_row, "subtotal")

        self.lots_table.resizeColumnsToContents()
        self.lots_table.resizeRowsToContents()
        self._updating_table = False

    def _readonly_item(self, text: str, **meta) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if meta:
            item.setData(Qt.UserRole, meta)
        return item

    def _style_special_row(self, row: int, kind: str) -> None:
        if kind == "lot_header":
            row_bg = QColor(self.LOT_ROW_BG)
            accent_bg = QColor(self.LOT_ROW_ACCENT)
            text_color = QColor("#0F2747")
        else:
            row_bg = QColor(self.SUBTOTAL_ROW_BG)
            accent_bg = QColor(self.SUBTOTAL_ROW_ACCENT)
            text_color = QColor("#1F2937")

        for col in range(self.lots_table.columnCount()):
            item = self.lots_table.item(row, col)
            if item:
                item.setBackground(row_bg)
                item.setForeground(text_color)
                font = item.font()
                font.setBold(col in (0, 1, 5))
                item.setFont(font)
                if col in (3, 4, 5):
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)

        first_item = self.lots_table.item(row, 0)
        if first_item is not None:
            first_item.setBackground(accent_bg)
            if kind == "lot_header":
                first_item.setForeground(QColor("#FFFFFF"))

    def _selected_line_ref(self) -> Optional[dict]:
        row = self.lots_table.currentRow()
        if row < 0:
            return None
        for col in (1, 0, 3):
            item = self.lots_table.item(row, col)
            if item is not None:
                data = item.data(Qt.UserRole)
                if isinstance(data, dict):
                    return data
        return None

    def _on_add_lot(self) -> None:
        if not self._is_client_set():
            show_error(self, "Client requis", "Veuillez renseigner le client avant d'ajouter des lots.")
            return
        if self.current_devis and not self.current_devis.utiliser_lots:
            show_error(self, "Mode sans lots", "Activez d'abord la structure par lots.")
            return
        if self.current_devis is None:
            self.current_devis = Devis()
        lot = Lot(nom=f"Titre lot {len(self.current_devis.lots) + 1}", lignes=[])
        self.current_devis.lots.append(lot)
        self._rebuild_lots_table()
        self._update_totaux()

    def _on_add_ligne(self) -> None:
        if not self._is_client_set():
            show_error(self, "Client requis", "Veuillez renseigner le client avant d'ajouter des lignes.")
            return
        if self.current_devis is None:
            self.current_devis = Devis()
        if not self.current_devis.utiliser_lots:
            flat = self._ensure_flat_lot()
            flat[0].lignes.append(Ligne())
            self._rebuild_lots_table()
            self._update_totaux()
            return

        ref = self._selected_line_ref()
        if ref is not None:
            lot_index = ref["lot_index"]
        elif self.current_devis.lots:
            lot_index = len(self.current_devis.lots) - 1
        else:
            self._on_add_lot()
            return

        self.current_devis.lots[lot_index].lignes.append(Ligne())
        self._rebuild_lots_table()
        self._update_totaux()

    def _on_delete_ligne(self) -> None:
        if self.current_devis is None:
            return
        ref = self._selected_line_ref()
        if ref is None:
            return

        lot_index = ref["lot_index"]
        kind = ref.get("kind")
        if kind == "line":
            ligne_index = ref["line_index"]
            lot = self.current_devis.lots[lot_index]
            lot.lignes.pop(ligne_index)
            if not lot.lignes:
                self.current_devis.lots.pop(lot_index)
        elif kind == "lot_header":
            self.current_devis.lots.pop(lot_index)
        else:
            return

        self._rebuild_lots_table()
        self._update_totaux()

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_table or self.current_devis is None:
            return

        row = item.row()
        col = item.column()
        ref = item.data(Qt.UserRole)
        if not isinstance(ref, dict):
            return
        lot_index = ref["lot_index"]
        kind = ref.get("kind")
        lot = self.current_devis.lots[lot_index]

        text = item.text().strip()
        try:
            if kind == "lot_header" and col == 1:
                lot.nom = text
            elif kind == "line" and col == 1:
                ligne = lot.lignes[ref["line_index"]]
                ligne.designation = (
                    text.replace("<br/>", "\n")
                    .replace("<br />", "\n")
                    .replace("<br>", "\n")
                )
            elif kind == "line" and col == 3:
                ligne = lot.lignes[ref["line_index"]]
                ligne.quantite = parse_decimal_fr(text)
            elif kind == "line" and col == 4:
                ligne = lot.lignes[ref["line_index"]]
                ligne.prix_unitaire_ht = parse_decimal_fr(text)
        except Exception:
            return

        self._rebuild_lots_table()
        self._update_totaux()

    def _on_unite_changed(self, lot_index: int, ligne_index: int, unite: str) -> None:
        if self.current_devis is None:
            return
        ligne = self.current_devis.lots[lot_index].lignes[ligne_index]
        ligne.unite = unite
        if unite == "Forfait":
            ligne.quantite = parse_decimal_fr("1")
        ligne.mesure = parse_decimal_fr("1")
        self._rebuild_lots_table()
        self._update_totaux()

    def _update_totaux(self) -> None:
        modalites_default = (
            "30% a la signature du devis • 40% selon l'avancement de l'affaire • 30% en fin d'affaire"
        )
        if self.current_devis is None:
            self.label_total_ht.setText("0,00 €")
            self.label_total_tva.setText("0,00 €")
            self.label_total_ttc.setText("0,00 €")
            self.preview_modalites_label.setText(f"Modalites de paiement: {modalites_default}")
            return

        self.label_total_ht.setText(format_euro_fr(self.current_devis.calculer_total_ht()))
        self.label_total_tva.setText(format_euro_fr(self.current_devis.calculer_total_tva()))
        self.label_total_ttc.setText(format_euro_fr(self.current_devis.calculer_total_ttc()))
        modalites = self.current_devis.modalites_paiement.strip() if self.current_devis.modalites_paiement.strip() else modalites_default
        self.preview_modalites_label.setText(f"Modalites de paiement: {modalites}")

    def _on_upload_logo(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir un logo",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not file_path:
            return
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            return

        self.logo_path = file_path
        self.logo_label.setPixmap(pixmap.scaled(220, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.btn_remove_logo.setEnabled(True)

    def _on_remove_logo(self) -> None:
        self.logo_path = self._default_logo_path()
        self.logo_label.clear()
        self.logo_label.setText("Aucun logo")
        self.btn_remove_logo.setEnabled(False)
        self._load_default_logo_if_available()

    def _on_generate_preview(self) -> None:
        if self.current_devis is None:
            return
        self._update_devis_from_ui()
        self._save_company_info_from_ui()

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        loading = show_loading(self, "Apercu PDF", "Generation de l'aperçu en cours...")
        try:
            PDFExporter(logo_path=self.logo_path).export(self.current_devis, tmp.name)
            loading.close()
            self._show_pdf_preview(tmp.name)
            show_success(self, "Apercu pret", "Le PDF a ete genere avec succes.")
        except Exception as exc:
            loading.close()
            show_error(self, "Erreur", f"Generation de l'aperçu impossible:\n{exc}")

    def _show_pdf_preview(self, pdf_path: str) -> None:
        # 1) Apercu natif QtPdf si disponible
        try:
            from PySide6.QtPdf import QPdfDocument  # type: ignore
            from PySide6.QtPdfWidgets import QPdfView  # type: ignore

            self._pdf_document = QPdfDocument(self)
            self._pdf_document.load(pdf_path)
            if self._pdf_document.pageCount() > 0:
                view = QPdfView()
                view.setDocument(self._pdf_document)
                if hasattr(QPdfView, "PageMode"):
                    try:
                        view.setPageMode(QPdfView.PageMode.MultiPage)
                    except Exception:
                        pass
                self.pdf_preview_area.setWidget(view)
                return
        except Exception:
            pass

        # 2) Fallback image via PyMuPDF si disponible
        try:
            import fitz  # type: ignore

            doc = fitz.open(pdf_path)
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(12)
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                label = QLabel()
                label.setAlignment(Qt.AlignCenter)
                label.setPixmap(QPixmap.fromImage(qimg.copy()))
                container_layout.addWidget(label)
            container_layout.addStretch()
            self.pdf_preview_area.setWidget(container)
            doc.close()
            return
        except Exception:
            pass

        # 3) Dernier fallback: ouverture externe
        fallback = QWidget()
        layout = QVBoxLayout(fallback)
        label = QLabel("Apercu integre indisponible sur cet environnement.")
        label.setWordWrap(True)
        layout.addWidget(label)
        path_label = QLabel(pdf_path)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(path_label)
        open_btn = QPushButton("Ouvrir le PDF")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path)))
        layout.addWidget(open_btn)
        layout.addStretch()
        self.pdf_preview_area.setWidget(fallback)

    def _on_save(self) -> None:
        self._update_devis_from_ui()
        self._save_company_info_from_ui()
        if self.current_devis is not None:
            self.devis_changed.emit(self.current_devis)

    def _update_devis_from_ui(self) -> None:
        if self.current_devis is None:
            self.current_devis = Devis()

        numero = self.numero_edit.text().strip()
        if numero:
            self.current_devis.numero = numero
        self.current_devis.date_devis = self.date_edit.date().toPython()
        self.current_devis.validite_jours = self.validite_spin.value()
        affaire_name = self.ref_affaire_edit.text().strip()
        self.current_devis.reference_affaire = affaire_name

        self.current_devis.client.nom = self.client_nom_edit.text().strip()
        self.current_devis.client.adresse = self.client_adresse_edit.text().strip()
        self.current_devis.client.code_postal = self.client_cp_edit.text().strip()
        self.current_devis.client.ville = self.client_ville_edit.text().strip()
        self.current_devis.client.telephone = self.client_tel_edit.text().strip()
        self.current_devis.client.email = self.client_email_edit.text().strip()

        self.current_devis.chantier.adresse = affaire_name
        self.current_devis.chantier.code_postal = ""
        self.current_devis.chantier.ville = ""

        self.current_devis.modalites_paiement = self.modalites_edit.text().strip()
        self.current_devis.delais = self.delais_edit.text().strip()
        self.current_devis.remarques = self.remarques_edit.toPlainText().strip()
        self.current_devis.tva_pourcent_global = parse_decimal_fr(str(self.tva_spin.value()))
        self.current_devis.utiliser_lots = self.use_lots_check.isChecked()
        self._update_client_banner()
        self._update_actions_state()

    def _apply_styles(self) -> None:
        # Keep styling centralized in global theme.qss.
        return

    def _load_default_logo_if_available(self) -> None:
        if self.logo_path and Path(self.logo_path).exists():
            pixmap = QPixmap(self.logo_path)
            if not pixmap.isNull():
                self.logo_label.setScaledContents(False)
                self.logo_label.setPixmap(
                    pixmap.scaled(220, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                self.btn_remove_logo.setEnabled(True)

    def _default_logo_path(self) -> Optional[str]:
        return resolve_logo_str()

    def _load_company_info_to_ui(self) -> None:
        info = get_company_info()
        self.company_forme_edit.setText(info.forme)
        self.company_raison_edit.setText(info.raison_sociale)
        self.company_adresse_edit.setText(info.adresse)
        self.company_cp_ville_edit.setText(info.code_postal_ville)
        self.company_siret_edit.setText(info.siret)
        self.company_rcs_edit.setText(info.rcs)
        self.company_tva_edit.setText(info.tva)
        self.company_tel_edit.setText(info.telephone)
        self.company_email_edit.setText(info.email)
        self.company_banque_nom_edit.setText(info.banque_nom)
        self.company_code_banque_edit.setText(info.code_banque)
        self.company_code_guichet_edit.setText(info.code_guichet)
        self.company_iban_edit.setText(info.iban)
        self.company_bic_edit.setText(info.bic)

    def _save_company_info_from_ui(self) -> None:
        info = CompanyInfo(
            forme=self.company_forme_edit.text().strip(),
            raison_sociale=self.company_raison_edit.text().strip(),
            adresse=self.company_adresse_edit.text().strip(),
            code_postal_ville=self.company_cp_ville_edit.text().strip(),
            siret=self.company_siret_edit.text().strip(),
            rcs=self.company_rcs_edit.text().strip(),
            tva=self.company_tva_edit.text().strip(),
            telephone=self.company_tel_edit.text().strip(),
            email=self.company_email_edit.text().strip(),
            banque_nom=self.company_banque_nom_edit.text().strip(),
            code_banque=self.company_code_banque_edit.text().strip(),
            code_guichet=self.company_code_guichet_edit.text().strip(),
            iban=self.company_iban_edit.text().strip(),
            bic=self.company_bic_edit.text().strip(),
        )
        save_company_info(info)

    def set_number_label(self, label: str) -> None:
        self.numero_label.setText(label)

    def _is_client_set(self) -> bool:
        return bool(self.client_nom_edit.text().strip())

    def _update_client_banner(self) -> None:
        name = self.client_nom_edit.text().strip()
        self.current_client_label.setText(name if name else "Aucun client sélectionné")

    def _update_actions_state(self) -> None:
        enabled = self._is_client_set()
        use_lots = self.use_lots_check.isChecked()
        self.btn_add_lot.setEnabled(enabled and use_lots)
        self.btn_add_ligne.setEnabled(enabled)

    def _on_client_changed(self) -> None:
        self._update_client_banner()
        self._update_actions_state()

    def _on_tva_changed(self, value: float) -> None:
        if self.current_devis is None:
            return
        self.current_devis.tva_pourcent_global = parse_decimal_fr(str(value))
        self._update_totaux()

    def _ensure_flat_lot(self) -> list[Lot]:
        if self.current_devis is None:
            return []
        if not self.current_devis.lots:
            self.current_devis.lots = [Lot(nom="", lignes=[])]
        if len(self.current_devis.lots) > 1:
            all_lines: list[Ligne] = []
            for lot in self.current_devis.lots:
                all_lines.extend(lot.lignes)
            self.current_devis.lots = [Lot(nom="", lignes=all_lines)]
        self.current_devis.lots[0].nom = ""
        return self.current_devis.lots

    def _on_toggle_lots_mode(self, checked: bool) -> None:
        if self.current_devis is None:
            return
        self.current_devis.utiliser_lots = checked
        if not checked:
            self._ensure_flat_lot()
        self._rebuild_lots_table()
        self._update_totaux()
        self._update_actions_state()

    def get_devis_from_ui(self) -> Optional[Devis]:
        self._update_devis_from_ui()
        self._save_company_info_from_ui()
        return self.current_devis

    def set_export_buttons(self, pdf_button: QPushButton, docx_button: QPushButton) -> None:
        self._export_pdf_button = pdf_button
        self._export_docx_button = docx_button
        if hasattr(self, "_export_buttons_container"):
            layout = self._export_buttons_container.layout()
            if layout is not None:
                while layout.count():
                    item = layout.takeAt(0)
                    if item.widget():
                        item.widget().setParent(None)
                pdf_button.setObjectName("ExportPdfButton")
                docx_button.setObjectName("ExportDocxButton")
                pdf_button.setText("Export PDF")
                docx_button.setText("Export DOCX")
                pdf_button.setProperty("variant", "primary")
                docx_button.setProperty("variant", "primary")
                layout.addWidget(pdf_button)
                layout.addWidget(docx_button)
