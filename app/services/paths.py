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
    return executable_dir() / filename
