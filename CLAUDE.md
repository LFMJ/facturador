# Facturador

App de escritorio en Python (CustomTkinter) para facturar en PDF, con un servidor Flask propio
donde se guarda todo. Interfaz y mensajes de error en **español**.

## Arquitectura

- **Cliente de escritorio** (raíz): `main.py` (asistente de conexión), `app.py` (ventana y navegación),
  una `tab_*.py` por pestaña (empresa, clientes, proveedores, productos, factura, historial).
- **`db.py`**: cliente HTTP hacia el servidor. Todas las funciones reciben un `Server(base_url, api_key)`.
  No hay SQL en el cliente. Los errores se lanzan como `db.DBError` con mensaje listo para mostrar al usuario.
- **`server/app.py`**: API Flask + SQLite (`facturador_server.db`). Desplegada en PythonAnywhere
  (ver `server/DEPLOY.md`). Todas las rutas exigen el header `X-API-Key`.
- **`pdf_gen.py`**: PDF con reportlab. La fecha se formatea con `format_date_es` (no usar `strftime('%B')`,
  sale en inglés según el locale del sistema).
- **`config.py`**: guarda URL y clave en `~/.facturador/config.json` (por equipo).

## Reglas de negocio importantes

- Los artículos de una factura se eligen **siempre desde el catálogo** (`product_id`), nunca texto libre.
- Al crear una factura el servidor descuenta stock y registra `stock_movements`; si no alcanza el stock
  responde 400 con el detalle. Al eliminar la factura el stock se restaura.
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

No hay suite automática. Para probar la GUI sin pantalla: `xvfb-run -a python3 script.py` con el servidor
local levantado **en el mismo comando** (cada llamada de shell es una sesión nueva). Conviene envolver con
`timeout`, porque una ventana modal abierta cuelga el proceso.

## Cuidado

- La clave de API por defecto en `server/app.py` es `cambia-esta-clave`; la real se define al desplegar
  y **no debe commitearse**.
- `*.db` está en `.gitignore`: no subir bases de datos con datos reales.
