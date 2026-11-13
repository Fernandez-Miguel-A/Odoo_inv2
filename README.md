# Odoo Inv

Aplicación de escritorio de facturación en PySide6, inspirada en la factura de
cliente de la imagen de referencia. Incluye una factura de demostración, cálculo
de descuentos e impuestos, almacenamiento local SQLite, registro de pagos,
notas de crédito, vista previa de impresión y paneles de resumen.

«Print & Send» publica la factura y abre la vista previa; desde allí se puede
imprimir o guardar como PDF. Esta versión no envía correos automáticamente.
El módulo de proveedores se muestra como pendiente; la aplicación se centra en
facturas de cliente.

## Requisitos

- Python 3.10 o posterior
- PySide6

## Instalar y ejecutar

Desde la raíz del proyecto:

```powershell
python -m pip install -r requirements.txt
python -m Odoo_inv
```

La aplicación guarda sus datos en `%LOCALAPPDATA%\Odoo_inv\invoices.sqlite3`
(o en `~/Odoo_inv/invoices.sqlite3` si `LOCALAPPDATA` no está definido).

## Pruebas

```powershell
python -m unittest discover -s Odoo_inv/tests -v
```

El paquete y todo el código fuente de la aplicación están en [Odoo_inv](./Odoo_inv).