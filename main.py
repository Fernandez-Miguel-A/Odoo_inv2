from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from Odoo_inv2.database import InventoryDatabase
from Odoo_inv2.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Odoo Inventory")
    app.setOrganizationName("Odoo Inv2")
    window = MainWindow(InventoryDatabase())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
