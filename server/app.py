"""
API del Facturador. Expone por HTTP las operaciones de empresa, clientes,
proveedores, productos (con inventario), facturas (con descuento por línea,
vendedor, garantía, estado de pago y anulación), usuarios, resumen de ventas
y copias de seguridad. También sirve la versión web (static/index.html).

Acceso:
- Cada empleado entra con su usuario y contraseña (POST /api/login) y recibe
  un token que envía en el header "Authorization: Bearer <token>".
- La clave maestra (FACTURADOR_API_KEY, header "X-API-Key") da acceso de
  administrador. Es solo para el dueño: crear los primeros usuarios o
  recuperar el acceso.

Despliegue gratuito sugerido: PythonAnywhere (ver DEPLOY.md).
"""
import base64
import datetime
import hashlib
import hmac
import io
import os
import secrets
import sqlite3
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from flask import Flask, g, request, jsonify, send_file, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

# pdf_gen.py puede estar junto a este archivo (en PythonAnywhere) o en la
# carpeta de arriba (al correrlo desde el repositorio).
SERVER_DIR = Path(__file__).parent
for _p in (SERVER_DIR, SERVER_DIR.parent):
    if (_p / "pdf_gen.py").exists() and str(_p) not in sys.path:
        sys.path.append(str(_p))
from pdf_gen import generate_invoice_pdf  # noqa: E402

# -------- configuración --------
API_KEY = os.environ.get("FACTURADOR_API_KEY", "cambia-esta-clave")
DB_PATH = os.environ.get("FACTURADOR_DB", str(SERVER_DIR / "facturador_server.db"))
BACKUP_DIR = Path(os.environ.get("FACTURADOR_BACKUPS", str(Path(DB_PATH).parent / "backups")))
STATIC_DIR = SERVER_DIR / "static"

