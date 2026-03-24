#!/bin/bash
# Script d'installation rapide des dépendances

echo "📦 Installation des dépendances pour Batikam Rénove..."
echo ""

# Vérifier si on est dans un venv
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Vous n'êtes pas dans un environnement virtuel."
    echo "💡 Activez votre venv d'abord : source venv/bin/activate"
    echo ""
    read -p "Continuer quand même ? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Détecter la version de Python
PYTHON_CMD="python3"
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
    echo "✅ Utilisation de Python 3.12"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
    echo "✅ Utilisation de $PYTHON_CMD (version $PYTHON_VERSION)"
else
    echo "❌ Python 3 n'est pas trouvé"
    exit 1
fi

echo ""
echo "📥 Mise à jour de pip..."
$PYTHON_CMD -m pip install --upgrade pip

echo ""
echo "📥 Installation des dépendances..."

# Installer PySide6 d'abord
echo "  - PySide6..."
$PYTHON_CMD -m pip install PySide6

# Installer les autres dépendances
echo "  - ReportLab..."
$PYTHON_CMD -m pip install reportlab

echo "  - docxtpl et python-docx..."
$PYTHON_CMD -m pip install docxtpl python-docx

echo "  - Tests..."
$PYTHON_CMD -m pip install pytest pytest-qt

echo "  - Build..."
$PYTHON_CMD -m pip install pyinstaller

echo ""
echo "✅ Installation terminée !"
echo ""
echo "Vérification des modules installés :"
$PYTHON_CMD -c "import PySide6; print('  ✅ PySide6', PySide6.__version__)" 2>/dev/null || echo "  ❌ PySide6"
$PYTHON_CMD -c "import reportlab; print('  ✅ ReportLab', reportlab.Version)" 2>/dev/null || echo "  ❌ ReportLab"
$PYTHON_CMD -c "import docxtpl; print('  ✅ docxtpl')" 2>/dev/null || echo "  ❌ docxtpl"
$PYTHON_CMD -c "import docx; print('  ✅ python-docx')" 2>/dev/null || echo "  ❌ python-docx"

echo ""
echo "🚀 Vous pouvez maintenant lancer l'application avec :"
echo "   python -m app"
echo "   ou"
echo "   ./run.sh"
