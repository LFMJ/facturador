# Facturador — app de escritorio + servidor

App de escritorio en Python para generar facturas en PDF con el logo y los
datos de tu empresa, gestionar clientes y productos, y mantener un
historial de facturas. Todos los equipos que usen la app se conectan a un
**mismo servidor central** (en vez de compartir una carpeta), así que la
información está siempre centralizada y disponible desde cualquier lugar
con internet.

**Versión web:** el mismo servidor también sirve una versión web, así que
cualquiera puede trabajar desde el **celular** o desde cualquier navegador
entrando a `https://tuusuario.pythonanywhere.com` con la clave de API, sin
instalar nada. App de escritorio y versión web comparten los mismos datos.

## 1. Desplegar el servidor (una sola vez, gratis)

Sigue `server/DEPLOY.md` para desplegar `server/app.py` gratis en
PythonAnywhere (no requiere tarjeta de crédito). Al final tendrás una URL
(`https://tuusuario.pythonanywhere.com`) y una clave de API — esos dos
datos son los que cada empleado ingresará en su app de escritorio.

## 2. Instalar y ejecutar la app de escritorio (cada equipo)

Necesitas Python 3.10 o superior.

```bash
pip install -r requirements.txt
python main.py
```

La primera vez, pide la URL del servidor y la clave de API, prueba la
conexión y guarda esos datos localmente (`~/.facturador/config.json`). Si
más adelante necesitas apuntar a otro servidor, usa el botón
**"⚙ Cambiar servidor"** en la barra lateral, sin salir de la app.

## 3. Empaquetar como ejecutable (.exe / .app) — opcional

Un ejecutable solo se puede generar **en el mismo sistema operativo en el
que se va a usar**.

### Windows
```powershell
pip install -r requirements.txt
python -m PyInstaller --noconfirm --windowed --name Facturador main.py
```
> Usa `python -m PyInstaller` (no solo `pyinstaller`) para evitar el error
> *"pyinstaller no se reconoce..."*, causado por el PATH de Windows.

El ejecutable queda en `dist/Facturador/Facturador.exe` — comparte toda la
carpeta `dist/Facturador`, no solo el `.exe` suelto. **Ejecuta el de
`dist`, no el de `build`** (esa carpeta son archivos intermedios, no la app
final).

### macOS
```bash
pip install -r requirements.txt
python -m PyInstaller --noconfirm --windowed --name Facturador main.py
```
Resultado en `dist/Facturador.app`.

## 4. Estructura del proyecto

```
facturador_app/
  main.py            punto de entrada + asistente de conexión al servidor
  app.py              ventana principal, navegación, cambiar servidor
  db.py                cliente HTTP hacia el servidor (antes hablaba con SQLite local)
  pdf_gen.py           generación del PDF de la factura (reportlab)
  config.py            URL/clave del servidor guardadas localmente por equipo
  theme.py              colores, fuentes y helpers de validación de UI
  tab_empresa.py       pestaña "Mi empresa" (datos + logo)
  tab_clientes.py       pestaña "Clientes"
  tab_productos.py      pestaña "Productos"
  tab_factura.py         pestaña "Nueva factura"
  tab_historial.py        pestaña "Historial"
  server/
    app.py               API (Flask) + versión web — la parte que se despliega en internet
    static/index.html    versión web para celular/navegador (servida en "/")
    requirements.txt
    DEPLOY.md            instrucciones de despliegue gratis en PythonAnywhere
```

## 5. Solución de problemas comunes

- **"No se pudo conectar con el servidor"**: revisa que la URL sea correcta
  (con `https://`, sin `/` al final) y que tengas internet. Prueba abrir
  la URL + `/api/ping` en el navegador.
- **"La clave de API no es correcta"**: revísala en "⚙ Cambiar servidor";
  debe ser exactamente igual a la que pusiste en `server/app.py`.
- **"El servidor no respondió a tiempo"**: si acabas de desplegar o hace
  mucho que nadie lo usa, puede tardar unos segundos en la primera
  petición. Intenta de nuevo.

## 6. Funciones agregadas: inventario, descuentos, garantía y vendedor

- **Proveedores**: pestaña nueva para registrar a quién le compras cada producto.
- **Productos**: ahora tienen proveedor, existencias (stock) y precio de costo.
  Botón "Reabastecer" para sumar stock sin editar el producto.
- **Nueva factura**: los artículos se eligen SIEMPRE desde el catálogo (no
  texto libre), para poder descontar el inventario automáticamente al
  facturar. Si no hay suficiente stock, la factura no se genera y te dice
  cuánto hay disponible. Al eliminar una factura, el stock se restaura.
- **Descuento por línea**: cada artículo de la factura admite un % de
  descuento independiente, editable en el momento (no es una tarifa fija).
- **Garantía** y **Vendedor**: dos campos nuevos al generar la factura,
  ambos opcionales, que se imprimen en el PDF.

## 7. Si ya tenías el servidor desplegado antes de esta versión

No hay que borrar nada: solo sube el nuevo `server/app.py` (reemplaza el
viejo) a PythonAnywhere y dale "Reload" en la pestaña "Web". La primera vez
que arranque, migra tu base de datos existente automáticamente (agrega las
columnas nuevas sin borrar clientes, productos ni facturas que ya tenías).

## 8. Versión web (celular)

- Se abre en la URL del servidor (`https://tuusuario.pythonanywhere.com`),
  pide la clave de API y tiene las mismas pestañas que la app de escritorio.
- El PDF lo genera el servidor (`/api/invoices/<id>/pdf`); en el celular se
  puede compartir directamente por WhatsApp/correo.
- Para actualizar un servidor ya desplegado: sube `server/app.py`,
  `server/static/` y `pdf_gen.py` (ver `server/DEPLOY.md`, paso 2) y dale
  "Reload". No hay cambios en la base de datos.
