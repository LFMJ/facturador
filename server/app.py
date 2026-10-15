"""
API del Facturador. Expone por HTTP las operaciones de empresa, clientes,
proveedores, productos (con inventario) y facturas (con descuento por línea,
vendedor y garantía). El inventario se descuenta automáticamente al facturar
y se restaura si una factura se elimina.

Despliegue gratuito sugerido: PythonAnywhere (ver DEPLOY.md).
"""
import base64
import hmac
import io
import os
import sqlite3
import sys
import time
import uuid
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify, send_file, send_from_directory
from werkzeug.exceptions import HTTPException

# pdf_gen.py puede estar junto a este archivo (en PythonAnywhere) o en la
# carpeta de arriba (al correrlo desde el repositorio).
SERVER_DIR = Path(__file__).parent
for _p in (SERVER_DIR, SERVER_DIR.parent):
    if (_p / "pdf_gen.py").exists() and str(_p) not in sys.path:
        sys.path.append(str(_p))
from pdf_gen import generate_invoice_pdf  # noqa: E402

# -------- configuración --------
API_KEY = os.environ.get("FACTURADOR_API_KEY", "cambia-esta-clave")
DB_PATH = str(SERVER_DIR / "facturador_server.db")
STATIC_DIR = SERVER_DIR / "static"

app = Flask(__name__, static_folder=None)

SCHEMA = """
CREATE TABLE IF NOT EXISTS company (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT DEFAULT '', tax_id TEXT DEFAULT '', address TEXT DEFAULT '',
    phone TEXT DEFAULT '', email TEXT DEFAULT '', website TEXT DEFAULT '',
    currency TEXT DEFAULT '$', tax_label TEXT DEFAULT 'IVA', tax_rate REAL DEFAULT 19,
    footer_note TEXT DEFAULT 'Gracias por su compra.',
    logo_blob BLOB, logo_mime TEXT, invoice_counter INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, doc TEXT DEFAULT '', address TEXT DEFAULT '',
    phone TEXT DEFAULT '', email TEXT DEFAULT '', created_at REAL
);
CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, contact_name TEXT DEFAULT '',
    phone TEXT DEFAULT '', email TEXT DEFAULT '', created_at REAL
);
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, price REAL NOT NULL,
    unit TEXT DEFAULT 'unidad', supplier_id TEXT, stock_qty REAL DEFAULT 0,
    cost_price REAL DEFAULT 0, created_at REAL
);
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY, number TEXT UNIQUE NOT NULL, created_at REAL,
    client_name TEXT, client_doc TEXT, client_address TEXT, client_phone TEXT, client_email TEXT,
    tax_rate REAL DEFAULT 0, notes TEXT DEFAULT '', warranty TEXT DEFAULT '', seller TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id TEXT, description TEXT NOT NULL, qty REAL NOT NULL, price REAL NOT NULL,
    discount REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL, change_qty REAL NOT NULL,
    reason TEXT NOT NULL, reference TEXT, created_at REAL
);
"""

# columnas que se agregaron después del primer lanzamiento: se aplican con
# ALTER TABLE sobre bases de datos ya existentes, sin perder datos.
MIGRATIONS = [
    ("products", "supplier_id", "ALTER TABLE products ADD COLUMN supplier_id TEXT"),
    ("products", "stock_qty", "ALTER TABLE products ADD COLUMN stock_qty REAL DEFAULT 0"),
    ("products", "cost_price", "ALTER TABLE products ADD COLUMN cost_price REAL DEFAULT 0"),
    ("invoices", "warranty", "ALTER TABLE invoices ADD COLUMN warranty TEXT DEFAULT ''"),
    ("invoices", "seller", "ALTER TABLE invoices ADD COLUMN seller TEXT DEFAULT ''"),
    ("invoice_items", "product_id", "ALTER TABLE invoice_items ADD COLUMN product_id TEXT"),
    ("invoice_items", "discount", "ALTER TABLE invoice_items ADD COLUMN discount REAL DEFAULT 0"),
]


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO company (id) VALUES (1)")
    for table, col, ddl in MIGRATIONS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            conn.execute(ddl)
    conn.commit()
    conn.close()


init_db()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA busy_timeout=8000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not hmac.compare_digest(request.headers.get("X-API-Key", "").encode(), API_KEY.encode()):
            return jsonify({"error": "Clave de API incorrecta o ausente."}), 401
        return fn(*args, **kwargs)
    return wrapper


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@app.errorhandler(ApiError)
def handle_api_error(e):
    return jsonify({"error": e.message}), e.status


