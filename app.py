import customtkinter as ctk

import config
import db
from db import Server
from theme import INK, BRASS, RED, FONT_BODY_SM
from tab_empresa import EmpresaTab
from tab_clientes import ClientesTab
from tab_proveedores import ProveedoresTab
from tab_productos import ProductosTab
from tab_factura import FacturaTab
from tab_historial import HistorialTab

TABS = [
    ("empresa", "Mi empresa", EmpresaTab),
    ("clientes", "Clientes", ClientesTab),
    ("proveedores", "Proveedores", ProveedoresTab),
    ("productos", "Productos", ProductosTab),
    ("nueva", "Nueva factura", FacturaTab),
    ("historial", "Historial", HistorialTab),
]


class ChangeServerDialog(ctk.CTkToplevel):
    """Permite, sin salir de la app, apuntar a otro servidor/clave."""
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Cambiar servidor")
        self.geometry("480x320")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        self._build()

    def _build(self):
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=22, pady=20)
        ctk.CTkLabel(pad, text="Cambiar servidor", font=("Georgia", 16, "bold"),
                     text_color=INK, anchor="w").pack(fill="x")
        ctk.CTkLabel(pad, text=f"Servidor actual:\n{self.app.server.base_url}", font=FONT_BODY_SM,
                     text_color="#3C4A5E", anchor="w", justify="left", wraplength=420).pack(fill="x", pady=(6, 16))

        ctk.CTkLabel(pad, text="Nueva URL del servidor", font=FONT_BODY_SM, anchor="w").pack(fill="x")
        self.e_url = ctk.CTkEntry(pad, height=34)
        self.e_url.insert(0, self.app.server.base_url)
        self.e_url.pack(fill="x", pady=(3, 10))

        ctk.CTkLabel(pad, text="Clave de API", font=FONT_BODY_SM, anchor="w").pack(fill="x")
        self.e_key = ctk.CTkEntry(pad, height=34, show="•")
        self.e_key.insert(0, self.app.server.api_key)
        self.e_key.pack(fill="x", pady=(3, 10))

        self.status = ctk.CTkLabel(pad, text="", font=FONT_BODY_SM, anchor="w", justify="left", wraplength=420)
        self.status.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(pad, text="Probar conexión y guardar", command=self._test_and_save,
                      fg_color=INK, hover_color="#233650", height=38).pack(anchor="w")

    def _test_and_save(self):
        url = self.e_url.get().strip()
        key = self.e_key.get().strip()
        if not url or not key:
            self.status.configure(text="Completa la URL y la clave.", text_color=RED)
            return
        new_server = Server(base_url=url, api_key=key)
        self.status.configure(text="Probando conexión…", text_color="#3C4A5E")
        self.update()
        try:
            db.test_connection(new_server)
        except db.DBError as e:
            self.status.configure(text=str(e), text_color=RED)
            return
        config.save_config(url, key)
        self.app.server = new_server
        self.app.show_toast("Servidor actualizado.")
        self.app.frames[self.app.current_tab].refresh()
        self.destroy()


class App(ctk.CTk):
    def __init__(self, server: Server):
        super().__init__()
        self.server = server
        self.title("Facturador")
        self.geometry("1180x760")
        self.minsize(920, 620)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content_area()
        self._build_toast()

        self.frames = {}
        for key, label, cls in TABS:
            self.frames[key] = cls(self.content_container, self)

        self.current_tab = None
        self.go_to("empresa")

    # ---------- layout ----------
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=200, fg_color=INK, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text="Facturador", font=("Georgia", 19, "bold"),
                     text_color="#FBF8F1").pack(anchor="w", padx=20, pady=(26, 4))
        ctk.CTkLabel(sidebar, text="PDF · en la nube", font=("Consolas", 10),
                     text_color=BRASS).pack(anchor="w", padx=20, pady=(0, 20))

        self.nav_buttons = {}
        for key, label, _cls in TABS:
            btn = ctk.CTkButton(
                sidebar, text=label, anchor="w", fg_color="transparent",
                text_color="#CFCABA", hover_color="#233650", font=FONT_BODY_SM,
                height=38, command=lambda k=key: self.go_to(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = btn

        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        ctk.CTkButton(
            sidebar, text="⚙  Cambiar servidor", anchor="w", fg_color="transparent",
            text_color=BRASS, hover_color="#233650", font=FONT_BODY_SM, height=34,
            command=lambda: ChangeServerDialog(self),
        ).pack(fill="x", padx=10, pady=(2, 16))

    def _build_content_area(self):
        self.content_container = ctk.CTkFrame(self, fg_color="#FDFCFA", corner_radius=0)
        self.content_container.grid(row=0, column=1, sticky="nsew")
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

    def _build_toast(self):
        self.toast = ctk.CTkLabel(self, text="", font=FONT_BODY_SM, text_color="#F8F6F0",
                                   fg_color=INK, corner_radius=6, height=36)

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
        self.after(2800, self.toast.place_forget)
