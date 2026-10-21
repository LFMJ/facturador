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
VOID_RED = colors.HexColor("#A23B3B")

PAYMENT_LABELS = {"efectivo": "Efectivo", "transferencia": "Transferencia", "tarjeta": "Tarjeta", "otro": "Otro"}


def _void_stamp(canvas, doc):
    """Sello diagonal "ANULADA" sobre toda la página."""
    canvas.saveState()
    canvas.setFillColor(VOID_RED)
    canvas.setFillAlpha(0.18)
    canvas.setFont("Helvetica-Bold", 96)
    w, h = doc.pagesize
    canvas.translate(w / 2, h / 2)
    canvas.rotate(35)
    canvas.drawCentredString(0, -30, "ANULADA")
    canvas.restoreState()


def _t(value) -> str:
    """Escapa texto del usuario para Paragraph (que interpreta <, > y & como marcado)."""
    return escape(str(value or ""))


def fmt_cop(value) -> str:
    """Número al estilo colombiano: 245.000 (punto de miles), con ",50" solo si hay centavos."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    cents = round(abs(value) * 100)
    txt = f"{cents // 100:,}".replace(",", ".")
    if cents % 100:
        txt += f",{cents % 100:02d}"
    return ("-" if value < 0 and cents else "") + txt


def fmt_money(value, currency="$"):
    """$ 245.000 / -$ 759.000 (formato colombiano)."""
    txt = fmt_cop(value)
    neg = txt.startswith("-")
    return f"{'-' if neg else ''}{currency} {txt.lstrip('-')}"


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
    lines_total = gross - discount_total
    tax_rate = float(invoice.get("tax_rate") or 0)
    if invoice.get("tax_included"):
        # el precio de cada artículo ya trae el IVA: se desglosa, no se suma
        total = lines_total
        subtotal = lines_total / (1 + tax_rate / 100)
    else:
        # facturas anteriores: el IVA se sumaba aparte
        subtotal = lines_total
        total = lines_total * (1 + tax_rate / 100)
    tax_amount = total - subtotal
    tax_label = _t(company.get("tax_label") or "Impuesto")
    currency = _t(currency)

    totals_rows = []
    if discount_total > 0:
        totals_rows.append([Paragraph("Valor sin descuento", style_td), Paragraph(fmt_money(gross, currency), style_td_r)])
        totals_rows.append([Paragraph("Descuento", style_td), Paragraph(f"- {fmt_money(discount_total, currency)}", style_td_r)])
    totals_rows.append([Paragraph("Subtotal (sin IVA)" if invoice.get("tax_included") else "Subtotal", style_td),
                        Paragraph(fmt_money(subtotal, currency), style_td_r)])
    tax_text = f"{tax_label} ({tax_rate:g}%)" + (" incluido" if invoice.get("tax_included") else "")
    totals_rows.append([Paragraph(tax_text, style_td), Paragraph(fmt_money(tax_amount, currency), style_td_r)])
    totals_rows.append([
        Paragraph("<b>Total</b>", ParagraphStyle("totlbl", fontName="Times-Bold", fontSize=12, textColor=INK)),
        Paragraph(f"<b>{fmt_money(total, currency)}</b>", ParagraphStyle("totval", fontName="Times-Bold", fontSize=12, textColor=INK, alignment=TA_RIGHT)),
    ])
    returned = float(invoice.get("returned") or 0)
    if returned > 0:
        totals_rows.append([Paragraph("Devoluciones", style_td), Paragraph(f"- {fmt_money(returned, currency)}", style_td_r)])
        totals_rows.append([
            Paragraph("<b>Total final</b>", ParagraphStyle("totlbl2", fontName="Times-Bold", fontSize=12, textColor=INK)),
            Paragraph(f"<b>{fmt_money(total - returned, currency)}</b>",
                      ParagraphStyle("totval2", fontName="Times-Bold", fontSize=12, textColor=INK, alignment=TA_RIGHT)),
        ])
        total -= returned
    totals_table = Table(totals_rows, colWidths=[42 * mm, 35 * mm], hAlign="RIGHT")
    last_row = len(totals_rows) - 1
    totals_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, last_row), (-1, last_row), 1.2, INK),
        ("TOPPADDING", (0, last_row), (-1, last_row), 8),
    ]))
    story.append(totals_table)

    # --- estado de pago (solo si la factura lleva registro de pagos) ---
    if invoice.get("payment_tracking") and invoice.get("status") != "anulada":
        paid = sum(float(p.get("amount") or 0) for p in invoice.get("payments") or [])
        balance = round(total - paid, 2)
        methods = sorted({PAYMENT_LABELS.get(p.get("method"), p.get("method") or "") for p in invoice.get("payments") or []})
        if total <= 0.004 and returned > 0:
            text = "DEVUELTA EN SU TOTALIDAD"
        elif balance <= 0.004:
            text = "PAGADA" + (f" · {', '.join(methods)}" if methods else "")
        else:
            text = (f"Abonado: {_t(fmt_money(paid, company.get('currency') or '$'))} · "
                    f"<b>Saldo pendiente: {_t(fmt_money(balance, company.get('currency') or '$'))}</b>")
        story.append(Spacer(1, 6))
        story.append(Paragraph(text, ParagraphStyle("paystate", parent=style_co_meta, alignment=TA_RIGHT)))

    if invoice.get("returns"):
        story.append(Spacer(1, 14))
        story.append(Paragraph("DEVOLUCIONES", style_label))
        for r in invoice["returns"]:
            detail = ", ".join(f'{float(x["qty"]):g} × {x["description"]}' for x in r.get("items") or [])
            line = f'{format_date_es(r["created_at"])} · {detail} · {fmt_money(r["amount"], company.get("currency") or "$")}'
            if r.get("reason"):
                line += f' · {r["reason"]}'
            if float(r.get("refund") or 0) > 0:
                line += f' · se devolvieron {fmt_money(r["refund"], company.get("currency") or "$")}'
            story.append(Paragraph(_t(line), style_footer))

    if invoice.get("status") == "anulada":
        story.append(Spacer(1, 14))
        story.append(Paragraph("FACTURA ANULADA", ParagraphStyle("void_lbl", parent=style_label, textColor=VOID_RED)))
        when = format_date_es(invoice["voided_at"]) if invoice.get("voided_at") else ""
        detail = " · ".join(x for x in [when, f"por {invoice['voided_by']}" if invoice.get("voided_by") else "",
                                         invoice.get("void_reason") or ""] if x)
        story.append(Paragraph(_t(detail), style_footer))

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

    if invoice.get("status") == "anulada":
        doc.build(story, onFirstPage=_void_stamp, onLaterPages=_void_stamp)
    else:
        doc.build(story)


STATUS_LABELS = {"pagada": "Pagada", "abono": "Abono", "pendiente": "Pendiente", "anulada": "Anulada",
                 "sin_registro": "Sin registro", "devuelta": "Devuelta"}


def generate_statement_pdf(statement: dict, company: dict, output_path):
    """Estado de cuenta de un cliente: sus facturas, lo pagado y el saldo pendiente."""
    client, summary = statement["client"], statement["summary"]
    currency = company.get("currency") or "$"
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm, title=f"Estado de cuenta {client.get('name', '')}")
    title = ParagraphStyle("st_title", fontName="Times-Bold", fontSize=18, textColor=INK, alignment=TA_RIGHT, leading=22)
    meta = ParagraphStyle("st_meta", fontName="Courier", fontSize=9, textColor=INK_SOFT, alignment=TA_RIGHT, leading=13)
    co_name = ParagraphStyle("st_co", fontName="Times-Bold", fontSize=14, textColor=INK, leading=18)
    co_meta = ParagraphStyle("st_cometa", fontName="Helvetica", fontSize=9, textColor=INK_SOFT, leading=13)
    label = ParagraphStyle("st_label", fontName="Helvetica-Bold", fontSize=8.5, textColor=BRASS, spaceAfter=4)
    body = ParagraphStyle("st_body", fontName="Helvetica", fontSize=10, textColor=INK, leading=14)
    th = ParagraphStyle("st_th", fontName="Helvetica-Bold", fontSize=8.5, textColor=INK_SOFT)
    th_r = ParagraphStyle("st_thr", parent=th, alignment=TA_RIGHT)
    td = ParagraphStyle("st_td", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#1E1E1E"), leading=13)
    td_r = ParagraphStyle("st_tdr", parent=td, alignment=TA_RIGHT)

    left = []
    if company.get("logo_blob"):
        try:
            img = Image(io.BytesIO(company["logo_blob"]))
            img._restrictSize(45 * mm, 20 * mm)
            left += [img, Spacer(1, 4)]
        except Exception:
            pass
    left.append(Paragraph(_t(company.get("name") or "Empresa"), co_name))
    for line in [company.get("tax_id"), company.get("address"),
                 " · ".join(x for x in [company.get("phone"), company.get("email")] if x)]:
        if line:
            left.append(Paragraph(_t(line), co_meta))
    right = [Paragraph("ESTADO DE CUENTA", title), Paragraph(format_date_es(datetime.datetime.now()), meta)]
    header = Table([[left, right]], colWidths=[100 * mm, 70 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story = [header, Spacer(1, 8), HRFlowable(width="100%", thickness=1.4, color=INK), Spacer(1, 14),
             Paragraph("CLIENTE", label)]
    for line in [client.get("name"), client.get("doc"), client.get("address"),
                 " · ".join(x for x in [client.get("phone"), client.get("email")] if x)]:
        if line:
            story.append(Paragraph(_t(line), body))
    story.append(Spacer(1, 14))

    rows = [[Paragraph(h, th) for h in ("FACTURA", "FECHA", "ESTADO")] +
            [Paragraph(h, th_r) for h in ("TOTAL", "PAGADO", "SALDO")]]
    for inv in statement["invoices"]:
        voided = inv.get("status") == "anulada"
        tracked = inv.get("payment_tracking")
        rows.append([
            Paragraph(_t(inv["number"]), td),
            Paragraph(datetime.datetime.fromtimestamp(inv["created_at"]).strftime("%d/%m/%Y"), td),
            Paragraph(_t(STATUS_LABELS.get(inv["payment_status"], inv["payment_status"])), td),
            Paragraph(_t(fmt_money(inv["total"], currency)), td_r),
            Paragraph(_t(fmt_money(inv["paid"], currency)) if tracked and not voided else "—", td_r),
            Paragraph(_t(fmt_money(inv["balance"], currency)) if tracked and not voided else "—", td_r),
        ])
    if len(rows) == 1:
        rows.append([Paragraph("Sin facturas.", td), "", "", "", "", ""])
    table = Table(rows, colWidths=[26 * mm, 24 * mm, 28 * mm, 31 * mm, 30 * mm, 31 * mm])
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story += [table, Spacer(1, 12)]

    big = ParagraphStyle("st_big", fontName="Times-Bold", fontSize=12, textColor=INK)
    big_r = ParagraphStyle("st_bigr", parent=big, alignment=TA_RIGHT)
    totals = Table([
        [Paragraph("Total comprado", td), Paragraph(_t(fmt_money(summary["total"], currency)), td_r)],
        [Paragraph("Total pagado", td), Paragraph(_t(fmt_money(summary["paid"], currency)), td_r)],
        [Paragraph("<b>Saldo pendiente</b>", big), Paragraph(f"<b>{_t(fmt_money(summary['balance'], currency))}</b>", big_r)],
    ], colWidths=[40 * mm, 40 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([("LINEABOVE", (0, 2), (-1, 2), 1.2, INK), ("TOPPADDING", (0, 2), (-1, 2), 8)]))
    story.append(totals)
    if company.get("footer_note"):
        story += [Spacer(1, 18), HRFlowable(width="100%", thickness=0.6, color=LINE), Spacer(1, 8),
                  Paragraph(_t(company["footer_note"]), co_meta)]
    doc.build(story)
