# Odoo Inv2

Aplicación de inventario y reabastecimiento de escritorio en PySide6, inspirada
en la vista de inventario de la imagen de referencia. Incluye árbol de
ubicaciones, filtros por ubicación y tipo de regla, selección múltiple, reglas
de reabastecimiento, órdenes locales, snooze y resúmenes.

## Requisitos

- Python 3.10 o posterior
- PySide6

## Instalar y ejecutar

Desde la raíz del proyecto:

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 main.py
```

La aplicación guarda el inventario exclusivamente en
`data/inventory.sqlite3`, dentro de la raíz del proyecto. Esta ruta no depende
de `LOCALAPPDATA` ni del directorio personal del usuario.
La primera ejecución crea productos, ubicaciones y existencias de demostración.

«Order Once» y «Order» crean órdenes de reabastecimiento locales y actualizan
las cantidades entrantes previstas. No conectan con proveedores externos ni
envían órdenes a una instancia de Odoo. La regla «Auto» se guarda como
configuración del producto; no inicia un servicio automático en segundo plano.

## Pruebas

```powershell
py -3.13 -m unittest discover -s Odoo_inv2/tests -v
```

El paquete y el código fuente están en [Odoo_inv2](./Odoo_inv2).