SESSION_DAYS = 30            # una sesión sin uso durante este tiempo expira
AUTO_BACKUP_EVERY = 24 * 3600
AUTO_BACKUP_KEEP = 14        # copias automáticas que se conservan
MAX_FAILED_LOGINS = 5
LOCK_SECONDS = 5 * 60
PAYMENT_METHODS = ("efectivo", "transferencia", "tarjeta", "otro")
ROLES = ("admin", "vendedor")

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
    tax_rate REAL DEFAULT 0, notes TEXT DEFAULT '', warranty TEXT DEFAULT '', seller TEXT DEFAULT '',
    status TEXT DEFAULT 'activa', voided_at REAL, voided_by TEXT DEFAULT '', void_reason TEXT DEFAULT '',
    user_id TEXT, user_name TEXT DEFAULT '', payment_tracking INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id TEXT, description TEXT NOT NULL, qty REAL NOT NULL, price REAL NOT NULL,
    discount REAL DEFAULT 0, unit_cost REAL
);
CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL, change_qty REAL NOT NULL,
    reason TEXT NOT NULL, reference TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL COLLATE NOCASE, name TEXT NOT NULL,
    password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'vendedor', active INTEGER DEFAULT 1,
    failed_logins INTEGER DEFAULT 0, locked_until REAL DEFAULT 0, created_at REAL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL, last_seen REAL
);
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    amount REAL NOT NULL, method TEXT NOT NULL, note TEXT DEFAULT '', created_at REAL,
    user_id TEXT, user_name TEXT DEFAULT ''
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
    ("invoices", "status", "ALTER TABLE invoices ADD COLUMN status TEXT DEFAULT 'activa'"),
    ("invoices", "voided_at", "ALTER TABLE invoices ADD COLUMN voided_at REAL"),
    ("invoices", "voided_by", "ALTER TABLE invoices ADD COLUMN voided_by TEXT DEFAULT ''"),
    ("invoices", "void_reason", "ALTER TABLE invoices ADD COLUMN void_reason TEXT DEFAULT ''"),
    ("invoices", "user_id", "ALTER TABLE invoices ADD COLUMN user_id TEXT"),
    ("invoices", "user_name", "ALTER TABLE invoices ADD COLUMN user_name TEXT DEFAULT ''"),
    # Las facturas anteriores a esta versión quedan con 0 ("sin registro de pago"),
    # para no marcarlas como pendientes ni como pagadas sin saberlo.
    ("invoices", "payment_tracking", "ALTER TABLE invoices ADD COLUMN payment_tracking INTEGER DEFAULT 0"),
    ("invoice_items", "product_id", "ALTER TABLE invoice_items ADD COLUMN product_id TEXT"),
    ("invoice_items", "discount", "ALTER TABLE invoice_items ADD COLUMN discount REAL DEFAULT 0"),
    ("invoice_items", "unit_cost", "ALTER TABLE invoice_items ADD COLUMN unit_cost REAL"),
]

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoices_created ON invoices(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO company (id) VALUES (1)")
    for table, col, ddl in MIGRATIONS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            conn.execute(ddl)
    conn.executescript(INDEXES)
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
    app.logger.exception("Error no controlado")
    return jsonify({"error": f"Error en el servidor: {e}"}), 500


def money(x):
    return round((x or 0) + 1e-9, 2)


def num(value, field, minimum=None, maximum=None, default=None):
    """Convierte a número validando rango; lanza ApiError con mensaje claro."""
    if value is None or value == "":
        if default is not None:
            return default
        raise ApiError(f"Falta el valor de {field}.")
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ApiError(f"{field} debe ser un número.")
    if v != v or v in (float("inf"), float("-inf")):
        raise ApiError(f"{field} debe ser un número.")
    if minimum is not None and v < minimum:
        raise ApiError(f"{field} no puede ser menor que {minimum:g}.")
    if maximum is not None and v > maximum:
        raise ApiError(f"{field} no puede ser mayor que {maximum:g}.")
    return v


def body():
    d = request.get_json(force=True, silent=True)
    if not isinstance(d, dict):
        raise ApiError("La petición no trae datos válidos.")
    return d


# ---------- autenticación ----------
MASTER_USER = {"id": None, "username": "clave-maestra", "name": "Administrador", "role": "admin", "master": True}
_DUMMY_HASH = generate_password_hash("contraseña-de-relleno")


def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _current_user():
    key = request.headers.get("X-API-Key", "")
    if key:
        if hmac.compare_digest(key.encode(), API_KEY.encode()):
            return MASTER_USER
        return None
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    th = _token_hash(auth[7:].strip())
    now = time.time()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT u.id, u.username, u.name, u.role, u.active, s.last_seen FROM sessions s
               JOIN users u ON u.id = s.user_id WHERE s.token_hash=?""", (th,)).fetchone()
        if not row or not row["active"] or (row["last_seen"] or 0) < now - SESSION_DAYS * 86400:
            return None
        if now - (row["last_seen"] or 0) > 3600:
            conn.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (now, th))
    return {"id": row["id"], "username": row["username"], "name": row["name"], "role": row["role"], "master": False}


def require_auth(admin=False):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = _current_user()
            if not user:
                return jsonify({"error": "Sesión vencida o datos de acceso incorrectos. Vuelve a entrar."}), 401
            if admin and user["role"] != "admin":
                return jsonify({"error": "Solo un administrador puede hacer esto."}), 403
            g.user = user
            return fn(*args, **kwargs)
        return wrapper
    return deco


def public_user(row):
    return {k: row[k] for k in ("id", "username", "name", "role")} | {"active": bool(row["active"])}


@app.post("/api/login")
def login():
    d = body()
    username = str(d.get("username", "")).strip()
    password = str(d.get("password", ""))
    if not username or not password:
        raise ApiError("Escribe tu usuario y tu contraseña.")
    now = time.time()
    with get_conn() as conn:
        u = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not u:
            check_password_hash(_DUMMY_HASH, password)  # mismo tiempo de respuesta
            raise ApiError("Usuario o contraseña incorrectos.", 401)
        if (u["locked_until"] or 0) > now:
            mins = int((u["locked_until"] - now) // 60) + 1
            raise ApiError(f"Demasiados intentos fallidos. Intenta de nuevo en {mins} minuto(s).", 429)
        if not check_password_hash(u["password_hash"], password):
            fails = (u["failed_logins"] or 0) + 1
            if fails >= MAX_FAILED_LOGINS:
                conn.execute("UPDATE users SET failed_logins=0, locked_until=? WHERE id=?", (now + LOCK_SECONDS, u["id"]))
            else:
                conn.execute("UPDATE users SET failed_logins=? WHERE id=?", (fails, u["id"]))
            conn.commit()
            raise ApiError("Usuario o contraseña incorrectos.", 401)
        if not u["active"]:
            raise ApiError("Este usuario está desactivado. Habla con el administrador.", 403)
        token = secrets.token_urlsafe(32)
        conn.execute("UPDATE users SET failed_logins=0, locked_until=0 WHERE id=?", (u["id"],))
        conn.execute("DELETE FROM sessions WHERE last_seen < ?", (now - SESSION_DAYS * 86400,))
        conn.execute("INSERT INTO sessions (token_hash, user_id, created_at, last_seen) VALUES (?,?,?,?)",
                     (_token_hash(token), u["id"], now, now))
        return jsonify({"token": token, "user": public_user(u)})


@app.post("/api/logout")
@require_auth()
def logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        with get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(auth[7:].strip()),))
    return jsonify({"ok": True})


@app.get("/api/me")
@require_auth()
def me():
    return jsonify({k: v for k, v in g.user.items()})


@app.post("/api/me/password")
@require_auth()
def change_own_password():
    if g.user["master"]:
        raise ApiError("La clave maestra se cambia en el servidor, no desde aquí.")
    d = body()
    new = str(d.get("new_password", ""))
    _check_password_rules(new)
    with get_conn() as conn:
        u = conn.execute("SELECT password_hash FROM users WHERE id=?", (g.user["id"],)).fetchone()
        if not check_password_hash(u["password_hash"], str(d.get("current_password", ""))):
            raise ApiError("La contraseña actual no es correcta.")
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new), g.user["id"]))
        # cierra las demás sesiones de este usuario (p. ej. un celular perdido)
        auth = request.headers.get("Authorization", "")
        conn.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?",
                     (g.user["id"], _token_hash(auth[7:].strip())))
    return jsonify({"ok": True})


def _check_password_rules(pw):
    if len(pw) < 6:
        raise ApiError("La contraseña debe tener al menos 6 caracteres.")


# ---------- usuarios (solo administrador) ----------
@app.get("/api/users")
@require_auth(admin=True)
def list_users():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY active DESC, name COLLATE NOCASE").fetchall()
        return jsonify([public_user(r) for r in rows])


@app.post("/api/users")
@require_auth(admin=True)
def create_user():
    d = body()
    username = str(d.get("username", "")).strip()
    name = str(d.get("name", "")).strip()
    role = d.get("role", "vendedor")
    password = str(d.get("password", ""))
    if not username or not name:
        raise ApiError("El usuario necesita nombre y nombre de usuario.")
    if " " in username:
        raise ApiError("El nombre de usuario no puede tener espacios.")
    if role not in ROLES:
        raise ApiError("El rol debe ser 'admin' o 'vendedor'.")
    _check_password_rules(password)
    uid = str(uuid.uuid4())
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users (id, username, name, password_hash, role, active, created_at) VALUES (?,?,?,?,?,1,?)",
                (uid, username, name, generate_password_hash(password), role, time.time()))
    except sqlite3.IntegrityError:
        raise ApiError(f'Ya existe un usuario "{username}".')
    return jsonify({"id": uid})


@app.put("/api/users/<uid>")
@require_auth(admin=True)
def update_user(uid):
    d = body()
    with get_conn() as conn:
        u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not u:
            raise ApiError("Usuario no encontrado.", 404)
        name = str(d.get("name", u["name"])).strip() or u["name"]
        role = d.get("role", u["role"])
        active = 1 if d.get("active", bool(u["active"])) else 0
        if role not in ROLES:
            raise ApiError("El rol debe ser 'admin' o 'vendedor'.")
        if uid == g.user["id"] and (not active or role != "admin"):
            raise ApiError("No puedes quitarte a ti mismo el rol de administrador ni desactivarte.")
        conn.execute("UPDATE users SET name=?, role=?, active=? WHERE id=?", (name, role, active, uid))
        if d.get("password"):
            _check_password_rules(str(d["password"]))
            conn.execute("UPDATE users SET password_hash=?, failed_logins=0, locked_until=0 WHERE id=?",
                         (generate_password_hash(str(d["password"])), uid))
        if not active or d.get("password"):
            conn.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    return jsonify({"ok": True})


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
@require_auth()
def ping():
    return jsonify({"ok": True, "name": "Facturador API"})


# ---------- empresa ----------
@app.get("/api/company")
@require_auth()
def get_company():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM company WHERE id=1").fetchone()
        data = dict(row) if row else {}
    logo_blob = data.pop("logo_blob", None)
    data["logo_base64"] = base64.b64encode(logo_blob).decode("ascii") if logo_blob else None
    return jsonify(data)


@app.post("/api/company")
@require_auth(admin=True)
def save_company():
    d = body()
    tax_rate = num(d.get("tax_rate"), "La tarifa de impuesto", 0, 100, default=0)
    with get_conn() as conn:
        conn.execute(
            """UPDATE company SET name=?, tax_id=?, address=?, phone=?, email=?, website=?,
               currency=?, tax_label=?, tax_rate=?, footer_note=? WHERE id=1""",
            (d.get("name", ""), d.get("tax_id", ""), d.get("address", ""), d.get("phone", ""),
             d.get("email", ""), d.get("website", ""), d.get("currency", "$"),
             d.get("tax_label", "IVA"), tax_rate, d.get("footer_note", "")),
        )
    return jsonify({"ok": True})


@app.post("/api/company/logo")
@require_auth(admin=True)
def save_logo():
    d = body()
    blob = base64.b64decode(d["data_base64"]) if d.get("data_base64") else None
    if blob and len(blob) > 3 * 1024 * 1024:
        raise ApiError("El logo pesa demasiado (máximo 3 MB).")
    with get_conn() as conn:
        conn.execute("UPDATE company SET logo_blob=?, logo_mime=? WHERE id=1", (blob, d.get("mime")))
    return jsonify({"ok": True})


# ---------- clientes ----------
@app.get("/api/clients")
@require_auth()
def list_clients():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM clients ORDER BY name COLLATE NOCASE").fetchall()
        return jsonify([dict(r) for r in rows])


@app.post("/api/clients")
@require_auth()
def create_client():
    d = body()
    if not str(d.get("name", "")).strip():
        raise ApiError("El nombre del cliente es obligatorio.")
    cid = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO clients (id, name, doc, address, phone, email, created_at) VALUES (?,?,?,?,?,?,?)",
            (cid, d["name"], d.get("doc", ""), d.get("address", ""), d.get("phone", ""), d.get("email", ""), time.time()),
        )
    return jsonify({"id": cid})


@app.put("/api/clients/<cid>")
@require_auth()
def update_client(cid):
    d = body()
    if not str(d.get("name", "")).strip():
        raise ApiError("El nombre del cliente es obligatorio.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE clients SET name=?, doc=?, address=?, phone=?, email=? WHERE id=?",
            (d.get("name", ""), d.get("doc", ""), d.get("address", ""), d.get("phone", ""), d.get("email", ""), cid),
        )
    return jsonify({"id": cid})


@app.delete("/api/clients/<cid>")
@require_auth(admin=True)
def delete_client(cid):
    with get_conn() as conn:
        conn.execute("DELETE FROM clients WHERE id=?", (cid,))
    return jsonify({"ok": True})


# ---------- proveedores ----------
@app.get("/api/suppliers")
@require_auth()
def list_suppliers():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM suppliers ORDER BY name COLLATE NOCASE").fetchall()
        return jsonify([dict(r) for r in rows])


@app.post("/api/suppliers")
@require_auth(admin=True)
def create_supplier():
    d = body()
    if not str(d.get("name", "")).strip():
        raise ApiError("El nombre del proveedor es obligatorio.")
    sid = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO suppliers (id, name, contact_name, phone, email, created_at) VALUES (?,?,?,?,?,?)",
            (sid, d["name"], d.get("contact_name", ""), d.get("phone", ""), d.get("email", ""), time.time()),
        )
    return jsonify({"id": sid})


@app.put("/api/suppliers/<sid>")
@require_auth(admin=True)
def update_supplier(sid):
    d = body()
    with get_conn() as conn:
        conn.execute(
            "UPDATE suppliers SET name=?, contact_name=?, phone=?, email=? WHERE id=?",
            (d.get("name", ""), d.get("contact_name", ""), d.get("phone", ""), d.get("email", ""), sid),
        )
    return jsonify({"id": sid})


@app.delete("/api/suppliers/<sid>")
@require_auth(admin=True)
def delete_supplier(sid):
    with get_conn() as conn:
        conn.execute("DELETE FROM suppliers WHERE id=?", (sid,))
    return jsonify({"ok": True})


# ---------- productos ----------
@app.get("/api/products")
@require_auth()
def list_products():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT p.*, s.name AS supplier_name FROM products p
               LEFT JOIN suppliers s ON s.id = p.supplier_id
               ORDER BY p.name COLLATE NOCASE"""
        ).fetchall()
    result = [dict(r) for r in rows]
    if g.user["role"] != "admin":
        for r in result:
            r.pop("cost_price", None)  # el costo (y la ganancia) solo lo ve el administrador
    return jsonify(result)