@app.errorhandler(Exception)
def handle_any_error(e):
    if isinstance(e, HTTPException):
        return e
    return jsonify({"error": f"Error en el servidor: {e}"}), 500


# ---------- versión web (celular / navegador) ----------
@app.get("/")
def web_index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/manifest.webmanifest")
def web_manifest():
    return send_from_directory(STATIC_DIR, "manifest.webmanifest", mimetype="application/manifest+json")


@app.get("/icon.svg")
def web_icon():
    return send_from_directory(STATIC_DIR, "icon.svg", mimetype="image/svg+xml")


# ---------- salud ----------
@app.get("/api/ping")
@require_api_key
def ping():
    return jsonify({"ok": True, "name": "Facturador API"})


# ---------- empresa ----------
@app.get("/api/company")
@require_api_key
def get_company():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM company WHERE id=1").fetchone()
        data = dict(row) if row else {}
    logo_blob = data.pop("logo_blob", None)
    data["logo_base64"] = base64.b64encode(logo_blob).decode("ascii") if logo_blob else None
    return jsonify(data)


@app.post("/api/company")
@require_api_key
def save_company():
    d = request.get_json(force=True)
    with get_conn() as conn:
        conn.execute(
            """UPDATE company SET name=?, tax_id=?, address=?, phone=?, email=?, website=?,
               currency=?, tax_label=?, tax_rate=?, footer_note=? WHERE id=1""",
            (d.get("name", ""), d.get("tax_id", ""), d.get("address", ""), d.get("phone", ""),
             d.get("email", ""), d.get("website", ""), d.get("currency", "$"),
             d.get("tax_label", "IVA"), d.get("tax_rate", 0), d.get("footer_note", "")),
        )
    return jsonify({"ok": True})


@app.post("/api/company/logo")
@require_api_key
def save_logo():
    d = request.get_json(force=True)
    blob = base64.b64decode(d["data_base64"]) if d.get("data_base64") else None
    with get_conn() as conn:
        conn.execute("UPDATE company SET logo_blob=?, logo_mime=? WHERE id=1", (blob, d.get("mime")))
    return jsonify({"ok": True})


# ---------- clientes ----------
@app.get("/api/clients")
@require_api_key
def list_clients():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM clients ORDER BY name COLLATE NOCASE").fetchall()
        return jsonify([dict(r) for r in rows])


@app.post("/api/clients")
@require_api_key
def create_client():
    d = request.get_json(force=True)
    if not d.get("name", "").strip():
        return jsonify({"error": "El nombre del cliente es obligatorio."}), 400
    cid = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO clients (id, name, doc, address, phone, email, created_at) VALUES (?,?,?,?,?,?,?)",
            (cid, d["name"], d.get("doc", ""), d.get("address", ""), d.get("phone", ""), d.get("email", ""), time.time()),
        )
    return jsonify({"id": cid})


@app.put("/api/clients/<cid>")
@require_api_key
def update_client(cid):
    d = request.get_json(force=True)
    with get_conn() as conn:
        conn.execute(
            "UPDATE clients SET name=?, doc=?, address=?, phone=?, email=? WHERE id=?",
            (d.get("name", ""), d.get("doc", ""), d.get("address", ""), d.get("phone", ""), d.get("email", ""), cid),
        )
    return jsonify({"id": cid})


@app.delete("/api/clients/<cid>")
@require_api_key
def delete_client(cid):
    with get_conn() as conn:
        conn.execute("DELETE FROM clients WHERE id=?", (cid,))
    return jsonify({"ok": True})


# ---------- proveedores ----------
@app.get("/api/suppliers")
@require_api_key
def list_suppliers():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM suppliers ORDER BY name COLLATE NOCASE").fetchall()
        return jsonify([dict(r) for r in rows])


@app.post("/api/suppliers")
@require_api_key
def create_supplier():
    d = request.get_json(force=True)
    if not d.get("name", "").strip():
        return jsonify({"error": "El nombre del proveedor es obligatorio."}), 400
    sid = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO suppliers (id, name, contact_name, phone, email, created_at) VALUES (?,?,?,?,?,?)",
            (sid, d["name"], d.get("contact_name", ""), d.get("phone", ""), d.get("email", ""), time.time()),
        )
    return jsonify({"id": sid})


