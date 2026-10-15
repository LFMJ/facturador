from tkinter import messagebox
import customtkinter as ctk

import db
from theme import (INK, INK_SOFT, BRASS, LINE, RED, FONT_HEAD, FONT_HEAD_SM, FONT_BODY_SM,
                    labeled_entry, show_error_border, is_valid_email)


class SupplierModal(ctk.CTkToplevel):
    def __init__(self, app, on_saved, existing=None):
        super().__init__(app)
        self.app = app
        self.on_saved = on_saved
        self.existing = existing
        self.title("Editar proveedor" if existing else "Nuevo proveedor")
        self.geometry("400x360")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        self._build()

    def _build(self):
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=20, pady=20)
        ex = self.existing or {}
        self.e_name, self.err_name = labeled_entry(pad, "Nombre del proveedor")
        self.e_contact, _ = labeled_entry(pad, "Persona de contacto")
        self.e_phone, _ = labeled_entry(pad, "Teléfono")
        self.e_email, self.err_email = labeled_entry(pad, "Correo")
        self.e_name.insert(0, ex.get("name", ""))
        self.e_contact.insert(0, ex.get("contact_name", ""))
        self.e_phone.insert(0, ex.get("phone", ""))
        self.e_email.insert(0, ex.get("email", ""))

        btn_row = ctk.CTkFrame(pad, fg_color="transparent")
        btn_row.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(btn_row, text="Guardar", command=self._save, fg_color=INK,
                      hover_color="#233650").pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="Cancelar", command=self.destroy, fg_color="transparent",
                      border_width=1, border_color=LINE, text_color=INK_SOFT,
                      hover_color="#F0EEE8").pack(side="left")

    def _save(self):
        self.err_name.clear(); self.err_email.clear()
        show_error_border(self.e_name, False); show_error_border(self.e_email, False)
        name = self.e_name.get().strip()
        email = self.e_email.get().strip()
        ok = True
        if not name:
            self.err_name.set("Escribe el nombre del proveedor: lo necesitas para ligarlo a tus productos.")
            show_error_border(self.e_name, True)
            ok = False
        if not is_valid_email(email):
            self.err_email.set(f'"{email}" no parece un correo válido. Debe tener el formato nombre@dominio.com.')
            show_error_border(self.e_email, True)
            ok = False
        if not ok:
            return
        supplier = {
            "id": (self.existing or {}).get("id"), "name": name,
            "contact_name": self.e_contact.get().strip(), "phone": self.e_phone.get().strip(), "email": email,
        }
        try:
            sid = db.save_supplier(self.app.server, supplier)
            supplier["id"] = sid
            self.app.show_toast("Proveedor guardado.")
            self.on_saved(supplier)
            self.destroy()
        except db.DBError as e:
            messagebox.showerror("No se pudo guardar", str(e))


class ProveedoresTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x")
        left = ctk.CTkFrame(head, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text="Proveedores", font=FONT_HEAD, text_color=INK, anchor="w").pack(fill="x")
        ctk.CTkLabel(left, text="A quién le compras cada producto que vendes.",
                     font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        ctk.CTkButton(head, text="+ Nuevo proveedor", command=self._new,
                      fg_color=BRASS, hover_color="#7C5F2C", text_color="#211804").pack(side="right")

        self.list_card = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color=LINE, corner_radius=8)
        self.list_card.pack(fill="both", expand=True, pady=(16, 0))

    def refresh(self):
        for w in self.list_card.winfo_children():
            w.destroy()
        try:
            suppliers = db.list_suppliers(self.app.server)
        except db.DBError as e:
            ctk.CTkLabel(self.list_card, text=str(e), text_color=RED, wraplength=500,
                         justify="left").pack(padx=20, pady=20, anchor="w")
            return
        if not suppliers:
            ctk.CTkLabel(self.list_card, text="Aún no tienes proveedores. Añade el primero.",
                         text_color=INK_SOFT, font=FONT_BODY_SM).pack(padx=20, pady=30)
            return
        for s in suppliers:
            self._render_row(s)

    def _render_row(self, s):
        row = ctk.CTkFrame(self.list_card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=8)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=s["name"], font=FONT_HEAD_SM, text_color=INK, anchor="w").pack(fill="x")
        meta = " · ".join([x for x in [s.get("contact_name"), s.get("phone"), s.get("email")] if x])
        if meta:
            ctk.CTkLabel(info, text=meta, font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.pack(side="right")
        ctk.CTkButton(btns, text="Editar", width=70, height=28, fg_color="transparent",
                      border_width=1, border_color=LINE, text_color=INK_SOFT,
                      hover_color="#F0EEE8", command=lambda: self._edit(s)).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Eliminar", width=70, height=28, fg_color="transparent",
                      text_color=RED, hover_color="#F7E9E9",
                      command=lambda: self._delete(s)).pack(side="left", padx=4)

    def _new(self):
        SupplierModal(self.app, lambda s: self.refresh())

    def _edit(self, s):
        SupplierModal(self.app, lambda s2: self.refresh(), existing=s)

    def _delete(self, s):
        if not messagebox.askyesno("Eliminar proveedor", f'¿Eliminar a "{s["name"]}"? Los productos que ya le tenías asignado quedarán sin proveedor.'):
            return
        try:
            db.delete_supplier(self.app.server, s["id"])
            self.refresh()
        except db.DBError as e:
            messagebox.showerror("No se pudo eliminar", str(e))
