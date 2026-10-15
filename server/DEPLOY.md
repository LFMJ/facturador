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
subir `app.py` y `requirements.txt`.

## 3. Cambiar la clave de API
Abre `app.py` (puedes editarlo directo en el navegador de PythonAnywhere) y
cambia esta línea por una clave secreta tuya:
```python
API_KEY = os.environ.get("FACTURADOR_API_KEY", "cambia-esta-clave")
```
Reemplaza `"cambia-esta-clave"` por algo largo y difícil de adivinar. Esta
es la clave que vas a compartir con tus empleados (junto con la URL) para
que sus apps de escritorio se conecten.

## 4. Instalar Flask
En el panel, abre una **"Bash console"** (pestaña "Consoles") y ejecuta:
```bash
pip install --user flask
```

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
Debería mostrar algo como `{"error":"Clave de API incorrecta o ausente."}`
— eso es correcto, significa que el servidor está vivo (solo falta la clave,
que la app de escritorio sí va a enviar).

## 8. Configurar la app de escritorio
En cada equipo, al abrir la app por primera vez (o desde "⚙ Cambiar
servidor"), ingresa:
- **URL del servidor:** `https://tuusuario.pythonanywhere.com`
- **Clave de API:** la que pusiste en el paso 3

## Límites del plan gratuito a tener en cuenta
- Espacio en disco limitado (~512 MB) — más que suficiente para años de
  facturas de una pyme (son solo texto).
- Cierto límite de tráfico saliente diario, sin relevancia para este uso.
- La cuenta gratuita puede requerir "reactivarse" con un clic cada 3 meses
  si no hay actividad — PythonAnywhere te avisa por correo antes.
