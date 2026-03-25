# -*- coding: utf-8 -*-
"""Branding helpers (logo principal, assets)."""

from pathlib import Path
from typing import Optional

from app.services.paths import resolve_resource_path


def resolve_logo_path() -> Optional[Path]:
    """Return the primary app logo path if available."""
    candidates = (
        "assets/logo_principal.png",
        "assets/logo_main.png",
        "assets/logo_transparent.png",
        "assets/logo.png",
    )
    for candidate in candidates:
        path = resolve_resource_path(candidate)
        if path.exists():
            return path
    return None


def resolve_logo_str() -> Optional[str]:
    path = resolve_logo_path()
    return str(path) if path else None