@app.put("/api/suppliers/<sid>")
@require_api_key
def update_supplier(sid):
    d = request.get_json(force=True)
    with get_conn() as conn:
        conn.execute(
            "UPDATE suppliers SET name=?, contact_name=?, phone=?, email=? WHERE id=?",
            (d.get("name", ""), d.get("contact_name", ""), d.get("phone", ""), d.get("email", ""), sid),
        )
    return jsonify({"id": sid})


@app.delete("/api/suppliers/<sid>")
@require_api_key
def delete_supplier(sid):
    with get_conn() as conn:
        conn.execute("DELETE FROM suppliers WHERE id=?", (sid,))
    return jsonify({"ok": True})


# ---------- productos ----------
@app.get("/api/products")
@require_api_key
def list_products():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT p.*, s.name AS supplier_name FROM products p
               LEFT JOIN suppliers s ON s.id = p.supplier_id
               ORDER BY p.name COLLATE NOCASE"""
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@app.post("/api/products")
@require_api_key
def create_product():
    d = request.get_json(force=True)
    if not d.get("name", "").strip() or not (d.get("price", 0) or 0) > 0:
        return jsonify({"error": "El producto necesita nombre y precio mayor que cero."}), 400
    pid = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO products (id, name, price, unit, supplier_id, stock_qty, cost_price, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (pid, d["name"], d["price"], d.get("unit", "unidad"), d.get("supplier_id") or None,
             d.get("stock_qty", 0) or 0, d.get("cost_price", 0) or 0, time.time()),
        )
    return jsonify({"id": pid})


@app.put("/api/products/<pid>")
@require_api_key
def update_product(pid):
    d = request.get_json(force=True)
    with get_conn() as conn:
        conn.execute(
            """UPDATE products SET name=?, price=?, unit=?, supplier_id=?, stock_qty=?, cost_price=?
               WHERE id=?""",
            (d.get("name", ""), d.get("price", 0), d.get("unit", "unidad"), d.get("supplier_id") or None,
             d.get("stock_qty", 0) or 0, d.get("cost_price", 0) or 0, pid),
        )
    return jsonify({"id": pid})


@app.delete("/api/products/<pid>")
@require_api_key
def delete_product(pid):
    with get_conn() as conn:
        conn.execute("DELETE FROM products WHERE id=?", (pid,))
    return jsonify({"ok": True})


@app.post("/api/products/<pid>/restock")
@require_api_key
def restock_product(pid):
    d = request.get_json(force=True)
    qty = d.get("qty", 0) or 0
    if qty <= 0:
        return jsonify({"error": "La cantidad a ingresar debe ser mayor que cero."}), 400
    with get_conn() as conn:
        row = conn.execute("SELECT stock_qty FROM products WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({"error": "Producto no encontrado."}), 404
        new_qty = (row["stock_qty"] or 0) + qty
        conn.execute("UPDATE products SET stock_qty=? WHERE id=?", (new_qty, pid))
        conn.execute(
            "INSERT INTO stock_movements (product_id, change_qty, reason, reference, created_at) VALUES (?,?,?,?,?)",
            (pid, qty, "reabastecimiento", d.get("note", ""), time.time()),
        )
    return jsonify({"ok": True, "stock_qty": new_qty})


# ---------- facturas ----------
def _invoice_total(conn, invoice_id, tax_rate):
    items = conn.execute("SELECT qty, price, discount FROM invoice_items WHERE invoice_id=?", (invoice_id,)).fetchall()
    subtotal = sum(i["qty"] * i["price"] * (1 - (i["discount"] or 0) / 100) for i in items)
    return subtotal * (1 + (tax_rate or 0) / 100)


@app.get("/api/invoices")
@require_api_key
def list_invoices():
    with get_conn() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM invoices ORDER BY created_at DESC").fetchall()]
        for r in rows:
            r["total"] = _invoice_total(conn, r["id"], r.get("tax_rate"))
        return jsonify(rows)


@app.get("/api/invoices/<iid>")
@require_api_key
def get_invoice(iid):
    with get_conn() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id=?", (iid,)).fetchone()
        if not inv:
            return jsonify({"error": "Factura no encontrada."}), 404
        items = conn.execute("SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id", (iid,)).fetchall()
        result = dict(inv)
        result["items"] = [dict(i) for i in items]
        return jsonify(result)


@app.post("/api/invoices")
@require_api_key
def create_invoice():
    d = request.get_json(force=True)
    client = d.get("client_snapshot", {})
    items = d.get("items", [])
    tax_rate = d.get("tax_rate", 0)
    notes = d.get("notes", "")
    warranty = d.get("warranty", "")
    seller = d.get("seller", "")
    if not items:
        return jsonify({"error": "La factura necesita al menos un artículo."}), 400

    invoice_id = str(uuid.uuid4())
    for _attempt in range(5):
        try:
            with get_conn() as conn:
                # Validar producto y stock de TODOS los artículos antes de tocar nada.
                resolved = []
                for it in items:
                    pid = it.get("product_id")
                    qty = it.get("qty", 0) or 0
                    product = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
                    if not product:
                        raise ApiError(f"Uno de los productos ya no existe en el catálogo (id {pid}).")
                    if qty <= 0:
                        raise ApiError(f'La cantidad de "{product["name"]}" debe ser mayor que cero.')
                    if (product["stock_qty"] or 0) < qty:
                        raise ApiError(
                            f'No hay suficiente stock de "{product["name"]}": '
                            f'disponible {product["stock_qty"]:g}, solicitado {qty:g}.'
                        )
                    resolved.append((product, it))

                row = conn.execute("SELECT invoice_counter FROM company WHERE id=1").fetchone()
                counter = row["invoice_counter"] if row else 1
                number = f"FAC-{counter:04d}"

                conn.execute(
                    """INSERT INTO invoices (id, number, created_at, client_name, client_doc,
                       client_address, client_phone, client_email, tax_rate, notes, warranty, seller)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (invoice_id, number, time.time(), client.get("name", ""), client.get("doc", ""),
                     client.get("address", ""), client.get("phone", ""), client.get("email", ""),
                     tax_rate, notes, warranty, seller),
                )
                for product, it in resolved:
                    price = it.get("price", product["price"])
                    discount = it.get("discount", 0) or 0
                    qty = it["qty"]
                    conn.execute(
                        """INSERT INTO invoice_items (invoice_id, product_id, description, qty, price, discount)
                           VALUES (?,?,?,?,?,?)""",
                        (invoice_id, product["id"], product["name"], qty, price, discount),
                    )
                    conn.execute(
                        "UPDATE products SET stock_qty = stock_qty - ? WHERE id=?", (qty, product["id"])
                    )
                    conn.execute(
                        "INSERT INTO stock_movements (product_id, change_qty, reason, reference, created_at) VALUES (?,?,?,?,?)",
                        (product["id"], -qty, "venta", number, time.time()),
                    )
                conn.execute("UPDATE company SET invoice_counter=? WHERE id=1", (counter + 1,))
            return jsonify({"id": invoice_id, "number": number})
        except sqlite3.IntegrityError:
            with get_conn() as conn2:
                row = conn2.execute("SELECT invoice_counter FROM company WHERE id=1").fetchone()
                conn2.execute("UPDATE company SET invoice_counter=? WHERE id=1", ((row["invoice_counter"] if row else 1) + 1,))
            continue
    return jsonify({"error": "No se pudo generar un número de factura único."}), 500


