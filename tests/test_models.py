"""Tests pour les modèles de données."""

import pytest
from decimal import Decimal
from datetime import date

from app.models.devis import Devis, Client, Chantier, Lot, Ligne


class TestLigne:
    """Tests pour le modèle Ligne."""
    
    def test_calculer_total_ht_simple(self):
        """Test calcul total HT simple."""
        ligne = Ligne(
            quantite=Decimal("10"),
            prix_unitaire_ht=Decimal("5"),
            remise_pourcent=Decimal("0")
        )
        assert ligne.calculer_total_ht() == Decimal("50.00")
    
    def test_calculer_total_ht_avec_remise(self):
        """Test calcul avec remise."""
        ligne = Ligne(
            quantite=Decimal("10"),
            prix_unitaire_ht=Decimal("5"),
            remise_pourcent=Decimal("10")
        )
        assert ligne.calculer_total_ht() == Decimal("45.00")
    
    def test_calculer_total_ht_force(self):
        """Test avec total forcé."""
        ligne = Ligne(
            quantite=Decimal("10"),
            prix_unitaire_ht=Decimal("5"),
            remise_pourcent=Decimal("0"),
            total_ligne_ht=Decimal("75"),
            forcer_total=True
        )
        assert ligne.calculer_total_ht() == Decimal("75.00")
    
    def test_calculer_tva(self):
        """Test calcul TVA."""
        ligne = Ligne(
            quantite=Decimal("10"),
            prix_unitaire_ht=Decimal("10"),
            remise_pourcent=Decimal("0"),
            tva_pourcent=Decimal("20")
        )
        assert ligne.calculer_total_ht() == Decimal("100.00")
        assert ligne.calculer_tva() == Decimal("20.00")


class TestLot:
    """Tests pour le modèle Lot."""
    
    def test_calculer_sous_total_ht(self):
        """Test calcul sous-total lot."""
        lot = Lot(nom="Lot 1")
        lot.lignes.append(Ligne(
            quantite=Decimal("10"),
            prix_unitaire_ht=Decimal("5"),
            remise_pourcent=Decimal("0")
        ))
        lot.lignes.append(Ligne(
            quantite=Decimal("5"),
            prix_unitaire_ht=Decimal("10"),
            remise_pourcent=Decimal("0")
        ))
        
        assert lot.calculer_sous_total_ht() == Decimal("100.00")


class TestDevis:
    """Tests pour le modèle Devis."""
    
    def test_calculer_totaux(self):
        """Test calcul des totaux d'un devis."""
        devis = Devis()
        
        lot1 = Lot(nom="Lot 1")
        lot1.lignes.append(Ligne(
            quantite=Decimal("10"),
            prix_unitaire_ht=Decimal("10"),
            remise_pourcent=Decimal("0"),
            tva_pourcent=Decimal("20")
        ))
        
        lot2 = Lot(nom="Lot 2")
        lot2.lignes.append(Ligne(
            quantite=Decimal("5"),
            prix_unitaire_ht=Decimal("20"),
            remise_pourcent=Decimal("10"),
            tva_pourcent=Decimal("20")
        ))
        
        devis.lots = [lot1, lot2]
        
        assert devis.calculer_total_ht() == Decimal("190.00")  # 100 + 90
        assert devis.calculer_total_tva() == Decimal("38.00")  # 20 + 18
        assert devis.calculer_total_ttc() == Decimal("228.00")  # 190 + 38
