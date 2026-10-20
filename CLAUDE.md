# Facturador

Sistema de facturación **web** (celular y computador) con un servidor Flask + SQLite propio, desplegado en
PythonAnywhere. Interfaz y mensajes de error en **español**. La app de escritorio (CustomTkinter) se retiró;
su código está en el historial de git (commit `abf58e9`) por si se vuelve a integrar.

## Arquitectura

- **`server/app.py`**: toda la API y las rutas de la web. Todas las rutas `/api/*` (salvo `/api/login`) usan
  `@require_auth()` o `@require_auth(admin=True)`: aceptan `Authorization: Bearer <token>` (sesión de un
  usuario, tabla `sessions`, se guarda solo el sha256 del token) o `X-API-Key` (clave maestra = administrador).
  El usuario actual queda en `g.user`. Roles: `admin` y `vendedor`.
- **`server/static/index.html`**: la aplicación web (HTML + JS sin frameworks ni build). Una función
  `views.<pestaña>` por pestaña; `ALL_TABS` define cuáles ve cada rol. Todo texto del usuario va por `esc()`
  antes de `innerHTML`. Diálogos con `openForm()` (formularios) y `showDialog()` (contenido libre); para
  encadenar un diálogo tras otro usar `await closeModal(dlg)`, no `dlg.close()`.
- **`server/pdf_gen.py`**: PDF de factura y de estado de cuenta (reportlab). Todo texto del usuario pasa por
  `_t()` (escape), porque `Paragraph` interpreta `<`, `>` y `&` como marcado. Fechas con `format_date_es`
  (no `strftime('%B')`, sale en inglés).
- **WhatsApp**: `whatsappPdf()` en la web envía el PDF **como archivo adjunto** con `navigator.share({files})`
  (menú "Compartir" del celular; el PDF se descarga antes de mostrar el botón porque `share` exige un toque
  reciente). Si el navegador no puede compartir archivos, descarga el PDF y abre `wa.me/<número>` con un
  texto (el indicativo sale de `company.phone_country`). No se envían enlaces a la página: no hay rutas
  públicas para ver facturas (la columna `invoices.public_token` quedó sin uso).
- **Copias de seguridad**: `auto_backup()` (before_request) guarda una por día en `backups/` (se conservan 14);
  `/api/backup` descarga una copia al momento (API de backup de SQLite).
- **Registro de actividad**: `log(conn, entidad, id, resumen)` dentro de la misma transacción de cada cambio.
  Toda ruta nueva que modifique datos debe registrar su actividad.

## Reglas de negocio importantes

- Los artículos de una factura se eligen **siempre desde el catálogo** (`product_id`), nunca texto libre.
- Al facturar se descuenta stock (sumando líneas repetidas del mismo producto); si no alcanza responde 400.
- Las facturas **no se borran**: se anulan (`status='anulada'`) y se restaura el stock no devuelto antes.
  Si el cliente había pagado, se registra un pago **negativo** por el neto pagado, con la fecha de la anulación
  (así la caja de ese día descuenta el dinero y la del día de la venta no cambia). Igual al anular una compra
  pagada (`supplier_payments` negativo = el proveedor devuelve). `_fix_voided_without_refund()` corrige al
  arrancar los registros anulados antes de esta regla. `DELETE /api/invoices/<id>` también anula.
- **Devoluciones parciales** (`returns` / `return_items`): suben el stock y bajan el total de la factura
  (`total` = facturado − devuelto; `original_total` = facturado). Si el cliente ya había pagado más que el
  nuevo total, se registra un pago **negativo** (dinero devuelto).
- Pagos en `payments`. Estado calculado en `_with_totals`: pagada / abono / pendiente / anulada / devuelta /
  sin_registro (`payment_tracking=0`: facturas anteriores al registro de pagos).
- **Compras** (`purchases`): suman stock y recalculan `products.cost_price` con promedio ponderado. Pagos al
  proveedor en `supplier_payments`. Anular una compra exige que el stock alcance para restarla.
- `invoice_items.unit_cost` guarda el costo al vender (para la ganancia). Costo y ganancia solo los ve el admin.
- **Cierre de caja**: esperado por método = cobros − dinero devuelto a clientes − pagos a proveedores + dinero
  devuelto por proveedores − gastos (+ base en efectivo), filtrado por `user_id`. Un cierre por día y por persona (o "todos"). El vendedor solo ve su caja.
- Descuento por línea en %, antes del impuesto. Numeración `FAC-0001` y `COM-0001` en `company`.
- Columnas nuevas se agregan a `MIGRATIONS` en `server/app.py` (ALTER TABLE idempotente) para no romper la
  base desplegada. No cambies el esquema sin añadir su migración.

## Comandos

```bash
cd server && pip install -r requirements.txt
FACTURADOR_API_KEY=test123 python -m flask --app app run --port 5050   # http://127.0.0.1:5050
```

## Pruebas

No hay suite en el repositorio. El servidor se prueba con `app.test_client()` usando las variables
`FACTURADOR_DB` y `FACTURADOR_BACKUPS` para no tocar la base real. La web se prueba con Playwright contra el
servidor local (levantarlo **en el mismo comando** de shell; cada llamada es una sesión nueva).

## Despliegue (PythonAnywhere)

- Se sube el contenido de `server/` a `/home/<usuario>/facturador_server/` y se da "Reload" (ver
  `server/DEPLOY.md`). La base se migra sola al arrancar.
- La clave maestra va en el archivo WSGI (`os.environ["FACTURADOR_API_KEY"]`), **nunca** en el repositorio.
  El WSGI debe hacer `sys.path.insert(0, ...)`: en `/home/<usuario>/` puede haber un `app.py` viejo.
- `*.db` y `backups/` están en `.gitignore`: no subir bases de datos con datos reales.
