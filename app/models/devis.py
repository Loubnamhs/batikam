"""Modeles de donnees pour les devis."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from app.services.calc import (
    arrondir_deux_decimales,
    calculer_total_ligne_ht,
    calculer_tva_ligne,
    to_decimal,
)


@dataclass
class Client:
    """Informations client."""
    nom: str = ""
    adresse: str = ""
    code_postal: str = ""
    ville: str = ""
    telephone: str = ""
    email: str = ""


@dataclass
class Chantier:
    """Informations chantier."""
    adresse: str = ""
    code_postal: str = ""
    ville: str = ""


@dataclass
class Ligne:
    """Ligne de devis."""
    designation: str = ""
    unite: str = "U"  # U, m2, ml, forfait
    quantite: Decimal = Decimal("0")
    mesure: Decimal = Decimal("1")  # Colonne m2/ml
    prix_unitaire_ht: Decimal = Decimal("0")
    remise_pourcent: Decimal = Decimal("0")
    tva_pourcent: Decimal = Decimal("20")
    total_ligne_ht: Optional[Decimal] = None  # None = calculé, sinon override
    forcer_total: bool = False
    
    def calculer_total_ht(self) -> Decimal:
        """Calcule le total HT de la ligne."""
        quantite = Decimal("1") if self.unite.lower() == "forfait" else to_decimal(self.quantite)
        mesure = to_decimal(self.mesure)
        total_force = self.total_ligne_ht if self.forcer_total else None
        return calculer_total_ligne_ht(
            quantite=quantite * mesure,
            prix_unitaire_ht=self.prix_unitaire_ht,
            remise_pourcent=self.remise_pourcent,
            total_force=total_force,
        )
    
    def calculer_tva(self) -> Decimal:
        """Calcule la TVA de la ligne."""
        return calculer_tva_ligne(self.calculer_total_ht(), self.tva_pourcent)


@dataclass
class Lot:
    """Lot de devis contenant des lignes."""
    nom: str = ""
    lignes: list[Ligne] = field(default_factory=list)
    
    def calculer_sous_total_ht(self) -> Decimal:
        """Calcule le sous-total HT du lot."""
        total = sum((ligne.calculer_total_ht() for ligne in self.lignes), Decimal("0"))
        return arrondir_deux_decimales(total)


@dataclass
class Devis:
    """Devis complet."""
    id: Optional[int] = None
    numero: str = ""
    date_devis: date = field(default_factory=date.today)
    validite_jours: int = 30
    reference_affaire: str = ""
    client: Client = field(default_factory=Client)
    chantier: Chantier = field(default_factory=Chantier)
    modalites_paiement: str = ""
    delais: str = ""
    remarques: str = ""
    statut: str = "Brouillon"  # Brouillon, Envoyé, Accepté, Refusé
    tva_pourcent_global: Decimal = Decimal("20")
    utiliser_lots: bool = True
    lots: list[Lot] = field(default_factory=list)
    date_creation: Optional[datetime] = None
    date_modification: Optional[datetime] = None
    
    def calculer_total_ht(self) -> Decimal:
        """Calcule le total HT de tous les lots."""
        total = sum((lot.calculer_sous_total_ht() for lot in self.lots), Decimal("0"))
        return arrondir_deux_decimales(total)
    
    def calculer_total_tva(self) -> Decimal:
        """Calcule le total TVA."""
        base = self.calculer_total_ht()
        taux = to_decimal(self.tva_pourcent_global)
        total_tva = (base * taux) / Decimal("100")
        return arrondir_deux_decimales(total_tva)
    
    def calculer_total_ttc(self) -> Decimal:
        """Calcule le total TTC."""
        return arrondir_deux_decimales(self.calculer_total_ht() + self.calculer_total_tva())
