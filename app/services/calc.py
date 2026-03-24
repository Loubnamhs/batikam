"""Fonctions de calcul pour les devis."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


CENTIME = Decimal("0.01")


def to_decimal(value: Decimal | str | int | float | None) -> Decimal:
    """Convertit une valeur en Decimal de maniere robuste."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def parse_decimal_fr(value: str) -> Decimal:
    """Parse une valeur numerique FR/EN depuis une chaine."""
    return to_decimal(value.strip().replace(" ", "").replace(",", "."))


def format_euro_fr(value: Decimal) -> str:
    """Formate une valeur en euros avec virgule francaise."""
    return f"{arrondir_deux_decimales(value):.2f} €".replace(".", ",")


def arrondir_deux_decimales(value: Decimal) -> Decimal:
    """Arrondit a 2 decimales."""
    return to_decimal(value).quantize(CENTIME, rounding=ROUND_HALF_UP)


def calculer_total_ligne_ht(
    quantite: Decimal,
    prix_unitaire_ht: Decimal,
    remise_pourcent: Decimal,
    total_force: Optional[Decimal] = None
) -> Decimal:
    """
    Calcule le total HT d'une ligne.
    
    Args:
        quantite: Quantité
        prix_unitaire_ht: Prix unitaire HT
        remise_pourcent: Remise en pourcentage
        total_force: Total forcé (si None, calcule normalement)
    
    Returns:
        Total HT arrondi à 2 décimales
    """
    quantite = to_decimal(quantite)
    prix_unitaire_ht = to_decimal(prix_unitaire_ht)
    remise_pourcent = to_decimal(remise_pourcent)

    if total_force is not None:
        return arrondir_deux_decimales(to_decimal(total_force))

    total = (quantite * prix_unitaire_ht) * (Decimal("1") - (remise_pourcent / Decimal("100")))
    return arrondir_deux_decimales(total)


def calculer_tva_ligne(total_ligne_ht: Decimal, tva_pourcent: Decimal) -> Decimal:
    """
    Calcule la TVA d'une ligne.
    
    Args:
        total_ligne_ht: Total HT de la ligne
        tva_pourcent: TVA en pourcentage
    
    Returns:
        TVA arrondie à 2 décimales
    """
    total_ligne_ht = to_decimal(total_ligne_ht)
    tva_pourcent = to_decimal(tva_pourcent)
    tva = total_ligne_ht * (tva_pourcent / Decimal("100"))
    return arrondir_deux_decimales(tva)


def calculer_sous_total_lot(totaux_lignes: list[Decimal]) -> Decimal:
    """
    Calcule le sous-total d'un lot.
    
    Args:
        totaux_lignes: Liste des totaux HT des lignes
    
    Returns:
        Sous-total arrondi à 2 décimales
    """
    total = sum(totaux_lignes)
    return arrondir_deux_decimales(total)


def calculer_totaux_globaux(
    total_ht: Decimal,
    total_tva: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Calcule les totaux globaux.
    
    Args:
        total_ht: Total HT
        total_tva: Total TVA
    
    Returns:
        Tuple (HT, TVA, TTC)
    """
    total_ht = arrondir_deux_decimales(total_ht)
    total_tva = arrondir_deux_decimales(total_tva)
    total_ttc = arrondir_deux_decimales(total_ht + total_tva)
    return total_ht, total_tva, total_ttc
