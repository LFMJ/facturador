import datetime
from tkinter import messagebox, filedialog
import customtkinter as ctk

import db
from pdf_gen import generate_invoice_pdf, fmt_money
from theme import (INK, INK_SOFT, LINE, RED, GREEN, FONT_HEAD, FONT_HEAD_SM, FONT_BODY_SM,
                   labeled_entry, show_error_border)

PAYMENT_METHODS = [("efectivo", "Efectivo"), ("transferencia", "Transferencia"), ("tarjeta", "Tarjeta"), ("otro", "Otro")]
STATUS = {
    "pagada": ("Pagada", GREEN), "abono": ("Abono", "#8A5A00"), "pendiente": ("Pendiente", RED),
    "anulada": ("ANULADA", RED), "sin_registro": ("Sin registro de pago", INK_SOFT),
}
FILTERS = [("todas", "Todas"), ("por_cobrar", "Por cobrar"), ("pagada", "Pagadas"), ("anulada", "Anuladas")]


def parse_amount(raw):
    try:
        v = float(raw.strip().replace(",", "."))
        return v if v > 0 else None
    except ValueError:
        return None


class PaymentModal(ctk.CTkToplevel):
    def __init__(self, app, inv, on_done):
        super().__init__(app)
        self.app, self.inv, self.on_done = app, inv, on_done
        self.title(f'Registrar pago · {inv["number"]}')
        self.geometry("400x420")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        cur = app.frames["historial"].currency
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=20, pady=20)
        due = inv["balance"] if inv.get("payment_tracking") else inv["total"]
        info = f'{inv.get("client_name", "")}\nTotal: {fmt_money(inv["total"], cur)}'
        if inv.get("payment_tracking"):
            info += f'   ·   Saldo: {fmt_money(inv["balance"], cur)}'
        ctk.CTkLabel(pad, text=info, font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w", justify="left").pack(fill="x", pady=(0, 10))
        self.e_amount, self.err_amount = labeled_entry(pad, "Monto recibido")
        self.e_amount.insert(0, f"{due:.2f}")
        ctk.CTkLabel(pad, text="Método de pago", font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        self.method = ctk.CTkOptionMenu(pad, values=[l for _v, l in PAYMENT_METHODS])
        self.method.pack(fill="x", pady=(3, 10))
        self.e_note, _ = labeled_entry(pad, "Nota (opcional)", "ej. número de transferencia")
        ctk.CTkButton(pad, text="Registrar pago", command=self._save, fg_color=INK,
                      hover_color="#233650").pack(anchor="w", pady=(10, 0))

    def _save(self):
        self.err_amount.clear()
        show_error_border(self.e_amount, False)
        amount = parse_amount(self.e_amount.get())
        if amount is None:
            self.err_amount.set("Escribe un monto mayor que cero.")
            show_error_border(self.e_amount, True)
            return
        method = dict((l, v) for v, l in PAYMENT_METHODS)[self.method.get()]
        try:
            db.add_payment(self.app.server, self.inv["id"], amount, method, self.e_note.get().strip())
        except db.DBError as e:
            messagebox.showerror("No se pudo registrar el pago", str(e), parent=self)
            return
        self.app.show_toast("Pago registrado.")
        self.destroy()
        self.on_done()


class VoidModal(ctk.CTkToplevel):
    def __init__(self, app, inv, on_done):
        super().__init__(app)
        self.app, self.inv, self.on_done = app, inv, on_done
        self.title(f'Anular {inv["number"]}')
        self.geometry("440x330")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(pad, wraplength=390, justify="left", anchor="w", font=FONT_BODY_SM, text_color=INK_SOFT,
                     text=("La factura queda en el historial marcada como ANULADA (no se borra, para no dejar "
                           "huecos en la numeración) y el stock de sus artículos vuelve al inventario. "
                           "No se puede deshacer.")).pack(fill="x", pady=(0, 12))
        self.e_reason, self.err_reason = labeled_entry(pad, "Motivo de la anulación", "ej. error en el cliente, devolución…")
        ctk.CTkButton(pad, text="Anular factura", command=self._save, fg_color=RED,
                      hover_color="#7A2E2E").pack(anchor="w", pady=(10, 0))

    def _save(self):
        reason = self.e_reason.get().strip()
        if not reason:
            self.err_reason.set("Escribe el motivo: queda registrado en la factura.")
            show_error_border(self.e_reason, True)
            return
        try:
            db.void_invoice(self.app.server, self.inv["id"], reason)
        except db.DBError as e:
            messagebox.showerror("No se pudo anular", str(e), parent=self)
            return
        self.app.show_toast(f'Factura {self.inv["number"]} anulada.')
        self.destroy()
        self.on_done()


class HistorialTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.filter = "todas"
        self.invoices = []
        self.currency = "$"
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Historial de facturas", font=FONT_HEAD, text_color=INK, anchor="w").pack(fill="x")
        ctk.CTkLabel(self, text="Todas las facturas de la empresa, con su estado de pago.",
                     font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x", pady=(2, 10))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 10))
        # sin textvariable: con ella CustomTkinter no muestra el texto de ayuda
        self.search = ctk.CTkEntry(bar, placeholder_text="Buscar por número, cliente o vendedor…", width=320, height=34)
        self.search.bind("<KeyRelease>", lambda _e: self._render())
        self.search.pack(side="left")
        self.filter_menu = ctk.CTkSegmentedButton(bar, values=[l for _k, l in FILTERS], command=self._on_filter)
        self.filter_menu.set("Todas")
        self.filter_menu.pack(side="left", padx=12)
        self.pending_label = ctk.CTkLabel(bar, text="", font=FONT_BODY_SM, text_color=INK_SOFT)
        self.pending_label.pack(side="right")
        card = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color=LINE, corner_radius=8)
        card.pack(fill="both", expand=True)
        self.scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=8, pady=8)

    def _on_filter(self, label):
        self.filter = dict((l, k) for k, l in FILTERS)[label]
        self._render()

    def refresh(self):
        try:
            self.invoices = db.list_invoices(self.app.server)
            company = db.get_company(self.app.server)
        except db.DBError as e:
            self.invoices = []
            self._clear()
            ctk.CTkLabel(self.scroll, text=str(e), text_color=RED, wraplength=500,
                         justify="left").pack(padx=12, pady=20, anchor="w")
            return
        self.currency = company.get("currency") or "$"
        pending = sum(i["balance"] for i in self.invoices if i["payment_status"] in ("pendiente", "abono"))
        self.pending_label.configure(text=f"Por cobrar: {fmt_money(pending, self.currency)}" if pending else "")
        self._render()

    def _clear(self):
        for w in self.scroll.winfo_children():
            w.destroy()

    def _matches(self, inv):
        if self.filter == "por_cobrar":
            ok = inv["payment_status"] in ("pendiente", "abono")
        elif self.filter == "todas":
            ok = True
        else:
            ok = inv["payment_status"] == self.filter
        q = self.search.get().strip().lower()
        text = " ".join(str(inv.get(k) or "") for k in ("number", "client_name", "client_doc", "seller", "user_name")).lower()
        return ok and q in text

    def _render(self):
        self._clear()
        rows = [i for i in self.invoices if self._matches(i)]
        if not rows:
            msg = 'Aún no hay facturas. Genera la primera desde "Nueva factura".' if not self.invoices else "Sin resultados."
            ctk.CTkLabel(self.scroll, text=msg, text_color=INK_SOFT, font=FONT_BODY_SM).pack(padx=12, pady=30)
            return
        for inv in rows[:300]:
            self._render_row(inv)

    def _render_row(self, inv):
        date_str = datetime.datetime.fromtimestamp(inv["created_at"]).strftime("%d/%m/%Y") if inv.get("created_at") else ""
        voided = inv["status"] == "anulada"
        label, color = STATUS.get(inv["payment_status"], (inv["payment_status"], INK_SOFT))

        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=6)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=f'{inv["number"]}   ·   {date_str}', font=FONT_HEAD_SM,
                     text_color=INK_SOFT if voided else INK, anchor="w").pack(fill="x")
        detail = f'{inv.get("client_name") or "Sin cliente"}   ·   {fmt_money(inv["total"], self.currency)}'
        if inv["payment_status"] in ("pendiente", "abono"):
            detail += f'   ·   saldo {fmt_money(inv["balance"], self.currency)}'
        if inv.get("user_name"):
            detail += f'   ·   hecha por {inv["user_name"]}'
        ctk.CTkLabel(info, text=detail, font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        status_text = label + (f' — {inv.get("void_reason")}' if voided and inv.get("void_reason") else "")
        ctk.CTkLabel(info, text=status_text, font=("Segoe UI", 11, "bold"), text_color=color, anchor="w").pack(fill="x")

        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.pack(side="right")
        ghost = dict(width=96, height=28, fg_color="transparent", border_width=1, border_color=LINE,
                     text_color=INK_SOFT, hover_color="#F0EEE8")
        ctk.CTkButton(btns, text="Descargar PDF", command=lambda: self._download(inv), **ghost).pack(side="left", padx=4)
        if not voided and inv["payment_status"] != "pagada":
            ctk.CTkButton(btns, text="Registrar pago", width=104, height=28, fg_color="transparent", border_width=1,
                          border_color=GREEN, text_color=GREEN, hover_color="#EAF3EE",
                          command=lambda: PaymentModal(self.app, inv, self.refresh)).pack(side="left", padx=4)
        if self.app.is_admin and not voided:
            ctk.CTkButton(btns, text="Anular", width=70, height=28, fg_color="transparent",
                          text_color=RED, hover_color="#F7E9E9",
                          command=lambda: VoidModal(self.app, inv, self.refresh)).pack(side="left", padx=4)

    def _download(self, inv):
        out_path = filedialog.asksaveasfilename(
            title="Guardar factura como", defaultextension=".pdf",
            initialfile=f'{inv["number"]}.pdf', filetypes=[("PDF", "*.pdf")],
        )
        if not out_path:
            return
        try:
            full_invoice = db.get_invoice_with_items(self.app.server, inv["id"])
            company = db.get_company(self.app.server)
            generate_invoice_pdf(full_invoice, company, out_path)
            self.app.show_toast(f'Factura {inv["number"]} descargada.')
        except db.DBError as e:
            messagebox.showerror("No se pudo leer la factura", str(e))
        except Exception as e:
            messagebox.showerror("No se pudo generar el PDF", str(e))
