# Desplegar el servidor gratis en PythonAnywhere

PythonAnywhere tiene un plan gratuito ("Beginner") que no requiere tarjeta
de crédito, no se "duerme" (a diferencia de otros hosts gratis), y es
suficiente para que varios empleados usen el Facturador.

## 1. Crear la cuenta
Ve a https://www.pythonanywhere.com/registration/register/beginner/ y crea
una cuenta gratuita. Anota tu nombre de usuario: tu servidor quedará en
`https://tuusuario.pythonanywhere.com`.

## 2. Subir el código del servidor
En el panel de PythonAnywhere, abre la pestaña **"Files"** y sube el
contenido de la carpeta `server/` (arrástralos o usa "Upload a file") a una
carpeta nueva, por ejemplo `/home/tuusuario/facturador_server/`. Debes
subir:
- `app.py` y `requirements.txt` (de la carpeta `server/`)
- la carpeta **`static/`** completa (de `server/static/`: `index.html`,
  `manifest.webmanifest`, `icon.svg`) — es la versión web para celular
- **`pdf_gen.py`** (está en la raíz del proyecto, no en `server/`) — el
  servidor lo usa para generar los PDF de la versión web

Debe quedar así:
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

## 3. Poner tu clave maestra
Abre `app.py` (puedes editarlo directo en el navegador de PythonAnywhere) y
cambia esta línea por una clave secreta tuya:
```python
API_KEY = os.environ.get("FACTURADOR_API_KEY", "cambia-esta-clave")
```
Reemplaza `"cambia-esta-clave"` por algo largo y difícil de adivinar. Esta es
la **clave maestra**: da acceso total y es **solo para ti** (el dueño). No se
la des a los empleados: cada uno tendrá su propio usuario (paso 8).

## 4. Instalar dependencias
En el panel, abre una **"Bash console"** (pestaña "Consoles") y ejecuta:
```bash
pip install --user flask reportlab pillow
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
import sys
path = '/home/tuusuario/facturador_server'
if path not in sys.path:
    sys.path.append(path)

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
- **Vendedor:** hace facturas, registra pagos, ve el historial, consulta
  productos y crea/edita clientes.
- **Administrador:** todo lo anterior, más Resumen de ventas (con ganancias),
  anular facturas, productos, proveedores, datos de la empresa, copias de
  seguridad y usuarios.

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

## 10. Configurar la app de escritorio
En cada equipo, al abrir la app escribe la **URL del servidor**
(`https://tuusuario.pythonanywhere.com`), tu **usuario** y tu **contraseña**.
La app recuerda la sesión en ese equipo hasta que toques "Cerrar sesión".

## 11. Copias de seguridad
- **Automáticas:** el servidor guarda una copia por día en la carpeta
  `backups/` (junto a `app.py`) y conserva las últimas 14.
- **Manuales (recomendado una vez por semana):** en **Mi empresa → Copias de
  seguridad → "Descargar copia ahora"** (web o escritorio). Guarda ese archivo
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
Sube los archivos nuevos (`app.py`, `pdf_gen.py` y la carpeta `static/`)
reemplazando los viejos y dale **"Reload"**. **No se borra nada**: la base de
datos se actualiza sola la primera vez (agrega las columnas y tablas nuevas).
Después sigue el paso 8 para crear los usuarios.

- Las facturas que ya existían quedan como **"Sin registro de pago"** (no se
  marcan como pagadas ni como pendientes porque no se sabe). Si quieres, desde
  Historial → Detalle puedes registrarles el pago.
- La clave que usaban todos pasa a ser la **clave maestra**. Cuando cada
  empleado tenga su usuario, **cámbiala** (paso 3) para que nadie más la use.
- Las apps de escritorio viejas siguen funcionando con esa clave hasta que la
  cambies; actualízalas a la nueva versión para que pidan usuario y contraseña.
- Las facturas ya no se eliminan: se **anulan** (quedan en el historial con un
  sello de ANULADA y el stock vuelve al inventario), para no dejar huecos en
  la numeración.

## Límites del plan gratuito a tener en cuenta
- Espacio en disco limitado (~512 MB) — más que suficiente para años de
  facturas de una pyme (son solo texto).
- Cierto límite de tráfico saliente diario, sin relevancia para este uso.
- La cuenta gratuita puede requerir "reactivarse" con un clic cada 3 meses
  si no hay actividad — PythonAnywhere te avisa por correo antes.
