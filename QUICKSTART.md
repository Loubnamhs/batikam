# Démarrage rapide

## Installation

### Méthode automatique (recommandée)

```bash
./setup.sh
```

### Méthode manuelle

```bash
# Créer un environnement virtuel
python3 -m venv venv
source venv/bin/activate  # Sur macOS/Linux
# ou: venv\Scripts\activate  # Sur Windows

# Installer les dépendances
pip install -r requirements.txt
```

### Alternative : Installation utilisateur (si venv ne fonctionne pas)

```bash
python3 -m pip install --user -r requirements.txt
```

## Lancement

### Avec environnement virtuel

```bash
./run.sh
```

Ou manuellement :
```bash
source venv/bin/activate
python -m app
```

### Sans environnement virtuel

**Important :** Utilisez `python3` et non `python` (qui pointe vers Python 2.7 sur macOS).

```bash
python3 -m app
```

## Première utilisation

1. Cliquez sur "Nouveau devis"
2. Remplissez les informations client et chantier
3. Ajoutez un lot avec "Ajouter un lot"
4. Ajoutez des lignes avec "Ajouter une ligne"
5. Remplissez les lignes (désignation, quantité, prix unitaire, etc.)
6. Les totaux se calculent automatiquement
7. Cliquez sur "Sauvegarder"

## Export

- **Export PDF** : Génère un PDF professionnel avec ReportLab
- **Export DOCX** : Génère un document Word à partir du template

## Tests

```bash
pytest tests/
```

## Structure des données

Les devis sont sauvegardés dans `batikam_devis.db` (SQLite local).

## Notes

- Le numéro de devis est auto-généré au format YYYY-NNNN
- Les calculs sont en temps réel
- L'option "Forcer total" permet d'override le calcul automatique
- Le template DOCX est créé automatiquement s'il n'existe pas
