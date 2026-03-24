# Installation - Guide étape par étape

## Prérequis

- Python 3.11 ou supérieur
- pip (gestionnaire de paquets Python)

## Installation

### Option 1 : Installation globale (simple mais moins recommandé)

```bash
python3 -m pip install -r requirements.txt
```

### Option 2 : Avec environnement virtuel (recommandé)

1. Créer un environnement virtuel :
```bash
python3 -m venv venv
```

2. Activer l'environnement virtuel :
```bash
# Sur macOS/Linux :
source venv/bin/activate

# Sur Windows :
venv\Scripts\activate
```

3. Installer les dépendances :
```bash
pip install -r requirements.txt
```

4. Lancer l'application :
```bash
python3 -m app
```

## Vérification

Pour vérifier que PySide6 est installé :
```bash
python3 -c "import PySide6; print('PySide6 installé avec succès')"
```

## Dépannage

### Erreur "No module named 'PySide6'"
- Vérifiez que vous utilisez `python3` et non `python`
- Vérifiez que pip est à jour : `python3 -m pip install --upgrade pip`
- Réessayez l'installation : `python3 -m pip install -r requirements.txt`

### Erreur de permissions
Si vous obtenez une erreur de permissions, utilisez `--user` :
```bash
python3 -m pip install --user -r requirements.txt
```

Ou utilisez un environnement virtuel (Option 2 ci-dessus).
