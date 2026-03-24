# Batikam Rénove - Gestion des Devis

Application desktop Python pour créer, éditer et imprimer des devis "Batikam Rénove".

## Technologies

- **Python 3.11+**
- **PySide6** (Qt) pour l'interface graphique
- **SQLite** pour la persistance des données
- **ReportLab** pour l'export PDF
- **docxtpl** pour l'export DOCX
- **PyInstaller** pour le build Windows

## Installation (développement sur macOS)

### Installation automatique (recommandé)

```bash
./setup.sh
```

Ce script crée automatiquement l'environnement virtuel et installe toutes les dépendances.

### Installation manuelle

1. Créer un environnement virtuel :
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Installer les dépendances :
```bash
pip install -r requirements.txt
```

## Lancement

### Avec environnement virtuel (recommandé)

Si vous avez utilisé `./setup.sh`, utilisez simplement :
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

## Structure du projet

```
batikam/
├── app/
│   ├── main.py              # Point d'entrée
│   ├── models/              # Modèles de données
│   ├── ui/                  # Interface Qt
│   └── services/            # Services (storage, export, calculs)
├── assets/                  # Logo, documents de référence
├── templates/               # Template DOCX
├── tests/                   # Tests unitaires
└── requirements.txt
```

## Fonctionnalités

### Gestion des devis (CRUD)
- Liste des devis avec recherche et tri
- Création, édition, duplication, suppression
- Sauvegarde automatique en SQLite

### Éditeur de devis
- **En-tête** : N° devis (auto), date, validité, référence affaire
- **Client** : Nom, adresse, CP/ville, téléphone, email
- **Chantier** : Adresse, CP/ville
- **Conditions** : Modalités de paiement, délais, remarques

### Lots et lignes
- Organisation par lots (Lot 1, Lot 2...)
- Lignes avec : Désignation, Unité, Quantité, Prix unitaire HT, Remise %, TVA %
- Calcul automatique des totaux (HT, TVA, TTC)
- Option "Forcer total" pour override manuel

### Calculs
- Total ligne HT = (qty × pu_ht) × (1 - remise/100)
- TVA ligne = total_ligne_ht × (tva/100)
- Totaux globaux : somme HT / somme TVA / somme TTC
- Recalcul en temps réel

### Exports
- **PDF** : Génération native avec ReportLab
- **DOCX** : Remplissage de template avec docxtpl

## Tests

Lancer les tests :
```bash
pytest tests/
```

Les tests couvrent :
- Calculs de totaux (avec et sans remise)
- Calculs de TVA
- Cas avec override de total
- Arrondis corrects

## Build Windows (Release)

### Build local sur Windows

Depuis PowerShell (dans le dossier du projet) :

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
.\scripts\build_windows.ps1 -Version "v1.0.0"
```

Artefact généré :
- `dist/release/BatikamRenove-Windows-v1.0.0.zip`

### Build/Releases automatisés (GitHub Actions)

Le workflow `.github/workflows/build-windows.yml` :
- installe les dépendances,
- lance les tests,
- génère un package Windows via PyInstaller (`onedir`),
- publie l'artefact ZIP.

Sur un tag `v*` (ex: `v1.2.0`), il crée aussi automatiquement une release GitHub avec le ZIP attaché.

## Format des numéros de devis

Format : `YYYY-NNNN` (ex: `2026-0001`)

Numérotation automatique par année.

## Base de données

Fichier SQLite local : `batikam_devis.db`

Structure :
- Table `devis` avec tous les champs
- Données client/chantier/lots stockées en JSON

## Licence

Propriétaire - Batikam Rénove
