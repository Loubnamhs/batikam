#!/bin/bash
# Script de lancement pour Batikam Rénove
# Active l'environnement virtuel si présent, sinon utilise Python 3 directement

if [ -d "venv" ]; then
    source venv/bin/activate
    python -m app "$@"
else
    echo "⚠️  Environnement virtuel non trouvé. Utilisation de Python 3 système."
    echo "💡 Pour créer un environnement virtuel, exécutez : ./setup.sh"
    python3 -m app "$@"
fi