def _product_values(d):
    name = str(d.get("name", "")).strip()
    if not name:
        raise ApiError("El producto necesita un nombre.")
    price = num(d.get("price"), "El precio", 0)
    if price <= 0:
        raise ApiError("El precio debe ser mayor que cero.")
    return (name, price, d.get("unit") or "unidad", d.get("supplier_id") or None,
            num(d.get("stock_qty"), "Las existencias", 0, default=0),
            num(d.get("cost_price"), "El costo", 0, default=0))


@app.post("/api/products")
@require_auth(admin=True)
def create_product():
    vals = _product_values(body())
    pid = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO products (name, price, unit, supplier_id, stock_qty, cost_price, id, created_at)
               VALUES (?,?,?,?,?,?,?,?)""", vals + (pid, time.time()))
    return jsonify({"id": pid})


@app.put("/api/products/<pid>")
@require_auth(admin=True)
def update_product(pid):
    vals = _product_values(body())
    with get_conn() as conn:
        conn.execute(
            "UPDATE products SET name=?, price=?, unit=?, supplier_id=?, stock_qty=?, cost_price=? WHERE id=?",
            vals + (pid,))
    return jsonify({"id": pid})


@app.delete("/api/products/<pid>")
@require_auth(admin=True)
def delete_product(pid):
    with get_conn() as conn:
        conn.execute("DELETE FROM products WHERE id=?", (pid,))
    return jsonify({"ok": True})


@app.post("/api/products/<pid>/restock")
@require_auth(admin=True)
def restock_product(pid):
    d = body()
    qty = num(d.get("qty"), "La cantidad", 0)
    if qty <= 0:
        raise ApiError("La cantidad a ingresar debe ser mayor que cero.")
    with get_conn() as conn:
        row = conn.execute("SELECT stock_qty FROM products WHERE id=?", (pid,)).fetchone()
        if not row:
            raise ApiError("Producto no encontrado.", 404)
        new_qty = (row["stock_qty"] or 0) + qty
        conn.execute("UPDATE products SET stock_qty=? WHERE id=?", (new_qty, pid))
        conn.execute(
            "INSERT INTO stock_movements (product_id, change_qty, reason, reference, created_at) VALUES (?,?,?,?,?)",
            (pid, qty, "reabastecimiento", d.get("note", ""), time.time()),
        )
    return jsonify({"ok": True, "stock_qty": new_qty})


# ---------- facturas ----------
INVOICE_SELECT = """
SELECT i.*,
  (SELECT COALESCE(SUM(qty * price * (1 - COALESCE(discount, 0) / 100.0)), 0)
     FROM invoice_items WHERE invoice_id = i.id) AS net,
  (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE invoice_id = i.id) AS paid
