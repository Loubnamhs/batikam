# Solution : Problème de compatibilité Python 3.14 avec PySide6

## Problème

PySide6 6.6.0+ ne supporte pas Python 3.14 (limite: Python 3.12).
Vous avez Python 3.14.2, ce qui cause l'erreur :
```
ERROR: Could not find a version that satisfies the requirement PySide6>=6.6.0
```

## Solutions

### Solution 1 : Utiliser Python 3.12 dans un venv (Recommandé)

```bash
# Installer Python 3.12 avec Homebrew (si nécessaire)
brew install python@3.12

# Créer un venv avec Python 3.12
python3.12 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python -m app
```

### Solution 2 : Installer PySide6 sans contrainte de version

J'ai modifié `requirements.txt` pour installer la dernière version compatible :

```bash
pip install PySide6
```

Puis installer les autres dépendances :
```bash
pip install reportlab docxtpl python-docx
```

### Solution 3 : Utiliser PyQt6 à la place (alternative)

Si PySide6 ne fonctionne pas, vous pouvez utiliser PyQt6 :

```bash
pip install PyQt6
```

Puis modifier les imports dans le code :
- `from PySide6` → `from PyQt6`
- `app.exec()` → `app.exec()` (identique)

### Solution 4 : Installer PySide6 depuis les sources (avancé)

```bash
pip install --upgrade pip
pip install PySide6 --no-binary PySide6
```

## Vérification

Après installation, vérifiez :
```bash
python3 -c "import PySide6; print(f'PySide6 {PySide6.__version__} installé')"
```

## Recommandation

**Utilisez la Solution 1** (Python 3.12 dans un venv) pour garantir la compatibilité avec toutes les dépendances.
