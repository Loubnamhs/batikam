# -*- coding: utf-8 -*-
"""Constantes de style partagées pour les rendus PDF/DOCX.

Palette sobre, professionnelle — inspirée Apple / Material Design.
Un seul accent fort (ardoise), le reste en nuances de blanc/gris clair.
"""

from __future__ import annotations


# ── Palette principale ────────────────────────────────────────────────────────
COLOR_NAVY        = "#1A2B4A"   # Ardoise profond — accent unique (titres, TTC…)
COLOR_GOLD        = "#B8974B"   # Or chaleureux — filet footer, séparateur header
COLOR_BORDER      = "#E5E7EB"   # Séparateurs ultra-fins
COLOR_SOFT        = "#F9FAFB"   # Fond quasi-blanc
COLOR_SECTION     = "#F3F4F6"   # Zones notes / mentions
COLOR_TEXT        = "#111827"   # Texte principal (quasi-noir)
COLOR_MUTED       = "#6B7280"   # Texte secondaire / labels

# ── Palette tableau ───────────────────────────────────────────────────────────
# Header clair (pas sombre) — texte quasi-noir pour lisibilité maximale
COLOR_TABLE_HEADER_BG   = "#F0F2F5"   # Gris clair neutre
COLOR_TABLE_HEADER_TEXT = "#111827"   # Quasi-noir
COLOR_TABLE_STRIP_BG    = "#F9FAFB"   # Alternance très subtile
COLOR_TABLE_LOT_BG      = "#EEF2F8"   # En-tête lot — bleu ardoise très clair
COLOR_TABLE_SUBTOTAL_BG = "#E8EDF5"   # Sous-total — légèrement plus marqué
COLOR_TABLE_SUBTOTAL_TEXT = "#1A2B4A" # Ardoise
COLOR_TABLE_GRID        = "#E5E7EB"   # Ligne séparatrice fine
COLOR_TABLE_ALT_BG      = "#F9FAFB"   # Ligne paire — presque blanc


# ── Dimensions header (PDF / DOCX) ───────────────────────────────────────────
# Total largeur utile = 18.5 cm (marges 1.1 cm × 2)
HEADER_LEFT_COL_CM  = 10.5
HEADER_RIGHT_COL_CM =  8.0

PDF_HEADER_LOGO_WIDTH_CM        =  8.0
PDF_HEADER_LOGO_HEIGHT_CM       =  4.5
PDF_HEADER_LOGO_X_OFFSET_CM     = -2.5
PDF_HEADER_LOGO_BOX_HEIGHT_CM   =  3.8
PDF_HEADER_GAP_LOGO_TO_COMPANY_CM = 0.0
PDF_HEADER_COMPANY_Y_OFFSET_PT    = 0
PDF_HEADER_COMPANY_LEFT_INDENT_PT = 0
PDF_HEADER_COMPANY_FONT_SIZE_PT   = 8.2
PDF_HEADER_COMPANY_LEADING_PT     = 10.0
PDF_HEADER_SPACER_AFTER_CM        = 0.5
PDF_HEADER_RIGHT_BLOCK_Y_OFFSET_PT = 0
PDF_HEADER_GAP_AFTER_CLIENT_PT    = 6
PDF_HEADER_GAP_AFTER_AFFAIRE_PT   = 8
PDF_SPACE_BEFORE_TABLE_CM         = 0.6

DOCX_HEADER_LOGO_WIDTH_CM       =  4.8
DOCX_HEADER_LOGO_HEIGHT_CM      =  2.2
DOCX_HEADER_LOGO_LEFT_INDENT_PT =  0
DOCX_HEADER_GAP_LOGO_TO_COMPANY_PT = 0
DOCX_HEADER_COMPANY_Y_OFFSET_PT    = 0
DOCX_HEADER_COMPANY_LEFT_INDENT_PT = 0
DOCX_HEADER_COMPANY_TITLE_FONT_PT  = 9.4
DOCX_HEADER_COMPANY_FONT_PT        = 8.9
DOCX_HEADER_COMPANY_LINE_AFTER_PT  = 2
DOCX_HEADER_LEGAL_AFTER_PT         = 8
DOCX_HEADER_DOC_BLOCK_GAP_PT       = 6
DOCX_HEADER_RIGHT_BLOCK_Y_OFFSET_PT = 0
DOCX_HEADER_GAP_AFTER_CLIENT_PT    = 6
DOCX_HEADER_GAP_AFTER_AFFAIRE_PT   = 8
DOCX_SPACE_BEFORE_TABLE_PT         = 18
DOCX_HEADER_LEFT_COL_CM   = 10.0
DOCX_HEADER_RIGHT_COL_CM  =  7.6
DOCX_LINE_TABLE_WIDTHS_CM = (10.5, 1.9, 2.2, 3.0)
DOCX_CONTENT_TABLE_WIDTH_CM = sum(DOCX_LINE_TABLE_WIDTHS_CM)

# ── Footer (DOCX) ─────────────────────────────────────────────────────────────
DOCX_FOOTER_DISTANCE_CM   = 0.7
DOCX_FOOTER_LINE_COLOR    = COLOR_GOLD
DOCX_FOOTER_TEXT_COLOR    = COLOR_MUTED
DOCX_FOOTER_LINE1_FONT_PT = 8.0
DOCX_FOOTER_LINE2_FONT_PT = 7.8
DOCX_FOOTER_LINE1_AFTER_PT = 1

# Backward compat
LOGO_WIDTH_CM = PDF_HEADER_LOGO_WIDTH_CM

# En-têtes du tableau prestations
LINE_TABLE_HEADERS = ["Description des travaux", "Qté", "PU HT", "Total HT"]