FROM invoices i
"""


def _with_totals(row):
    """Agrega total, pagado, saldo y estado de pago a una fila de INVOICE_SELECT."""
    inv = dict(row)
    inv["status"] = inv.get("status") or "activa"
    inv["total"] = money(inv.pop("net") * (1 + (inv.get("tax_rate") or 0) / 100))
    inv["paid"] = money(inv["paid"])
    inv["balance"] = money(inv["total"] - inv["paid"])
    if inv["status"] == "anulada":
        state = "anulada"
    elif not inv.get("payment_tracking"):
        state = "sin_registro"
    elif inv["balance"] <= 0.004:
        state = "pagada"
    elif inv["paid"] > 0:
        state = "abono"
    else:
        state = "pendiente"
    inv["payment_status"] = state
    return inv


def _load_invoice(conn, iid):
    row = conn.execute(INVOICE_SELECT + " WHERE i.id=?", (iid,)).fetchone()
    if not row:
        raise ApiError("Factura no encontrada.", 404)
    inv = _with_totals(row)
    inv["items"] = [dict(i) for i in conn.execute(
        "SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id", (iid,)).fetchall()]
    inv["payments"] = [dict(p) for p in conn.execute(
        "SELECT * FROM payments WHERE invoice_id=? ORDER BY created_at", (iid,)).fetchall()]
    if g.user["role"] != "admin":
        for it in inv["items"]:
            it.pop("unit_cost", None)
    return inv


@app.get("/api/invoices")
@require_auth()
def list_invoices():
    with get_conn() as conn:
        rows = conn.execute(INVOICE_SELECT + " ORDER BY i.created_at DESC").fetchall()
        return jsonify([_with_totals(r) for r in rows])


@app.get("/api/invoices/<iid>")
@require_auth()
def get_invoice(iid):
    with get_conn() as conn:
        return jsonify(_load_invoice(conn, iid))


def _parse_payment_method(method):
    method = (method or "efectivo").strip().lower()
    if method not in PAYMENT_METHODS:
        raise ApiError("Método de pago no válido. Usa: " + ", ".join(PAYMENT_METHODS) + ".")
    return method


@app.post("/api/invoices")
@require_auth()
def create_invoice():
    d = body()
    client = d.get("client_snapshot") or {}
    items = d.get("items") or []
    tax_rate = num(d.get("tax_rate"), "La tarifa de impuesto", 0, 100, default=0)
    payment = d.get("payment")  # None = app antigua: no se lleva registro de pago
    if payment is not None and not isinstance(payment, dict):
        raise ApiError("La forma de pago no es válida.")
    if not items:
        raise ApiError("La factura necesita al menos un artículo.")
    if not str(client.get("name", "")).strip():
        raise ApiError("La factura necesita un cliente.")

    parsed = []
    for it in items:
        qty = num(it.get("qty"), "La cantidad", 0)
        if qty <= 0:
            raise ApiError("Todas las cantidades deben ser mayores que cero.")
        discount = num(it.get("discount"), "El descuento", 0, 100, default=0)
        price = it.get("price")
        price = None if price is None else num(price, "El precio", 0)
        parsed.append((it.get("product_id"), qty, price, discount))

    invoice_id = str(uuid.uuid4())
    for _attempt in range(5):
        try:
            with get_conn() as conn:
                # Validar producto y stock de TODOS los artículos antes de tocar nada.
                # Si un producto aparece en varias líneas, se suma lo pedido.
                products, wanted = {}, {}
                for pid, qty, _price, _disc in parsed:
                    if pid not in products:
                        product = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
                        if not product:
                            raise ApiError(f"Uno de los productos ya no existe en el catálogo (id {pid}).")
                        products[pid] = product
                    wanted[pid] = wanted.get(pid, 0) + qty
                for pid, qty in wanted.items():
                    p = products[pid]
                    if (p["stock_qty"] or 0) + 1e-9 < qty:
                        raise ApiError(
                            f'No hay suficiente stock de "{p["name"]}": '
                            f'disponible {p["stock_qty"]:g}, solicitado {qty:g}.')

                net = sum(qty * (price if price is not None else products[pid]["price"]) * (1 - disc / 100)
                          for pid, qty, price, disc in parsed)
                total = money(net * (1 + tax_rate / 100))
                pay_amount, pay_method = 0.0, None
                if payment is not None:
                    pay_method = _parse_payment_method(payment.get("method"))
                    if payment.get("mode") == "credito":
                        pay_amount = money(num(payment.get("amount"), "El abono inicial", 0, default=0))
                        if pay_amount > total:
                            raise ApiError("El abono inicial no puede ser mayor que el total de la factura.")
                    else:
                        pay_amount = total

                row = conn.execute("SELECT invoice_counter FROM company WHERE id=1").fetchone()
                counter = row["invoice_counter"] if row else 1
                number = f"FAC-{counter:04d}"
                now = time.time()
                user = g.user
                conn.execute(
                    """INSERT INTO invoices (id, number, created_at, client_name, client_doc,
                       client_address, client_phone, client_email, tax_rate, notes, warranty, seller,
                       status, user_id, user_name, payment_tracking)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'activa',?,?,?)""",
                    (invoice_id, number, now, client.get("name", ""), client.get("doc", ""),
                     client.get("address", ""), client.get("phone", ""), client.get("email", ""),
                     tax_rate, d.get("notes", ""), d.get("warranty", ""), d.get("seller", ""),
                     user["id"], user["name"], 1 if payment is not None else 0),
                )
                for pid, qty, price, discount in parsed:
                    product = products[pid]
                    conn.execute(
                        """INSERT INTO invoice_items (invoice_id, product_id, description, qty, price, discount, unit_cost)
                           VALUES (?,?,?,?,?,?,?)""",
                        (invoice_id, pid, product["name"], qty,
                         price if price is not None else product["price"], discount, product["cost_price"] or 0),
                    )
                    conn.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id=?", (qty, pid))
                    conn.execute(
                        "INSERT INTO stock_movements (product_id, change_qty, reason, reference, created_at) VALUES (?,?,?,?,?)",
                        (pid, -qty, "venta", number, now),
                    )
                if pay_amount > 0:
                    conn.execute(
                        """INSERT INTO payments (id, invoice_id, amount, method, note, created_at, user_id, user_name)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (str(uuid.uuid4()), invoice_id, pay_amount, pay_method,
                         "Pago al facturar" if payment.get("mode") != "credito" else "Abono inicial",
                         now, user["id"], user["name"]))
                conn.execute("UPDATE company SET invoice_counter=? WHERE id=1", (counter + 1,))
            return jsonify({"id": invoice_id, "number": number, "total": total})
        except sqlite3.IntegrityError:
            with get_conn() as conn2:
                row = conn2.execute("SELECT invoice_counter FROM company WHERE id=1").fetchone()
                conn2.execute("UPDATE company SET invoice_counter=? WHERE id=1", ((row["invoice_counter"] if row else 1) + 1,))
            continue
    raise ApiError("No se pudo generar un número de factura único.", 500)


