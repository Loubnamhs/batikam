# -*- coding: utf-8 -*-
"""Export PDF ReportLab — Batikam Rénove.

Design sobre et professionnel :
  - Palette minimaliste (blanc, gris clair, un seul accent ardoise)
  - Tableau sans grille verticale, séparateurs horizontaux fins
  - En-tête clair : logo + infos document à droite
  - Totaux alignés à droite, élégants
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    HRFlowable,
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
    COLOR_TABLE_ALT_BG,
    COLOR_TABLE_GRID,
    COLOR_TABLE_HEADER_BG,
    COLOR_TABLE_HEADER_TEXT,
    COLOR_TABLE_LOT_BG,
    COLOR_TABLE_STRIP_BG,
    COLOR_TABLE_SUBTOTAL_BG,
    COLOR_TABLE_SUBTOTAL_TEXT,
    COLOR_TEXT,
    HEADER_LEFT_COL_CM,
    HEADER_RIGHT_COL_CM,
    LINE_TABLE_HEADERS,
    PDF_HEADER_LOGO_BOX_HEIGHT_CM,
    PDF_HEADER_LOGO_HEIGHT_CM,
    PDF_HEADER_LOGO_X_OFFSET_CM,
    PDF_HEADER_SPACER_AFTER_CM,
    PDF_SPACE_BEFORE_TABLE_CM,
    PDF_HEADER_GAP_AFTER_CLIENT_PT,
    PDF_HEADER_GAP_AFTER_AFFAIRE_PT,
)


def euro_fr(value) -> str:
    return f"{float(value):,.2f} €".replace(",", "\u202f").replace(".", ",")


def date_fr(d) -> str:
    return d.strftime("%d/%m/%Y")


class LogoFrame(Flowable):
    """Affiche le logo en préservant le ratio."""

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
            # anchor="sw" → coin bas-gauche à (x_offset, 0)
            # Le logo remonte jusqu'à self.height — aligné en haut de la frame
            canv.drawImage(
                self.logo_path,
                self.x_offset, 0,
                self.width, self.height,
                preserveAspectRatio=True,
                anchor="sw",
                mask="auto",
            )
        canv.restoreState()


class PDFExporter:
    """Exporteur PDF professionnel — devis et factures."""

    def __init__(self, logo_path: Optional[str] = None):
        self.logo_path = logo_path or resolve_logo_str()

        self.c_navy   = colors.HexColor(COLOR_NAVY)
        self.c_gold   = colors.HexColor(COLOR_GOLD)
        self.c_border = colors.HexColor(COLOR_BORDER)
        self.c_soft   = colors.HexColor(COLOR_SOFT)
        self.c_section = colors.HexColor(COLOR_SECTION)
        self.c_text   = colors.HexColor(COLOR_TEXT)
        self.c_muted  = colors.HexColor(COLOR_MUTED)
        self.c_th_bg  = colors.HexColor(COLOR_TABLE_HEADER_BG)
        self.c_th_txt = colors.HexColor(COLOR_TABLE_HEADER_TEXT)
        self.c_alt    = colors.HexColor(COLOR_TABLE_ALT_BG)
        self.c_lot    = colors.HexColor(COLOR_TABLE_LOT_BG)
        self.c_sub_bg = colors.HexColor(COLOR_TABLE_SUBTOTAL_BG)
        self.c_sub_txt = colors.HexColor(COLOR_TABLE_SUBTOTAL_TEXT)
        self.c_grid   = colors.HexColor(COLOR_TABLE_GRID)

        base = getSampleStyleSheet()

        # Styles de base
        self.s_body = ParagraphStyle("s_body", parent=base["Normal"],
            fontName="Helvetica", fontSize=9.5, leading=13, textColor=self.c_text)
        self.s_left  = ParagraphStyle("s_left",  parent=self.s_body, alignment=TA_LEFT)
        self.s_right = ParagraphStyle("s_right", parent=self.s_body, alignment=TA_RIGHT)
        self.s_muted = ParagraphStyle("s_muted", parent=self.s_body, textColor=self.c_muted)
        self.s_muted_r = ParagraphStyle("s_muted_r", parent=self.s_muted, alignment=TA_RIGHT)

        # Header document (droite)
        self.s_doc_type = ParagraphStyle("s_doc_type", parent=self.s_body,
            fontName="Helvetica-Bold", fontSize=22, textColor=self.c_navy,
            alignment=TA_RIGHT, leading=26, spaceAfter=2)
        self.s_doc_num = ParagraphStyle("s_doc_num", parent=self.s_body,
            fontName="Helvetica", fontSize=11, textColor=self.c_muted,
            alignment=TA_RIGHT, leading=14)
        self.s_doc_meta_lbl = ParagraphStyle("s_doc_meta_lbl", parent=self.s_body,
            fontSize=8.5, textColor=self.c_muted, alignment=TA_LEFT)
        self.s_doc_meta_val = ParagraphStyle("s_doc_meta_val", parent=self.s_body,
            fontSize=8.5, fontName="Helvetica-Bold", textColor=self.c_text, alignment=TA_RIGHT)
        self.s_client_lbl = ParagraphStyle("s_client_lbl", parent=self.s_body,
            fontSize=7.5, fontName="Helvetica-Bold", textColor=self.c_muted,
            alignment=TA_RIGHT, spaceBefore=6)
        self.s_client_nom = ParagraphStyle("s_client_nom", parent=self.s_body,
            fontSize=10, fontName="Helvetica-Bold", textColor=self.c_navy, alignment=TA_RIGHT)
        self.s_client_adr = ParagraphStyle("s_client_adr", parent=self.s_body,
            fontSize=9, textColor=self.c_text, alignment=TA_RIGHT, leading=12.5)

        # Table header row
        self.s_th = ParagraphStyle("s_th", parent=self.s_body,
            fontName="Helvetica-Bold", fontSize=9, textColor=self.c_th_txt)
        self.s_th_r = ParagraphStyle("s_th_r", parent=self.s_th, alignment=TA_RIGHT)

        # Totaux
        self.s_tot_lbl = ParagraphStyle("s_tot_lbl", parent=self.s_body,
            fontSize=9.5, textColor=self.c_muted)
        self.s_tot_val = ParagraphStyle("s_tot_val", parent=self.s_body,
            fontSize=9.5, alignment=TA_RIGHT)
        self.s_ttc_lbl = ParagraphStyle("s_ttc_lbl", parent=self.s_body,
            fontName="Helvetica-Bold", fontSize=11, textColor=colors.white)
        self.s_ttc_val = ParagraphStyle("s_ttc_val", parent=self.s_body,
            fontName="Helvetica-Bold", fontSize=11, textColor=colors.white, alignment=TA_RIGHT)

    # ── Helpers ───────────────────────────────────────────────────────────────

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

    # ── Footer ────────────────────────────────────────────────────────────────

    def _footer(self, canv, doc):
        company = get_company_info()
        line1 = f"{company.forme} {company.raison_sociale}  •  {company.adresse}  •  {company.code_postal_ville}"
        line2 = f"Tél. {company.telephone}  •  {company.email}  •  SIRET {company.siret}"
        w = A4[0] - doc.leftMargin - doc.rightMargin
        canv.saveState()
        # Filet or très fin
        canv.setStrokeColor(self.c_gold)
        canv.setLineWidth(0.5)
        canv.line(doc.leftMargin, 1.55 * cm, doc.leftMargin + w, 1.55 * cm)
        canv.setFillColor(self.c_muted)
        canv.setFont("Helvetica", 7.8)
        canv.drawString(doc.leftMargin, 1.15 * cm, line1)
        canv.drawString(doc.leftMargin, 0.72 * cm, line2)
        # Numéro de page (droite)
        page_num = canv.getPageNumber()
        canv.drawRightString(doc.leftMargin + w, 0.72 * cm, f"Page {page_num}")
        canv.restoreState()

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self, devis: Devis) -> list:
        is_facture = (devis.statut or "").lower() == "facture"
        label   = "FACTURE" if is_facture else "DEVIS"
        numero  = devis.numero or "—"
        created = date_fr(devis.date_devis)

        # ── Colonne gauche : logo seul ─────────────────────────────────────
        logo_frame = LogoFrame(
            self.logo_path,
            HEADER_LEFT_COL_CM * cm,
            PDF_HEADER_LOGO_BOX_HEIGHT_CM * cm,
            x_offset=PDF_HEADER_LOGO_X_OFFSET_CM * cm,
        )

        # ── Colonne droite : type + N° + méta + client ────────────────────
        r: list = []

        # Type de document (grand, ardoise)
        r.append(Paragraph(label, self.s_doc_type))

        # N° discret
        r.append(Paragraph(f"N° {escape(numero)}", self.s_doc_num))
        r.append(Spacer(1, 6))

        # Date — label au-dessus, valeur en dessous (même style CLIENT/AFFAIRE)
        r.append(Paragraph("DATE", self.s_client_lbl))
        r.append(Paragraph(escape(created), self.s_client_adr))
        r.append(Spacer(1, 6))

        # Client
        client = devis.client
        r.append(Paragraph("CLIENT", self.s_client_lbl))
        if client.nom:
            r.append(Paragraph(escape(client.nom), self.s_client_nom))
        adr_parts = [
            client.adresse,
            f"{client.code_postal} {client.ville}".strip(),
        ]
        for part in adr_parts:
            if part.strip():
                r.append(Paragraph(escape(part), self.s_client_adr))

        affaire = (devis.reference_affaire or "").strip()
        if affaire:
            r.append(Spacer(1, 6))
            r.append(Paragraph("AFFAIRE", self.s_client_lbl))
            r.append(Paragraph(escape(affaire), self.s_client_adr))

        right_col = Table([[r]], colWidths=[HEADER_RIGHT_COL_CM * cm])
        right_col.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))

        # ── Assemblage sur 2 colonnes ──────────────────────────────────────
        header_row = Table(
            [[logo_frame, right_col]],
            colWidths=[HEADER_LEFT_COL_CM * cm, HEADER_RIGHT_COL_CM * cm],
        )
        header_row.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ]))

        # Filet or sous l'en-tête
        rule = HRFlowable(
            width="100%",
            thickness=0.8,
            color=self.c_gold,
            spaceAfter=0,
        )

        return [header_row, rule, Spacer(1, PDF_HEADER_SPACER_AFTER_CM * cm)]

    # ── Tableau principal ─────────────────────────────────────────────────────

    def _build_main_table(self, devis: Devis) -> Table:
        has_lots = self._has_grouped_lots(devis)

        # Colonnes : Description | Qté | PU HT | Total HT
        col_w = [9.5 * cm, 1.5 * cm, 1.8 * cm, 2.5 * cm, 3.2 * cm]

        # En-têtes
        rows: list = [[
            Paragraph(LINE_TABLE_HEADERS[0], self.s_th),
            Paragraph(LINE_TABLE_HEADERS[1], self.s_th_r),
            Paragraph(LINE_TABLE_HEADERS[2], self.s_th_r),
            Paragraph(LINE_TABLE_HEADERS[3], self.s_th_r),
            Paragraph(LINE_TABLE_HEADERS[4], self.s_th_r),
        ]]
        dyn: list = []
        r = 1  # index courant (ligne 0 = header)

        def _add_line(ligne, alt: bool):
            nonlocal r
            desc  = "<br/>".join(escape(p) for p in (ligne.designation or "").splitlines())
            qte   = "1" if ligne.unite.lower() == "forfait" else f"{ligne.quantite}"
            unite = "" if ligne.unite.lower() == "forfait" else escape(ligne.unite)
            rows.append([
                Paragraph(desc,  self.s_left),
                Paragraph(qte,   self.s_right),
                Paragraph(unite, self.s_right),
                Paragraph(euro_fr(ligne.prix_unitaire_ht),    self.s_right),
                Paragraph(euro_fr(ligne.calculer_total_ht()), self.s_right),
            ])
            if alt:
                dyn.append(("BACKGROUND", (0, r), (-1, r), self.c_alt))
            r += 1

        if has_lots:
            for i, lot in enumerate(devis.lots, start=1):
                if not lot.lignes:
                    continue
                lot_name = lot.nom or f"Lot {i}"

                # En-tête lot — fond discret, texte ardoise gras
                rows.append([
                    Paragraph(f"<b>{escape(lot_name)}</b>", self.s_left),
                    "", "", "", "",
                ])
                dyn.extend([
                    ("BACKGROUND", (0, r), (-1, r), self.c_lot),
                    ("TEXTCOLOR",  (0, r), (-1, r), self.c_navy),
                    ("SPAN",       (0, r),  (4, r)),
                    ("TOPPADDING", (0, r), (-1, r), 7),
                    ("BOTTOMPADDING", (0, r), (-1, r), 7),
                ])
                if lot.lignes:
                    dyn.append(("NOSPLIT", (0, r), (-1, r + 1)))
                r += 1

                for j, ligne in enumerate(lot.lignes):
                    _add_line(ligne, alt=(j % 2 == 1))

                # Sous-total lot
                rows.append([
                    Paragraph(f"Sous-total  {escape(lot_name)}", self.s_muted),
                    "", "", "",
                    Paragraph(f"<b>{euro_fr(lot.calculer_sous_total_ht())}</b>", self.s_right),
                ])
                dyn.extend([
                    ("BACKGROUND", (0, r), (-1, r), self.c_sub_bg),
                    ("TEXTCOLOR",  (0, r), (-1, r), self.c_sub_txt),
                    ("TOPPADDING", (0, r), (-1, r), 5),
                    ("BOTTOMPADDING", (0, r), (-1, r), 5),
                ])
                r += 1
        else:
            for j, ligne in enumerate(self._iter_all_lines(devis)):
                _add_line(ligne, alt=(j % 2 == 1))

        if len(rows) <= 1:
            rows.append(["Aucune prestation", "", "", "", euro_fr(0)])

        table = Table(rows, colWidths=col_w, repeatRows=1)
        table.setStyle(TableStyle([
            # Global
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9.5),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            # Alignements colonnes
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            # Header
            ("BACKGROUND",    (0, 0), (-1, 0), self.c_th_bg),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 9),
            ("TOPPADDING",    (0, 0), (-1, 0), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
            # Séparateurs horizontaux fins uniquement
            ("LINEBELOW",     (0, 0), (-1, -1), 0.3, self.c_grid),
            ("LINEABOVE",     (0, 0), (-1, 0),  0.5, self.c_grid),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, self.c_grid),
        ] + dyn))
        return table

    # ── Totaux & mentions ─────────────────────────────────────────────────────

    def _build_totals_and_bank(self, devis: Devis) -> list:
        company   = get_company_info()
        is_facture = (devis.statut or "").lower() == "facture"

        ht  = devis.calculer_total_ht()
        tva = devis.calculer_total_tva()
        ttc = devis.calculer_total_ttc()

        # Bloc totaux (aligné à droite, 8 cm de large)
        totals = Table(
            [
                [Paragraph("Total HT",                       self.s_tot_lbl),
                 Paragraph(euro_fr(ht),                      self.s_tot_val)],
                [Paragraph(f"TVA {devis.tva_pourcent_global} %", self.s_tot_lbl),
                 Paragraph(euro_fr(tva),                     self.s_tot_val)],
                [Paragraph("TOTAL TTC",                      self.s_ttc_lbl),
                 Paragraph(euro_fr(ttc),                     self.s_ttc_val)],
            ],
            colWidths=[4.8 * cm, 3.2 * cm],
        )
        totals.setStyle(TableStyle([
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            # Fond blanc lignes HT + TVA, ardoise ligne TTC
            ("BACKGROUND",    (0, 0), (-1, 1), colors.white),
            ("BACKGROUND",    (0, 2), (-1, 2), self.c_navy),
            # Séparateur fin entre HT et TVA
            ("LINEBELOW",     (0, 0), (-1, 1), 0.3, self.c_border),
            # Bordure extérieure discrète
            ("BOX",           (0, 0), (-1, -1), 0.4, self.c_grid),
            # Alignements
            ("ALIGN",  (0, 0), (0, -1), "LEFT"),
            ("ALIGN",  (1, 0), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        # Bloc notes / mentions
        notes: list[Paragraph] = []
        s_note_lbl = ParagraphStyle("s_nl", parent=self.s_body,
            fontSize=8, fontName="Helvetica-Bold", textColor=self.c_navy,
            spaceBefore=0, spaceAfter=3)
        s_note_val = ParagraphStyle("s_nv", parent=self.s_body,
            fontSize=8.8, textColor=self.c_text, leading=12)

        if devis.delais.strip():
            notes.append(Paragraph("Délais", s_note_lbl))
            notes.append(Paragraph(escape(devis.delais), s_note_val))
        if devis.remarques.strip():
            notes.append(Paragraph("Remarques", s_note_lbl))
            notes.append(Paragraph(
                escape(devis.remarques).replace("\n", "<br/>"), s_note_val))
        if is_facture:
            notes.append(Paragraph("Coordonnées bancaires", s_note_lbl))
            lines_bank = [
                company.banque_nom,
                f"Code Banque {company.code_banque}  •  Code Guichet {company.code_guichet}",
                f"IBAN : {company.iban}",
                f"BIC : {company.bic}",
            ]
            for ln in lines_bank:
                if ln.strip():
                    notes.append(Paragraph(escape(ln), s_note_val))

        if notes:
            notes_block = Table([[notes]], colWidths=[10.0 * cm])
            notes_block.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), self.c_section),
                ("BOX",           (0, 0), (-1, -1), 0.4, self.c_grid),
                ("LEFTPADDING",   (0, 0), (-1, -1), 12),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ]))
            row = Table(
                [[notes_block, Spacer(0.5 * cm, 1), totals]],
                colWidths=[10.0 * cm, 0.5 * cm, 8.0 * cm],
            )
        else:
            # Totaux alignés à droite sans bloc notes
            spacer = Spacer(10.0 * cm, 1)
            row = Table(
                [[spacer, totals]],
                colWidths=[10.5 * cm, 8.0 * cm],
            )

        row.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return [CondPageBreak(8 * cm), KeepTogether([Spacer(1, 0.3 * cm), row])]

    # ── Export ────────────────────────────────────────────────────────────────

    def export(self, devis: Devis, output_path: str):
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=1.2 * cm,
            leftMargin=1.2 * cm,
            topMargin=1.0 * cm,
            bottomMargin=2.2 * cm,
        )
        story = []
        story.extend(self._build_header(devis))
        story.append(Spacer(1, PDF_SPACE_BEFORE_TABLE_CM * cm))
        story.append(self._build_main_table(devis))
        story.extend(self._build_totals_and_bank(devis))
        doc.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
