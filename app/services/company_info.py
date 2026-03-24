# -*- coding: utf-8 -*-
"""Informations société Batikam Renov (source unique)."""

import json
from dataclasses import dataclass
from dataclasses import asdict
from pathlib import Path


@dataclass(frozen=True)
class CompanyInfo:
    forme: str = "SASU"
    raison_sociale: str = "Société Batikam Renov"
    adresse: str = "18 Avenue de la paix"
    code_postal_ville: str = "92600 Asnières-sur-Seine"
    siret: str = "999878119"
    rcs: str = "Nanterre"
    tva: str = "FR64999878119"
    telephone: str = "07 68 71 93 85"
    email: str = "batikamrenove@gmail.com"
    banque_nom: str = "BRED Asnières Hôtel de Ville"
    code_banque: str = "10107"
    code_guichet: str = "00281"
    iban: str = "FR76 1010 7002 8100 5220 6227 324"
    bic: str = "BREDFRPPXX"


COMPANY_INFO_PATH = Path("company_info.json")


def get_company_info(path: Path = COMPANY_INFO_PATH) -> CompanyInfo:
    defaults = CompanyInfo()
    if not path.exists():
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defaults
    if not isinstance(raw, dict):
        return defaults
    data = {}
    for field in defaults.__dataclass_fields__:
        value = raw.get(field, getattr(defaults, field))
        data[field] = value if isinstance(value, str) else str(value)
    return CompanyInfo(**data)


def save_company_info(info: CompanyInfo, path: Path = COMPANY_INFO_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(info), ensure_ascii=False, indent=2), encoding="utf-8")
