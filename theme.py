"""Paleta y helpers de UI compartidos, coherentes con la versión web."""
import re
import customtkinter as ctk

INK = "#16233A"
INK_SOFT = "#3C4A5E"
PAPER = "#FDFCFA"
PANEL = "#F5F4F0"
LINE = "#E1DFD8"
BRASS = "#9C7A3C"
BRASS_DEEP = "#7C5F2C"
RED = "#A23B3B"
GREEN = "#2F6F4E"

FONT_HEAD = ("Georgia", 18, "bold")
FONT_HEAD_SM = ("Georgia", 14, "bold")
FONT_BODY = ("Segoe UI", 13)
FONT_BODY_SM = ("Segoe UI", 11)
FONT_MONO = ("Consolas", 12)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def is_valid_email(v: str) -> bool:
    return not v or bool(EMAIL_RE.match(v))


class FieldError(ctk.CTkLabel):
    """Etiqueta roja de error bajo un campo, oculta hasta que hay algo que mostrar."""
    def __init__(self, parent):
        super().__init__(parent, text="", text_color=RED, font=FONT_BODY_SM,
                          anchor="w", justify="left", wraplength=380)
        self._visible = False

    def set(self, msg: str):
        if msg:
            self.configure(text=msg)
            if not self._visible:
                self.pack(fill="x", pady=(2, 6))
                self._visible = True
        else:
            self.clear()

    def clear(self):
        self.configure(text="")
        if self._visible:
            self.pack_forget()
            self._visible = False


def labeled_entry(parent, label_text, placeholder=""):
    """Crea un bloque label + entry + FieldError, devuelve (entry, field_error)."""
    wrap = ctk.CTkFrame(parent, fg_color="transparent")
    wrap.pack(fill="x", pady=(0, 4))
    ctk.CTkLabel(wrap, text=label_text, font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x")
    entry = ctk.CTkEntry(wrap, placeholder_text=placeholder, font=FONT_BODY, height=34)
    entry.pack(fill="x", pady=(3, 0))
    err = FieldError(wrap)
    return entry, err


def show_error_border(entry: ctk.CTkEntry, has_error: bool):
    entry.configure(border_color=RED if has_error else LINE, border_width=1.4 if has_error else 1)
