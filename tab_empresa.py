import io
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image as PILImage

import db
from theme import (INK, INK_SOFT, BRASS, LINE, FONT_HEAD, FONT_HEAD_SM, FONT_BODY, FONT_BODY_SM,
                    labeled_entry, show_error_border, is_valid_email)

MAX_LOGO_DIM = 500  # px — un logo no necesita más resolución que esta para una factura


class EmpresaTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.logo_bytes = None
        self.logo_mime = None
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Mi empresa", font=FONT_HEAD, text_color=INK, anchor="w").pack(fill="x")
        ctk.CTkLabel(self, text="Esta información aparece en el encabezado de cada factura generada.",
                     font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x", pady=(2, 16))

        card = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color=LINE, corner_radius=8)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=22, pady=20)

        row1 = ctk.CTkFrame(inner, fg_color="transparent"); row1.pack(fill="x")
        row1.grid_columnconfigure((0, 1), weight=1)
        f1 = ctk.CTkFrame(row1, fg_color="transparent"); f1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        f2 = ctk.CTkFrame(row1, fg_color="transparent"); f2.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.e_name, self.err_name = labeled_entry(f1, "Nombre del negocio", "Mi Empresa S.A.S.")
        self.e_tax, _ = labeled_entry(f2, "NIT / identificación fiscal", "900.123.456-7")

        self.e_addr, _ = labeled_entry(inner, "Dirección", "Calle 10 # 5-20, Barranquilla")

        row2 = ctk.CTkFrame(inner, fg_color="transparent"); row2.pack(fill="x")
        row2.grid_columnconfigure((0, 1), weight=1)
        f3 = ctk.CTkFrame(row2, fg_color="transparent"); f3.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        f4 = ctk.CTkFrame(row2, fg_color="transparent"); f4.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.e_phone, _ = labeled_entry(f3, "Teléfono", "+57 300 000 0000")
        self.e_email, self.err_email = labeled_entry(f4, "Correo", "contacto@miempresa.com")

        self.e_web, _ = labeled_entry(inner, "Sitio web (opcional)", "www.miempresa.com")

        row3 = ctk.CTkFrame(inner, fg_color="transparent"); row3.pack(fill="x")
        row3.grid_columnconfigure((0, 1, 2), weight=1)
        f5 = ctk.CTkFrame(row3, fg_color="transparent"); f5.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        f6 = ctk.CTkFrame(row3, fg_color="transparent"); f6.grid(row=0, column=1, sticky="ew", padx=6)
        f7 = ctk.CTkFrame(row3, fg_color="transparent"); f7.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        self.e_cur, self.err_cur = labeled_entry(f5, "Símbolo de moneda", "$")
        self.e_taxlabel, _ = labeled_entry(f6, "Nombre del impuesto", "IVA")
        self.e_taxrate, self.err_taxrate = labeled_entry(f7, "Tarifa por defecto (%)", "19")

        ctk.CTkLabel(inner, text="Nota de pie de factura", font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x", pady=(6, 3))
        self.t_footer = ctk.CTkTextbox(inner, height=60, font=FONT_BODY)
        self.t_footer.pack(fill="x")

        # --- logo ---
        ctk.CTkLabel(inner, text="Logo", font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x", pady=(16, 4))
        logo_row = ctk.CTkFrame(inner, fg_color="transparent")
        logo_row.pack(fill="x")
        self.logo_preview = ctk.CTkLabel(logo_row, text="(sin logo)", width=140, height=60,
                                          fg_color=LINE, corner_radius=6, text_color=INK_SOFT, font=FONT_BODY_SM)
        self.logo_preview.pack(side="left")
        logo_btns = ctk.CTkFrame(logo_row, fg_color="transparent")
        logo_btns.pack(side="left", padx=14)
        ctk.CTkButton(logo_btns, text="Subir / cambiar logo", command=self._pick_logo,
                       fg_color=BRASS, hover_color="#7C5F2C", text_color="#211804").pack(anchor="w")
        ctk.CTkLabel(logo_btns, text="Se reescala automáticamente; cualquier resolución sirve.",
                     font=FONT_BODY_SM, text_color=INK_SOFT).pack(anchor="w", pady=(4, 0))
        self.err_logo = ctk.CTkLabel(inner, text="", text_color="#A23B3B", font=FONT_BODY_SM, anchor="w")
        self.err_logo.pack(fill="x")

        ctk.CTkButton(inner, text="Guardar información", command=self._save,
                       fg_color=INK, hover_color="#233650", height=38).pack(anchor="w", pady=(18, 0))

        # --- copia de seguridad ---
        bcard = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color=LINE, corner_radius=8)
        bcard.pack(fill="x", pady=(14, 0))
        binner = ctk.CTkFrame(bcard, fg_color="transparent")
        binner.pack(fill="x", padx=22, pady=16)
        ctk.CTkLabel(binner, text="Copia de seguridad", font=FONT_HEAD_SM, text_color=INK, anchor="w").pack(fill="x")
        ctk.CTkLabel(binner, anchor="w", justify="left", wraplength=700, font=FONT_BODY_SM, text_color=INK_SOFT,
                     text=("El servidor guarda una copia automática cada día. Además, descarga una copia a este "
                           "computador (o a Google Drive) de vez en cuando: si algo le pasa al servidor, con ese "
                           "archivo se recupera todo.")).pack(fill="x", pady=(2, 8))
        ctk.CTkButton(binner, text="Descargar copia ahora", command=self._download_backup,
                      fg_color=BRASS, hover_color="#7C5F2C", text_color="#211804").pack(anchor="w")

    # ---------- data ----------
    def refresh(self):
        try:
            company = db.get_company(self.app.server)
        except db.DBError as e:
            messagebox.showerror("No se pudo cargar la información", str(e))
            return
        self.e_name.delete(0, "end"); self.e_name.insert(0, company.get("name") or "")
        self.e_tax.delete(0, "end"); self.e_tax.insert(0, company.get("tax_id") or "")
        self.e_addr.delete(0, "end"); self.e_addr.insert(0, company.get("address") or "")
        self.e_phone.delete(0, "end"); self.e_phone.insert(0, company.get("phone") or "")
        self.e_email.delete(0, "end"); self.e_email.insert(0, company.get("email") or "")
        self.e_web.delete(0, "end"); self.e_web.insert(0, company.get("website") or "")
        self.e_cur.delete(0, "end"); self.e_cur.insert(0, company.get("currency") or "$")
        self.e_taxlabel.delete(0, "end"); self.e_taxlabel.insert(0, company.get("tax_label") or "IVA")
        self.e_taxrate.delete(0, "end"); self.e_taxrate.insert(0, str(company.get("tax_rate") if company.get("tax_rate") is not None else 19))
        self.t_footer.delete("1.0", "end"); self.t_footer.insert("1.0", company.get("footer_note") or "")
        self.logo_bytes = company.get("logo_blob")
        self.logo_mime = company.get("logo_mime")
        self._render_logo_preview()

    def _render_logo_preview(self):
        if not self.logo_bytes:
            self.logo_preview.configure(image=None, text="(sin logo)")
            return
        try:
            pil_img = PILImage.open(io.BytesIO(self.logo_bytes))
            pil_img.thumbnail((130, 55))
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            self.logo_preview.configure(image=ctk_img, text="")
            self.logo_preview.image = ctk_img
        except Exception:
            self.logo_preview.configure(image=None, text="(no se pudo mostrar)")

    def _pick_logo(self):
        self.err_logo.configure(text="")
        path = filedialog.askopenfilename(
            title="Selecciona el logo",
            filetypes=[("Imágenes PNG o JPG", "*.png *.jpg *.jpeg")],
        )
        if not path:
            return
        try:
            pil_img = PILImage.open(path)
            pil_img.load()
        except Exception:
            self.err_logo.configure(text="No se pudo abrir el archivo como imagen. Prueba con otro PNG o JPG.")
            return

        fmt = (pil_img.format or "").upper()
        if fmt not in ("PNG", "JPEG", "JPG"):
            self.err_logo.configure(text=f'El archivo es de tipo "{fmt or "desconocido"}". Solo se aceptan PNG o JPG.')
            return

        # Redimensiona: un logo no necesita más resolución que esto para una factura,
        # y así el archivo compartido no crece innecesariamente.
        w, h = pil_img.size
        scale = min(1.0, MAX_LOGO_DIM / max(w, h))
        if scale < 1.0:
            pil_img = pil_img.resize((max(1, int(w * scale)), max(1, int(h * scale))), PILImage.LANCZOS)

        buf = io.BytesIO()
        if pil_img.mode in ("RGBA", "LA") or fmt == "PNG":
            pil_img.save(buf, format="PNG")
            mime = "image/png"
        else:
            pil_img.convert("RGB").save(buf, format="JPEG", quality=90)
            mime = "image/jpeg"

        self.logo_bytes = buf.getvalue()
        self.logo_mime = mime
        self._render_logo_preview()
        try:
            db.save_logo(self.app.server, self.logo_bytes, self.logo_mime)
            self.app.show_toast("Logo guardado.")
        except db.DBError as e:
            self.err_logo.configure(text=f"El logo se procesó pero no se pudo guardar: {e}")

    def _download_backup(self):
        import datetime
        out = filedialog.asksaveasfilename(
            title="Guardar copia de seguridad", defaultextension=".db",
            initialfile=f"facturador-copia-{datetime.date.today():%Y-%m-%d}.db",
            filetypes=[("Copia de Facturador", "*.db")])
        if not out:
            return
        try:
            data = db.download_backup(self.app.server)
            with open(out, "wb") as f:
                f.write(data)
            self.app.show_toast("Copia de seguridad guardada.")
        except (db.DBError, OSError) as e:
            messagebox.showerror("No se pudo descargar la copia", str(e))

    # ---------- validation + save ----------
    def _save(self):
        self.err_name.clear(); self.err_email.clear(); self.err_cur.clear(); self.err_taxrate.clear()
        for e in (self.e_name, self.e_email, self.e_cur, self.e_taxrate):
            show_error_border(e, False)

        name = self.e_name.get().strip()
        email = self.e_email.get().strip()
        currency = self.e_cur.get().strip()
        taxrate_raw = self.e_taxrate.get().strip()

        ok = True
        if not name:
            self.err_name.set("Escribe el nombre de tu negocio: aparece en el encabezado de cada factura y no puede quedar vacío.")
            show_error_border(self.e_name, True)
            ok = False
        if not is_valid_email(email):
            self.err_email.set(f'"{email}" no parece un correo válido. Debe tener el formato nombre@dominio.com.')
            show_error_border(self.e_email, True)
            ok = False
        if not currency:
            self.err_cur.set("Indica un símbolo de moneda (ej. $, USD, €) para mostrar los montos correctamente.")
            show_error_border(self.e_cur, True)
            ok = False
        try:
            taxrate = float(taxrate_raw) if taxrate_raw else 0.0
            if not (0 <= taxrate <= 100):
                raise ValueError
        except ValueError:
            self.err_taxrate.set("La tarifa debe ser un número entre 0 y 100 (por ejemplo, 19 para 19%).")
            show_error_border(self.e_taxrate, True)
            ok = False

        if not ok:
            self.app.show_toast("Corrige los campos marcados en rojo para poder guardar.", error=True)
            return

        data = {
            "name": name, "tax_id": self.e_tax.get().strip(), "address": self.e_addr.get().strip(),
            "phone": self.e_phone.get().strip(), "email": email, "website": self.e_web.get().strip(),
            "currency": currency, "tax_label": self.e_taxlabel.get().strip() or "IVA",
            "tax_rate": taxrate, "footer_note": self.t_footer.get("1.0", "end").strip(),
        }
        try:
            db.save_company(self.app.server, data)
            self.app.show_toast("Información de la empresa guardada.")
        except db.DBError as e:
            messagebox.showerror("No se pudo guardar", str(e))
