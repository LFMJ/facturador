import datetime
from tkinter import messagebox, filedialog
import customtkinter as ctk

import db
from pdf_gen import generate_invoice_pdf, fmt_money
from theme import INK, INK_SOFT, BRASS, LINE, RED, FONT_HEAD, FONT_BODY, FONT_BODY_SM, FONT_MONO
from tab_clientes import ClientModal

PLACEHOLDER_PRODUCT = "— elegir producto —"
PAYMENT_METHODS = [("efectivo", "Efectivo"), ("transferencia", "Transferencia"), ("tarjeta", "Tarjeta"), ("otro", "Otro")]


class ItemRow:
    """Una línea de factura: producto del catálogo (obligatorio), cantidad,
    precio (autocompletado, editable) y descuento %."""
    def __init__(self, parent, tab, index):
        self.tab = tab
        self.product = None  # dict del producto seleccionado
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.grid(row=index, column=0, sticky="ew", pady=3)
        self.frame.grid_columnconfigure(0, weight=1)

        self.qty_var = ctk.StringVar(value="1")
        self.price_var = ctk.StringVar(value="0")
        self.discount_var = ctk.StringVar(value="0")

        self.product_menu = ctk.CTkOptionMenu(self.frame, values=[PLACEHOLDER_PRODUCT],
                                               command=self._on_pick_product, font=FONT_BODY_SM, width=190)
        self.product_menu.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.e_qty = ctk.CTkEntry(self.frame, textvariable=self.qty_var, width=55, font=FONT_BODY, height=32)
        self.e_qty.grid(row=0, column=1, padx=4)
        self.e_price = ctk.CTkEntry(self.frame, textvariable=self.price_var, width=85, font=FONT_BODY, height=32)
        self.e_price.grid(row=0, column=2, padx=4)
        self.e_discount = ctk.CTkEntry(self.frame, textvariable=self.discount_var, width=55, font=FONT_BODY, height=32)
        self.e_discount.grid(row=0, column=3, padx=4)
        self.l_total = ctk.CTkLabel(self.frame, text="$ 0.00", font=FONT_MONO, width=90, anchor="e")
        self.l_total.grid(row=0, column=4, padx=4)
        self.b_del = ctk.CTkButton(self.frame, text="✕", width=28, height=28, fg_color="transparent",
                                    text_color=RED, hover_color="#F7E9E9", command=lambda: tab.remove_row(self))
        self.b_del.grid(row=0, column=5)

        for var in (self.qty_var, self.price_var, self.discount_var):
            var.trace_add("write", lambda *_: tab._recalc())

    def set_products(self, products):
        self._products_by_label = {f'{p["name"]} (stock: {p.get("stock_qty",0):g})': p for p in products}
        labels = [PLACEHOLDER_PRODUCT] + list(self._products_by_label.keys())
        current = self.product_menu.get()
        self.product_menu.configure(values=labels)
        if current not in labels:
            self.product_menu.set(PLACEHOLDER_PRODUCT)

    def _on_pick_product(self, label):
        product = self._products_by_label.get(label)
        self.product = product
        if product:
            self.price_var.set(str(product["price"]))
        self.tab._recalc()

    def get(self):
        try:
            qty = float(self.qty_var.get().replace(",", "."))
        except ValueError:
            qty = None
        try:
            price = float(self.price_var.get().replace(",", "."))
        except ValueError:
            price = None
        try:
            discount = float(self.discount_var.get().replace(",", "."))
        except ValueError:
            discount = None
        return {"product": self.product, "qty": qty, "price": price, "discount": discount}

    def update_total_label(self, currency):
        d = self.get()
        qty = d["qty"] or 0
        price = d["price"] or 0
        discount = d["discount"] or 0
        line_total = qty * price * (1 - discount / 100)
        self.l_total.configure(text=fmt_money(line_total, currency))

    def destroy(self):
        self.frame.destroy()


class FacturaTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.rows = []
        self.selected_client = None
        self.client_map = {}
        self.products = []
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Nueva factura", font=FONT_HEAD, text_color=INK, anchor="w").pack(fill="x")
        ctk.CTkLabel(self, text="Los artículos se eligen desde tu catálogo, para llevar el inventario al día.",
                     font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x", pady=(2, 12))

        self.error_box = ctk.CTkFrame(self, fg_color="#FBEEEC", border_width=1, border_color="#E7C3BE", corner_radius=6)
        self.error_label = ctk.CTkLabel(self.error_box, text="", text_color="#7A2E2E", font=FONT_BODY_SM,
                                         justify="left", anchor="w", wraplength=640)
        self.error_label.pack(padx=14, pady=10, anchor="w")

        card = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color=LINE, corner_radius=8)
        card.pack(fill="both", expand=True)
        inner = ctk.CTkScrollableFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=18)

        # --- cliente ---
        ctk.CTkLabel(inner, text="Cliente", font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        client_row = ctk.CTkFrame(inner, fg_color="transparent")
        client_row.pack(fill="x", pady=(3, 4))
        self.client_menu = ctk.CTkOptionMenu(client_row, values=["— elegir cliente —"], command=self._on_pick_client,
                                              font=FONT_BODY, width=260)
        self.client_menu.pack(side="left")
        ctk.CTkButton(client_row, text="+ Nuevo cliente rápido", fg_color="transparent", border_width=1,
                      border_color=LINE, text_color=INK_SOFT, hover_color="#F0EEE8",
                      command=self._quick_new_client).pack(side="left", padx=10)
        self.client_info = ctk.CTkLabel(inner, text="Selecciona un cliente.", font=FONT_BODY_SM,
                                         text_color=INK_SOFT, anchor="w", justify="left")
        self.client_info.pack(fill="x", pady=(0, 14))

        # --- items ---
        ctk.CTkLabel(inner, text="Artículos (desde tu catálogo)", font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(header, text="Producto", font=FONT_BODY_SM, text_color=INK_SOFT, width=190, anchor="w").grid(row=0, column=0, sticky="w", padx=(0,6))
        ctk.CTkLabel(header, text="Cant.", font=FONT_BODY_SM, text_color=INK_SOFT, width=55).grid(row=0, column=1, padx=4)
        ctk.CTkLabel(header, text="Precio", font=FONT_BODY_SM, text_color=INK_SOFT, width=85).grid(row=0, column=2, padx=4)
        ctk.CTkLabel(header, text="Desc. %", font=FONT_BODY_SM, text_color=INK_SOFT, width=55).grid(row=0, column=3, padx=4)
        ctk.CTkLabel(header, text="Total", font=FONT_BODY_SM, text_color=INK_SOFT, width=90).grid(row=0, column=4, padx=4)

        self.rows_container = ctk.CTkFrame(inner, fg_color="transparent")
        self.rows_container.pack(fill="x")
        self.rows_container.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(inner, text="+ Añadir línea", fg_color="transparent", border_width=1,
                      border_color=LINE, text_color=INK_SOFT, hover_color="#F0EEE8",
                      command=self.add_row).pack(anchor="w", pady=(6, 4))

        # --- impuesto / vendedor ---
        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x", pady=(14, 4))
        row2.grid_columnconfigure((0, 1), weight=1)
        f1 = ctk.CTkFrame(row2, fg_color="transparent"); f1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        f2 = ctk.CTkFrame(row2, fg_color="transparent"); f2.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.tax_label_widget = ctk.CTkLabel(f1, text="Impuesto (%)", font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w")
        self.tax_label_widget.pack(fill="x")
        self.tax_var = ctk.StringVar(value="19")
        self.e_tax = ctk.CTkEntry(f1, textvariable=self.tax_var, font=FONT_BODY, height=34)
        self.e_tax.pack(fill="x", pady=(3, 0))
        self.tax_var.trace_add("write", lambda *_: self._recalc())
        ctk.CTkLabel(f2, text="Vendedor", font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        self.e_seller = ctk.CTkEntry(f2, font=FONT_BODY, height=34, placeholder_text="¿Quién hizo la venta?")
        self._current_total = 0.0
        self.e_seller.pack(fill="x", pady=(3, 0))

        # --- notas / garantia ---
        row3 = ctk.CTkFrame(inner, fg_color="transparent")
        row3.pack(fill="x", pady=(10, 4))
        row3.grid_columnconfigure((0, 1), weight=1)
        f3 = ctk.CTkFrame(row3, fg_color="transparent"); f3.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        f4 = ctk.CTkFrame(row3, fg_color="transparent"); f4.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ctk.CTkLabel(f3, text="Notas (opcional)", font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        self.e_notes = ctk.CTkEntry(f3, font=FONT_BODY, height=34, placeholder_text="Condiciones de pago, gracias, etc.")
        self.e_notes.pack(fill="x", pady=(3, 0))
        ctk.CTkLabel(f4, text="Garantía (opcional)", font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        self.e_warranty = ctk.CTkEntry(f4, font=FONT_BODY, height=34, placeholder_text="ej. 6 meses por defectos de fábrica")
        self.e_warranty.pack(fill="x", pady=(3, 0))

        # --- totales ---
        totals = ctk.CTkFrame(inner, fg_color="#F5F4F0", corner_radius=6)
        totals.pack(fill="x", pady=(16, 4))
        tin = ctk.CTkFrame(totals, fg_color="transparent")
        tin.pack(fill="x", padx=16, pady=10)
        self.l_gross = self._totals_row(tin, "Subtotal")
        self.l_discount = self._totals_row(tin, "Descuento")
        self.l_taxamt = self._totals_row(tin, "Impuesto")
        self.l_total = self._totals_row(tin, "Total", bold=True)

        # --- forma de pago ---
        ctk.CTkLabel(inner, text="Forma de pago", font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x", pady=(10, 3))
        pay_row = ctk.CTkFrame(inner, fg_color="transparent")
        pay_row.pack(fill="x")
        self.pay_mode = ctk.CTkSegmentedButton(pay_row, values=["Pagada ahora", "A crédito"], command=self._on_pay_mode)
        self.pay_mode.set("Pagada ahora")
        self.pay_mode.pack(side="left")
        ctk.CTkLabel(pay_row, text="Método:", font=FONT_BODY_SM, text_color=INK_SOFT).pack(side="left", padx=(16, 4))
        self.pay_method = ctk.CTkOptionMenu(pay_row, values=[l for _v, l in PAYMENT_METHODS], width=140)
        self.pay_method.pack(side="left")
        self.abono_label = ctk.CTkLabel(pay_row, text="Abono inicial:", font=FONT_BODY_SM, text_color=INK_SOFT)
        self.e_abono = ctk.CTkEntry(pay_row, width=110, placeholder_text="0", font=FONT_BODY, height=32)

        ctk.CTkButton(inner, text="Generar factura y guardar PDF", command=self._generate,
                      fg_color=INK, hover_color="#233650", height=40).pack(anchor="w", pady=(16, 4))

    def _on_pay_mode(self, value):
        if value == "A crédito":
            self.abono_label.pack(side="left", padx=(16, 4))
            self.e_abono.pack(side="left")
        else:
            self.abono_label.pack_forget()
            self.e_abono.pack_forget()

    def _totals_row(self, parent, label, bold=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        weight_font = ("Georgia", 15, "bold") if bold else FONT_BODY
        val_font = ("Consolas", 15, "bold") if bold else FONT_MONO
        ctk.CTkLabel(row, text=label, font=weight_font, text_color=INK).pack(side="left")
        val = ctk.CTkLabel(row, text="$ 0.00", font=val_font, text_color=INK)
        val.pack(side="right")
        return val

    # ---------- lifecycle ----------
    def refresh(self):
        try:
            company = db.get_company(self.app.server)
            clients = db.list_clients(self.app.server)
            self.products = db.list_products(self.app.server)
        except db.DBError as e:
            messagebox.showerror("No se pudo cargar la información", str(e))
            return
        self.company = company
        self.currency = company.get("currency") or "$"
        self.tax_label_widget.configure(text=f'{company.get("tax_label") or "Impuesto"} (%)')
        if not self.rows:
            self.tax_var.set(str(company.get("tax_rate", 19)))
            self._reset_seller()
            self.add_row()
        else:
            for row in self.rows:
                row.set_products(self.products)

        self.client_map = {f'{c["name"]}' + (f' — {c["doc"]}' if c.get("doc") else ""): c for c in clients}
        labels = ["— elegir cliente —"] + list(self.client_map.keys())
        self.client_menu.configure(values=labels)

        self._recalc()

    def _reset_seller(self):
        self.e_seller.delete(0, "end")
        if not self.app.user.get("master"):
            self.e_seller.insert(0, self.app.user.get("name", ""))

    # ---------- cliente ----------
    def _on_pick_client(self, label):
        self.selected_client = self.client_map.get(label)
        self._render_client_info()

    def _render_client_info(self):
        c = self.selected_client
        if not c:
            self.client_info.configure(text="Selecciona un cliente.")
            return
        parts = [c["name"]]
        if c.get("doc"): parts.append(c["doc"])
        if c.get("address"): parts.append(c["address"])
        contact = " · ".join([x for x in [c.get("phone"), c.get("email")] if x])
        if contact: parts.append(contact)
        self.client_info.configure(text="\n".join(parts))

    def _quick_new_client(self):
        def on_saved(client):
            self.refresh()
            for label, c in self.client_map.items():
                if c["id"] == client["id"]:
                    self.client_menu.set(label)
                    self.selected_client = c
                    self._render_client_info()
                    break
        ClientModal(self.app, on_saved)

    # ---------- items ----------
    def add_row(self):
        row = ItemRow(self.rows_container, self, len(self.rows))
        row.set_products(self.products)
        self.rows.append(row)
        self._recalc()

    def remove_row(self, row):
        row.destroy()
        self.rows.remove(row)
        if not self.rows:
            self.add_row()
        else:
            self._regrid()
        self._recalc()

    def _regrid(self):
        for i, row in enumerate(self.rows):
            row.frame.grid(row=i, column=0, sticky="ew", pady=3)

    # ---------- cálculo ----------
    def _recalc(self):
        currency = getattr(self, "currency", "$")
        gross = 0.0
        discount_total = 0.0
        for row in self.rows:
            d = row.get()
            qty = d["qty"] or 0
            price = d["price"] or 0
            discount = d["discount"] or 0
            gross += qty * price
            discount_total += qty * price * (discount / 100)
            row.update_total_label(currency)
        net = gross - discount_total
        try:
            tax_rate = float(self.tax_var.get().replace(",", "."))
        except ValueError:
            tax_rate = 0.0
        tax_amt = net * (tax_rate / 100)
        total = net + tax_amt
        self._current_total = round(total, 2)
        self.l_gross.configure(text=fmt_money(gross, currency))
        self.l_discount.configure(text=("- " + fmt_money(discount_total, currency)) if discount_total else fmt_money(0, currency))
        self.l_taxamt.configure(text=fmt_money(tax_amt, currency))
        self.l_total.configure(text=fmt_money(total, currency))

    # ---------- generar ----------
    def _set_errors(self, errors):
        if errors:
            bullet_text = "Revisa lo siguiente antes de generar la factura:\n" + "\n".join(f"•  {e}" for e in errors)
            self.error_label.configure(text=bullet_text)
            self.error_box.pack(fill="x", pady=(0, 12))
        else:
            self.error_box.pack_forget()

    def _generate(self):
        errors = []
        if not self.selected_client:
            errors.append("Falta el cliente: selecciónalo de la lista o crea uno nuevo, para saber a quién se factura.")

        raw_items = [row.get() for row in self.rows]
        active = [it for it in raw_items if it["product"]]
        if not active:
            errors.append("Añade al menos un artículo seleccionado desde el catálogo.")
        else:
            for it in active:
                label = it["product"]["name"]
                if it["qty"] is None or it["qty"] <= 0:
                    errors.append(f'En "{label}": la cantidad debe ser un número mayor que cero.')
                elif it["qty"] > (it["product"].get("stock_qty", 0) or 0):
                    errors.append(
                        f'En "{label}": pediste {it["qty"]:g} pero solo hay {it["product"].get("stock_qty",0):g} en existencia.'
                    )
                if it["price"] is None or it["price"] <= 0:
                    errors.append(f'En "{label}": el precio debe ser un número mayor que cero.')
                if it["discount"] is None or not (0 <= it["discount"] <= 100):
                    errors.append(f'En "{label}": el descuento debe ser un número entre 0 y 100.')

        try:
            tax_rate = float(self.tax_var.get().replace(",", "."))
            if not (0 <= tax_rate <= 100):
                raise ValueError
        except ValueError:
            tax_rate = None
            errors.append(f'La tarifa de {self.company.get("tax_label","impuesto")} debe ser un número entre 0 y 100.')

        payment = {"mode": "credito" if self.pay_mode.get() == "A crédito" else "contado",
                   "method": dict((l, v) for v, l in PAYMENT_METHODS)[self.pay_method.get()]}
        if payment["mode"] == "credito":
            raw = self.e_abono.get().strip().replace(",", ".")
            try:
                payment["amount"] = float(raw) if raw else 0.0
                if payment["amount"] < 0:
                    raise ValueError
                if payment["amount"] > self._current_total + 0.004:
                    errors.append("El abono inicial no puede ser mayor que el total de la factura.")
            except ValueError:
                errors.append("El abono inicial debe ser un número igual o mayor que cero (o déjalo vacío).")

        self._set_errors(errors)
        if errors:
            self.app.show_toast("Hay datos por corregir antes de generar la factura.", error=True)
            return

        valid_items = [
            {"product_id": it["product"]["id"], "qty": it["qty"], "price": it["price"], "discount": it["discount"]}
            for it in active
        ]

        try:
            invoice_id, number = db.create_invoice(
                self.app.server, self.selected_client, valid_items, tax_rate,
                notes=self.e_notes.get().strip(), warranty=self.e_warranty.get().strip(),
                seller=self.e_seller.get().strip(), payment=payment,
            )
        except db.DBError as e:
            messagebox.showerror("No se pudo guardar la factura", str(e))
            return

        default_name = f"{number}.pdf"
        out_path = filedialog.asksaveasfilename(
            title="Guardar factura como", defaultextension=".pdf",
            initialfile=default_name, filetypes=[("PDF", "*.pdf")],
        )
        if out_path:
            try:
                full_invoice = db.get_invoice_with_items(self.app.server, invoice_id)
                company_full = db.get_company(self.app.server)
                generate_invoice_pdf(full_invoice, company_full, out_path)
                self.app.show_toast(f"Factura {number} generada y guardada.")
            except Exception as e:
                messagebox.showerror(
                    "La factura se guardó, pero el PDF falló",
                    f"La factura {number} quedó guardada (y el inventario ya se descontó), pero no se pudo "
                    f"crear el PDF ({e}). Puedes volver a descargarlo desde Historial.",
                )
        else:
            self.app.show_toast(f"Factura {number} guardada. Puedes descargar el PDF desde Historial.")

        # reset
        for row in list(self.rows):
            row.destroy()
        self.rows = []
        self.selected_client = None
        self.client_menu.set("— elegir cliente —")
        self._render_client_info()
        self.e_notes.delete(0, "end")
        self.e_warranty.delete(0, "end")
        self._reset_seller()
        self.pay_mode.set("Pagada ahora")
        self._on_pay_mode("Pagada ahora")
        self.e_abono.delete(0, "end")
        self.add_row()
        self._set_errors([])
        self.app.go_to("historial")
