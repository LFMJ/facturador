import datetime
from tkinter import messagebox, filedialog
import customtkinter as ctk

import db
from pdf_gen import generate_invoice_pdf, fmt_money
from theme import INK, INK_SOFT, LINE, RED, FONT_HEAD, FONT_HEAD_SM, FONT_BODY_SM


class HistorialTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Historial de facturas", font=FONT_HEAD, text_color=INK, anchor="w").pack(fill="x")
        ctk.CTkLabel(self, text="Todas las facturas generadas quedan guardadas aquí para toda la empresa.",
                     font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x", pady=(2, 16))
        card = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color=LINE, corner_radius=8)
        card.pack(fill="both", expand=True)
        self.scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        try:
            invoices = db.list_invoices(self.app.server)
            company = db.get_company(self.app.server)
        except db.DBError as e:
            ctk.CTkLabel(self.scroll, text=str(e), text_color=RED, wraplength=500,
                         justify="left").pack(padx=12, pady=20, anchor="w")
            return
        self.currency = company.get("currency") or "$"
        if not invoices:
            ctk.CTkLabel(self.scroll, text='Aún no hay facturas. Genera la primera desde "Nueva factura".',
                         text_color=INK_SOFT, font=FONT_BODY_SM).pack(padx=12, pady=30)
            return
        for inv in invoices:
            self._render_row(inv)

    def _render_row(self, inv):
        total = inv.get("total", 0)
        date_str = datetime.datetime.fromtimestamp(inv["created_at"]).strftime("%d/%m/%Y") if inv.get("created_at") else ""

        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=6)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=f'{inv["number"]}   ·   {date_str}', font=FONT_HEAD_SM,
                     text_color=INK, anchor="w").pack(fill="x")
        ctk.CTkLabel(info, text=f'{inv.get("client_name") or "Sin cliente"}   ·   {fmt_money(total, self.currency)}',
                     font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.pack(side="right")
        ctk.CTkButton(btns, text="Descargar PDF", width=110, height=28, fg_color="transparent",
                       border_width=1, border_color=LINE, text_color=INK_SOFT, hover_color="#F0EEE8",
                       command=lambda: self._download(inv)).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Eliminar", width=80, height=28, fg_color="transparent",
                       text_color=RED, hover_color="#F7E9E9",
                       command=lambda: self._delete(inv)).pack(side="left", padx=4)

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

    def _delete(self, inv):
        if not messagebox.askyesno("Eliminar factura", f'¿Eliminar la factura {inv["number"]}? Esta acción no se puede deshacer.'):
            return
        try:
            db.delete_invoice(self.app.server, inv["id"])
            self.refresh()
        except db.DBError as e:
            messagebox.showerror("No se pudo eliminar", str(e))
