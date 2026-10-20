# Facturador — app de escritorio + servidor

App de escritorio en Python para generar facturas en PDF con el logo y los
datos de tu empresa, gestionar clientes y productos, y mantener un
historial de facturas. Todos los equipos que usen la app se conectan a un
**mismo servidor central** (en vez de compartir una carpeta), así que la
información está siempre centralizada y disponible desde cualquier lugar
con internet.

**Versión web:** el mismo servidor también sirve una versión web, así que
cualquiera puede trabajar desde el **celular** o desde cualquier navegador
entrando a `https://tuusuario.pythonanywhere.com` con su usuario y
contraseña, sin instalar nada. App de escritorio y versión web comparten los mismos datos.

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

La primera vez, pide la URL del servidor, tu usuario y tu contraseña, y
guarda la sesión en ese equipo (`~/.facturador/config.json`, sin guardar la
contraseña). Para entrar con otro usuario o a otro servidor usa
**"⚙ Cambiar servidor o usuario"** en la barra lateral.

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
  app.py              ventana principal, pestañas según el rol, cerrar sesión
  login.py            formulario de acceso (usuario/contraseña o clave maestra)
  tab_resumen.py       pestaña "Resumen" (solo administrador)
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
- **"Usuario o contraseña incorrectos"**: revísalos; tras 5 intentos fallidos
  el usuario se bloquea 5 minutos. Un administrador puede cambiarle la
  contraseña en la pestaña **Usuarios** de la versión web.
- **"Tu sesión terminó"**: el administrador te desactivó o cambió tu contraseña,
  o pasaron 30 días sin usar la app. Vuelve a entrar.
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
  cuánto hay disponible. Al anular una factura, el stock se restaura.
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

## 9. Usuarios, pagos, anulación, resumen y copias de seguridad

- **Usuarios y roles:** cada empleado entra con su usuario. El *vendedor*
  factura, cobra y consulta; el *administrador* además ve el resumen, anula
  facturas, maneja productos, proveedores, empresa, usuarios y copias. Cada
  factura y cada pago guardan quién los hizo. La clave de API pasa a ser la
  **clave maestra** del dueño (ver `server/DEPLOY.md`, paso 8).
- **Estado de pago:** al facturar se elige "Pagada ahora" o "A crédito" (con
  abono inicial opcional) y el método (efectivo, transferencia, tarjeta, otro).
  En Historial se registran los abonos y se filtra "Por cobrar".
- **Anular en vez de eliminar:** la factura queda en el historial con sello
  ANULADA en el PDF, motivo y quién la anuló; el stock vuelve al inventario y
  la numeración no tiene huecos.
- **Resumen de ventas** (administrador): ventas, ganancia estimada (usa el
  precio de costo guardado en cada venta), cobrado por método, cuentas por
  cobrar, productos más vendidos y ventas por vendedor; en la web con gráfica.
- **Copias de seguridad:** automáticas diarias en el servidor y descarga manual
  desde Mi empresa. Cómo restaurar: `server/DEPLOY.md`, paso 11.
