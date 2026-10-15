"""
Punto de entrada. En el primer uso en un equipo, pide la URL del servidor y
la clave de API, prueba la conexión, y guarda esos datos localmente. En los
siguientes usos arranca directo.
"""
import sys
from typing import Optional
from tkinter import messagebox

import customtkinter as ctk

import config
import db
from db import Server


def run_setup_wizard() -> Optional[Server]:
    wizard = ctk.CTk()
    wizard.title("Configurar Facturador")
    wizard.geometry("560x360")
    wizard.resizable(False, False)
    result = {"server": None}

    pad = ctk.CTkFrame(wizard, fg_color="transparent")
    pad.pack(fill="both", expand=True, padx=28, pady=24)

    ctk.CTkLabel(pad, text="Bienvenido a Facturador", font=("Georgia", 20, "bold")).pack(anchor="w")
    ctk.CTkLabel(
        pad, justify="left", wraplength=500, anchor="w",
        text=("Conéctate al servidor de tu empresa para que todos los equipos vean "
              "los mismos clientes, productos y facturas.\n\n"
              "Pide la URL y la clave de API a quien configuró el servidor."),
    ).pack(anchor="w", pady=(10, 18))

    ctk.CTkLabel(pad, text="URL del servidor", font=("Segoe UI", 11), anchor="w").pack(fill="x")
    e_url = ctk.CTkEntry(pad, placeholder_text="https://tuusuario.pythonanywhere.com", height=34)
    e_url.pack(fill="x", pady=(3, 12))

    ctk.CTkLabel(pad, text="Clave de API", font=("Segoe UI", 11), anchor="w").pack(fill="x")
    e_key = ctk.CTkEntry(pad, placeholder_text="La clave que te dieron", height=34, show="•")
    e_key.pack(fill="x", pady=(3, 6))

    status = ctk.CTkLabel(pad, text="", font=("Segoe UI", 11), anchor="w")
    status.pack(fill="x", pady=(0, 10))

    def test_and_save():
        url = e_url.get().strip()
        key = e_key.get().strip()
        if not url or not key:
            status.configure(text="Completa la URL y la clave antes de continuar.", text_color="#A23B3B")
            return
        server = Server(base_url=url, api_key=key)
        status.configure(text="Probando conexión…", text_color="#3C4A5E")
        wizard.update()
        try:
            db.test_connection(server)
        except db.DBError as e:
            status.configure(text=str(e), text_color="#A23B3B")
            return
        result["server"] = server
        wizard.destroy()

    ctk.CTkButton(pad, text="Probar conexión y continuar", command=test_and_save,
                  fg_color="#16233A", hover_color="#233650", height=38).pack(anchor="w")

    wizard.mainloop()
    return result["server"]


def main():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    server = config.get_server()
    if not server or not server.base_url or not server.api_key:
        server = run_setup_wizard()
        if not server:
            sys.exit(0)
        config.save_config(server.base_url, server.api_key)

    from app import App
    app = App(server)
    app.mainloop()


if __name__ == "__main__":
    main()
