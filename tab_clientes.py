from tkinter import messagebox
import customtkinter as ctk

import db
from theme import (INK, INK_SOFT, BRASS, LINE, RED, FONT_HEAD, FONT_HEAD_SM, FONT_BODY_SM,
                    labeled_entry, show_error_border, is_valid_email)


class ClientModal(ctk.CTkToplevel):
    """Ventana emergente para crear/editar un cliente. on_saved(client_dict) se
    llama tras guardar exitosamente."""
    def __init__(self, app, on_saved, existing=None):
        super().__init__(app)
        self.app = app
        self.on_saved = on_saved
        self.existing = existing
        self.title("Editar cliente" if existing else "Nuevo cliente")
        self.geometry("420x480")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        self._build()

    def _build(self):
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=20, pady=20)
        ex = self.existing or {}
        self.e_name, self.err_name = labeled_entry(pad, "Nombre")
        self.e_doc, _ = labeled_entry(pad, "Documento / NIT")
        self.e_addr, _ = labeled_entry(pad, "Dirección")
        self.e_phone, _ = labeled_entry(pad, "Teléfono")
        self.e_email, self.err_email = labeled_entry(pad, "Correo")
        self.e_name.insert(0, ex.get("name", ""))
        self.e_doc.insert(0, ex.get("doc", ""))
        self.e_addr.insert(0, ex.get("address", ""))
        self.e_phone.insert(0, ex.get("phone", ""))
        self.e_email.insert(0, ex.get("email", ""))

        btn_row = ctk.CTkFrame(pad, fg_color="transparent")
        btn_row.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(btn_row, text="Guardar", command=self._save, fg_color=INK,
                       hover_color="#233650").pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="Cancelar", command=self.destroy, fg_color="transparent",
                       border_width=1, border_color=LINE, text_color=INK_SOFT,
                       hover_color="#F0EEE8").pack(side="left")

    def read_valid_client(self):
        """Valida los campos del formulario; devuelve el dict del cliente si es
        válido, o None tras mostrar los errores explicativos correspondientes."""
        self.err_name.clear(); self.err_email.clear()
        show_error_border(self.e_name, False); show_error_border(self.e_email, False)
        name = self.e_name.get().strip()
        email = self.e_email.get().strip()
        ok = True
        if not name:
            self.err_name.set("Escribe el nombre del cliente: lo necesitas para identificarlo en la factura.")
            show_error_border(self.e_name, True)
            ok = False
        if not is_valid_email(email):
            self.err_email.set(f'"{email}" no parece un correo válido. Debe tener el formato nombre@dominio.com.')
            show_error_border(self.e_email, True)
            ok = False
        if not ok:
            return None
        return {
            "id": (self.existing or {}).get("id"),
            "name": name, "doc": self.e_doc.get().strip(), "address": self.e_addr.get().strip(),
            "phone": self.e_phone.get().strip(), "email": email,
        }

    def _save(self):
        client = self.read_valid_client()
        if client is None:
            return
        try:
            client_id = db.save_client(self.app.server, client)
            client["id"] = client_id
            self.app.show_toast("Cliente guardado.")
            self.on_saved(client)
            self.destroy()
        except db.DBError as e:
            messagebox.showerror("No se pudo guardar", str(e))


class ClientesTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x")
        left = ctk.CTkFrame(head, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text="Clientes", font=FONT_HEAD, text_color=INK, anchor="w").pack(fill="x")
        ctk.CTkLabel(left, text="Guarda los datos de tus clientes para usarlos al facturar.",
                     font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        ctk.CTkButton(head, text="+ Nuevo cliente", command=self._new_client,
                       fg_color=BRASS, hover_color="#7C5F2C", text_color="#211804").pack(side="right")

        self.list_card = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color=LINE, corner_radius=8)
        self.list_card.pack(fill="both", expand=True, pady=(16, 0))

    def refresh(self):
        for w in self.list_card.winfo_children():
            w.destroy()
        try:
            clients = db.list_clients(self.app.server)
        except db.DBError as e:
            ctk.CTkLabel(self.list_card, text=str(e), text_color=RED, wraplength=500,
                         justify="left").pack(padx=20, pady=20, anchor="w")
            return
        if not clients:
            ctk.CTkLabel(self.list_card, text="Aún no tienes clientes. Añade el primero para empezar a facturar.",
                         text_color=INK_SOFT, font=FONT_BODY_SM).pack(padx=20, pady=30)
            return
        for c in clients:
            self._render_row(c)

    def _render_row(self, c):
        row = ctk.CTkFrame(self.list_card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=8)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=c["name"], font=FONT_HEAD_SM, text_color=INK, anchor="w").pack(fill="x")
        meta = " · ".join([x for x in [c.get("doc"), c.get("email")] if x])
        if meta:
            ctk.CTkLabel(info, text=meta, font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.pack(side="right")
        ctk.CTkButton(btns, text="Editar", width=70, height=28, fg_color="transparent",
                       border_width=1, border_color="#E1DFD8", text_color=INK_SOFT,
                       hover_color="#F0EEE8", command=lambda: self._edit_client(c)).pack(side="left", padx=4)
        if self.app.is_admin:
            ctk.CTkButton(btns, text="Eliminar", width=70, height=28, fg_color="transparent",
                           text_color=RED, hover_color="#F7E9E9",
                           command=lambda: self._delete_client(c)).pack(side="left", padx=4)

    def _new_client(self, on_saved=None):
        ClientModal(self.app, on_saved or (lambda c: self.refresh()))

    def _edit_client(self, c):
        ClientModal(self.app, lambda c2: self.refresh(), existing=c)

    def _delete_client(self, c):
        if not messagebox.askyesno("Eliminar cliente", f'¿Eliminar a "{c["name"]}"? Esta acción no se puede deshacer.'):
            return
        try:
            db.delete_client(self.app.server, c["id"])
            self.refresh()
        except db.DBError as e:
            messagebox.showerror("No se pudo eliminar", str(e))
