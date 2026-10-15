"""
Generación del PDF de la factura con reportlab, replicando el estilo tipo
"libro contable": logo + datos de la empresa, título FACTURA, datos del
cliente, tabla de artículos y totales.
"""
import io
import datetime
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
)

INK = colors.HexColor("#16233A")
INK_SOFT = colors.HexColor("#3C4A5E")
BRASS = colors.HexColor("#7C5F2C")
LINE = colors.HexColor("#E1DFD8")


def _t(value) -> str:
    """Escapa texto del usuario para Paragraph (que interpreta <, > y & como marcado)."""
    return escape(str(value or ""))


def fmt_money(value, currency="$"):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    return f"{currency} {value:,.2f}"


MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def format_date_es(dt) -> str:
    """Formatea una fecha en español (p. ej. '14 de septiembre de 2026') sin
    depender de la configuración regional (locale) del sistema operativo,
    que casi nunca tiene el idioma español instalado por defecto y hace que
    strftime('%B') devuelva el nombre del mes en inglés."""
    if isinstance(dt, (int, float)):
        dt = datetime.datetime.fromtimestamp(dt)
    return f"{dt.day} de {MESES_ES[dt.month - 1]} de {dt.year}"


def generate_invoice_pdf(invoice: dict, company: dict, output_path: str):
    """invoice: dict con number, created_at, client_name/doc/address/phone/email,
    tax_rate, notes, items:[{description, qty, price}]
    company: dict con name, tax_id, address, phone, email, currency, tax_label,
    footer_note, logo_blob (bytes|None), logo_mime"""
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Factura {invoice.get('number','')}",
    )
    story = []
    currency = company.get("currency") or "$"

    style_title = ParagraphStyle("title", fontName="Times-Bold", fontSize=20, textColor=INK,
                                  alignment=TA_RIGHT, leading=24, spaceAfter=3)
    style_meta = ParagraphStyle("meta", fontName="Courier", fontSize=9, textColor=INK_SOFT,
                                 alignment=TA_RIGHT, leading=13)
    style_co_name = ParagraphStyle("coname", fontName="Times-Bold", fontSize=14, textColor=INK,
                                    leading=18, spaceAfter=3)
    style_co_meta = ParagraphStyle("cometa", fontName="Helvetica", fontSize=9, textColor=INK_SOFT, leading=13)
    style_label = ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=8.5, textColor=BRASS, spaceAfter=4)
    style_body = ParagraphStyle("body", fontName="Helvetica", fontSize=10, textColor=INK, leading=14)
    style_th = ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8.5, textColor=INK_SOFT)
    style_th_r = ParagraphStyle("thr", fontName="Helvetica-Bold", fontSize=8.5, textColor=INK_SOFT, alignment=TA_RIGHT)
    style_td = ParagraphStyle("td", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#1E1E1E"), leading=13)
    style_td_r = ParagraphStyle("tdr", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#1E1E1E"), alignment=TA_RIGHT, leading=13)
    style_footer = ParagraphStyle("footer", fontName="Helvetica", fontSize=8.5, textColor=INK_SOFT, leading=12)

    # --- Encabezado: logo/empresa a la izquierda, FACTURA a la derecha ---
    left_cell = []
    if company.get("logo_blob"):
        try:
            img_buf = io.BytesIO(company["logo_blob"])
            img = Image(img_buf)
            img._restrictSize(45 * mm, 20 * mm)
            left_cell.append(img)
            left_cell.append(Spacer(1, 4))
        except Exception:
            pass
    left_cell.append(Paragraph(_t(company.get("name") or "Empresa"), style_co_name))
    co_lines = [l for l in [company.get("tax_id"), company.get("address"),
                             " · ".join([x for x in [company.get("phone"), company.get("email")] if x])] if l]
    for l in co_lines:
        left_cell.append(Paragraph(_t(l), style_co_meta))

    right_cell = [
        Paragraph("FACTURA", style_title),
        Paragraph(_t(invoice.get("number", "")), style_meta),
        Paragraph(format_date_es(invoice.get("created_at") or datetime.datetime.now()), style_meta),
    ]

    header_table = Table([[left_cell, right_cell]], colWidths=[105 * mm, 65 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.4, color=INK))
    story.append(Spacer(1, 14))

    # --- Facturar a ---
    story.append(Paragraph("FACTURAR A", style_label))
    client_lines = [l for l in [
        invoice.get("client_name"), invoice.get("client_doc"), invoice.get("client_address"),
        " · ".join([x for x in [invoice.get("client_phone"), invoice.get("client_email")] if x])
    ] if l]
    for l in client_lines:
        story.append(Paragraph(_t(l), style_body))
    if invoice.get("seller"):
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"Atendido por: {_t(invoice['seller'])}", style_co_meta))
    story.append(Spacer(1, 16))

    # --- Tabla de artículos ---
    has_discount = any((it.get("discount") or 0) > 0 for it in invoice.get("items", []))
    if has_discount:
        header_row = [
            Paragraph("DESCRIPCIÓN", style_th), Paragraph("CANT.", style_th_r),
            Paragraph("PRECIO", style_th_r), Paragraph("DESC.", style_th_r), Paragraph("TOTAL", style_th_r),
        ]
        col_widths = [70 * mm, 20 * mm, 26 * mm, 18 * mm, 36 * mm]
    else:
        header_row = [
            Paragraph("DESCRIPCIÓN", style_th), Paragraph("CANT.", style_th_r),
            Paragraph("PRECIO", style_th_r), Paragraph("TOTAL", style_th_r),
        ]
        col_widths = [85 * mm, 22 * mm, 30 * mm, 33 * mm]

    rows = [header_row]
    gross = 0.0
    discount_total = 0.0
    for it in invoice.get("items", []):
        qty = float(it.get("qty", 0))
        price = float(it.get("price", 0))
        discount = float(it.get("discount") or 0)
        line_gross = qty * price
        line_total = line_gross * (1 - discount / 100)
        gross += line_gross
        discount_total += line_gross - line_total
        row_cells = [Paragraph(_t(it.get("description") or "—"), style_td), Paragraph(f"{qty:g}", style_td_r),
                     Paragraph(_t(fmt_money(price, currency)), style_td_r)]
        if has_discount:
            row_cells.append(Paragraph(f"{discount:g}%" if discount else "—", style_td_r))
        row_cells.append(Paragraph(_t(fmt_money(line_total, currency)), style_td_r))
        rows.append(row_cells)

    items_table = Table(rows, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 10))

    # --- Totales ---
    net = gross - discount_total
    tax_rate = float(invoice.get("tax_rate") or 0)
    tax_amount = net * (tax_rate / 100)
    total = net + tax_amount
    tax_label = _t(company.get("tax_label") or "Impuesto")
    currency = _t(currency)

    totals_rows = []
    if discount_total > 0:
        totals_rows.append([Paragraph("Subtotal", style_td), Paragraph(fmt_money(gross, currency), style_td_r)])
        totals_rows.append([Paragraph("Descuento", style_td), Paragraph(f"- {fmt_money(discount_total, currency)}", style_td_r)])
    else:
        totals_rows.append([Paragraph("Subtotal", style_td), Paragraph(fmt_money(net, currency), style_td_r)])
    totals_rows.append([Paragraph(f"{tax_label} ({tax_rate:g}%)", style_td), Paragraph(fmt_money(tax_amount, currency), style_td_r)])
    totals_rows.append([
        Paragraph("<b>Total</b>", ParagraphStyle("totlbl", fontName="Times-Bold", fontSize=12, textColor=INK)),
        Paragraph(f"<b>{fmt_money(total, currency)}</b>", ParagraphStyle("totval", fontName="Times-Bold", fontSize=12, textColor=INK, alignment=TA_RIGHT)),
    ])
    totals_table = Table(totals_rows, colWidths=[35 * mm, 35 * mm], hAlign="RIGHT")
    last_row = len(totals_rows) - 1
    totals_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, last_row), (-1, last_row), 1.2, INK),
        ("TOPPADDING", (0, last_row), (-1, last_row), 8),
    ]))
    story.append(totals_table)

    if invoice.get("warranty"):
        story.append(Spacer(1, 16))
        story.append(Paragraph("GARANTÍA", style_label))
        story.append(Paragraph(_t(invoice["warranty"]), style_footer))

    notes = invoice.get("notes") or ""
    footer_note = company.get("footer_note") or ""
    if notes or footer_note:
        story.append(Spacer(1, 18))
        story.append(HRFlowable(width="100%", thickness=0.6, color=LINE))
        story.append(Spacer(1, 8))
        if notes:
            story.append(Paragraph(_t(notes), style_footer))
        if footer_note:
            story.append(Paragraph(_t(footer_note), style_footer))

    doc.build(story)
