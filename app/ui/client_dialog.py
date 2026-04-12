"""Dialogue de création / modification d'un client."""
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
)

from qfluentwidgets import LineEdit, PushButton, PrimaryPushButton


class ClientDialog(QDialog):
    """Popup pour créer ou modifier un client."""

    def __init__(self, data: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        is_new = data is None
        self.setWindowTitle("Nouveau client" if is_new else "Modifier le client")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._data = data or {}
        self._build_ui()
        self._load()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setVerticalSpacing(14)
        form.setHorizontalSpacing(18)

        self.nom_edit = LineEdit()
        self.nom_edit.setPlaceholderText("Nom ou raison sociale *")
        form.addRow("Nom *", self.nom_edit)

        self.adresse_edit = LineEdit()
        form.addRow("Adresse", self.adresse_edit)

        self.cp_edit = LineEdit()
        self.cp_edit.setMaximumWidth(90)
        self.ville_edit = LineEdit()
        cp_row = QHBoxLayout()
        cp_row.setSpacing(8)
        cp_row.addWidget(self.cp_edit)
        cp_row.addWidget(self.ville_edit, 1)
        form.addRow("CP / Ville", cp_row)

        self.tel_edit = LineEdit()
        form.addRow("Téléphone", self.tel_edit)

        self.email_edit = LineEdit()
        form.addRow("Email", self.email_edit)

        root.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        btn_cancel = PushButton("Annuler")
        btn_cancel.setMinimumWidth(110)
        btn_cancel.clicked.connect(self.reject)
        btn_ok = PrimaryPushButton("Enregistrer")
        btn_ok.setMinimumWidth(130)
        btn_ok.clicked.connect(self._on_accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    # ── Logique ──────────────────────────────────────────────────────────────

    def _load(self) -> None:
        self.nom_edit.setText(self._data.get("nom", ""))
        self.adresse_edit.setText(self._data.get("adresse", ""))
        self.cp_edit.setText(self._data.get("code_postal", ""))
        self.ville_edit.setText(self._data.get("ville", ""))
        self.tel_edit.setText(self._data.get("telephone", ""))
        self.email_edit.setText(self._data.get("email", ""))

    def _on_accept(self) -> None:
        if not self.nom_edit.text().strip():
            from app.ui.feedback import show_error
            show_error(self, "Champ requis", "Le nom du client est obligatoire.")
            return
        self.accept()

    # ── Résultat ─────────────────────────────────────────────────────────────

    def get_data(self) -> dict:
        """Retourne les données saisies sous forme de dict."""
        return {
            "nom": self.nom_edit.text().strip(),
            "adresse": self.adresse_edit.text().strip(),
            "code_postal": self.cp_edit.text().strip(),
            "ville": self.ville_edit.text().strip(),
            "telephone": self.tel_edit.text().strip(),
            "email": self.email_edit.text().strip(),
        }
