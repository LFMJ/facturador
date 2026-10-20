# Facturador

Sistema de facturación web para una pyme: facturas en PDF con el logo de la
empresa, inventario, cobros, compras a proveedores, gastos, cierre de caja y
resumen de ventas. Funciona en el **celular, la tablet y el computador** desde
el navegador (se puede "instalar" como app), y todos los empleados trabajan
sobre los mismos datos en un servidor propio y gratuito (PythonAnywhere).

## Instalar el servidor

Sigue `server/DEPLOY.md` (despliegue gratis en PythonAnywhere, sin tarjeta de
crédito). Al final tendrás una dirección como `https://tuusuario.pythonanywhere.com`;
cada empleado entra ahí con su usuario y contraseña.

Para probarlo en tu computador:

```bash
cd server
pip install -r requirements.txt
FACTURADOR_API_KEY=clave-de-prueba python -m flask --app app run --port 5050
# abre http://127.0.0.1:5050 y entra con "Entrar con la clave maestra"
```

## Qué hace

- **Facturas**: los artículos salen del catálogo y descuentan el inventario;
  descuento por línea; pagada ahora o a crédito (con abono); PDF para descargar
  o compartir y **envío por WhatsApp** con un enlace a la factura.
- **Historial**: estado de pago (pagada, abono, pendiente), cobros, filtro
  "Por cobrar", **devoluciones parciales** (el stock vuelve y, si el cliente ya
  había pagado, se registra el dinero devuelto) y anulación (las facturas no se
  borran, para no dejar huecos en la numeración).
- **Clientes**: saldo de cada uno, **estado de cuenta** en PDF y **recordatorio
  de pago por WhatsApp**.
- **Productos** con **categorías**, existencias y costo.
- **Compras a proveedores**: la mercancía que llega suma al inventario y
  actualiza el costo (promedio ponderado); compras a crédito con abonos y
  saldo por pagar a cada proveedor.
- **Gastos** del negocio por categoría (arriendo, servicios, nómina…), que se
  restan para mostrar la **ganancia real**.
- **Cierre de caja** diario: cuánto debería haber por método de pago (cobros −
  devoluciones − pagos a proveedores − gastos + base) contra lo contado, por
  vendedor o de todos.
- **Resumen de ventas** (administrador): ventas, ganancia, gastos, ganancia
  real, cobrado, cuentas por cobrar y por pagar, productos más vendidos,
  vendedores y gráfica por día.
- **Usuarios** con rol de *administrador* o *vendedor*, y **registro de
  actividad**: quién creó, cambió, anuló o borró qué, y cuándo.
- **Copias de seguridad** automáticas diarias y descarga manual.

## Estructura

```
server/
  app.py            API (Flask + SQLite) y rutas de la versión web
  pdf_gen.py        PDF de facturas y estados de cuenta (reportlab)
  static/index.html la aplicación web (HTML + JavaScript, sin compilar)
  DEPLOY.md         instalación y actualización en PythonAnywhere
```

## App de escritorio

Hasta octubre de 2026 existió una app de escritorio (Python + CustomTkinter).
Se retiró para concentrar el trabajo en la versión web, que hace todo lo mismo
y más. Su código sigue en el historial de git (commit `abf58e9`) por si se
quiere volver a integrar.

## Problemas comunes

- **"Usuario o contraseña incorrectos"**: tras 5 intentos fallidos el usuario
  se bloquea 5 minutos. Un administrador puede cambiarle la contraseña en la
  pestaña **Usuarios**.
- **"Tu sesión terminó"**: el administrador te desactivó o cambió tu
  contraseña, o pasaron 30 días sin usarla. Vuelve a entrar.
- **La página muestra "Coming Soon" de PythonAnywhere**: venció el plan
  gratuito. En la pestaña **Web** toca "Run until 3 months from today" y
  **Reload**.
- **Facturación electrónica (DIAN)**: el PDF es un comprobante interno; no
  reemplaza la factura electrónica si tu negocio está obligado a emitirla.
