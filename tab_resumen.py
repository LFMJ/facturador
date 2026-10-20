import datetime
import time

import customtkinter as ctk

import db
from pdf_gen import fmt_money
from theme import INK, INK_SOFT, LINE, RED, FONT_HEAD, FONT_HEAD_SM, FONT_BODY_SM, FONT_MONO

PRESETS = ["Hoy", "7 días", "30 días", "Este mes", "Mes pasado", "Este año"]
METHOD_LABEL = {"efectivo": "Efectivo", "transferencia": "Transferencia", "tarjeta": "Tarjeta", "otro": "Otro"}


def preset_range(name):
    """(inicio, fin) en hora local del equipo para cada período."""
    today = datetime.datetime.combine(datetime.date.today(), datetime.time())
    day = datetime.timedelta(days=1)
    if name == "Hoy":
        return today, today + day
    if name == "7 días":
        return today - 6 * day, today + day
    if name == "30 días":
        return today - 29 * day, today + day
    first = today.replace(day=1)
    next_month = (first + 32 * day).replace(day=1)
    if name == "Este mes":
        return first, next_month
    if name == "Mes pasado":
        return (first - day).replace(day=1), first
    return today.replace(month=1, day=1), today.replace(year=today.year + 1, month=1, day=1)


def local_utc_offset_minutes():
    """Igual que getTimezoneOffset() de JavaScript: minutos que hay que sumar a la hora local para llegar a UTC."""
    offset = datetime.datetime.now().astimezone().utcoffset()
    return int(-offset.total_seconds() // 60)


class ResumenTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.preset = "30 días"
        self._build()

    def _build(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="Resumen de ventas", font=FONT_HEAD, text_color=INK, anchor="w").pack(side="left")
        self.seg = ctk.CTkSegmentedButton(head, values=PRESETS, command=self._on_preset)
        self.seg.set(self.preset)
        self.seg.pack(side="right")
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, pady=(14, 0))

    def _on_preset(self, value):
        self.preset = value
        self.refresh()

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()
        start, end = preset_range(self.preset)
        try:
            company = db.get_company(self.app.server)
            d = db.dashboard(self.app.server, time.mktime(start.timetuple()), time.mktime(end.timetuple()),
                             local_utc_offset_minutes())
        except db.DBError as e:
            ctk.CTkLabel(self.body, text=str(e), text_color=RED, wraplength=600, justify="left").pack(anchor="w", pady=20)
            return
        cur = company.get("currency") or "$"
        s = d["summary"]
        margin = round(s["profit"] / s["net"] * 100) if s["net"] > 0 else 0

        tiles = ctk.CTkFrame(self.body, fg_color="transparent")
        tiles.pack(fill="x")
        tiles.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="t")
        methods = " · ".join(METHOD_LABEL.get(m["method"], m["method"]) for m in d["collected"]["by_method"]) or "sin pagos"
        data = [
            (f'Ventas (con {company.get("tax_label") or "impuesto"})', fmt_money(s["total"], cur),
             f'{s["count"]} factura{"" if s["count"] == 1 else "s"}'),
            ("Ganancia estimada", fmt_money(s["profit"], cur), f"{margin}% sobre ventas sin impuesto"),
            ("Cobrado en el período", fmt_money(d["collected"]["total"], cur), methods),
            ("Por cobrar (total)", fmt_money(d["receivables"]["total"], cur),
             f'{d["receivables"]["count"]} factura(s) con saldo'),
        ]
        for col, (k, v, sub) in enumerate(data):
            t = ctk.CTkFrame(tiles, fg_color="white", border_width=1, border_color=LINE, corner_radius=8)
            t.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 6, 0))
            ctk.CTkLabel(t, text=k, font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x", padx=14, pady=(10, 0))
            ctk.CTkLabel(t, text=v, font=("Consolas", 18, "bold"), text_color=INK, anchor="w").pack(fill="x", padx=14)
            ctk.CTkLabel(t, text=sub, font=("Segoe UI", 10), text_color=INK_SOFT, anchor="w",
                         wraplength=200, justify="left").pack(fill="x", padx=14, pady=(0, 10))

        if s["items_without_cost"]:
            ctk.CTkLabel(self.body, text=(f'{s["items_without_cost"]} artículo(s) vendidos no tienen precio de costo, así '
                                          "que la ganancia aparece más alta de lo real. Pon el costo en Productos."),
                         font=FONT_BODY_SM, text_color=INK_SOFT, fg_color="#F5F4F0", corner_radius=6,
                         anchor="w", justify="left", wraplength=800).pack(fill="x", pady=(10, 0), ipadx=10, ipady=6)

        self._table("Productos más vendidos", ["Producto", "Cant.", "Ventas sin imp."],
                    [(p["name"], f'{p["qty"]:g}', fmt_money(p["net"], cur)) for p in d["top_products"]],
                    "Sin ventas en este período.")
        self._table("Por vendedor", ["Vendedor", "Facturas", "Ventas"],
                    [(x["name"], str(x["count"]), fmt_money(x["total"], cur)) for x in d["by_seller"]],
                    "Sin ventas en este período.")
        self._table("Cuentas por cobrar", ["Factura", "Cliente", "Saldo"],
                    [(f'{r["number"]}  ·  {datetime.datetime.fromtimestamp(r["created_at"]):%d/%m/%Y}',
                      r["client_name"] or "", fmt_money(r["balance"], cur)) for r in d["receivables"]["invoices"]],
                    "Nadie te debe.")
        ctk.CTkLabel(self.body, text="La gráfica de ventas por día está en la versión web (pestaña Resumen).",
                     font=FONT_BODY_SM, text_color=INK_SOFT, anchor="w").pack(fill="x", pady=(12, 0))

    def _table(self, title, headers, rows, empty):
        card = ctk.CTkFrame(self.body, fg_color="white", border_width=1, border_color=LINE, corner_radius=8)
        card.pack(fill="x", pady=(14, 0))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(inner, text=title, font=FONT_HEAD_SM, text_color=INK, anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        if not rows:
            ctk.CTkLabel(inner, text=empty, font=FONT_BODY_SM, text_color=INK_SOFT).grid(row=1, column=0, sticky="w")
            return
        inner.grid_columnconfigure(0, weight=1)
        for c, h in enumerate(headers):
            ctk.CTkLabel(inner, text=h.upper(), font=("Segoe UI", 10, "bold"), text_color=INK_SOFT,
                         anchor="w" if c == 0 else "e").grid(row=1, column=c, sticky="ew", padx=6)
        for r, row in enumerate(rows, start=2):
            for c, val in enumerate(row):
                ctk.CTkLabel(inner, text=val, font=FONT_MONO if c == len(row) - 1 else FONT_BODY_SM, text_color=INK,
                             anchor="w" if c == 0 else "e").grid(row=r, column=c, sticky="ew", padx=6, pady=1)
