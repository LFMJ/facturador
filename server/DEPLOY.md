# Desplegar el servidor gratis en PythonAnywhere

PythonAnywhere tiene un plan gratuito ("Beginner") que no requiere tarjeta
de crédito, no se "duerme" (a diferencia de otros hosts gratis), y es
suficiente para que varios empleados usen el Facturador.

## 1. Crear la cuenta
Ve a https://www.pythonanywhere.com/registration/register/beginner/ y crea
una cuenta gratuita. Anota tu nombre de usuario: tu servidor quedará en
`https://tuusuario.pythonanywhere.com`.

## 2. Subir el código del servidor
En el panel de PythonAnywhere, abre la pestaña **"Files"** y sube **todo el
contenido de la carpeta `server/`** a una carpeta nueva, por ejemplo
`/home/tuusuario/facturador_server/`. Debe quedar así:
```
/home/tuusuario/facturador_server/
  app.py
  pdf_gen.py
  requirements.txt
  static/
    index.html
    manifest.webmanifest
    icon.svg
```

## 3. Elegir tu clave maestra
Inventa una clave larga y difícil de adivinar (por ejemplo, 30 letras y
números al azar). Esta es la **clave maestra**: da acceso total y es **solo
para ti** (el dueño). No se la des a los empleados: cada uno tendrá su propio
usuario (paso 8). Se escribe en el archivo WSGI (paso 5), **no** en `app.py`,
para que nunca termine en GitHub.

## 4. Instalar dependencias
En el panel, abre una **"Bash console"** (pestaña "Consoles") y ejecuta:
```bash
pip install --user flask reportlab pillow openpyxl
```
(Normalmente ya vienen instaladas en PythonAnywhere; si dice
"Requirement already satisfied", está bien.)

## 5. Crear la "Web app"
En la pestaña **"Web"**, clic en **"Add a new web app"**:
- Dominio: acepta el que te ofrecen (`tuusuario.pythonanywhere.com`).
- Framework: elige **"Flask"**.
- Versión de Python: la más reciente disponible (3.10 o superior).
- Ruta del proyecto: elige la carpeta donde subiste `app.py`
  (`/home/tuusuario/facturador_server/`).

PythonAnywhere genera automáticamente un archivo `flask_app.py` o similar,
y un archivo de configuración WSGI. Abre el **"WSGI configuration file"**
(el enlace aparece en la misma pestaña "Web") y reemplaza su contenido para
que apunte a tu `app.py`, algo así:

```python
import os
import sys

# Clave maestra (paso 3). Para cambiarla, edita esta línea y dale "Reload".
os.environ["FACTURADOR_API_KEY"] = "pon-aqui-tu-clave-maestra"

path = '/home/tuusuario/facturador_server'
if path in sys.path:
    sys.path.remove(path)
sys.path.insert(0, path)  # de primera, para que no cargue otro app.py

from app import app as application
```
(Ajusta `tuusuario` por tu usuario real.)

## 6. Recargar
Vuelve a la pestaña "Web" y haz clic en el botón verde **"Reload"**.

## 7. Probar
Abre en el navegador:
```
https://tuusuario.pythonanywhere.com/api/ping
```
Debería mostrar algo como `{"error":"Sesión vencida o datos de acceso incorrectos..."}`
— eso es correcto, significa que el servidor está vivo.

## 8. Crear los usuarios (una sola vez)
1. Abre `https://tuusuario.pythonanywhere.com` en el navegador.
2. Toca **"Entrar con la clave maestra (dueño)"** y escribe la clave del paso 3.
3. Ve a la pestaña **Usuarios** y crea:
   - **tu propio usuario administrador** (para el día a día, en vez de la clave maestra);
   - un usuario **vendedor** para cada empleado.
4. Toca **Salir** y entra con tu usuario nuevo.

Roles:
- **Vendedor:** hace facturas, cobra, las envía por WhatsApp, ve el historial y
  los estados de cuenta, maneja clientes, consulta productos, registra gastos de
  caja chica y cierra **su propia** caja.
- **Administrador:** todo lo anterior, más Resumen de ventas (con ganancias),
  devoluciones, anular facturas, compras, productos, proveedores, gastos de
  todos, la caja de todos, datos de la empresa, copias de seguridad, usuarios y
  el registro de Actividad.

Si alguien deja la empresa o pierde el celular: en **Usuarios → Editar**,
desmarca "Usuario activo" (o cámbiale la contraseña). Su sesión se cierra en
todos sus dispositivos al instante, sin afectar a los demás.

## 9. Usar la versión web (celular, tablet o cualquier computador)
Cada persona abre `https://tuusuario.pythonanywhere.com` y entra con su
usuario y contraseña. El navegador recuerda la sesión hasta que toque **"Salir"**
(o 30 días sin usarla).

**Instalarla como app en el celular** (opcional): en Android/Chrome, menú
⋮ → "Agregar a la pantalla principal"; en iPhone/Safari, botón Compartir →
"Agregar a inicio". Queda un ícono como si fuera una app.

En el computador también se puede "instalar": en Chrome o Edge, ícono de
**Instalar** en la barra de direcciones (o menú ⋮ → "Instalar Facturador").

## 10. Copias de seguridad
- **Automáticas:** el servidor guarda una copia por día en la carpeta
  `backups/` (junto a `app.py`) y conserva las últimas 14.
- **Manuales (recomendado una vez por semana):** en **Mi empresa → Copias de
  seguridad → "Descargar copia ahora"**. Guarda ese archivo
  `.db` en tu computador o en Google Drive: las copias automáticas viven en el
  mismo servidor, así que no sirven si pierdes la cuenta de PythonAnywhere.

**Restaurar una copia** (solo si se dañó o se borró la información):
1. En PythonAnywhere, pestaña **"Web"**, toca **"Disable"** (apaga la app).
2. En **"Files"**, entra a la carpeta del servidor, renombra
   `facturador_server.db` a `facturador_server-danado.db` (por si acaso).
3. Sube tu copia (`facturador-copia-....db` o una de `backups/`) y renómbrala
   a `facturador_server.db`.
4. En **"Web"**, toca **"Enable"** y luego **"Reload"**.

## Si ya tenías el servidor funcionando (actualizar)
Sube los archivos de `server/` (`app.py`, `pdf_gen.py` y la carpeta `static/`)
reemplazando los viejos y dale **"Reload"**. **No se borra nada**: la base de
datos se actualiza sola la primera vez que arranca (agrega las columnas y
tablas nuevas). Antes de actualizar, descarga una copia de seguridad.

- Si en la carpeta de inicio (`/home/tuusuario/`) quedó un `app.py` viejo, el
  archivo WSGI debe poner la carpeta del servidor **de primera** en `sys.path`
  (con `sys.path.insert(0, path)`, como en el paso 5); si no, Python carga el
  viejo.
- Las facturas de antes del registro de pagos quedan como **"Sin registro de
  pago"**; desde Historial → Detalle se les puede registrar el pago.
- Las facturas viejas se enlazan solas con su cliente (mismo nombre y
  documento) para que aparezcan en su estado de cuenta.

## Límites del plan gratuito a tener en cuenta
- Espacio en disco limitado (~512 MB) — más que suficiente para años de
  facturas de una pyme (son solo texto).
- Cierto límite de tráfico saliente diario, sin relevancia para este uso.
- La cuenta gratuita puede requerir "reactivarse" con un clic cada 3 meses
  si no hay actividad — PythonAnywhere te avisa por correo antes.