@app.get("/api/invoices/<iid>/pdf")
@require_auth()
def invoice_pdf(iid):
    with get_conn() as conn:
        invoice = _load_invoice(conn, iid)
        company = dict(conn.execute("SELECT * FROM company WHERE id=1").fetchone())
    buf = io.BytesIO()
    generate_invoice_pdf(invoice, company, buf)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", download_name=f'{invoice["number"]}.pdf')


def _void_invoice(iid, reason):
    reason = (reason or "").strip()
    if not reason:
        raise ApiError("Escribe el motivo de la anulación.")
    with get_conn() as conn:
        inv = conn.execute("SELECT number, status FROM invoices WHERE id=?", (iid,)).fetchone()
        if not inv:
            raise ApiError("Factura no encontrada.", 404)
        if inv["status"] == "anulada":
            raise ApiError(f'La factura {inv["number"]} ya estaba anulada.')
        now = time.time()
        for it in conn.execute("SELECT product_id, qty FROM invoice_items WHERE invoice_id=?", (iid,)).fetchall():
            if it["product_id"]:
                conn.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id=?", (it["qty"], it["product_id"]))
                conn.execute(
                    "INSERT INTO stock_movements (product_id, change_qty, reason, reference, created_at) VALUES (?,?,?,?,?)",
                    (it["product_id"], it["qty"], "anulación factura", inv["number"], now),
                )
        conn.execute("UPDATE invoices SET status='anulada', voided_at=?, voided_by=?, void_reason=? WHERE id=?",
                     (now, g.user["name"], reason, iid))
    return jsonify({"ok": True})


