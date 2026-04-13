# -*- coding: utf-8 -*-
"""Export PDF ReportLab Batikam - devis/facture, mise en page professionnelle."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.devis import Devis, Ligne
from app.services.branding import resolve_logo_str
from app.services.company_info import get_company_info
from app.services.document_theme import (
    COLOR_BORDER,
    COLOR_GOLD,
    COLOR_MUTED,
    COLOR_NAVY,
    COLOR_SECTION,
    COLOR_SOFT,
    COLOR_TABLE_GRID,
    COLOR_TABLE_HEADER_BG,
    COLOR_TABLE_HEADER_TEXT,
    COLOR_TABLE_ALT_BG,
    COLOR_TABLE_LOT_BG,
    COLOR_TABLE_STRIP_BG,
    COLOR_TABLE_SUBTOTAL_BG,
    COLOR_TABLE_SUBTOTAL_TEXT,
    COLOR_TEXT,
    HEADER_LEFT_COL_CM,
    HEADER_RIGHT_COL_CM,
    LINE_TABLE_HEADERS,
    PDF_HEADER_GAP_LOGO_TO_COMPANY_CM,
    PDF_HEADER_GAP_AFTER_AFFAIRE_PT,
    PDF_HEADER_GAP_AFTER_CLIENT_PT,
    PDF_HEADER_COMPANY_FONT_SIZE_PT,
    PDF_HEADER_COMPANY_LEFT_INDENT_PT,
    PDF_HEADER_COMPANY_LEADING_PT,
    PDF_HEADER_COMPANY_Y_OFFSET_PT,
    PDF_HEADER_RIGHT_BLOCK_Y_OFFSET_PT,
    PDF_HEADER_LOGO_BOX_HEIGHT_CM,
    PDF_HEADER_LOGO_HEIGHT_CM,
    PDF_HEADER_LOGO_X_OFFSET_CM,
    PDF_SPACE_BEFORE_TABLE_CM,
    PDF_HEADER_SPACER_AFTER_CM,
)


def euro_fr(value) -> str:
    amount = float(value)
    return f"{amount:,.2f} €".replace(",", " ").replace(".", ",")


def date_fr(d) -> str:
    return d.strftime("%d/%m/%Y")


class LogoFrame(Flowable):
    """Bloc logo discret."""

    def __init__(self, logo_path: Optional[str], width: float, height: float, x_offset: float = 0.0):
        super().__init__()
        self.logo_path = logo_path
        self.width = width
        self.height = height
        self.x_offset = x_offset

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        canv = self.canv
        canv.saveState()
        if self.logo_path and Path(self.logo_path).exists():
            px = self.x_offset
            logo_h = min(self.height, PDF_HEADER_LOGO_HEIGHT_CM * cm)
            py = max(0, self.height - logo_h)
            canv.drawImage(
                self.logo_path,
                px,
                py,
                self.width,
                logo_h,
                preserveAspectRatio=True,
                mask="auto",
            )
        canv.restoreState()


class PDFExporter:
    """Exporteur PDF professionnel pour devis/factures."""

    def __init__(self, logo_path: Optional[str] = None):
        self.logo_path = logo_path if logo_path else resolve_logo_str()

        # Palette centrale
        self.navy = colors.HexColor(COLOR_NAVY)
        self.gold = colors.HexColor(COLOR_GOLD)
        self.border = colors.HexColor(COLOR_BORDER)
        self.soft = colors.HexColor(COLOR_SOFT)
        self.section = colors.HexColor(COLOR_SECTION)
        self.text = colors.HexColor(COLOR_TEXT)
        self.muted = colors.HexColor(COLOR_MUTED)
        self.table_header_bg = colors.HexColor(COLOR_TABLE_HEADER_BG)
        self.table_header_text = colors.HexColor(COLOR_TABLE_HEADER_TEXT)
        self.table_strip_bg = colors.HexColor(COLOR_TABLE_STRIP_BG)
        self.table_alt_bg = colors.HexColor(COLOR_TABLE_ALT_BG)
        self.table_lot_bg = colors.HexColor(COLOR_TABLE_LOT_BG)
        self.table_subtotal_bg = colors.HexColor(COLOR_TABLE_SUBTOTAL_BG)
        self.table_subtotal_text = colors.HexColor(COLOR_TABLE_SUBTOTAL_TEXT)
        self.table_grid = colors.HexColor(COLOR_TABLE_GRID)

        base = getSampleStyleSheet()
        self.style_body = ParagraphStyle(
            "bat_body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.5,
            textColor=self.text,
        )
        self.style_left = ParagraphStyle("bat_left", parent=self.style_body, alignment=TA_LEFT)
        self.style_right = ParagraphStyle("bat_right", parent=self.style_body, alignment=TA_RIGHT)
        self.style_footer = ParagraphStyle(
            "bat_footer",
            parent=self.style_body,
            fontSize=8.7,
            leading=10.0,
            textColor=self.muted,
        )
        self.style_company = ParagraphStyle(
            "bat_company",
            parent=self.style_body,
            fontSize=PDF_HEADER_COMPANY_FONT_SIZE_PT,
            leading=PDF_HEADER_COMPANY_LEADING_PT,
            leftIndent=PDF_HEADER_COMPANY_LEFT_INDENT_PT,
            textColor=self.text,
        )
        self.style_doc_label = ParagraphStyle(
            "bat_doc_label",
            parent=self.style_body,
            alignment=TA_RIGHT,
            fontName="Helvetica-Bold",
            fontSize=10.8,
            textColor=self.navy,
            leading=12,
        )
        self.style_doc_number = ParagraphStyle(
            "bat_doc_number",
            parent=self.style_body,
            alignment=TA_RIGHT,
            fontName="Helvetica-Bold",
            fontSize=13.0,
            textColor=self.gold,
            leading=15,
        )
        self.style_doc_client = ParagraphStyle(
            "bat_doc_client",
            parent=self.style_body,
            alignment=TA_RIGHT,
            fontSize=9.1,
            leading=11.0,
            textColor=self.text,
        )

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

    def _footer(self, canv, doc):
        company = get_company_info()
        line1 = f"{company.forme} {company.raison_sociale} • {company.adresse} • {company.code_postal_ville}"
        line2 = f"Tél. {company.telephone} • {company.email} • SIRET {company.siret}"
        canv.saveState()
        canv.setStrokeColor(self.gold)
        canv.setLineWidth(0.7)
        canv.line(doc.leftMargin, 1.4 * cm, A4[0] - doc.rightMargin, 1.4 * cm)
        canv.setFillColor(self.muted)
        canv.setFont("Helvetica", 8.2)
        canv.drawString(doc.leftMargin, 0.95 * cm, line1)
        canv.drawString(doc.leftMargin, 0.62 * cm, line2)
        canv.restoreState()

    def _build_header(self, devis: Devis) -> list:
        company = get_company_info()
        is_facture = (devis.statut or "").lower() == "facture"
        label = "FACTURE" if is_facture else "DEVIS"
        numero = devis.numero or "-"
        created = date_fr(devis.date_devis)
        echeance = date_fr(devis.date_devis + timedelta(days=max(1, devis.validite_jours)))

        flow = []

        left_content = [
            LogoFrame(
                self.logo_path,
                HEADER_LEFT_COL_CM * cm,
                PDF_HEADER_LOGO_BOX_HEIGHT_CM * cm,
                x_offset=PDF_HEADER_LOGO_X_OFFSET_CM * cm,
            ),
        ]
        left_block = Table([[left_content]], colWidths=[HEADER_LEFT_COL_CM * cm])
        left_block.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 2),
                ]
            )
        )

        # Badge DEVIS / FACTURE — fond navy, texte blanc
        badge_style = ParagraphStyle(
            "bat_badge",
            parent=self.style_body,
            alignment=TA_RIGHT,
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.white,
            leading=14,
        )
        right_head_top = Table(
            [
                [Paragraph(f"<b>{escape(label)}</b>", badge_style)],
                [Paragraph(f"N° {escape(numero)}", self.style_doc_number)],
            ],
            colWidths=[HEADER_RIGHT_COL_CM * cm],
        )
        right_head_top.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.navy),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (0, 0), 7),
                    ("BOTTOMPADDING", (0, 0), (0, 0), 7),
                    ("TOPPADDING", (0, 1), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 2),
                ]
            )
        )

        meta = Table(
            [
                [Paragraph("<font color='#4B5563'>Date</font>", self.style_body), Paragraph(f"<b>{escape(created)}</b>", self.style_right)],
                [Paragraph("<font color='#4B5563'>Échéance</font>", self.style_body), Paragraph(f"<b>{escape(echeance)}</b>", self.style_right)],
            ],
            colWidths=[2.7 * cm, (HEADER_RIGHT_COL_CM - 2.7) * cm],
        )
        meta.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.35, self.border),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        affaire_name = escape((devis.reference_affaire or "").strip()) or "-"
        client_lines = [
            "<b><font color='#0F2747'>CLIENT</font></b>",
            f"<b>{escape(devis.client.nom or '-')}</b>",
            escape(devis.client.adresse or ""),
            escape(f"{devis.client.code_postal} {devis.client.ville}".strip()),
        ]
        client_txt = "<br/>".join(line for line in client_lines if line.strip())
        client_txt += f"<br/><font size='{PDF_HEADER_GAP_AFTER_CLIENT_PT}'> </font><br/>"
        client_txt += "<b><font color='#0F2747'>AFFAIRE</font></b><br/>"
        client_txt += affaire_name
        client_txt += f"<br/><font size='{PDF_HEADER_GAP_AFTER_AFFAIRE_PT}'> </font><br/>"
        client_block = Table(
            [[Paragraph(client_txt, self.style_doc_client)]],
            colWidths=[HEADER_RIGHT_COL_CM * cm],
        )
        client_block.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        right_header = Table(
            [[Spacer(1, PDF_HEADER_RIGHT_BLOCK_Y_OFFSET_PT)], [right_head_top], [meta], [client_block]],
            colWidths=[HEADER_RIGHT_COL_CM * cm],
        )
        right_header.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        top = Table(
            [[left_block, right_header]],
            colWidths=[HEADER_LEFT_COL_CM * cm, HEADER_RIGHT_COL_CM * cm],
        )
        top.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), 0),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.55, self.border),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        flow.append(top)
        flow.append(Spacer(1, PDF_HEADER_SPACER_AFTER_CM * cm))
        return flow

    def _build_main_table(self, devis: Devis) -> Table:
        # 4 colonnes modernes — pas de col vide initiale
        has_lots = self._has_grouped_lots(devis)
        sep_color = colors.HexColor("#D8E4F2")

        rows = [LINE_TABLE_HEADERS]
        styles_rows: list = []
        row_idx = 1  # ligne 0 = header

        if has_lots:
            for i, lot in enumerate(devis.lots, start=1):
                if not lot.lignes:
                    continue
                lot_name = lot.nom or f"Lot {i}"

                # En-tête de lot — fond bleu clair, texte navy gras, pleine largeur
                rows.append([Paragraph(f"<b>{escape(lot_name)}</b>", self.style_left), "", "", ""])
                styles_rows.extend([
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), self.table_lot_bg),
                    ("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, row_idx), (-1, row_idx), self.navy),
                    ("TOPPADDING", (0, row_idx), (-1, row_idx), 8),
                    ("BOTTOMPADDING", (0, row_idx), (-1, row_idx), 8),
                    ("SPAN", (0, row_idx), (3, row_idx)),
                ])
                if lot.lignes:
                    styles_rows.append(("NOSPLIT", (0, row_idx), (-1, row_idx + 1)))
                row_idx += 1

                for j, line in enumerate(lot.lignes):
                    desc = "<br/>".join(escape(p) for p in (line.designation or "").splitlines())
                    qte = "1" if line.unite.lower() == "forfait" else f"{line.quantite}"
                    rows.append([
                        Paragraph(desc, self.style_left),
                        qte,
                        euro_fr(line.prix_unitaire_ht),
                        euro_fr(line.calculer_total_ht()),
                    ])
                    if j % 2 == 1:
                        styles_rows.append(("BACKGROUND", (0, row_idx), (-1, row_idx), self.table_alt_bg))
                    row_idx += 1

                # Sous-total du lot
                rows.append([
                    Paragraph(f"<i>Sous-total {escape(lot_name)}</i>", self.style_left),
                    "",
                    "",
                    Paragraph(f"<b>{euro_fr(lot.calculer_sous_total_ht())}</b>", self.style_right),
                ])
                styles_rows.extend([
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), self.table_subtotal_bg),
                    ("TEXTCOLOR", (0, row_idx), (-1, row_idx), self.table_subtotal_text),
                    ("TOPPADDING", (0, row_idx), (-1, row_idx), 5),
                    ("BOTTOMPADDING", (0, row_idx), (-1, row_idx), 5),
                ])
                row_idx += 1
        else:
            for j, line in enumerate(self._iter_all_lines(devis)):
                desc = "<br/>".join(escape(p) for p in (line.designation or "").splitlines())
                qte = "1" if line.unite.lower() == "forfait" else f"{line.quantite}"
                rows.append([
                    Paragraph(desc, self.style_left),
                    qte,
                    euro_fr(line.prix_unitaire_ht),
                    euro_fr(line.calculer_total_ht()),
                ])
                if j % 2 == 1:
                    styles_rows.append(("BACKGROUND", (0, row_idx), (-1, row_idx), self.table_alt_bg))
                row_idx += 1

        if len(rows) <= 1:
            rows.append(["Aucune ligne", "", "", euro_fr(0)])

        table = Table(
            rows,
            colWidths=[11.0 * cm, 2.0 * cm, 2.5 * cm, 3.0 * cm],
            repeatRows=1,
        )
        table.setStyle(TableStyle([
            # Global
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            # Alignements
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), self.table_header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), self.table_header_text),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("TOPPADDING", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
            # Bordure extérieure uniquement + séparateurs horizontaux fins
            ("BOX", (0, 0), (-1, -1), 0.5, self.table_grid),
            ("LINEBELOW", (0, 0), (-1, -2), 0.3, sep_color),
        ] + styles_rows))
        return table

    def _build_totals_and_bank(self, devis: Devis) -> list:
        company = get_company_info()
        is_facture = (devis.statut or "").lower() == "facture"

        total_ht  = devis.calculer_total_ht()
        total_tva = devis.calculer_total_tva()
        total_ttc = devis.calculer_total_ttc()

        sep = colors.HexColor("#D8E4F2")

        style_lbl = ParagraphStyle("tot_lbl", parent=self.style_body, fontSize=9.8, textColor=self.muted)
        style_val = ParagraphStyle("tot_val", parent=self.style_body, fontSize=9.8, alignment=TA_RIGHT)
        style_ttc_lbl = ParagraphStyle("tot_ttc_lbl", parent=self.style_body, fontSize=11.5,
                                       fontName="Helvetica-Bold", textColor=colors.white)
        style_ttc_val = ParagraphStyle("tot_ttc_val", parent=self.style_body, fontSize=11.5,
                                       fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_RIGHT)

        totals = Table(
            [
                [Paragraph("Total HT", style_lbl), Paragraph(euro_fr(total_ht), style_val)],
                [Paragraph(f"TVA ({devis.tva_pourcent_global} %)", style_lbl), Paragraph(euro_fr(total_tva), style_val)],
                [Paragraph("TOTAL TTC", style_ttc_lbl), Paragraph(euro_fr(total_ttc), style_ttc_val)],
            ],
            colWidths=[4.5 * cm, 3.2 * cm],
        )
        totals.setStyle(TableStyle([
            ("BOX",        (0, 0), (-1, -1), 0.5, self.table_grid),
            ("LINEBELOW",  (0, 0), (-1, 1),  0.3, sep),
            ("ALIGN",      (0, 0), (0, -1),  "LEFT"),
            ("ALIGN",      (1, 0), (1, -1),  "RIGHT"),
            ("BACKGROUND", (0, 0), (-1, 1),  colors.white),
            ("BACKGROUND", (0, 2), (-1, 2),  self.navy),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ]))

        mentions_lines = []
        if devis.delais.strip():
            mentions_lines.append(f"<b>Délais :</b> {escape(devis.delais)}")
        if devis.remarques.strip():
            mentions_lines.append(f"<b>Remarques :</b> {escape(devis.remarques).replace(chr(10), '<br/>')}")
        if is_facture:
            mentions_lines.extend([
                "<b>Coordonnées bancaires :</b>",
                escape(company.banque_nom),
                f"Code Banque {escape(company.code_banque)}  •  Code Guichet {escape(company.code_guichet)}",
                f"IBAN : {escape(company.iban)}",
                f"BIC : {escape(company.bic)}",
            ])

        style_mention_title = ParagraphStyle("men_t", parent=self.style_body, fontSize=8.5,
                                             fontName="Helvetica-Bold", textColor=self.navy,
                                             spaceAfter=4)
        mentions_content = [Paragraph("<b>Notes</b>", style_mention_title)] if mentions_lines else []
        for line in mentions_lines:
            mentions_content.append(Paragraph(line, self.style_body))

        if not mentions_content:
            mentions_content = [Paragraph(" ", self.style_body)]

        mentions = Table([[mentions_content]], colWidths=[11.0 * cm])
        mentions.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), self.section),
            ("BOX",           (0, 0), (-1, -1), 0.5, self.table_grid),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))

        gap = Spacer(0.4 * cm, 1)
        row = Table([[mentions, gap, totals]], colWidths=[11.0 * cm, 0.4 * cm, 7.1 * cm])
        row.setStyle(TableStyle([
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return [CondPageBreak(7.5 * cm), KeepTogether([row])]

    def export(self, devis: Devis, output_path: str):
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=1.1 * cm,
            leftMargin=1.1 * cm,
            topMargin=0.9 * cm,
            bottomMargin=2.0 * cm,
        )

        story = []
        story.extend(self._build_header(devis))
        story.append(Spacer(1, PDF_SPACE_BEFORE_TABLE_CM * cm))
        story.append(self._build_main_table(devis))
        story.append(Spacer(1, 0.22 * cm))
        story.extend(self._build_totals_and_bank(devis))

        doc.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
