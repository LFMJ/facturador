import webbrowser
from tkinter import messagebox

import customtkinter as ctk

import config
import db
from db import Server
from theme import INK, INK_SOFT, BRASS, RED, LINE, FONT_BODY_SM, labeled_entry
from login import LoginForm
from tab_resumen import ResumenTab
from tab_empresa import EmpresaTab
from tab_clientes import ClientesTab
from tab_proveedores import ProveedoresTab
from tab_productos import ProductosTab
from tab_factura import FacturaTab
from tab_historial import HistorialTab

# (clave, etiqueta, clase, solo administrador)
TABS = [
    ("resumen", "Resumen", ResumenTab, True),
    ("nueva", "Nueva factura", FacturaTab, False),
    ("historial", "Historial", HistorialTab, False),
    ("productos", "Productos", ProductosTab, False),
    ("clientes", "Clientes", ClientesTab, False),
    ("proveedores", "Proveedores", ProveedoresTab, True),
    ("empresa", "Mi empresa", EmpresaTab, True),
]


class SwitchUserDialog(ctk.CTkToplevel):
    """Permite, sin salir de la app, entrar con otro usuario u otro servidor."""
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Cambiar servidor o usuario")
        self.geometry("500x480")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=22, pady=20)
        ctk.CTkLabel(pad, text="Cambiar servidor o usuario", font=("Georgia", 16, "bold"),
                     text_color=INK, anchor="w").pack(fill="x", pady=(0, 12))
        LoginForm(pad, self._done, initial_url=app.server.base_url,
                  initial_user=config.last_username()).pack(fill="x")

    def _done(self, server, user):
        old = self.app.server
        self.destroy()
        if old.token and old.token != server.token:
            try:
                db.logout(old)
            except db.DBError:
                pass
        self.app.restart_with(server, user)


class ChangePasswordDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Cambiar mi contraseña")
        self.geometry("420x400")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=20, pady=20)
        self.e_cur, _ = labeled_entry(pad, "Contraseña actual")
        self.e_new, _ = labeled_entry(pad, "Contraseña nueva (mínimo 6 caracteres)")
        self.e_rep, _ = labeled_entry(pad, "Repite la contraseña nueva")
        for e in (self.e_cur, self.e_new, self.e_rep):
            e.configure(show="•")
        self.status = ctk.CTkLabel(pad, text="", text_color=RED, font=FONT_BODY_SM, anchor="w", wraplength=360, justify="left")
        self.status.pack(fill="x", pady=(4, 8))
        ctk.CTkButton(pad, text="Cambiar contraseña", command=self._save, fg_color=INK,
                      hover_color="#233650").pack(anchor="w")

    def _save(self):
        new = self.e_new.get()
        if len(new) < 6:
            self.status.configure(text="La contraseña nueva debe tener al menos 6 caracteres.")
            return
        if new != self.e_rep.get():
            self.status.configure(text="Las contraseñas nuevas no coinciden.")
            return
        try:
            db.change_password(self.app.server, self.e_cur.get(), new)
        except db.DBError as e:
            self.status.configure(text=str(e))
            return
        self.app.show_toast("Contraseña cambiada. Se cerró tu sesión en otros dispositivos.")
        self.destroy()