@app.post("/api/invoices/<iid>/void")
@require_auth(admin=True)
def void_invoice(iid):
    return _void_invoice(iid, body().get("reason"))


@app.delete("/api/invoices/<iid>")
@require_auth(admin=True)
def delete_invoice(iid):
    # Las facturas no se borran (la numeración debe quedar completa): las apps
    # de escritorio antiguas que llaman a "eliminar" en realidad la anulan.
    return _void_invoice(iid, "Anulada desde una versión anterior de la app")


# ---------- pagos ----------
@app.post("/api/invoices/<iid>/payments")
@require_auth()
def add_payment(iid):
    d = body()
    amount = money(num(d.get("amount"), "El monto", 0))
    if amount <= 0:
        raise ApiError("El monto del pago debe ser mayor que cero.")
    method = _parse_payment_method(d.get("method"))
    with get_conn() as conn:
        inv = _load_invoice(conn, iid)
        if inv["status"] == "anulada":
            raise ApiError("No se pueden registrar pagos en una factura anulada.")
        if inv["payment_tracking"] and amount > inv["balance"] + 0.004:
            raise ApiError(f'El pago supera el saldo pendiente ({inv["balance"]:,.2f}).')
        if not inv["payment_tracking"] and amount > inv["total"] + 0.004:
            raise ApiError(f'El pago supera el total de la factura ({inv["total"]:,.2f}).')
        conn.execute(
            """INSERT INTO payments (id, invoice_id, amount, method, note, created_at, user_id, user_name)
               VALUES (?,?,?,?,?,?,?,?)""",
            (str(uuid.uuid4()), iid, amount, method, str(d.get("note", "")).strip(), time.time(),
             g.user["id"], g.user["name"]))
        conn.execute("UPDATE invoices SET payment_tracking=1 WHERE id=?", (iid,))
        return jsonify(_load_invoice(conn, iid))


