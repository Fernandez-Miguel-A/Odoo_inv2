# Odoo Inv2

Aplicacion tipo Odoo, segundo programa

## Requisitos

- Python 3.10 o posterior
- PySide6

## Instalar y ejecutar

Desde la raíz del proyecto:

```powershell
python -m pip install -r requirements.txt
python -m Odoo_inv2
```

La aplicación guarda sus datos en `%LOCALAPPDATA%\Odoo_inv2\invoices.sqlite3`
(o en `~/Odoo_inv/invoices.sqlite3` si `LOCALAPPDATA` no está definido).

## Pruebas

```powershell
python -m unittest discover -s Odoo_inv2/tests -v
```

El paquete y todo el código fuente de la aplicación están en [Odoo_inv2](./Odoo_inv2).