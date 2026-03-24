# Installation Simple - Batikam Rénove

## Option 1 : Installation avec environnement virtuel (Recommandé)

Exécutez simplement :
```bash
./setup.sh
```

Puis lancez l'application :
```bash
./run.sh
```

## Option 2 : Installation manuelle avec venv

```bash
# Créer l'environnement virtuel
python3 -m venv venv

# Activer l'environnement
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python -m app
```

## Option 3 : Installation avec --user (si venv ne fonctionne pas)

```bash
python3 -m pip install --user -r requirements.txt
python3 -m app
```

## Option 4 : Installation avec pipx (pour une application standalone)

```bash
# Installer pipx si nécessaire
brew install pipx

# Installer l'application
pipx install -e .
```

## Vérification

Pour vérifier que tout est installé :
```bash
python3 -c "import PySide6; print('✅ PySide6 installé')"
python3 -c "import reportlab; print('✅ ReportLab installé')"
python3 -c "import docxtpl; print('✅ docxtpl installé')"
```

## Dépannage

### Erreur "externally-managed-environment"
→ Utilisez l'Option 1 (environnement virtuel) ou l'Option 3 (--user)

### Erreur "Permission denied"
→ Utilisez l'Option 3 (--user) ou l'Option 1 (venv)

### Erreur "No module named 'PySide6'"
→ Vérifiez que les dépendances sont installées avec une des options ci-dessus
