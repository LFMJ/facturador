"""Formulario de acceso (usuario + contraseña, o clave maestra del dueño)."""
import customtkinter as ctk

import config
import db
from db import Server
from theme import INK, INK_SOFT, RED


class LoginForm(ctk.CTkFrame):
    """Formulario de acceso reutilizable (ventana inicial y "Cambiar servidor o usuario").
    on_success(server, user) se llama cuando el acceso es válido."""
    def __init__(self, parent, on_success, initial_url="", initial_user="", message=""):
        super().__init__(parent, fg_color="transparent")
        self.on_success = on_success
        self.master_var = ctk.BooleanVar(value=False)

        ctk.CTkLabel(self, text="URL del servidor", font=("Segoe UI", 11), anchor="w").pack(fill="x")
        self.e_url = ctk.CTkEntry(self, placeholder_text="https://tuusuario.pythonanywhere.com", height=34)
        self.e_url.pack(fill="x", pady=(3, 10))
        if initial_url:
            self.e_url.insert(0, initial_url)

        self.user_wrap = ctk.CTkFrame(self, fg_color="transparent")
        self.user_wrap.pack(fill="x")
        ctk.CTkLabel(self.user_wrap, text="Usuario", font=("Segoe UI", 11), anchor="w").pack(fill="x")
        self.e_user = ctk.CTkEntry(self.user_wrap, height=34)
        self.e_user.pack(fill="x", pady=(3, 10))
        if initial_user:
            self.e_user.insert(0, initial_user)

        self.pass_label = ctk.CTkLabel(self, text="Contraseña", font=("Segoe UI", 11), anchor="w")
        self.pass_label.pack(fill="x")
        self.e_pass = ctk.CTkEntry(self, height=34, show="•")
        self.e_pass.pack(fill="x", pady=(3, 6))
        self.e_pass.bind("<Return>", lambda _e: self.submit())

        ctk.CTkCheckBox(self, text="Entrar con la clave maestra (solo el dueño)", variable=self.master_var,
                        command=self._toggle_master, font=("Segoe UI", 11)).pack(anchor="w", pady=(2, 8))

        self.status = ctk.CTkLabel(self, text=message, font=("Segoe UI", 11), anchor="w", justify="left",
                                   wraplength=480, text_color=RED)
        self.status.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(self, text="Entrar", command=self.submit, fg_color=INK, hover_color="#233650",
                      height=38).pack(anchor="w")

    def _toggle_master(self):
        if self.master_var.get():
            self.user_wrap.pack_forget()
            self.pass_label.configure(text="Clave maestra")
        else:
            self.user_wrap.pack(fill="x", before=self.pass_label)
            self.pass_label.configure(text="Contraseña")

    def submit(self):
        url = self.e_url.get().strip().rstrip("/")
        password = self.e_pass.get()
        username = self.e_user.get().strip()
        if not url or not password or (not self.master_var.get() and not username):
            self.status.configure(text="Completa todos los campos para entrar.", text_color=RED)
            return
        self.status.configure(text="Conectando…", text_color=INK_SOFT)
        self.update()
        try:
            if self.master_var.get():
                server = Server(base_url=url, api_key=password.strip())
                user = db.me(server)
            else:
                server, user = db.login(url, username, password)
        except db.DBError as e:
            self.status.configure(text=str(e), text_color=RED)
            return
        config.save_server(server, username if not self.master_var.get() else config.last_username())
        self.on_success(server, user)
