# -*- coding: utf-8 -*-
"""Export DOCX Batikam - priorité qualité Word professionnelle."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Optional

from app.models.devis import Devis, Ligne
from app.services.branding import resolve_logo_path
from app.services.company_info import get_company_info
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


def euro_fr(value) -> str:
    amount = float(value)
    return f"{amount:,.2f} €".replace(",", " ").replace(".", ",")


def date_fr(d) -> str:
    return d.strftime("%d/%m/%Y")


class DOCXExporter:
    """Exporteur DOCX pour devis/facture avec rendu métier propre."""

    def __init__(self, template_path: Optional[str] = None):
        self.template_path = template_path or "templates/devis_template.docx"

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

        p = left_cell.add_paragraph()
        p.paragraph_format.left_indent = Pt(DOCX_HEADER_COMPANY_LEFT_INDENT_PT)
        set_paragraph_spacing(
            p,
            before=DOCX_HEADER_COMPANY_Y_OFFSET_PT,
            after=DOCX_HEADER_COMPANY_LINE_AFTER_PT,
        )
        set_run_font(
            p.add_run(f"{company.forme} {company.raison_sociale}"),
            DOCX_HEADER_COMPANY_TITLE_FONT_PT,
            bold=False,
            color=NAVY,
        )
        for line in [
            company.adresse,
            company.code_postal_ville,
            f"Tél. : {company.telephone}",
            f"Email : {company.email}",
            f"SIRET : {company.siret}",
            f"RCS : {company.rcs}",
            f"TVA : {company.tva}",
        ]:
            p = left_cell.add_paragraph(line)
            p.paragraph_format.left_indent = Pt(DOCX_HEADER_COMPANY_LEFT_INDENT_PT)
            set_paragraph_spacing(p, after=DOCX_HEADER_COMPANY_LINE_AFTER_PT)
            if p.runs:
                set_run_font(p.runs[0], DOCX_HEADER_COMPANY_FONT_PT)

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

        # ---------- Main table ----------
        p_table_gap = doc.add_paragraph("")
        set_paragraph_spacing(p_table_gap, after=DOCX_SPACE_BEFORE_TABLE_PT)
        columns = LINE_TABLE_HEADERS
        table = doc.add_table(rows=1, cols=len(columns))
        table.autofit = False
        line_table_widths_cm = list(DOCX_LINE_TABLE_WIDTHS_CM)
        for i, width_cm in enumerate(line_table_widths_cm):
            table.columns[i].width = Cm(width_cm)

        for i, title in enumerate(columns):
            cell = table.rows[0].cells[i]
            cell.text = title
            set_cell_shading(cell, TABLE_HEADER_BG)
            set_cell_borders(cell, color=TABLE_GRID)
            p = cell.paragraphs[0]
            if i >= 2:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if p.runs:
                set_run_font(p.runs[0], 11, bold=True, color=TABLE_HEADER_TEXT)
            set_paragraph_spacing(p, after=2)

        strip = table.add_row().cells
        for c in strip:
            c.text = ""
            set_cell_shading(c, TABLE_STRIP_BG)
            set_cell_borders(c, color=TABLE_GRID)

        has_lots = self._has_grouped_lots(devis)
        if has_lots:
            for idx, lot in enumerate(devis.lots, start=1):
                if not lot.lignes:
                    continue

                lot_row = table.add_row()
                set_row_no_split(lot_row)
                row = lot_row.cells
                for c in row:
                    set_cell_shading(c, TABLE_LOT_BG)
                    set_cell_borders(c, color=TABLE_GRID)
                row[0].text = f"Lot {idx}"
                row[1].text = lot.nom or f"Lot {idx}"
                for c in (row[0], row[1]):
                    if c.paragraphs[0].runs:
                        set_run_font(c.paragraphs[0].runs[0], 11, bold=True, color=NAVY)

                for ligne in lot.lignes:
                    data_row = table.add_row().cells
                    for c in data_row:
                        set_cell_borders(c, color=TABLE_GRID)
                    data_row[1].text = f"- {(ligne.designation or '').replace(chr(10), ' ')}"
                    data_row[2].text = "1" if ligne.unite.lower() == "forfait" else str(ligne.quantite)
                    data_row[3].text = euro_fr(ligne.prix_unitaire_ht)
                    data_row[4].text = euro_fr(ligne.calculer_total_ht())
                    for idx_num in (2, 3, 4):
                        data_row[idx_num].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

                sub_row = table.add_row().cells
                for c in sub_row:
                    set_cell_shading(c, TABLE_SUBTOTAL_BG)
                    set_cell_borders(c, color=TABLE_GRID)
                sub_row[1].text = f"Sous-total {lot.nom or f'Lot {idx}'}"
                sub_row[4].text = euro_fr(lot.calculer_sous_total_ht())
                sub_row[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                for c in (sub_row[1], sub_row[4]):
                    if c.paragraphs[0].runs:
                        set_run_font(c.paragraphs[0].runs[0], 10.5, bold=True, color=TABLE_SUBTOTAL_TEXT)
        else:
            lines = self._iter_all_lines(devis)
            if not lines:
                row = table.add_row().cells
                for c in row:
                    set_cell_borders(c, color=TABLE_GRID)
                row[1].text = "Aucune ligne"
                row[4].text = euro_fr(0)
                row[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            else:
                for ligne in lines:
                    row = table.add_row().cells
                    for c in row:
                        set_cell_borders(c, color=TABLE_GRID)
                    row[1].text = f"- {(ligne.designation or '').replace(chr(10), ' ')}"
                    row[2].text = "1" if ligne.unite.lower() == "forfait" else str(ligne.quantite)
                    row[3].text = euro_fr(ligne.prix_unitaire_ht)
                    row[4].text = euro_fr(ligne.calculer_total_ht())
                    for idx_num in (2, 3, 4):
                        row[idx_num].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # ---------- Totals ----------
        doc.add_paragraph("")
        total_table = doc.add_table(rows=3, cols=3)
        total_table.autofit = False
        total_col_widths_cm = [4.2, 3.0]
        total_left_spacer_cm = sum(line_table_widths_cm) - sum(total_col_widths_cm)
        total_table.columns[0].width = Cm(total_left_spacer_cm)
        total_table.columns[1].width = Cm(total_col_widths_cm[0])
        total_table.columns[2].width = Cm(total_col_widths_cm[1])

        totals = [
            ("Total HT", euro_fr(devis.calculer_total_ht())),
            (f"TVA ({devis.tva_pourcent_global}%)", euro_fr(devis.calculer_total_tva())),
            ("TOTAL TTC", euro_fr(devis.calculer_total_ttc())),
        ]
        for r, (left_txt, right_txt) in enumerate(totals):
            row = total_table.rows[r].cells
            row[0].text = ""
            set_cell_no_borders(row[0])
            set_cell_shading(row[0], "FFFFFF")

            row[1].text = left_txt
            row[2].text = right_txt
            for c in (row[1], row[2]):
                set_cell_borders(c)
                set_cell_shading(c, COLOR_NAVY.replace("#", "") if r == 2 else "FFFFFF")
            row[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for c in (row[1], row[2]):
                if c.paragraphs[0].runs:
                    set_run_font(c.paragraphs[0].runs[0], 12 if r == 2 else 10.5, bold=True)
                    if r == 2:
                        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

        # ---------- Mentions / règlement ----------
        doc.add_paragraph("")
        mentions = doc.add_table(rows=1, cols=1)
        mentions.autofit = False
        mentions.columns[0].width = Cm(DOCX_CONTENT_TABLE_WIDTH_CM)
        mention_cell = mentions.cell(0, 0)
        set_cell_borders(mention_cell)
        set_cell_shading(mention_cell, SECTION)

        lines = []
        if devis.modalites_paiement.strip():
            lines.append(f"Modalités de règlement : {devis.modalites_paiement}")
        if devis.delais.strip():
            lines.append(f"Délais : {devis.delais}")
        if devis.remarques.strip():
            lines.append(f"Remarques : {devis.remarques}")
        if is_facture:
            lines.extend(
                [
                    "Coordonnées bancaires :",
                    company.banque_nom,
                    f"Code Banque {company.code_banque}",
                    f"Code Guichet {company.code_guichet}",
                    f"IBAN : {company.iban}",
                    f"BIC : {company.bic}",
                ]
            )
        if not lines:
            lines = [" "]

        mention_cell.text = ""
        for idx, line in enumerate(lines):
            p = mention_cell.paragraphs[0] if idx == 0 else mention_cell.add_paragraph()
            p.text = line
            set_paragraph_spacing(p, after=2)
            if p.runs:
                set_run_font(p.runs[0], 9.8, bold=(line.endswith(":") or line.startswith("IBAN") or line.startswith("BIC")))

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
