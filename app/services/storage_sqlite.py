"""Service de stockage SQLite pour les devis."""

import json
import sqlite3
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from app.models.devis import Chantier, Client, Devis, Ligne, Lot
from app.services.numbering import obtenir_prochain_numero
from app.services.paths import app_data_path


class StorageSQLite:
    """Gestionnaire de persistance SQLite."""

    def __init__(self, db_path: str = "batikam_devis.db"):
        self.db_path = str(app_data_path(db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS devis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero TEXT UNIQUE NOT NULL,
                    date_devis TEXT NOT NULL,
                    validite_jours INTEGER NOT NULL DEFAULT 30,
                    reference_affaire TEXT,
                    client_json TEXT NOT NULL,
                    chantier_json TEXT NOT NULL,
                    modalites_paiement TEXT,
                    delais TEXT,
                    remarques TEXT,
                    statut TEXT NOT NULL DEFAULT 'Brouillon',
                    tva_pourcent_global TEXT NOT NULL DEFAULT '20',
                    utiliser_lots INTEGER NOT NULL DEFAULT 1,
                    lots_json TEXT NOT NULL,
                    date_creation TEXT,
                    date_modification TEXT
                )
                """
            )
            # Migration for old databases
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(devis)").fetchall()]
            if "tva_pourcent_global" not in columns:
                conn.execute(
                    "ALTER TABLE devis ADD COLUMN tva_pourcent_global TEXT NOT NULL DEFAULT '20'"
                )
            if "utiliser_lots" not in columns:
                conn.execute(
                    "ALTER TABLE devis ADD COLUMN utiliser_lots INTEGER NOT NULL DEFAULT 1"
                )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS factures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero TEXT UNIQUE NOT NULL,
                    date_facture TEXT NOT NULL,
                    client_id INTEGER,
                    projet_id INTEGER,
                    client_nom TEXT NOT NULL,
                    projet TEXT NOT NULL,
                    source_devis_id INTEGER,
                    montant_ht TEXT NOT NULL,
                    tva_pourcent TEXT NOT NULL DEFAULT '20',
                    montant_tva TEXT NOT NULL,
                    montant_ttc TEXT NOT NULL,
                    statut TEXT NOT NULL DEFAULT 'Brouillon',
                    lines_json TEXT NOT NULL DEFAULT '[]',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    notes TEXT,
                    date_creation TEXT NOT NULL,
                    date_modification TEXT NOT NULL
                )
                """
            )
            facture_columns = [row["name"] for row in conn.execute("PRAGMA table_info(factures)").fetchall()]
            if "client_id" not in facture_columns:
                conn.execute("ALTER TABLE factures ADD COLUMN client_id INTEGER")
            if "projet_id" not in facture_columns:
                conn.execute("ALTER TABLE factures ADD COLUMN projet_id INTEGER")
            if "lines_json" not in facture_columns:
                conn.execute("ALTER TABLE factures ADD COLUMN lines_json TEXT NOT NULL DEFAULT '[]'")
            if "payload_json" not in facture_columns:
                conn.execute("ALTER TABLE factures ADD COLUMN payload_json TEXT NOT NULL DEFAULT '{}'")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT UNIQUE NOT NULL,
                    data_json TEXT NOT NULL DEFAULT '{}',
                    date_creation TEXT NOT NULL,
                    date_modification TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    nom TEXT NOT NULL,
                    source_devis_id INTEGER,
                    statut TEXT NOT NULL DEFAULT 'Actif',
                    data_json TEXT NOT NULL DEFAULT '{}',
                    date_creation TEXT NOT NULL,
                    date_modification TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS depenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    facture_id INTEGER,
                    date_depense TEXT NOT NULL,
                    client_nom TEXT NOT NULL,
                    projet TEXT NOT NULL,
                    categorie TEXT NOT NULL,
                    montant TEXT NOT NULL,
                    notes TEXT
                )
                """
            )
            conn.commit()

    def _serialize_client(self, client: Client) -> str:
        return json.dumps(
            {
                "nom": client.nom,
                "adresse": client.adresse,
                "code_postal": client.code_postal,
                "ville": client.ville,
                "telephone": client.telephone,
                "email": client.email,
            },
            ensure_ascii=False,
        )

    def _serialize_chantier(self, chantier: Chantier) -> str:
        return json.dumps(
            {
                "adresse": chantier.adresse,
                "code_postal": chantier.code_postal,
                "ville": chantier.ville,
            },
            ensure_ascii=False,
        )

    def _serialize_lots(self, lots: list[Lot]) -> str:
        payload = []
        for lot in lots:
            payload.append(
                {
                    "nom": lot.nom,
                    "lignes": [
                        {
                            "designation": ligne.designation,
                            "unite": ligne.unite,
                            "quantite": str(ligne.quantite),
                            "mesure": str(ligne.mesure),
                            "prix_unitaire_ht": str(ligne.prix_unitaire_ht),
                            "remise_pourcent": str(ligne.remise_pourcent),
                            "tva_pourcent": str(ligne.tva_pourcent),
                            "total_ligne_ht": str(ligne.total_ligne_ht)
                            if ligne.total_ligne_ht is not None
                            else None,
                            "forcer_total": ligne.forcer_total,
                        }
                        for ligne in lot.lignes
                    ],
                }
            )
        return json.dumps(payload, ensure_ascii=False)

    def _parse_client(self, raw_json: str) -> Client:
        data = json.loads(raw_json or "{}")
        return Client(
            nom=data.get("nom", ""),
            adresse=data.get("adresse", ""),
            code_postal=data.get("code_postal", ""),
            ville=data.get("ville", ""),
            telephone=data.get("telephone", ""),
            email=data.get("email", ""),
        )

    def _parse_chantier(self, raw_json: str) -> Chantier:
        data = json.loads(raw_json or "{}")
        return Chantier(
            adresse=data.get("adresse", ""),
            code_postal=data.get("code_postal", ""),
            ville=data.get("ville", ""),
        )

    def _parse_lots(self, raw_json: str) -> list[Lot]:
        data = json.loads(raw_json or "[]")
        lots: list[Lot] = []
        for lot_data in data:
            lignes: list[Ligne] = []
            for ligne_data in lot_data.get("lignes", []):
                lignes.append(
                    Ligne(
                        designation=ligne_data.get("designation", ""),
                        unite=ligne_data.get("unite", "U"),
                        quantite=Decimal(ligne_data.get("quantite", "0")),
                        mesure=Decimal(ligne_data.get("mesure", "1")),
                        prix_unitaire_ht=Decimal(ligne_data.get("prix_unitaire_ht", "0")),
                        remise_pourcent=Decimal(ligne_data.get("remise_pourcent", "0")),
                        tva_pourcent=Decimal(ligne_data.get("tva_pourcent", "20")),
                        total_ligne_ht=Decimal(ligne_data["total_ligne_ht"])
                        if ligne_data.get("total_ligne_ht") is not None
                        else None,
                        forcer_total=bool(ligne_data.get("forcer_total", False)),
                    )
                )
            lots.append(Lot(nom=lot_data.get("nom", ""), lignes=lignes))
        return lots

    def _row_to_devis(self, row: sqlite3.Row) -> Devis:
        devis = Devis(
            id=row["id"],
            numero=row["numero"],
            date_devis=datetime.fromisoformat(row["date_devis"]).date(),
            validite_jours=int(row["validite_jours"]),
            reference_affaire=row["reference_affaire"] or "",
            client=self._parse_client(row["client_json"]),
            chantier=self._parse_chantier(row["chantier_json"]),
            modalites_paiement=row["modalites_paiement"] or "",
            delais=row["delais"] or "",
            remarques=row["remarques"] or "",
            statut=row["statut"] or "Brouillon",
            tva_pourcent_global=Decimal(row["tva_pourcent_global"] or "20"),
            utiliser_lots=bool(row["utiliser_lots"]) if "utiliser_lots" in row.keys() else True,
            lots=self._parse_lots(row["lots_json"]),
            date_creation=datetime.fromisoformat(row["date_creation"]) if row["date_creation"] else None,
            date_modification=datetime.fromisoformat(row["date_modification"]) if row["date_modification"] else None,
        )
        return devis

    def create(self, devis: Devis) -> Devis:
        if not devis.numero:
            devis.numero = obtenir_prochain_numero(self.db_path)

        now = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO devis (
                    numero, date_devis, validite_jours, reference_affaire,
                    client_json, chantier_json, modalites_paiement, delais, remarques,
                    statut, tva_pourcent_global, utiliser_lots, lots_json, date_creation, date_modification
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    devis.numero,
                    devis.date_devis.isoformat(),
                    devis.validite_jours,
                    devis.reference_affaire,
                    self._serialize_client(devis.client),
                    self._serialize_chantier(devis.chantier),
                    devis.modalites_paiement,
                    devis.delais,
                    devis.remarques,
                    devis.statut,
                    str(devis.tva_pourcent_global),
                    1 if devis.utiliser_lots else 0,
                    self._serialize_lots(devis.lots),
                    now,
                    now,
                ),
            )
            devis.id = int(cursor.lastrowid)
            conn.commit()
        return devis

    def read(self, devis_id: int) -> Optional[Devis]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM devis WHERE id = ?", (devis_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_devis(row)

    def read_by_numero(self, numero: str) -> Optional[Devis]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM devis WHERE numero = ?", (numero,)).fetchone()
        if row is None:
            return None
        return self._row_to_devis(row)

    def update(self, devis: Devis) -> Devis:
        if not devis.id:
            raise ValueError("Le devis doit avoir un ID pour etre mis a jour")

        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE devis SET
                    numero = ?, date_devis = ?, validite_jours = ?, reference_affaire = ?,
                    client_json = ?, chantier_json = ?, modalites_paiement = ?, delais = ?, remarques = ?,
                    statut = ?, tva_pourcent_global = ?, utiliser_lots = ?, lots_json = ?, date_modification = ?
                WHERE id = ?
                """,
                (
                    devis.numero,
                    devis.date_devis.isoformat(),
                    devis.validite_jours,
                    devis.reference_affaire,
                    self._serialize_client(devis.client),
                    self._serialize_chantier(devis.chantier),
                    devis.modalites_paiement,
                    devis.delais,
                    devis.remarques,
                    devis.statut,
                    str(devis.tva_pourcent_global),
                    1 if devis.utiliser_lots else 0,
                    self._serialize_lots(devis.lots),
                    now,
                    devis.id,
                ),
            )
            conn.commit()
        return devis

    def delete(self, devis_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM devis WHERE id = ?", (devis_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_all(self, search: str = "") -> list[Devis]:
        search = (search or "").strip()
        query = "SELECT * FROM devis"
        params: tuple[str, ...] = ()

        if search:
            like = f"%{search}%"
            query += (
                " WHERE numero LIKE ?"
                " OR json_extract(client_json, '$.nom') LIKE ?"
                " OR reference_affaire LIKE ?"
                " OR json_extract(chantier_json, '$.adresse') LIKE ?"
                " OR json_extract(chantier_json, '$.ville') LIKE ?"
            )
            params = (like, like, like, like, like)

        query += " ORDER BY date_creation DESC, id DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_devis(row) for row in rows]

    # ---- Facturation ----
    def _next_facture_numero(self, conn: sqlite3.Connection) -> str:
        year = datetime.now().year
        prefix = f"FAC-{year}-"
        row = conn.execute(
            "SELECT numero FROM factures WHERE numero LIKE ? ORDER BY numero DESC LIMIT 1",
            (f"{prefix}%",),
        ).fetchone()
        if row is None:
            return f"{prefix}0001"
        last = row["numero"].split("-")[-1]
        return f"{prefix}{int(last) + 1:04d}"

    def create_facture_manual(
        self,
        client_nom: str,
        projet: str,
        montant_ht: Decimal,
        tva_pourcent: Decimal,
        statut: str = "Brouillon",
        notes: str = "",
        source_devis_id: Optional[int] = None,
        lines: Optional[list[dict[str, str]]] = None,
        client_id: Optional[int] = None,
        projet_id: Optional[int] = None,
    ) -> int:
        now = datetime.now().isoformat()
        lines_payload = lines or []
        if lines_payload:
            montant_ht = self._facture_lines_ht(lines_payload)
        montant_tva = (montant_ht * tva_pourcent) / Decimal("100")
        montant_ttc = montant_ht + montant_tva
        with self._connect() as conn:
            numero = self._next_facture_numero(conn)
            cursor = conn.execute(
                """
                INSERT INTO factures (
                    numero, date_facture, client_id, projet_id, client_nom, projet, source_devis_id,
                    montant_ht, tva_pourcent, montant_tva, montant_ttc, statut, lines_json, notes, date_creation, date_modification
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    numero,
                    datetime.now().date().isoformat(),
                    client_id,
                    projet_id,
                    client_nom,
                    projet,
                    source_devis_id,
                    str(montant_ht),
                    str(tva_pourcent),
                    str(montant_tva),
                    str(montant_ttc),
                    statut,
                    json.dumps(lines_payload, ensure_ascii=False),
                    notes,
                    now,
                    now,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def create_facture_from_devis(self, devis: Devis) -> int:
        client_id, projet_id = self.validate_prospect_to_client_project(devis)
        client_nom = devis.client.nom or "Client"
        projet = devis.reference_affaire or devis.chantier.adresse or devis.numero
        lines: list[dict[str, str]] = []
        for lot in devis.lots:
            for ligne in lot.lignes:
                qte = Decimal("1") if ligne.unite.lower() == "forfait" else ligne.quantite
                qte = qte * ligne.mesure
                lines.append(
                    {
                        "designation": ligne.designation or lot.nom or "Prestation",
                        "unite": ligne.unite,
                        "quantite": str(qte),
                        "prix_unitaire_ht": str(ligne.prix_unitaire_ht),
                    }
                )
        facture_id = self.create_facture_manual(
            client_nom=client_nom,
            projet=projet,
            montant_ht=devis.calculer_total_ht(),
            tva_pourcent=devis.tva_pourcent_global,
            statut="Validee",
            notes=f"Facture creee depuis devis {devis.numero}",
            source_devis_id=devis.id,
            lines=lines,
            client_id=client_id,
            projet_id=projet_id,
        )
        self.update_facture_devis(facture_id, devis, statut="Validee", notes=f"Facture creee depuis devis {devis.numero}")
        return facture_id

    def create_facture_acompte_from_facture(self, source_facture_id: int, mode: str, value: Decimal) -> int:
        source_row = self.read_facture(source_facture_id)
        if source_row is None:
            raise ValueError("Facture source introuvable.")

        total_ttc = Decimal(str(source_row["montant_ttc"] or "0"))
        if total_ttc <= 0:
            raise ValueError("La facture source doit avoir un montant TTC positif.")

        tva = Decimal(str(source_row["tva_pourcent"] or "20"))
        if mode == "percent":
            if value <= 0 or value > Decimal("100"):
                raise ValueError("Le pourcentage d'acompte doit être compris entre 0 et 100.")
            acompte_ttc = (total_ttc * value / Decimal("100")).quantize(Decimal("0.01"))
            libelle_pct = value.quantize(Decimal("0.01"))
        elif mode == "ttc":
            if value <= 0:
                raise ValueError("Le montant d'acompte doit être strictement positif.")
            acompte_ttc = value.quantize(Decimal("0.01"))
            if acompte_ttc > total_ttc:
                raise ValueError("Le montant d'acompte ne peut pas dépasser le TTC de la facture source.")
            libelle_pct = (acompte_ttc / total_ttc * Decimal("100")).quantize(Decimal("0.01"))
        else:
            raise ValueError("Mode d'acompte invalide.")

        denom = Decimal("1") + (tva / Decimal("100"))
        acompte_ht = (acompte_ttc / denom).quantize(Decimal("0.01"))
        source_numero = source_row["numero"] or f"#{source_facture_id}"
        note = f"Facture d'acompte générée depuis {source_numero} ({acompte_ttc} EUR TTC)."

        source_devis = self.read_facture_devis(source_facture_id) or Devis()
        payload = deepcopy(source_devis)
        payload.id = None
        payload.numero = ""
        payload.date_devis = datetime.now().date()
        payload.statut = "Facture"
        payload.tva_pourcent_global = tva
        payload.validite_jours = max(1, int(payload.validite_jours or 30))
        payload.reference_affaire = (payload.reference_affaire or source_row["projet"] or "").strip()
        if not payload.client.nom.strip():
            payload.client.nom = source_row["client_nom"] or "Client"
        if not payload.chantier.adresse.strip():
            payload.chantier.adresse = payload.reference_affaire
        payload.utiliser_lots = True
        payload.lots = [
            Lot(
                nom="Acompte",
                lignes=[
                    Ligne(
                        designation=f"Acompte {libelle_pct}% sur facture {source_numero}",
                        unite="Forfait",
                        quantite=Decimal("1"),
                        mesure=Decimal("1"),
                        prix_unitaire_ht=acompte_ht,
                        remise_pourcent=Decimal("0"),
                        tva_pourcent=tva,
                    )
                ],
            )
        ]
        payload.modalites_paiement = payload.modalites_paiement or "Paiement à réception"
        base_remarques = (payload.remarques or "").strip()
        payload.remarques = f"{base_remarques}\n{note}".strip() if base_remarques else note

        facture_id = self.create_facture_empty()
        self.update_facture_devis(facture_id, payload, statut="Brouillon", notes=note)
        return facture_id

    def list_factures(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM factures ORDER BY date_creation DESC, id DESC"
            ).fetchall()
        return rows

    def read_facture(self, facture_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM factures WHERE id = ?", (facture_id,)).fetchone()
        return row

    def delete_facture(self, facture_id: int) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM depenses WHERE facture_id = ?", (facture_id,))
            cursor = conn.execute("DELETE FROM factures WHERE id = ?", (facture_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_clients(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM clients ORDER BY nom").fetchall()

    def list_projets_by_client(self, client_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM projets WHERE client_id = ? ORDER BY date_creation DESC, id DESC",
                (client_id,),
            ).fetchall()

    def list_factures_by_projet(self, projet_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM factures WHERE projet_id = ? ORDER BY date_creation DESC, id DESC",
                (projet_id,),
            ).fetchall()

    def update_facture(
        self,
        facture_id: int,
        client_nom: str,
        projet: str,
        montant_ht: Decimal,
        tva_pourcent: Decimal,
        statut: str,
        notes: str,
        lines: Optional[list[dict[str, str]]] = None,
    ) -> None:
        lines_payload = lines or []
        if lines_payload:
            montant_ht = self._facture_lines_ht(lines_payload)
        montant_tva = (montant_ht * tva_pourcent) / Decimal("100")
        montant_ttc = montant_ht + montant_tva
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE factures
                SET client_nom=?, projet=?, montant_ht=?, tva_pourcent=?, montant_tva=?, montant_ttc=?, statut=?, lines_json=?, notes=?, date_modification=?
                WHERE id=?
                """,
                (
                    client_nom,
                    projet,
                    str(montant_ht),
                    str(tva_pourcent),
                    str(montant_tva),
                    str(montant_ttc),
                    statut,
                    json.dumps(lines_payload, ensure_ascii=False),
                    notes,
                    datetime.now().isoformat(),
                    facture_id,
                ),
            )
            conn.commit()

    def _facture_lines_ht(self, lines: list[dict[str, str]]) -> Decimal:
        total = Decimal("0")
        for line in lines:
            qte = Decimal(str(line.get("quantite", "0")))
            pu = Decimal(str(line.get("prix_unitaire_ht", "0")))
            total += qte * pu
        return total

    # ---- Depenses / Suivi ----
    def add_depense(
        self,
        facture_id: Optional[int],
        client_nom: str,
        projet: str,
        categorie: str,
        montant: Decimal,
        notes: str = "",
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO depenses (facture_id, date_depense, client_nom, projet, categorie, montant, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    facture_id,
                    datetime.now().date().isoformat(),
                    client_nom,
                    projet,
                    categorie,
                    str(montant),
                    notes,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def list_depenses(self, facture_id: Optional[int] = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM depenses"
        params: tuple[object, ...] = ()
        if facture_id is not None:
            query += " WHERE facture_id = ?"
            params = (facture_id,)
        query += " ORDER BY date_depense DESC, id DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return rows

    def total_depenses_facture(self, facture_id: int) -> Decimal:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(CAST(montant AS REAL)), 0) AS total FROM depenses WHERE facture_id = ?",
                (facture_id,),
            ).fetchone()
        return Decimal(str(row["total"] if row else 0))

    # ---- Facture payload (edition complete type devis) ----
    def generate_next_facture_numero(self) -> str:
        with self._connect() as conn:
            return self._next_facture_numero(conn)

    def _serialize_facture_payload(self, devis: Devis) -> str:
        payload = {
            "numero": devis.numero,
            "date_devis": devis.date_devis.isoformat(),
            "validite_jours": devis.validite_jours,
            "reference_affaire": devis.reference_affaire,
            "client": json.loads(self._serialize_client(devis.client)),
            "chantier": json.loads(self._serialize_chantier(devis.chantier)),
            "modalites_paiement": devis.modalites_paiement,
            "delais": devis.delais,
            "remarques": devis.remarques,
            "statut": devis.statut,
            "tva_pourcent_global": str(devis.tva_pourcent_global),
            "utiliser_lots": bool(devis.utiliser_lots),
            "lots": json.loads(self._serialize_lots(devis.lots)),
        }
        return json.dumps(payload, ensure_ascii=False)

    def _parse_facture_payload(self, raw_json: str) -> Devis:
        data = json.loads(raw_json or "{}")
        devis = Devis(
            numero=data.get("numero", ""),
            date_devis=datetime.fromisoformat(data.get("date_devis")).date() if data.get("date_devis") else datetime.now().date(),
            validite_jours=int(data.get("validite_jours", 30)),
            reference_affaire=data.get("reference_affaire", ""),
            client=self._parse_client(json.dumps(data.get("client", {}), ensure_ascii=False)),
            chantier=self._parse_chantier(json.dumps(data.get("chantier", {}), ensure_ascii=False)),
            modalites_paiement=data.get("modalites_paiement", ""),
            delais=data.get("delais", ""),
            remarques=data.get("remarques", ""),
            statut=data.get("statut", "Facture"),
            tva_pourcent_global=Decimal(data.get("tva_pourcent_global", "20")),
            utiliser_lots=bool(data.get("utiliser_lots", True)),
            lots=self._parse_lots(json.dumps(data.get("lots", []), ensure_ascii=False)),
        )
        return devis

    def create_facture_empty(self) -> int:
        numero = self.generate_next_facture_numero()
        devis = Devis(numero=numero, statut="Facture")
        now = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO factures (
                    numero, date_facture, client_id, projet_id, client_nom, projet, source_devis_id,
                    montant_ht, tva_pourcent, montant_tva, montant_ttc, statut,
                    lines_json, payload_json, notes, date_creation, date_modification
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    numero,
                    devis.date_devis.isoformat(),
                    None,
                    None,
                    "",
                    "",
                    None,
                    "0",
                    str(devis.tva_pourcent_global),
                    "0",
                    "0",
                    "Brouillon",
                    "[]",
                    self._serialize_facture_payload(devis),
                    "",
                    now,
                    now,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def read_facture_devis(self, facture_id: int) -> Optional[Devis]:
        row = self.read_facture(facture_id)
        if row is None:
            return None
        raw = row["payload_json"] or "{}"
        devis = self._parse_facture_payload(raw)
        devis.numero = row["numero"] or devis.numero
        devis.statut = "Facture"
        return devis

    def update_facture_devis(self, facture_id: int, devis: Devis, statut: str = "Brouillon", notes: str = "") -> None:
        client_id, projet_id = self.validate_prospect_to_client_project(devis)
        facture_row = self.read_facture(facture_id)
        if facture_row is None:
            raise ValueError(f"Facture introuvable: {facture_id}")
        facture_numero = (devis.numero or "").strip() or facture_row["numero"]
        payload_devis = deepcopy(devis)
        payload_devis.numero = facture_numero
        payload_devis.statut = "Facture"
        montant_ht = devis.calculer_total_ht()
        taux = devis.tva_pourcent_global
        montant_tva = (montant_ht * taux) / Decimal("100")
        montant_ttc = montant_ht + montant_tva
        lines: list[dict[str, str]] = []
        for lot in devis.lots:
            for ligne in lot.lignes:
                qte = Decimal("1") if ligne.unite.lower() == "forfait" else ligne.quantite
                qte = qte * ligne.mesure
                lines.append(
                    {
                        "designation": ligne.designation or lot.nom or "Prestation",
                        "unite": ligne.unite,
                        "quantite": str(qte),
                        "prix_unitaire_ht": str(ligne.prix_unitaire_ht),
                    }
                )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE factures
                SET numero=?, date_facture=?, client_id=?, projet_id=?, client_nom=?, projet=?, montant_ht=?, tva_pourcent=?, montant_tva=?, montant_ttc=?,
                    statut=?, lines_json=?, payload_json=?, notes=?, date_modification=?
                WHERE id=?
                """,
                (
                    facture_numero,
                    devis.date_devis.isoformat(),
                    client_id,
                    projet_id,
                    devis.client.nom,
                    devis.reference_affaire or devis.chantier.adresse or "",
                    str(montant_ht),
                    str(taux),
                    str(montant_tva),
                    str(montant_ttc),
                    statut,
                    json.dumps(lines, ensure_ascii=False),
                    self._serialize_facture_payload(payload_devis),
                    notes,
                    datetime.now().isoformat(),
                    facture_id,
                ),
            )
            conn.commit()

    # ---- Prospect -> Client/Projet ----
    def validate_prospect_to_client_project(self, devis: Devis) -> tuple[int, int]:
        if not devis.client.nom.strip():
            raise ValueError("Le prospect doit avoir un nom client.")
        projet_nom = (devis.reference_affaire or devis.chantier.adresse or devis.numero).strip()
        if not projet_nom:
            projet_nom = "Projet"
        now = datetime.now().isoformat()
        client_payload = json.dumps(
            {
                "adresse": devis.client.adresse,
                "code_postal": devis.client.code_postal,
                "ville": devis.client.ville,
                "telephone": devis.client.telephone,
                "email": devis.client.email,
            },
            ensure_ascii=False,
        )
        projet_payload = json.dumps(
            {
                "chantier": json.loads(self._serialize_chantier(devis.chantier)),
                "source_devis_numero": devis.numero,
            },
            ensure_ascii=False,
        )
        with self._connect() as conn:
            row_client = conn.execute("SELECT id FROM clients WHERE nom = ?", (devis.client.nom.strip(),)).fetchone()
            if row_client is None:
                cursor = conn.execute(
                    "INSERT INTO clients (nom, data_json, date_creation, date_modification) VALUES (?, ?, ?, ?)",
                    (devis.client.nom.strip(), client_payload, now, now),
                )
                client_id = int(cursor.lastrowid)
            else:
                client_id = int(row_client["id"])
                conn.execute(
                    "UPDATE clients SET data_json=?, date_modification=? WHERE id=?",
                    (client_payload, now, client_id),
                )

            row_proj = conn.execute(
                "SELECT id FROM projets WHERE client_id = ? AND nom = ?",
                (client_id, projet_nom),
            ).fetchone()
            if row_proj is None:
                cursor = conn.execute(
                    """
                    INSERT INTO projets (client_id, nom, source_devis_id, statut, data_json, date_creation, date_modification)
                    VALUES (?, ?, ?, 'Actif', ?, ?, ?)
                    """,
                    (client_id, projet_nom, devis.id, projet_payload, now, now),
                )
                projet_id = int(cursor.lastrowid)
            else:
                projet_id = int(row_proj["id"])
                conn.execute(
                    "UPDATE projets SET source_devis_id=?, data_json=?, date_modification=? WHERE id=?",
                    (devis.id, projet_payload, now, projet_id),
                )
            conn.commit()

        if devis.id:
            devis.statut = "Accepté"
            self.update(devis)
        return client_id, projet_id
