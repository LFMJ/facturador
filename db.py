"""
Cliente HTTP hacia el servidor del Facturador.

Mantiene exactamente las mismas funciones y firmas que la versión anterior
(que usaba SQLite local/carpeta compartida), para que el resto de la app
(tab_empresa.py, tab_clientes.py, etc.) no tenga que cambiar cómo las llama.
Donde antes se pasaba una ruta de carpeta, ahora se pasa un objeto Server
con la URL y los datos de acceso (token de sesión del usuario, o la clave
maestra del dueño).
"""
import base64
from dataclasses import dataclass

import requests


class DBError(Exception):
    """Error ya traducido a un mensaje claro para mostrar al usuario."""
    pass


class SessionExpired(DBError):
    """La sesión venció o el usuario fue desactivado: hay que volver a entrar."""
    pass


@dataclass
class Server:
    base_url: str
    api_key: str = ""   # clave maestra (solo el dueño)
    token: str = ""     # sesión de un usuario (lo normal)

    def headers(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {"X-API-Key": self.api_key}


TIMEOUT = 12


def _request(server: Server, method: str, path: str, json=None, raw=False):
    if not server or not server.base_url:
        raise DBError('Todavía no se ha configurado el servidor. Ve a "Cambiar servidor" para hacerlo.')
    url = server.base_url.rstrip("/") + path
    try:
        r = requests.request(method, url, json=json, timeout=TIMEOUT, headers=server.headers())
    except requests.exceptions.ConnectTimeout:
        raise DBError(f"El servidor no respondió a tiempo ({server.base_url}). Puede estar apagado o dormido; espera unos segundos e intenta de nuevo.")
    except requests.exceptions.ConnectionError:
        raise DBError(f"No se pudo conectar con el servidor ({server.base_url}). Verifica tu conexión a internet y que la URL sea correcta.")
    except requests.exceptions.Timeout:
        raise DBError("El servidor tardó demasiado en responder. Intenta de nuevo en unos segundos.")
    except requests.exceptions.RequestException as e:
        raise DBError(f"Error de red al hablar con el servidor: {e}")

    if r.status_code == 401 and path != "/api/login":
        raise SessionExpired("Tu sesión terminó o los datos de acceso no son correctos. Vuelve a entrar.")
    if r.status_code >= 400:
        try:
            detail = r.json().get("error", r.text)
        except ValueError:
            detail = r.text
        raise DBError(detail if r.status_code in (400, 401, 403, 404, 429) else f"El servidor respondió con un error: {detail}")
    if raw:
        return r.content
    try:
        return r.json()
    except ValueError:
        raise DBError("El servidor respondió con datos que no se pudieron interpretar.")


def test_connection(server: Server):
    """Valida URL + datos de acceso."""
    _request(server, "GET", "/api/ping")


# ---------- sesión ----------

def login(base_url: str, username: str, password: str):
    """Devuelve (Server con token, usuario)."""
    result = _request(Server(base_url=base_url), "POST", "/api/login",
                      json={"username": username, "password": password})
    return Server(base_url=base_url, token=result["token"]), result["user"]


def logout(server: Server):
    if server.token:
        _request(server, "POST", "/api/logout")


def me(server: Server) -> dict:
    return _request(server, "GET", "/api/me")


def change_password(server: Server, current: str, new: str):
    _request(server, "POST", "/api/me/password", json={"current_password": current, "new_password": new})


# ---------- empresa ----------

def get_company(server: Server) -> dict:
    data = _request(server, "GET", "/api/company")
    logo_b64 = data.pop("logo_base64", None)
    data["logo_blob"] = base64.b64decode(logo_b64) if logo_b64 else None
    return data


def save_company(server: Server, data: dict):
    _request(server, "POST", "/api/company", json=data)


def save_logo(server: Server, blob: bytes, mime: str):
    payload = {"data_base64": base64.b64encode(blob).decode("ascii") if blob else None, "mime": mime}
    _request(server, "POST", "/api/company/logo", json=payload)


# ---------- clientes ----------

def list_clients(server: Server):
    return _request(server, "GET", "/api/clients")


def save_client(server: Server, client: dict):
    if client.get("id"):
        _request(server, "PUT", f'/api/clients/{client["id"]}', json=client)
        return client["id"]
    result = _request(server, "POST", "/api/clients", json=client)
    return result["id"]


def delete_client(server: Server, client_id: str):
    _request(server, "DELETE", f"/api/clients/{client_id}")


# ---------- proveedores ----------

def list_suppliers(server: Server):
    return _request(server, "GET", "/api/suppliers")


def save_supplier(server: Server, supplier: dict):
    if supplier.get("id"):
        _request(server, "PUT", f'/api/suppliers/{supplier["id"]}', json=supplier)
        return supplier["id"]
    result = _request(server, "POST", "/api/suppliers", json=supplier)
    return result["id"]


def delete_supplier(server: Server, supplier_id: str):
    _request(server, "DELETE", f"/api/suppliers/{supplier_id}")


# ---------- productos ----------

def list_products(server: Server):
    return _request(server, "GET", "/api/products")


def save_product(server: Server, product: dict):
    if product.get("id"):
        _request(server, "PUT", f'/api/products/{product["id"]}', json=product)
        return product["id"]
    result = _request(server, "POST", "/api/products", json=product)
    return result["id"]


def delete_product(server: Server, product_id: str):
    _request(server, "DELETE", f"/api/products/{product_id}")


def restock_product(server: Server, product_id: str, qty: float, note: str = ""):
    return _request(server, "POST", f"/api/products/{product_id}/restock", json={"qty": qty, "note": note})


# ---------- facturas ----------

def create_invoice(server: Server, client_snapshot: dict, items: list, tax_rate: float,
                    notes: str = "", warranty: str = "", seller: str = "", payment: dict = None):
    """payment: {"mode": "contado"|"credito", "method": "efectivo"|..., "amount": abono (solo crédito)}"""
    payload = {
        "client_snapshot": client_snapshot,
        "items": [
            {"product_id": it["product_id"], "qty": it["qty"], "price": it["price"], "discount": it.get("discount", 0)}
            for it in items
        ],
        "tax_rate": tax_rate,
        "notes": notes,
        "warranty": warranty,
        "seller": seller,
        "payment": payment or {"mode": "contado", "method": "efectivo"},
    }
    result = _request(server, "POST", "/api/invoices", json=payload)
    return result["id"], result["number"]


def list_invoices(server: Server):
    return _request(server, "GET", "/api/invoices")


def get_invoice_with_items(server: Server, invoice_id: str):
    return _request(server, "GET", f"/api/invoices/{invoice_id}")


def void_invoice(server: Server, invoice_id: str, reason: str):
    """Anula la factura (no se borra) y devuelve el stock al inventario."""
    _request(server, "POST", f"/api/invoices/{invoice_id}/void", json={"reason": reason})


def add_payment(server: Server, invoice_id: str, amount: float, method: str, note: str = ""):
    return _request(server, "POST", f"/api/invoices/{invoice_id}/payments",
                    json={"amount": amount, "method": method, "note": note})


# ---------- resumen y copias de seguridad (administrador) ----------

def dashboard(server: Server, start: float, end: float, tz_offset_minutes: int):
    return _request(server, "GET", f"/api/dashboard?start={start}&end={end}&tz={tz_offset_minutes}")


def download_backup(server: Server) -> bytes:
    return _request(server, "GET", "/api/backup", raw=True)
