"""Tests unitaires pour les calculs."""

import pytest
from decimal import Decimal

from app.services.calc import (
    arrondir_deux_decimales,
    calculer_total_ligne_ht,
    calculer_tva_ligne,
    calculer_sous_total_lot,
    calculer_totaux_globaux
)


class TestCalculs:
    """Tests pour les fonctions de calcul."""
    
    def test_arrondir_deux_decimales(self):
        """Test de l'arrondi à 2 décimales."""
        assert arrondir_deux_decimales(Decimal("10.125")) == Decimal("10.13")
        assert arrondir_deux_decimales(Decimal("10.124")) == Decimal("10.12")
        assert arrondir_deux_decimales(Decimal("10.1255")) == Decimal("10.13")
        assert arrondir_deux_decimales(Decimal("10.00")) == Decimal("10.00")
    
    def test_calculer_total_ligne_ht_simple(self):
        """Test calcul total ligne HT simple."""
        # 10 unités à 5€ HT = 50€
        total = calculer_total_ligne_ht(
            Decimal("10"),
            Decimal("5"),
            Decimal("0")
        )
        assert total == Decimal("50.00")
    
    def test_calculer_total_ligne_ht_avec_remise(self):
        """Test calcul total ligne HT avec remise."""
        # 10 unités à 5€ HT avec 10% remise = 45€
        total = calculer_total_ligne_ht(
            Decimal("10"),
            Decimal("5"),
            Decimal("10")
        )
        assert total == Decimal("45.00")
    
    def test_calculer_total_ligne_ht_avec_remise_decimale(self):
        """Test calcul avec remise décimale."""
        # 3 unités à 10.50€ HT avec 15% remise = 26.78€
        total = calculer_total_ligne_ht(
            Decimal("3"),
            Decimal("10.50"),
            Decimal("15")
        )
        assert total == Decimal("26.78")
    
    def test_calculer_total_ligne_ht_force(self):
        """Test calcul avec total forcé."""
        # Total forcé à 100€, ignore qty/pu/remise
        total = calculer_total_ligne_ht(
            Decimal("10"),
            Decimal("5"),
            Decimal("0"),
            total_force=Decimal("100")
        )
        assert total == Decimal("100.00")
    
    def test_calculer_tva_ligne(self):
        """Test calcul TVA."""
        # 100€ HT avec 20% TVA = 20€
        tva = calculer_tva_ligne(Decimal("100"), Decimal("20"))
        assert tva == Decimal("20.00")
        
        # 50€ HT avec 10% TVA = 5€
        tva = calculer_tva_ligne(Decimal("50"), Decimal("10"))
        assert tva == Decimal("5.00")
    
    def test_calculer_sous_total_lot(self):
        """Test calcul sous-total lot."""
        totaux = [Decimal("100"), Decimal("50"), Decimal("25.75")]
        sous_total = calculer_sous_total_lot(totaux)
        assert sous_total == Decimal("175.75")
    
    def test_calculer_totaux_globaux(self):
        """Test calcul totaux globaux."""
        ht, tva, ttc = calculer_totaux_globaux(
            Decimal("1000"),
            Decimal("200")
        )
        assert ht == Decimal("1000.00")
        assert tva == Decimal("200.00")
        assert ttc == Decimal("1200.00")
    
    def test_cas_complexe_1(self):
        """Cas complexe : plusieurs lignes avec remises différentes."""
        # Ligne 1: 5 unités à 20€, 10% remise, 20% TVA
        total1 = calculer_total_ligne_ht(Decimal("5"), Decimal("20"), Decimal("10"))
        tva1 = calculer_tva_ligne(total1, Decimal("20"))
        
        # Ligne 2: 10 m² à 15€, 5% remise, 20% TVA
        total2 = calculer_total_ligne_ht(Decimal("10"), Decimal("15"), Decimal("5"))
        tva2 = calculer_tva_ligne(total2, Decimal("20"))
        
        # Totaux
        total_ht = total1 + total2
        total_tva = tva1 + tva2
        _, _, total_ttc = calculer_totaux_globaux(total_ht, total_tva)
        
        assert total_ht == Decimal("232.50")  # 90 + 142.50
        assert total_tva == Decimal("46.50")
        assert total_ttc == Decimal("279.00")
    
    def test_cas_override_total(self):
        """Cas avec override de total."""
        # Ligne normale
        total_normal = calculer_total_ligne_ht(Decimal("10"), Decimal("5"), Decimal("0"))
        
        # Même ligne avec total forcé
        total_force = calculer_total_ligne_ht(
            Decimal("10"),
            Decimal("5"),
            Decimal("0"),
            total_force=Decimal("75")
        )
        
        assert total_normal == Decimal("50.00")
        assert total_force == Decimal("75.00")
        assert total_force != total_normal
    
    def test_arrondi_cumulatif(self):
        """Test que les arrondis ne s'accumulent pas incorrectement."""
        # 3 lignes de 33.33€ chacune = 99.99€, arrondi correct
        total1 = calculer_total_ligne_ht(Decimal("1"), Decimal("33.33"), Decimal("0"))
        total2 = calculer_total_ligne_ht(Decimal("1"), Decimal("33.33"), Decimal("0"))
        total3 = calculer_total_ligne_ht(Decimal("1"), Decimal("33.33"), Decimal("0"))
        
        sous_total = calculer_sous_total_lot([total1, total2, total3])
        assert sous_total == Decimal("99.99")
