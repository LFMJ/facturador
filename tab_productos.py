from tkinter import messagebox
import customtkinter as ctk

import db
from theme import (INK, INK_SOFT, BRASS, LINE, RED, GREEN, FONT_HEAD, FONT_HEAD_SM, FONT_BODY_SM,
                    labeled_entry, show_error_border)


class ProductModal(ctk.CTkToplevel):
    def __init__(self, app, on_saved, suppliers, existing=None):
        super().__init__(app)
        self.app = app
        self.on_saved = on_saved
        self.existing = existing
        self.suppliers = suppliers  # list of dicts
        self.supplier_map = {"— sin proveedor —": None}
        self.supplier_map.update({s["name"]: s["id"] for s in suppliers})
        self.title("Editar producto" if existing else "Nuevo producto")
        self.geometry("420x560")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        self._build()

    def _build(self):
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=20, pady=20)
        ex = self.existing or {}
        self.e_name, self.err_name = labeled_entry(pad, "Nombre")
        self.e_price, self.err_price = labeled_entry(pad, "Precio de venta")
        self.e_cost, self.err_cost = labeled_entry(pad, "Precio de costo (opcional)")
        self.e_unit, _ = labeled_entry(pad, "Unidad", "unidad, hora, caja...")

        ctk.CTkLabel(pad, text="Proveedor", font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x", pady=(0, 4))
        current_supplier_name = next((s["name"] for s in self.suppliers if s["id"] == ex.get("supplier_id")), "— sin proveedor —")
        self.supplier_menu = ctk.CTkOptionMenu(pad, values=list(self.supplier_map.keys()), font=("Segoe UI", 13))
        self.supplier_menu.set(current_supplier_name)
        self.supplier_menu.pack(fill="x", pady=(0, 10))

        stock_label = "Existencias iniciales" if not self.existing else "Existencias actuales (usa \"Reabastecer\" para sumar, no edites aquí para restar por ventas)"
        self.e_stock, self.err_stock = labeled_entry(pad, stock_label)

        self.e_name.insert(0, ex.get("name", ""))
        self.e_price.insert(0, str(ex.get("price", "")) if ex.get("price") is not None else "")
        self.e_cost.insert(0, str(ex.get("cost_price", "")) if ex.get("cost_price") else "")
        self.e_unit.insert(0, ex.get("unit", "") or "unidad")
        self.e_stock.insert(0, str(ex.get("stock_qty", 0)) if ex.get("stock_qty") is not None else "0")

        btn_row = ctk.CTkFrame(pad, fg_color="transparent")
        btn_row.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(btn_row, text="Guardar", command=self._save, fg_color=INK,
                      hover_color="#233650").pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="Cancelar", command=self.destroy, fg_color="transparent",
                      border_width=1, border_color=LINE, text_color=INK_SOFT,
                      hover_color="#F0EEE8").pack(side="left")

    def _save(self):
        self.err_name.clear(); self.err_price.clear(); self.err_cost.clear(); self.err_stock.clear()
        for e in (self.e_name, self.e_price, self.e_cost, self.e_stock):
            show_error_border(e, False)

        name = self.e_name.get().strip()
        price_raw = self.e_price.get().strip()
        cost_raw = self.e_cost.get().strip()
        stock_raw = self.e_stock.get().strip()
        ok = True

        if not name:
            self.err_name.set("Escribe un nombre para el producto: lo necesitas para añadirlo a una factura.")
            show_error_border(self.e_name, True)
            ok = False
        try:
            price = float(price_raw)
            if price <= 0:
                raise ValueError
        except ValueError:
            self.err_price.set("El precio de venta debe ser un número mayor que cero (ej. 25000).")
            show_error_border(self.e_price, True)
            ok = False
        cost = 0.0
        if cost_raw:
            try:
                cost = float(cost_raw)
                if cost < 0:
                    raise ValueError
            except ValueError:
                self.err_cost.set("El precio de costo debe ser un número (0 o mayor). Déjalo vacío si no lo sabes.")
                show_error_border(self.e_cost, True)
                ok = False
        try:
            stock = float(stock_raw) if stock_raw else 0.0
            if stock < 0:
                raise ValueError
        except ValueError:
            self.err_stock.set("Las existencias deben ser un número igual o mayor que cero.")
            show_error_border(self.e_stock, True)
            ok = False

        if not ok:
            return

        product = {
            "id": (self.existing or {}).get("id"), "name": name, "price": price,
            "unit": self.e_unit.get().strip() or "unidad",
            "supplier_id": self.supplier_map.get(self.supplier_menu.get()),
            "cost_price": cost, "stock_qty": stock,
        }
        try:
            pid = db.save_product(self.app.server, product)
            product["id"] = pid
            self.app.show_toast("Producto guardado.")
            self.on_saved(product)
            self.destroy()
        except db.DBError as e:
            messagebox.showerror("No se pudo guardar", str(e))


