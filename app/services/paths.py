# -*- coding: utf-8 -*-
"""Path helpers for development and frozen (PyInstaller) runtime."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root()


def bundle_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return executable_dir()


def resolve_resource_path(*parts: str) -> Path:
    rel = Path(*parts)
    candidates = (
        bundle_root() / rel,
        executable_dir() / rel,
        Path.cwd() / rel,
    )
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def app_data_path(filename: str) -> Path:
    """Retourne le chemin persistant de la BDD — unique par machine.

    - En mode frozen (exe installé) : %APPDATA%\\Batikam Renove\\
      Ce dossier est partagé par toutes les versions installées sur la machine,
      garantissant une seule base de données quelle que soit la version de l'exe.
    - En mode dev : dossier racine du projet
    """
    if is_frozen():
        import os
        appdata = os.environ.get("APPDATA")
        data_dir = Path(appdata) / "Batikam Renove" if appdata else Path.home() / ".batikam-renove"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / filename
    return executable_dir() / filename
