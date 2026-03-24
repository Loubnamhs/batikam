"""Service de numérotation automatique des devis."""

from datetime import datetime
from typing import Optional
import sqlite3


def generer_numero_devis(annee: Optional[int] = None) -> str:
    """
    Génère un numéro de devis au format YYYY-NNNN.
    
    Args:
        annee: Année (par défaut année courante)
    
    Returns:
        Numéro de devis (ex: "2026-0001")
    """
    if annee is None:
        annee = datetime.now().year
    
    return f"DEV-{annee}-0001"


def _extract_sequence(numero: str, annee: int) -> Optional[int]:
    """Extrait la séquence d'un numéro devis historique ou nouveau format."""
    if not numero:
        return None
    numero = numero.strip().upper()
    if numero.startswith(f"DEV-{annee}-"):
        try:
            return int(numero.split("-")[-1])
        except (ValueError, IndexError):
            return None
    # Compatibilité historique: YYYY-XXXX
    if numero.startswith(f"{annee}-"):
        try:
            return int(numero.split("-")[-1])
        except (ValueError, IndexError):
            return None
    return None


def obtenir_prochain_numero(db_path: str, annee: Optional[int] = None) -> str:
    """
    Obtient le prochain numéro de devis disponible.
    
    Args:
        db_path: Chemin vers la base SQLite
        annee: Année (par défaut année courante)
    
    Returns:
        Numéro de devis (ex: "2026-0001")
    """
    if annee is None:
        annee = datetime.now().year
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Récupérer le dernier numéro pour cette année
        rows = cursor.execute("SELECT numero FROM devis").fetchall()
        
        conn.close()
        
        max_seq = 0
        for row in rows:
            seq = _extract_sequence(row[0], annee)
            if seq is not None and seq > max_seq:
                max_seq = seq

        return f"DEV-{annee}-{max_seq + 1:04d}"
    
    except sqlite3.Error:
        # En cas d'erreur, retourner un numéro par défaut
        return f"DEV-{annee}-0001"