class RestockModal(ctk.CTkToplevel):
    """Ventana para sumar existencias (reabastecer) sin editar el producto."""
    def __init__(self, app, product, on_done):
        super().__init__(app)
        self.app = app
        self.product = product
        self.on_done = on_done
        self.title(f'Reabastecer "{product["name"]}"')
        self.geometry("380x280")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        self._build()

    def _build(self):
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(pad, text=f'Existencias actuales: {self.product.get("stock_qty", 0):g}',
                     font=("Segoe UI", 12), text_color=INK_SOFT, anchor="w").pack(fill="x", pady=(0, 12))
        self.e_qty, self.err_qty = labeled_entry(pad, "Cantidad que estás ingresando")
        self.e_note, _ = labeled_entry(pad, "Nota (opcional)", "ej. compra a proveedor, factura #123")

        btn_row = ctk.CTkFrame(pad, fg_color="transparent")
        btn_row.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(btn_row, text="Agregar al stock", command=self._save, fg_color=INK,
                      hover_color="#233650").pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="Cancelar", command=self.destroy, fg_color="transparent",
                      border_width=1, border_color=LINE, text_color=INK_SOFT,
                      hover_color="#F0EEE8").pack(side="left")

    def _save(self):
        self.err_qty.clear()
        show_error_border(self.e_qty, False)
        try:
            qty = float(self.e_qty.get().strip())
            if qty <= 0:
                raise ValueError
        except ValueError:
            self.err_qty.set("Escribe cuántas unidades estás ingresando (un número mayor que cero).")
            show_error_border(self.e_qty, True)
            return
        try:
            db.restock_product(self.app.server, self.product["id"], qty, self.e_note.get().strip())
            self.app.show_toast(f'Se sumaron {qty:g} unidades a "{self.product["name"]}".')
            self.on_done()
            self.destroy()
        except db.DBError as e:
            messagebox.showerror("No se pudo reabastecer", str(e))


class ProductosTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x")
        left = ctk.CTkFrame(head, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text="Productos e inventario", font=FONT_HEAD, text_color=INK, anchor="w").pack(fill="x")
        ctk.CTkLabel(left, text="Tu catálogo, con existencias y proveedor de cada artículo.",
                     font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        self.new_btn = ctk.CTkButton(head, text="+ Nuevo producto", command=self._new_product,
                                     fg_color=BRASS, hover_color="#7C5F2C", text_color="#211804")
        if self.app.is_admin:
            self.new_btn.pack(side="right")

        self.list_card = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color=LINE, corner_radius=8)
        self.list_card.pack(fill="both", expand=True, pady=(16, 0))

    def refresh(self):
        for w in self.list_card.winfo_children():
            w.destroy()
        try:
            company = db.get_company(self.app.server)
            self.suppliers = db.list_suppliers(self.app.server) if self.app.is_admin else []
            products = db.list_products(self.app.server)
        except db.DBError as e:
            ctk.CTkLabel(self.list_card, text=str(e), text_color=RED, wraplength=500,
                         justify="left").pack(padx=20, pady=20, anchor="w")
            return
        self.currency = company.get("currency") or "$"
        if not products:
            ctk.CTkLabel(self.list_card, text="Sin productos aún. Añade uno para reutilizarlo en tus facturas.",
                         text_color=INK_SOFT, font=FONT_BODY_SM).pack(padx=20, pady=30)
            return
        for p in products:
            self._render_row(p)

    def _render_row(self, p):
        row = ctk.CTkFrame(self.list_card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=8)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=p["name"], font=FONT_HEAD_SM, text_color=INK, anchor="w").pack(fill="x")
        stock = p.get("stock_qty", 0) or 0
        stock_color = RED if stock <= 0 else INK_SOFT
        meta = f'{self.currency} {p["price"]:,.2f} / {p.get("unit","unidad")}   ·   Existencias: {stock:g}'
        if p.get("supplier_name"):
            meta += f'   ·   Proveedor: {p["supplier_name"]}'
        ctk.CTkLabel(info, text=meta, font=FONT_BODY_SM, text_color=stock_color, anchor="w").pack(fill="x")
        if not self.app.is_admin:
            return  # el vendedor solo consulta precios y existencias
        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.pack(side="right")
        ctk.CTkButton(btns, text="Reabastecer", width=90, height=28, fg_color="transparent",
                      border_width=1, border_color=GREEN, text_color=GREEN, hover_color="#EAF3EE",
                      command=lambda: self._restock(p)).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Editar", width=60, height=28, fg_color="transparent",
                      border_width=1, border_color=LINE, text_color=INK_SOFT,
                      hover_color="#F0EEE8", command=lambda: self._edit_product(p)).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Eliminar", width=70, height=28, fg_color="transparent",
                      text_color=RED, hover_color="#F7E9E9",
                      command=lambda: self._delete_product(p)).pack(side="left", padx=4)

    def _new_product(self):
        ProductModal(self.app, lambda p: self.refresh(), self.suppliers)

    def _edit_product(self, p):
        ProductModal(self.app, lambda p2: self.refresh(), self.suppliers, existing=p)

    def _restock(self, p):
        RestockModal(self.app, p, self.refresh)

    def _delete_product(self, p):
        if not messagebox.askyesno("Eliminar producto", f'¿Eliminar "{p["name"]}"? Esta acción no se puede deshacer.'):
            return
        try:
            db.delete_product(self.app.server, p["id"])
            self.refresh()
        except db.DBError as e:
            messagebox.showerror("No se pudo eliminar", str(e))
