"""
Punto de entrada. Pide entrar con usuario y contraseña (o con la clave
maestra, si es el dueño) la primera vez en cada equipo o cuando la sesión
vence. La sesión queda guardada en este equipo hasta que se cierre.
"""
import sys
from typing import Optional

import customtkinter as ctk

import config
import db
from login import LoginForm


def run_login_window(message="") -> Optional[tuple]:
    win = ctk.CTk()
    win.title("Entrar a Facturador")
    win.geometry("560x520")
    win.resizable(False, False)
    result = {}

    pad = ctk.CTkFrame(win, fg_color="transparent")
    pad.pack(fill="both", expand=True, padx=28, pady=22)
    ctk.CTkLabel(pad, text="Bienvenido a Facturador", font=("Georgia", 20, "bold")).pack(anchor="w")
    ctk.CTkLabel(pad, justify="left", wraplength=500, anchor="w",
                 text="Entra con el usuario y la contraseña que te dio el administrador.").pack(anchor="w", pady=(6, 14))

    cfg = config.get_server()

    def done(server, user):
        result["value"] = (server, user)
        win.destroy()

    LoginForm(pad, done, initial_url=cfg.base_url if cfg else "", initial_user=config.last_username(),
              message=message).pack(fill="x")
    win.mainloop()
    return result.get("value")


def main():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    server, user, message = config.get_server(), None, ""
    if server and server.base_url and (server.token or server.api_key):
        try:
            user = db.me(server)
        except db.SessionExpired as e:
            message = str(e)
        except db.DBError as e:
            message = str(e)
    if not user:
        logged = run_login_window(message)
        if not logged:
            sys.exit(0)
        server, user = logged

    from app import App
    app = App(server, user)
    app.mainloop()


if __name__ == "__main__":
    main()