@app.get("/api/invoices/<iid>/pdf")
@require_api_key
def invoice_pdf(iid):
    with get_conn() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id=?", (iid,)).fetchone()
        if not inv:
            return jsonify({"error": "Factura no encontrada."}), 404
        invoice = dict(inv)
        invoice["items"] = [dict(i) for i in conn.execute(
            "SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id", (iid,)).fetchall()]
        company = dict(conn.execute("SELECT * FROM company WHERE id=1").fetchone())
    buf = io.BytesIO()
    generate_invoice_pdf(invoice, company, buf)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", download_name=f'{invoice["number"]}.pdf')


@app.delete("/api/invoices/<iid>")
@require_api_key
def delete_invoice(iid):
    with get_conn() as conn:
        inv = conn.execute("SELECT number FROM invoices WHERE id=?", (iid,)).fetchone()
        items = conn.execute("SELECT product_id, qty FROM invoice_items WHERE invoice_id=?", (iid,)).fetchall()
        for it in items:
            if it["product_id"]:
                conn.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id=?", (it["qty"], it["product_id"]))
                conn.execute(
                    "INSERT INTO stock_movements (product_id, change_qty, reason, reference, created_at) VALUES (?,?,?,?,?)",
                    (it["product_id"], it["qty"], "anulación factura", inv["number"] if inv else iid, time.time()),
                )
        conn.execute("DELETE FROM invoice_items WHERE invoice_id=?", (iid,))
        conn.execute("DELETE FROM invoices WHERE id=?", (iid,))
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