@app.delete("/api/payments/<pay_id>")
@require_auth(admin=True)
def delete_payment(pay_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM payments WHERE id=?", (pay_id,))
    return jsonify({"ok": True})


# ---------- resumen de ventas (solo administrador) ----------
@app.get("/api/dashboard")
@require_auth(admin=True)
def dashboard():
    now = time.time()
    start = num(request.args.get("start"), "start", default=now - 30 * 86400)
    end = num(request.args.get("end"), "end", default=now)
    tz_offset = num(request.args.get("tz"), "tz", -14 * 60, 14 * 60, default=0)  # minutos, como JS getTimezoneOffset()

    def local_day(ts):
        return datetime.datetime.fromtimestamp(ts - tz_offset * 60, datetime.timezone.utc).date()

    with get_conn() as conn:
        invoices = [_with_totals(r) for r in conn.execute(
            INVOICE_SELECT + " WHERE i.created_at >= ? AND i.created_at < ? AND COALESCE(i.status,'activa') <> 'anulada'",
            (start, end)).fetchall()]
        items = conn.execute(
            """SELECT it.*, COALESCE(it.unit_cost, p.cost_price, 0) AS cost, i.tax_rate FROM invoice_items it
               JOIN invoices i ON i.id = it.invoice_id LEFT JOIN products p ON p.id = it.product_id
               WHERE i.created_at >= ? AND i.created_at < ? AND COALESCE(i.status,'activa') <> 'anulada'""",
            (start, end)).fetchall()
        payments = conn.execute(
            """SELECT p.method, SUM(p.amount) AS amount FROM payments p JOIN invoices i ON i.id = p.invoice_id
               WHERE p.created_at >= ? AND p.created_at < ? AND COALESCE(i.status,'activa') <> 'anulada'
               GROUP BY p.method ORDER BY amount DESC""", (start, end)).fetchall()
        receivables = [_with_totals(r) for r in conn.execute(
            INVOICE_SELECT + " WHERE COALESCE(i.status,'activa') <> 'anulada' AND i.payment_tracking = 1"
            " ORDER BY i.created_at").fetchall()]
    receivables = [r for r in receivables if r["balance"] > 0.004]

    gross = sum(i["qty"] * i["price"] for i in items)
    net = sum(i["qty"] * i["price"] * (1 - (i["discount"] or 0) / 100) for i in items)
    cost = sum(i["qty"] * (i["cost"] or 0) for i in items)
    total = sum(inv["total"] for inv in invoices)

    products = {}
    for i in items:
        key = i["product_id"] or i["description"]
        p = products.setdefault(key, {"name": i["description"], "qty": 0, "net": 0.0})
        p["qty"] += i["qty"]
        p["net"] += i["qty"] * i["price"] * (1 - (i["discount"] or 0) / 100)

    sellers = {}
    for inv in invoices:
        name = (inv.get("seller") or "").strip() or inv.get("user_name") or "Sin vendedor"
        s = sellers.setdefault(name, {"name": name, "count": 0, "total": 0.0})
        s["count"] += 1
        s["total"] += inv["total"]

    # serie por día (o por mes si el período es largo), con ceros en los días sin ventas
    first, last = local_day(start), local_day(max(start, end - 1))
    monthly = (last - first).days > 62
    buckets = {}
    day = first
    while day <= last:
        key = day.strftime("%Y-%m") if monthly else day.isoformat()
        buckets.setdefault(key, {"date": key, "total": 0.0, "count": 0})
        day += datetime.timedelta(days=1)
    for inv in invoices:
        d = local_day(inv["created_at"])
        key = d.strftime("%Y-%m") if monthly else d.isoformat()
        if key in buckets:
            buckets[key]["total"] += inv["total"]
            buckets[key]["count"] += 1

    return jsonify({
        "summary": {
            "count": len(invoices), "gross": money(gross), "discount": money(gross - net), "net": money(net),
            "tax": money(total - net), "total": money(total), "cost": money(cost), "profit": money(net - cost),
            "avg_ticket": money(total / len(invoices)) if invoices else 0,
            "items_without_cost": sum(1 for i in items if not i["cost"]),
        },
        "series": {"unit": "month" if monthly else "day",
                   "points": [dict(b, total=money(b["total"])) for b in buckets.values()]},
        "collected": {"total": money(sum(p["amount"] for p in payments)),
                      "by_method": [{"method": p["method"], "amount": money(p["amount"])} for p in payments]},
        "top_products": sorted(({**p, "net": money(p["net"])} for p in products.values()),
                               key=lambda p: -p["net"])[:10],
        "by_seller": sorted(({**s, "total": money(s["total"])} for s in sellers.values()),
                            key=lambda s: -s["total"]),
        "receivables": {
            "total": money(sum(r["balance"] for r in receivables)), "count": len(receivables),
            "invoices": [{k: r[k] for k in ("id", "number", "client_name", "created_at", "total", "balance")}
                         for r in receivables[:50]],
        },
    })


# ---------- copias de seguridad ----------
def _write_backup(dest: Path):
    """Copia consistente de la base (aunque haya gente usándola) usando la API de backup de SQLite."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".db", dir=dest.parent)
    os.close(fd)
    try:
        src = sqlite3.connect(DB_PATH, timeout=10)
        dst = sqlite3.connect(tmp)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


_last_backup_check = 0.0


@app.before_request
def auto_backup():
    """Una vez al día (aprovechando cualquier petición) guarda una copia en backups/."""
    global _last_backup_check
    now = time.time()
    if now - _last_backup_check < 3600:
        return
    _last_backup_check = now
    try:
        autos = sorted(BACKUP_DIR.glob("auto-*.db")) if BACKUP_DIR.exists() else []
        if autos and now - autos[-1].stat().st_mtime < AUTO_BACKUP_EVERY:
            return
        _write_backup(BACKUP_DIR / f"auto-{datetime.datetime.now():%Y-%m-%d_%H%M}.db")
        for old in sorted(BACKUP_DIR.glob("auto-*.db"))[:-AUTO_BACKUP_KEEP]:
            old.unlink()
    except Exception:
        app.logger.exception("No se pudo crear la copia de seguridad automática")


@app.get("/api/backup")
@require_auth(admin=True)
def download_backup():
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        src = sqlite3.connect(DB_PATH, timeout=10)
        dst = sqlite3.connect(tmp)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        with open(tmp, "rb") as f:
            data = io.BytesIO(f.read())
    finally:
        os.remove(tmp)
    return send_file(data, mimetype="application/octet-stream", as_attachment=True,
                     download_name=f"facturador-copia-{datetime.datetime.now():%Y-%m-%d_%H%M}.db")


@app.get("/api/backups")
@require_auth(admin=True)
def list_backups():
    files = sorted(BACKUP_DIR.glob("auto-*.db"), reverse=True) if BACKUP_DIR.exists() else []
    return jsonify([{"name": f.name, "size": f.stat().st_size, "created_at": f.stat().st_mtime} for f in files])


@app.get("/api/backups/<name>")
@require_auth(admin=True)
def get_backup(name):
    if not (name.startswith("auto-") and name.endswith(".db")) or "/" in name or "\\" in name or ".." in name:
        raise ApiError("Copia no encontrada.", 404)
    path = BACKUP_DIR / name
    if not path.is_file():
        raise ApiError("Copia no encontrada.", 404)
    return send_file(path, mimetype="application/octet-stream", as_attachment=True, download_name=name)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
