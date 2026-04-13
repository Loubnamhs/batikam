# -*- coding: utf-8 -*-
"""Export DOCX Batikam - priorité qualité Word professionnelle."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Optional

from app.models.devis import Devis, Ligne
from app.services.branding import resolve_logo_path
from app.services.company_info import get_company_info
from app.services.paths import resolve_resource_path
from app.services.document_theme import (
    COLOR_BORDER,
    COLOR_GOLD,
    COLOR_NAVY,
    COLOR_SECTION,
    COLOR_TABLE_GRID,
    COLOR_TABLE_HEADER_BG,
    COLOR_TABLE_HEADER_TEXT,
    COLOR_TABLE_LOT_BG,
    COLOR_TABLE_STRIP_BG,
    COLOR_TABLE_SUBTOTAL_BG,
    COLOR_TABLE_SUBTOTAL_TEXT,
    DOCX_HEADER_GAP_AFTER_AFFAIRE_PT,
    DOCX_HEADER_GAP_AFTER_CLIENT_PT,
    DOCX_HEADER_COMPANY_LINE_AFTER_PT,
    DOCX_HEADER_DOC_BLOCK_GAP_PT,
    DOCX_HEADER_RIGHT_BLOCK_Y_OFFSET_PT,
    DOCX_HEADER_COMPANY_FONT_PT,
    DOCX_HEADER_COMPANY_LEFT_INDENT_PT,
    DOCX_HEADER_COMPANY_Y_OFFSET_PT,
    DOCX_HEADER_COMPANY_TITLE_FONT_PT,
    DOCX_HEADER_GAP_LOGO_TO_COMPANY_PT,
    DOCX_HEADER_LOGO_LEFT_INDENT_PT,
    DOCX_HEADER_LOGO_WIDTH_CM,
    DOCX_FOOTER_DISTANCE_CM,
    DOCX_FOOTER_LINE1_AFTER_PT,
    DOCX_FOOTER_LINE1_FONT_PT,
    DOCX_FOOTER_LINE2_FONT_PT,
    DOCX_FOOTER_LINE_COLOR,
    DOCX_FOOTER_TEXT_COLOR,
    DOCX_HEADER_LEFT_COL_CM,
    DOCX_HEADER_RIGHT_COL_CM,
    DOCX_LINE_TABLE_WIDTHS_CM,
    DOCX_CONTENT_TABLE_WIDTH_CM,
    DOCX_SPACE_BEFORE_TABLE_PT,
    LINE_TABLE_HEADERS,
)


def _set_cell_multiline(cell, text: str) -> None:
    """Écrit un texte multi-lignes dans une cellule DOCX en respectant les \\n."""
    lines = text.splitlines()
    if not lines:
        cell.text = ""
        return
    cell.paragraphs[0].clear()
    cell.paragraphs[0].add_run(lines[0])
    for line in lines[1:]:
        cell.add_paragraph(line)


def euro_fr(value) -> str:
    amount = float(value)
    return f"{amount:,.2f} €".replace(",", " ").replace(".", ",")


def date_fr(d) -> str:
    return d.strftime("%d/%m/%Y")


class DOCXExporter:
    """Exporteur DOCX pour devis/facture avec rendu métier propre."""

    def __init__(self, template_path: Optional[str] = None):
        self.template_path = template_path or str(resolve_resource_path("templates", "devis_template.docx"))

    def _has_grouped_lots(self, devis: Devis) -> bool:
        if not devis.utiliser_lots:
            return False
        non_empty = [lot for lot in devis.lots if lot.lignes]
        if len(non_empty) <= 1:
            return bool((non_empty[0].nom if non_empty else "").strip())
        return True

    def _iter_all_lines(self, devis: Devis) -> list[Ligne]:
        lines: list[Ligne] = []
        for lot in devis.lots:
            lines.extend(lot.lignes)
        return lines

    def export(self, devis: Devis, output_path: str):
        self._export_with_python_docx(devis, output_path)

    def _export_with_python_docx(self, devis: Devis, output_path: str) -> None:
        from docx import Document
        from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Cm, Pt, RGBColor

        company = get_company_info()
        logo_path = resolve_logo_path()
        is_facture = (devis.statut or "").lower() == "facture"

        NAVY = RGBColor.from_string(COLOR_NAVY.replace("#", ""))
        GOLD = RGBColor.from_string(COLOR_GOLD.replace("#", ""))
        BORDER = COLOR_BORDER.replace("#", "")
        SECTION = COLOR_SECTION.replace("#", "")
        TABLE_GRID = COLOR_TABLE_GRID.replace("#", "")
        TABLE_HEADER_BG = COLOR_TABLE_HEADER_BG.replace("#", "")
        TABLE_HEADER_TEXT = RGBColor.from_string(COLOR_TABLE_HEADER_TEXT.replace("#", ""))
        TABLE_STRIP_BG = COLOR_TABLE_STRIP_BG.replace("#", "")
        TABLE_LOT_BG = COLOR_TABLE_LOT_BG.replace("#", "")
        TABLE_SUBTOTAL_BG = COLOR_TABLE_SUBTOTAL_BG.replace("#", "")
        TABLE_SUBTOTAL_TEXT = RGBColor.from_string(COLOR_TABLE_SUBTOTAL_TEXT.replace("#", ""))
        FOOTER_TEXT = RGBColor.from_string(DOCX_FOOTER_TEXT_COLOR.replace("#", ""))
        FOOTER_LINE = DOCX_FOOTER_LINE_COLOR.replace("#", "")

        def set_cell_shading(cell, fill: str) -> None:
            tc_pr = cell._tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), fill)
            tc_pr.append(shd)

        def set_cell_borders(cell, color: str = BORDER, size: str = "6") -> None:
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_borders = OxmlElement("w:tcBorders")
            for edge in ("top", "left", "bottom", "right"):
                edge_el = OxmlElement(f"w:{edge}")
                edge_el.set(qn("w:val"), "single")
                edge_el.set(qn("w:sz"), size)
                edge_el.set(qn("w:color"), color)
                tc_borders.append(edge_el)
            tc_pr.append(tc_borders)

        def set_cell_margins(cell, left_twips: int = 0, right_twips: int = 0, top_twips: int = 0, bottom_twips: int = 0) -> None:
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_mar = OxmlElement("w:tcMar")
            for side, value in (
                ("left", left_twips),
                ("right", right_twips),
                ("top", top_twips),
                ("bottom", bottom_twips),
            ):
                side_el = OxmlElement(f"w:{side}")
                side_el.set(qn("w:w"), str(max(0, int(value))))
                side_el.set(qn("w:type"), "dxa")
                tc_mar.append(side_el)
            tc_pr.append(tc_mar)

        def set_row_no_split(row) -> None:
            tr_pr = row._tr.get_or_add_trPr()
            cant_split = OxmlElement("w:cantSplit")
            tr_pr.append(cant_split)

        def set_run_font(run, size: float, bold: bool = False, color: Optional[RGBColor] = None) -> None:
            run.font.name = "Calibri"
            run.font.size = Pt(size)
            run.bold = bold
            if color is not None:
                run.font.color.rgb = color

        def set_paragraph_spacing(paragraph, before: float = 0, after: float = 4, line: float = 1.15) -> None:
            fmt = paragraph.paragraph_format
            # Word n'accepte pas de spacing negatif: on borne pour eviter les erreurs d'export.
            fmt.space_before = Pt(max(0.0, float(before)))
            fmt.space_after = Pt(max(0.0, float(after)))
            fmt.line_spacing = line

        def set_paragraph_top_border(paragraph, color: str, size: str = "8") -> None:
            p_pr = paragraph._p.get_or_add_pPr()
            p_bdr = OxmlElement("w:pBdr")
            top = OxmlElement("w:top")
            top.set(qn("w:val"), "single")
            top.set(qn("w:sz"), size)
            top.set(qn("w:space"), "1")
            top.set(qn("w:color"), color)
            p_bdr.append(top)
            p_pr.append(p_bdr)

        def set_cell_no_borders(cell) -> None:
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_borders = OxmlElement("w:tcBorders")
            for edge in ("top", "left", "bottom", "right"):
                edge_el = OxmlElement(f"w:{edge}")
                edge_el.set(qn("w:val"), "nil")
                tc_borders.append(edge_el)
            tc_pr.append(tc_borders)

        doc = Document()
        section = doc.sections[0]
        section.top_margin = Cm(1.0)
        section.bottom_margin = Cm(1.8)
        section.left_margin = Cm(1.1)
        section.right_margin = Cm(1.1)
        section.footer_distance = Cm(DOCX_FOOTER_DISTANCE_CM)

        # Normalize base style
        normal_style = doc.styles["Normal"]
        normal_style.font.name = "Calibri"
        normal_style.font.size = Pt(11)

        # ---------- Header ----------
        top = doc.add_table(rows=1, cols=2)
        top.autofit = False
        top.columns[0].width = Cm(DOCX_HEADER_LEFT_COL_CM)
        top.columns[1].width = Cm(DOCX_HEADER_RIGHT_COL_CM)

        left_cell = top.cell(0, 0)
        right_cell = top.cell(0, 1)
        for c in (left_cell, right_cell):
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
        set_cell_margins(left_cell, 0, 0, 0, 0)
        set_cell_margins(right_cell, 0, 0, 0, 0)

        p_logo = left_cell.paragraphs[0]
        p_logo.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_logo.paragraph_format.left_indent = Pt(DOCX_HEADER_LOGO_LEFT_INDENT_PT)
        set_paragraph_spacing(p_logo, after=DOCX_HEADER_GAP_LOGO_TO_COMPANY_PT)
        if logo_path and Path(logo_path).exists():
            p_logo.add_run().add_picture(str(logo_path), width=Cm(DOCX_HEADER_LOGO_WIDTH_CM))

        label = "FACTURE" if is_facture else "DEVIS"
        date_cree = date_fr(devis.date_devis)
        date_ech = date_fr(devis.date_devis + timedelta(days=max(1, devis.validite_jours)))

        p = right_cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_paragraph_spacing(p, before=DOCX_HEADER_RIGHT_BLOCK_Y_OFFSET_PT, after=1)
        set_run_font(p.add_run(label), 10.8, bold=True, color=NAVY)

        p = right_cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_paragraph_spacing(p, after=DOCX_HEADER_DOC_BLOCK_GAP_PT)
        set_run_font(p.add_run(f"N° {devis.numero or '-'}"), 13.2, bold=True, color=GOLD)

        meta = right_cell.add_table(rows=2, cols=2)
        meta.autofit = False
        meta.columns[0].width = Cm(2.7)
        meta.columns[1].width = Cm(max(0.1, DOCX_HEADER_RIGHT_COL_CM - 2.7))
        meta.cell(0, 0).text = "Date"
        meta.cell(0, 1).text = date_cree
        meta.cell(1, 0).text = "Échéance"
        meta.cell(1, 1).text = date_ech
        for r in range(2):
            for c in range(2):
                cell = meta.cell(r, c)
                tc_pr = cell._tc.get_or_add_tcPr()
                tc_borders = OxmlElement("w:tcBorders")
                bottom = OxmlElement("w:bottom")
                bottom.set(qn("w:val"), "single")
                bottom.set(qn("w:sz"), "4" if r == 0 else "0")
                bottom.set(qn("w:color"), BORDER)
                tc_borders.append(bottom)
                tc_pr.append(tc_borders)
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if c == 0 else WD_ALIGN_PARAGRAPH.RIGHT
                set_paragraph_spacing(p, after=1)
                if p.runs:
                    set_run_font(
                        p.runs[0],
                        9.9,
                        bold=(c == 1),
                        color=RGBColor.from_string("4B5563") if c == 0 else None,
                    )

        affaire_name = (devis.reference_affaire or "").strip() or "-"
        client_lines = [
            devis.client.nom or "-",
            devis.client.adresse or "",
            f"{devis.client.code_postal} {devis.client.ville}".strip(),
        ]
        p = right_cell.add_paragraph("CLIENT")
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_paragraph_spacing(p, before=6, after=2)
        if p.runs:
            set_run_font(p.runs[0], 9.4, bold=True, color=NAVY)
        for line in client_lines:
            if not line:
                continue
            p = right_cell.add_paragraph(line)
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            set_paragraph_spacing(p, after=1)
            if p.runs:
                set_run_font(p.runs[0], 9.2, bold=(line == client_lines[0]))
        p = right_cell.add_paragraph("AFFAIRE")
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_paragraph_spacing(p, before=DOCX_HEADER_GAP_AFTER_CLIENT_PT, after=1)
        if p.runs:
            set_run_font(p.runs[0], 9.3, bold=True, color=NAVY)
        p = right_cell.add_paragraph(affaire_name)
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_paragraph_spacing(p, after=DOCX_HEADER_GAP_AFTER_AFFAIRE_PT)
        if p.runs:
            set_run_font(p.runs[0], 9.2)

        # trait discret de séparation en bas d'en-tête
        sep = doc.add_table(rows=1, cols=1)
        sep.autofit = False
        sep.columns[0].width = Cm(DOCX_CONTENT_TABLE_WIDTH_CM)
        sep_cell = sep.cell(0, 0)
        sep_cell.text = ""
        sep_pr = sep_cell._tc.get_or_add_tcPr()
        sep_borders = OxmlElement("w:tcBorders")
        sep_bottom = OxmlElement("w:bottom")
        sep_bottom.set(qn("w:val"), "single")
        sep_bottom.set(qn("w:sz"), "6")
        sep_bottom.set(qn("w:color"), BORDER)
        sep_borders.append(sep_bottom)
        sep_pr.append(sep_borders)
        set_paragraph_spacing(sep_cell.paragraphs[0], after=0)
        doc.add_paragraph("")

        # ---------- Main table — 4 colonnes modernes ----------
        p_table_gap = doc.add_paragraph("")
        set_paragraph_spacing(p_table_gap, after=DOCX_SPACE_BEFORE_TABLE_PT)
        columns = LINE_TABLE_HEADERS  # 4 cols: Description, Qté, PU HT, Total HT
        table = doc.add_table(rows=1, cols=len(columns))
        table.autofit = False
        line_table_widths_cm = list(DOCX_LINE_TABLE_WIDTHS_CM)
        for i, width_cm in enumerate(line_table_widths_cm):
            table.columns[i].width = Cm(width_cm)

        # Header row
        for i, title in enumerate(columns):
            cell = table.rows[0].cells[i]
            cell.text = title
            set_cell_shading(cell, TABLE_HEADER_BG)
            set_cell_borders(cell, color=TABLE_GRID)
            p = cell.paragraphs[0]
            if i >= 1:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            if p.runs:
                set_run_font(p.runs[0], 11, bold=True, color=TABLE_HEADER_TEXT)
            set_paragraph_spacing(p, before=4, after=4)

        has_lots = self._has_grouped_lots(devis)
        ALT_BG = "EDF4FF"  # bleu très clair pour lignes alternées

        if has_lots:
            for lot_idx, lot in enumerate(devis.lots, start=1):
                if not lot.lignes:
                    continue

                # Ligne en-tête de lot — fond bleu clair, text navy, span all cols
                lot_row = table.add_row()
                set_row_no_split(lot_row)
                row = lot_row.cells
                lot_name = lot.nom or f"Lot {lot_idx}"
                # Merge all cells for the lot header
                merged = row[0].merge(row[-1])
                merged.text = lot_name
                set_cell_shading(merged, TABLE_LOT_BG)
                set_cell_borders(merged, color=TABLE_GRID)
                if merged.paragraphs[0].runs:
                    set_run_font(merged.paragraphs[0].runs[0], 11, bold=True, color=NAVY)
                set_paragraph_spacing(merged.paragraphs[0], before=4, after=4)

                for line_idx, ligne in enumerate(lot.lignes):
                    data_row = table.add_row().cells
                    bg = ALT_BG if line_idx % 2 == 1 else "FFFFFF"
                    for c in data_row:
                        set_cell_shading(c, bg)
                        set_cell_borders(c, color=TABLE_GRID, size="4")
                    _set_cell_multiline(data_row[0], ligne.designation or "")
                    data_row[1].text = "1" if ligne.unite.lower() == "forfait" else str(ligne.quantite)
                    data_row[2].text = euro_fr(ligne.prix_unitaire_ht)
                    data_row[3].text = euro_fr(ligne.calculer_total_ht())
                    for col_num in (1, 2, 3):
                        data_row[col_num].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    for c in data_row:
                        if c.paragraphs[0].runs:
                            set_run_font(c.paragraphs[0].runs[0], 10.5)
                    set_paragraph_spacing(data_row[0].paragraphs[0], after=2)

                # Sous-total du lot
                sub_row = table.add_row().cells
                for c in sub_row:
                    set_cell_shading(c, TABLE_SUBTOTAL_BG)
                    set_cell_borders(c, color=TABLE_GRID)
                sub_row[0].text = f"Sous-total  {lot_name}"
                sub_row[3].text = euro_fr(lot.calculer_sous_total_ht())
                sub_row[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                for c in (sub_row[0], sub_row[3]):
                    if c.paragraphs[0].runs:
                        set_run_font(c.paragraphs[0].runs[0], 10.5, bold=True, color=TABLE_SUBTOTAL_TEXT)
                set_paragraph_spacing(sub_row[0].paragraphs[0], before=3, after=3)
        else:
            lines = self._iter_all_lines(devis)
            if not lines:
                row = table.add_row().cells
                for c in row:
                    set_cell_shading(c, "FFFFFF")
                    set_cell_borders(c, color=TABLE_GRID)
                row[0].text = "Aucune ligne"
                row[3].text = euro_fr(0)
                row[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            else:
                for line_idx, ligne in enumerate(lines):
                    row = table.add_row().cells
                    bg = ALT_BG if line_idx % 2 == 1 else "FFFFFF"
                    for c in row:
                        set_cell_shading(c, bg)
                        set_cell_borders(c, color=TABLE_GRID, size="4")
                    _set_cell_multiline(row[0], ligne.designation or "")
                    row[1].text = "1" if ligne.unite.lower() == "forfait" else str(ligne.quantite)
                    row[2].text = euro_fr(ligne.prix_unitaire_ht)
                    row[3].text = euro_fr(ligne.calculer_total_ht())
                    for col_num in (1, 2, 3):
                        row[col_num].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    for c in row:
                        if c.paragraphs[0].runs:
                            set_run_font(c.paragraphs[0].runs[0], 10.5)

        # ---------- Totaux — bloc aligné à droite ----------
        doc.add_paragraph("")
        total_col_w = [4.5, 3.2]
        total_left_spacer = sum(line_table_widths_cm) - sum(total_col_w)
        total_table = doc.add_table(rows=3, cols=3)
        total_table.autofit = False
        total_table.columns[0].width = Cm(max(0.1, total_left_spacer))
        total_table.columns[1].width = Cm(total_col_w[0])
        total_table.columns[2].width = Cm(total_col_w[1])

        totals_data = [
            ("Total HT",                        euro_fr(devis.calculer_total_ht()),  False),
            (f"TVA ({devis.tva_pourcent_global}%)", euro_fr(devis.calculer_total_tva()), False),
            ("TOTAL TTC",                        euro_fr(devis.calculer_total_ttc()), True),
        ]
        for r, (left_txt, right_txt, is_ttc) in enumerate(totals_data):
            row = total_table.rows[r].cells
            row[0].text = ""
            set_cell_no_borders(row[0])
            set_cell_shading(row[0], "FFFFFF")

            row[1].text = left_txt
            row[2].text = right_txt
            bg_hex = COLOR_NAVY.replace("#", "") if is_ttc else "FFFFFF"
            for c in (row[1], row[2]):
                set_cell_borders(c, color=TABLE_GRID)
                set_cell_shading(c, bg_hex)
                set_paragraph_spacing(c.paragraphs[0], before=4, after=4)
            row[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for c in (row[1], row[2]):
                if c.paragraphs[0].runs:
                    run = c.paragraphs[0].runs[0]
                    set_run_font(run, 12 if is_ttc else 10.5, bold=is_ttc)
                    if is_ttc:
                        run.font.color.rgb = RGBColor(255, 255, 255)

        # ---------- Mentions / règlement ----------
        doc.add_paragraph("")
        mentions = doc.add_table(rows=1, cols=1)
        mentions.autofit = False
        mentions.columns[0].width = Cm(DOCX_CONTENT_TABLE_WIDTH_CM)
        mention_cell = mentions.cell(0, 0)
        set_cell_borders(mention_cell, color=TABLE_GRID)
        set_cell_shading(mention_cell, SECTION)
        set_cell_margins(mention_cell, 120, 120, 80, 80)

        lines = []
        if devis.delais.strip():
            lines.append(("Délais", devis.delais, False))
        if devis.remarques.strip():
            lines.append(("Remarques", devis.remarques, False))
        if is_facture:
            lines.append(("Coordonnées bancaires", "", True))
            lines.append(("", company.banque_nom, False))
            lines.append(("", f"Code Banque {company.code_banque}  •  Code Guichet {company.code_guichet}", False))
            lines.append(("", f"IBAN : {company.iban}", False))
            lines.append(("", f"BIC : {company.bic}", False))

        if not lines:
            lines = [("", " ", False)]

        mention_cell.text = ""
        for idx, (label, value, is_section) in enumerate(lines):
            p = mention_cell.paragraphs[0] if idx == 0 else mention_cell.add_paragraph()
            p.text = ""
            set_paragraph_spacing(p, after=2)
            if label:
                run_lbl = p.add_run(f"{label} : " if value else label)
                set_run_font(run_lbl, 9.8, bold=True,
                             color=RGBColor.from_string(COLOR_NAVY.replace("#", "")) if is_section else None)
            if value:
                run_val = p.add_run(value)
                set_run_font(run_val, 9.8)

        # ---------- Footer ----------
        footer_line1 = f"{company.forme} {company.raison_sociale} • {company.adresse} • {company.code_postal_ville}"
        footer_line2 = f"Tél. {company.telephone} • {company.email} • SIRET {company.siret}"
        footer = section.footer
        p1 = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        p1.text = ""
        p1.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_paragraph_spacing(p1, before=4, after=DOCX_FOOTER_LINE1_AFTER_PT, line=1.0)
        set_paragraph_top_border(p1, FOOTER_LINE)
        run1 = p1.add_run(footer_line1)
        set_run_font(run1, DOCX_FOOTER_LINE1_FONT_PT, color=FOOTER_TEXT)

        p2 = footer.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_paragraph_spacing(p2, after=0, line=1.0)
        run2 = p2.add_run(footer_line2)
        set_run_font(run2, DOCX_FOOTER_LINE2_FONT_PT, color=FOOTER_TEXT)

        doc.save(output_path)
