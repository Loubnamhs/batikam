#!/bin/bash
# Script d'installation pour Batikam Rénove

set -e

echo "🚀 Installation de Batikam Rénove..."
echo ""

# Vérifier Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python $PYTHON_VERSION détecté"
echo ""

# Créer l'environnement virtuel s'il n'existe pas
if [ ! -d "venv" ]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv venv
    echo "✅ Environnement virtuel créé"
else
    echo "✅ Environnement virtuel déjà présent"
fi

echo ""

# Activer l'environnement virtuel et installer les dépendances
echo "📥 Installation des dépendances..."
source venv/bin/activate
pip install --upgrade pip

# Détecter la version de Python
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

# Si Python 3.14+, utiliser le fichier requirements spécial
if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 14 ]; then
    echo "⚠️  Python 3.14+ détecté. Utilisation de requirements_python314.txt"
    if [ -f "requirements_python314.txt" ]; then
        pip install -r requirements_python314.txt
    else
        echo "⚠️  requirements_python314.txt non trouvé, installation de PySide6 sans contrainte..."
        pip install PySide6 reportlab docxtpl python-docx pytest pytest-qt pyinstaller
    fi
else
    pip install -r requirements.txt
fi

echo ""
echo "✅ Installation terminée avec succès !"
echo ""
echo "Pour lancer l'application :"
echo "  source venv/bin/activate"
echo "  python3 -m app"
echo ""
echo "Ou utilisez le script run.sh qui active automatiquement l'environnement virtuel."