class App(ctk.CTk):
    def __init__(self, server: Server, user: dict):
        super().__init__()
        self.title("Facturador")
        self.geometry("1180x760")
        self.minsize(920, 620)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_content_area()
        self._build_toast()
        self.sidebar = None
        self.restart_with(server, user)

    @property
    def is_admin(self):
        return self.user.get("role") == "admin"

    def restart_with(self, server: Server, user: dict):
        """(Re)construye la ventana para el usuario actual: las pestañas dependen de su rol."""
        self.server = server
        self.user = user
        if self.sidebar:
            self.sidebar.destroy()
        for frame in getattr(self, "frames", {}).values():
            frame.destroy()
        self.tabs = [t for t in TABS if self.is_admin or not t[3]]
        self._build_sidebar()
        self.frames = {key: cls(self.content_container, self) for key, _label, cls, _adm in self.tabs}
        self.current_tab = None
        self.go_to(self.tabs[0][0])

    # ---------- layout ----------
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=210, fg_color=INK, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        self.sidebar = sidebar

        ctk.CTkLabel(sidebar, text="Facturador", font=("Georgia", 19, "bold"),
                     text_color="#FBF8F1").pack(anchor="w", padx=20, pady=(26, 2))
        role = "Administrador" if self.is_admin else "Vendedor"
        ctk.CTkLabel(sidebar, text=f'{self.user.get("name", "")}\n{role}', font=("Segoe UI", 11), justify="left",
                     text_color=BRASS, anchor="w", wraplength=180).pack(anchor="w", padx=20, pady=(0, 18))

        self.nav_buttons = {}
        for key, label, _cls, _adm in self.tabs:
            btn = ctk.CTkButton(
                sidebar, text=label, anchor="w", fg_color="transparent",
                text_color="#CFCABA", hover_color="#233650", font=FONT_BODY_SM,
                height=38, command=lambda k=key: self.go_to(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = btn

        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        small = dict(anchor="w", fg_color="transparent", text_color=BRASS, hover_color="#233650",
                     font=FONT_BODY_SM, height=32)
        if self.is_admin:
            ctk.CTkButton(sidebar, text="👥  Usuarios (en la web)", command=self._open_users_web,
                          **small).pack(fill="x", padx=10, pady=1)
        if not self.user.get("master"):
            ctk.CTkButton(sidebar, text="🔑  Cambiar mi contraseña", command=lambda: ChangePasswordDialog(self),
                          **small).pack(fill="x", padx=10, pady=1)
        ctk.CTkButton(sidebar, text="⚙  Cambiar servidor o usuario", command=lambda: SwitchUserDialog(self),
                      **small).pack(fill="x", padx=10, pady=1)
        ctk.CTkButton(sidebar, text="⎋  Cerrar sesión", command=self._logout,
                      **small).pack(fill="x", padx=10, pady=(1, 16))

    def _build_content_area(self):
        self.content_container = ctk.CTkFrame(self, fg_color="#FDFCFA", corner_radius=0)
        self.content_container.grid(row=0, column=1, sticky="nsew")
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

    def _build_toast(self):
        self.toast = ctk.CTkLabel(self, text="", font=FONT_BODY_SM, text_color="#F8F6F0",
                                   fg_color=INK, corner_radius=6, height=36)

    def _open_users_web(self):
        messagebox.showinfo(
            "Usuarios",
            "Los usuarios se administran desde la versión web, en la pestaña \"Usuarios\".\n\n"
            "Se abrirá en tu navegador; entra con tu usuario de administrador.")
        webbrowser.open(self.server.base_url)

    def _logout(self):
        if not messagebox.askyesno("Cerrar sesión", "¿Cerrar la sesión en este equipo?"):
            return
        try:
            db.logout(self.server)
        except db.DBError:
            pass
        config.forget_session()
        self.destroy()

    # ---------- navegación ----------
    def go_to(self, key):
        for k, btn in self.nav_buttons.items():
            btn.configure(fg_color=("#EDE9DE" if k == key else "transparent"),
                           text_color=(INK if k == key else "#CFCABA"))
        for k, frame in self.frames.items():
            if k != key:
                frame.grid_remove()
        self.current_tab = key
        self.frames[key].grid(row=0, column=0, sticky="nsew", padx=28, pady=20)
        self.frames[key].refresh()

    # ---------- toast ----------
    def show_toast(self, msg, error=False):
        self.toast.configure(text=msg, fg_color=RED if error else INK)
        self.toast.place(relx=0.98, rely=0.97, anchor="se")
        self.toast.lift()
        self.after(3200, self.toast.place_forget)
