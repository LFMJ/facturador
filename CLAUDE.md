# Facturador

App de escritorio en Python (CustomTkinter) para facturar en PDF, con un servidor Flask propio
donde se guarda todo. Interfaz y mensajes de error en **español**.

## Arquitectura

- **Cliente de escritorio** (raíz): `main.py` (asistente de conexión), `app.py` (ventana y navegación),
  una `tab_*.py` por pestaña (empresa, clientes, proveedores, productos, factura, historial).
- **`db.py`**: cliente HTTP hacia el servidor. Todas las funciones reciben un `Server(base_url, api_key, token)`.
  No hay SQL en el cliente. Los errores se lanzan como `db.DBError` con mensaje listo para mostrar al usuario.
- **`server/app.py`**: API Flask + SQLite (`facturador_server.db`). Desplegada en PythonAnywhere
  (ver `server/DEPLOY.md`). Todas las rutas `/api/*` (salvo `/api/login`) usan `@require_auth()` o
  `@require_auth(admin=True)`: aceptan `Authorization: Bearer <token>` (sesión de un usuario, tabla
  `sessions`, se guarda solo el sha256 del token) o `X-API-Key` (clave maestra = administrador). El
  usuario actual queda en `g.user`. Roles: `admin` y `vendedor`.
- **Copias de seguridad**: `auto_backup()` (before_request) guarda una por día en `backups/` (se conservan 14);
  `/api/backup` descarga una copia al momento (API de backup de SQLite, consistente con la app en uso).
- **Versión web**: `server/static/index.html` (HTML + JS sin frameworks ni build), servida en `/`. Usa la
  misma API con el token (o la clave maestra) guardado en `localStorage`. Todo texto del usuario va por `esc()` antes de `innerHTML`.
  El PDF lo genera el servidor en `/api/invoices/<id>/pdf` importando `pdf_gen.py` (que en PythonAnywhere
  se sube junto a `app.py`).
- **`pdf_gen.py`**: PDF con reportlab. Todo texto del usuario pasa por `_t()` (escape), porque `Paragraph`
  interpreta `<`, `>` y `&` como marcado. La fecha se formatea con `format_date_es` (no usar `strftime('%B')`,
  sale en inglés según el locale del sistema).
- **`config.py`**: guarda URL, token de sesión y último usuario en `~/.facturador/config.json` (por equipo;
  nunca la contraseña). `login.py` tiene el formulario de acceso; las pestañas visibles dependen del rol
  (`TABS` en `app.py`).

## Reglas de negocio importantes

- Los artículos de una factura se eligen **siempre desde el catálogo** (`product_id`), nunca texto libre.
- Al crear una factura el servidor descuenta stock (sumando líneas repetidas del mismo producto) y registra
  `stock_movements`; si no alcanza el stock responde 400 con el detalle.
- Las facturas **no se borran**: se anulan (`status='anulada'`, motivo, quién y cuándo) y el stock se
  restaura. `DELETE /api/invoices/<id>` también anula (compatibilidad con apps viejas).
- Pagos en la tabla `payments`. Estado calculado en `_with_totals`: pagada / abono / pendiente / anulada /
  sin_registro (`payment_tracking=0`: facturas anteriores al registro de pagos o de apps viejas).
- `invoice_items.unit_cost` guarda el costo al momento de vender (para la ganancia del resumen). El costo
  y la ganancia solo los ve el administrador.
- El descuento es **por línea, en %**, y se aplica antes del impuesto.
- La numeración (`FAC-0001`) la lleva el servidor (`company.invoice_counter`).
- Columnas nuevas en el servidor se agregan a la lista `MIGRATIONS` de `server/app.py` (ALTER TABLE
  idempotente) para no romper la base ya desplegada. No cambies el esquema sin añadir su migración.

## Comandos

```bash
pip install -r requirements.txt
python main.py                              # app de escritorio
cd server && FACTURADOR_API_KEY=test123 python -m flask --app app run --port 5050   # servidor local
python -m PyInstaller --noconfirm --windowed --name Facturador main.py              # .exe (en Windows)
```

- En Windows usar `python -m PyInstaller`, no `pyinstaller` (suele no estar en el PATH).
- El ejecutable válido está en `dist/Facturador/`, no en `build/`. Se reparte la carpeta completa.

## Pruebas

No hay suite automática. El servidor se puede probar con `app.test_client()` usando las variables
`FACTURADOR_DB` y `FACTURADOR_BACKUPS` para no tocar la base real. Para probar la GUI sin pantalla: `xvfb-run -a python3 script.py` con el servidor
local levantado **en el mismo comando** (cada llamada de shell es una sesión nueva). Conviene envolver con
`timeout`, porque una ventana modal abierta cuelga el proceso.

## Cuidado

- La clave de API por defecto en `server/app.py` es `cambia-esta-clave`; la real se define al desplegar
  y **no debe commitearse**.
- `*.db` está en `.gitignore`: no subir bases de datos con datos reales.
