from __future__ import annotations

import html
import sqlite3
from collections import defaultdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Odoo_inv2.database import InventoryDatabase
from Odoo_inv2.models import Location, Replenishment


PURPLE = "#714b67"
TEAL = "#087c86"
PALE_BLUE = "#d9eff2"


def quantity(value: float) -> str:
    return f"{value:,.2f}"


class MainWindow(QMainWindow):
    def __init__(self, database: InventoryDatabase) -> None:
        super().__init__()
        self.database = database
        self.location_filter: int | None = None
        self.trigger_filter = "all"
        self.current_rows: list[Replenishment] = []
        self._locations: list[Location] = []
        self._populating_table = False
        self.setWindowTitle("Odoo Inventory | Replenishment")
        self.resize(1420, 850)
        self.setMinimumSize(980, 650)
        self.setStyleSheet(self._style_sheet())
        self._build_ui()
        self._populate_location_tree()
        self.refresh()

    @staticmethod
    def _style_sheet() -> str:
        return """
            QWidget {
                color: #242a35;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }
            QMainWindow, QStackedWidget, QScrollArea,
            QScrollArea > QWidget > QWidget {
                background: #f7f8fa;
            }
            QFrame#topBar, QFrame#sideBar {
                background: #ffffff;
                border: none;
                border-bottom: 1px solid #e1e4e8;
            }
            QFrame#sideBar { border-right: 1px solid #e1e4e8; }
            QFrame#contentCard, QFrame#statCard {
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
            }
            QLabel#appMark {
                color: white; background: #714b67; border-radius: 4px;
                padding: 5px 8px; font-weight: 700;
            }
            QLabel#appTitle { font-size: 16px; font-weight: 600; }
            QLabel#sectionTitle { font-size: 22px; font-weight: 600; }
            QLabel#sectionCaption, QLabel#muted { color: #737b86; }
            QLabel#filterTitle {
                color: #626a75; font-size: 11px; font-weight: 700;
            }
            QLabel#productCode { color: #087c86; font-weight: 600; }
            QLabel#statValue { color: #714b67; font-size: 23px; font-weight: 700; }
            QPushButton {
                background: #f0f2f5; border: 1px solid #dfe3e8;
                border-radius: 4px; padding: 7px 11px;
            }
            QPushButton:hover { background: #e7eaee; }
            QPushButton#primaryButton {
                color: white; background: #714b67; border-color: #714b67;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover { background: #5e3d55; }
            QPushButton#navButton {
                background: transparent; border: none; padding: 9px 10px;
            }
            QPushButton#navButton:checked {
                color: #714b67; border-bottom: 2px solid #714b67;
                font-weight: 600;
            }
            QPushButton#linkButton {
                color: #087c86; background: transparent; border: none;
                text-align: left; padding: 3px 1px;
            }
            QPushButton#rowAction {
                color: #087c86; background: transparent;
                border: none; padding: 4px 3px; font-size: 11px;
            }
            QPushButton#rowAction:hover {
                background: #eaf5f6; border-radius: 3px;
            }
            QPushButton#filterButton {
                background: transparent; border: none;
                text-align: left; padding: 5px 9px;
            }
            QPushButton#filterButton:checked {
                background: #e8f3f4; color: #087c86; font-weight: 600;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                background: white; border: 1px solid #cfd4dc;
                border-radius: 3px; padding: 6px;
            }
            QTreeWidget {
                background: white; border: none;
                outline: none; selection-background-color: #e8f3f4;
            }
            QTableWidget {
                background: white; border: 1px solid #dfe3e8;
                gridline-color: #e7e9ed;
                selection-background-color: #d9eff2;
                alternate-background-color: #fbfbfc;
            }
            QHeaderView::section {
                background: #fbfbfc; border: none;
                border-bottom: 1px solid #dfe3e8;
                color: #39414d; font-weight: 600; padding: 9px 7px;
            }
            QStatusBar { background: #fff; border-top: 1px solid #e1e4e8; }
        """

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        top = QFrame()
        top.setObjectName("topBar")
        nav = QHBoxLayout(top)
        nav.setContentsMargins(22, 6, 20, 6)
        mark = QLabel("◆")
        mark.setObjectName("appMark")
        nav.addWidget(mark)
        title = QLabel("Inventory")
        title.setObjectName("appTitle")
        nav.addWidget(title)
        nav.addSpacing(8)
        self.pages = QStackedWidget()
        self._nav_buttons: dict[str, QPushButton] = {}
        self._page_names = [
            "Inventory",
            "Overview",
            "Operations",
            "Products",
            "Reporting",
            "Configuration",
        ]
        for index, name in enumerate(self._page_names):
            button = QPushButton(name)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, page_index=index: self._navigate(page_index)
            )
            nav.addWidget(button)
            self._nav_buttons[name] = button
        nav.addStretch(1)
        self.company_label = QLabel(
            self.database.get_setting("company_name", "A")
        )
        self.company_label.setToolTip("Company")
        nav.addWidget(self.company_label)
        root_layout.addWidget(top)

        self._build_replenishment_page()
        self._build_overview_page()
        self._build_operations_page()
        self._build_products_page()
        self._build_reporting_page()
        self._build_configuration_page()
        root_layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Inventory ready")
        self._navigate(0)

    def _build_replenishment_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(9)

        toolbar = QHBoxLayout()
        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self._new_stock_item)
        toolbar.addWidget(self.new_button)
        order_button = QPushButton("Order")
        order_button.setObjectName("primaryButton")
        order_button.setToolTip("Create replenishment orders for selected rows.")
        order_button.clicked.connect(self._order_selected)
        toolbar.addWidget(order_button)
        snooze_button = QPushButton("Snooze")
        snooze_button.clicked.connect(self._snooze_selected)
        toolbar.addWidget(snooze_button)
        max_button = QPushButton("Order To Max")
        max_button.clicked.connect(self._order_all_to_max)
        toolbar.addWidget(max_button)
        toolbar.addWidget(self._label("Replenishment", "sectionTitle"))
        toolbar.addStretch(1)
        self.selection_label = QLabel("0 selected")
        self.selection_label.setObjectName("muted")
        toolbar.addWidget(self.selection_label)
        self.actions_button = QPushButton("⚙ Actions")
        self.actions_button.setMenu(self._create_actions_menu())
        toolbar.addWidget(self.actions_button)
        layout.addLayout(toolbar)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.addWidget(self._build_sidebar())

        table_panel = QWidget()
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(5)
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("Search products or locations…")
        self.search_edit.textChanged.connect(self.refresh)
        search_row.addWidget(self.search_edit)
        self.result_label = QLabel("")
        self.result_label.setObjectName("muted")
        search_row.addWidget(self.result_label)
        table_layout.addLayout(search_row)
        self.replenishment_table = QTableWidget(0, 10)
        self.replenishment_table.setObjectName("replenishmentTable")
        self.replenishment_table.setHorizontalHeaderLabels(
            [
                "",
                "Product",
                "Location",
                "On Hand",
                "Forecast",
                "Route",
                "Min",
                "Max",
                "To Order",
                "Actions",
            ]
        )
        self.replenishment_table.setAlternatingRowColors(True)
        self.replenishment_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.replenishment_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.replenishment_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.replenishment_table.verticalHeader().setVisible(False)
        self.replenishment_table.verticalHeader().setDefaultSectionSize(38)
        self.replenishment_table.itemChanged.connect(self._selection_changed)
        header = self.replenishment_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.replenishment_table.setColumnWidth(0, 34)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.replenishment_table.setColumnWidth(2, 170)
        for col, width in ((3, 78), (4, 78), (5, 95), (6, 60), (7, 60), (8, 84)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.replenishment_table.setColumnWidth(col, width)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        self.replenishment_table.setColumnWidth(9, 235)
        table_layout.addWidget(self.replenishment_table, 1)
        split.addWidget(table_panel)
        split.setSizes([200, 1180])
        layout.addWidget(split, 1)
        self.pages.addWidget(page)

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sideBar")
        panel.setMinimumWidth(178)
        panel.setMaximumWidth(260)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        layout.addWidget(self._label("▣  LOCATIONS", "filterTitle"))
        all_locations = QPushButton("All")
        all_locations.setObjectName("filterButton")
        all_locations.clicked.connect(lambda: self._set_location_filter(None))
        layout.addWidget(all_locations)
        self.location_tree = QTreeWidget()
        self.location_tree.setHeaderHidden(True)
        self.location_tree.itemClicked.connect(self._location_clicked)
        layout.addWidget(self.location_tree, 1)

        layout.addWidget(self._label("▣  TRIGGER", "filterTitle"))
        self.trigger_buttons: dict[str, QPushButton] = {}
        for key, label in (("all", "All"), ("auto", "Auto"), ("manual", "Manual")):
            button = QPushButton(label)
            button.setObjectName("filterButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, trigger=key: self._set_trigger_filter(trigger)
            )
            self.trigger_buttons[key] = button
            layout.addWidget(button)
        layout.addStretch(1)
        return panel

    def _create_actions_menu(self):
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.addAction("Select all", self._select_all)
        menu.addAction("Clear selection", self._clear_selection)
        menu.addSeparator()
        menu.addAction("Set selected to Auto", lambda: self._set_selected_trigger("auto"))
        menu.addAction(
            "Set selected to Manual", lambda: self._set_selected_trigger("manual")
        )
        menu.addAction("Snooze selected for 7 days", self._snooze_selected)
        return menu

    @staticmethod
    def _label(text: str, object_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        return label

    def _build_overview_page(self) -> None:
        page, layout = self._page_container(
            "Inventory Overview", "A summary of stock and replenishment needs."
        )
        self.overview_cards = QHBoxLayout()
        layout.addLayout(self.overview_cards)
        heading = self._label("Products to Replenish", "sectionTitle")
        layout.addWidget(heading)
        self.overview_table = self._data_table(
            ["Product", "Location", "Forecast", "To Order", "Trigger"]
        )
        layout.addWidget(self.overview_table, 1)
        button = QPushButton("Open Replenishment")
        button.clicked.connect(lambda: self._navigate(0))
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        self.pages.addWidget(page)

    def _build_operations_page(self) -> None:
        page, layout = self._page_container(
            "Operations", "Replenishment orders created from your stock rules."
        )
        self.orders_table = self._data_table(
            ["Reference", "Product", "Location", "Quantity", "Route", "Status", "Created"]
        )
        layout.addWidget(self.orders_table, 1)
        self.pages.addWidget(page)

    def _build_products_page(self) -> None:
        page, layout = self._page_container(
            "Products", "Product catalog with stock totals across locations."
        )
        self.products_table = self._data_table(
            ["Internal Reference", "Product", "Locations", "On Hand", "Reserved", "Incoming"]
        )
        layout.addWidget(self.products_table, 1)
        self.pages.addWidget(page)

    def _build_reporting_page(self) -> None:
        page, layout = self._page_container(
            "Reporting", "Stock and replenishment metrics grouped by trigger."
        )
        self.reporting_table = self._data_table(
            ["Trigger", "Locations", "Products to Replenish", "Total To Order"]
        )
        layout.addWidget(self.reporting_table, 1)
        self.pages.addWidget(page)

    def _build_configuration_page(self) -> None:
        page, layout = self._page_container(
            "Configuration", "Set the company name shown in the navigation bar."
        )
        card = QFrame()
        card.setObjectName("contentCard")
        form = QFormLayout(card)
        form.setContentsMargins(20, 20, 20, 20)
        self.company_edit = QLineEdit(
            self.database.get_setting("company_name", "A")
        )
        form.addRow("Company Name", self.company_edit)
        save = QPushButton("Save Configuration")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save_configuration)
        form.addRow("", save)
        layout.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
        layout.addStretch(1)
        self.pages.addWidget(page)

    @staticmethod
    def _page_container(title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(MainWindow._label(title, "sectionTitle"))
        layout.addWidget(MainWindow._label(subtitle, "sectionCaption"))
        return page, layout

    @staticmethod
    def _data_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _navigate(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        name = self._page_names[index]
        for page_name, button in self._nav_buttons.items():
            button.setChecked(page_name == name)
        self.refresh()

    def _populate_location_tree(self) -> None:
        self._locations = self.database.list_locations()
        self.location_tree.clear()
        all_rows = self.database.list_replenishments()
        counts: dict[int, int] = defaultdict(int)
        for row in all_rows:
            counts[row.location_id] += 1
        all_item = QTreeWidgetItem([f"All  {len(all_rows)}"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, None)
        self.location_tree.addTopLevelItem(all_item)
        physical = QTreeWidgetItem(["Physical Locations"])
        physical.setFlags(physical.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.location_tree.addTopLevelItem(physical)

        items_by_id: dict[int, QTreeWidgetItem] = {}
        for location in self._locations:
            count = counts[location.id]
            item = QTreeWidgetItem([f"{location.name}  {count}"])
            item.setData(0, Qt.ItemDataRole.UserRole, location.id)
            if location.parent_id in items_by_id:
                items_by_id[location.parent_id].addChild(item)
            else:
                physical.addChild(item)
            items_by_id[location.id] = item
        self.location_tree.expandAll()
        self.location_tree.setCurrentItem(all_item)
        self._set_trigger_filter(self.trigger_filter)

    def _location_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        location_id = item.data(0, Qt.ItemDataRole.UserRole)
        if location_id is not None:
            self.location_filter = int(location_id)
        else:
            self.location_filter = None
        self.refresh()

    def _set_location_filter(self, location_id: int | None) -> None:
        self.location_filter = location_id
        self.location_tree.clearSelection()
        self.refresh()

    def _set_trigger_filter(self, trigger: str) -> None:
        self.trigger_filter = trigger
        for key, button in self.trigger_buttons.items():
            button.setChecked(key == trigger)
        if hasattr(self, "current_rows"):
            self.refresh()

    def refresh(self, *_args: object) -> None:
        if not hasattr(self, "replenishment_table"):
            return
        self.current_rows = self.database.list_replenishments(
            location_id=self.location_filter,
            trigger=self.trigger_filter,
            search=self.search_edit.text(),
        )
        self._populate_replenishment_table()
        self._refresh_summary_pages()

    def _populate_replenishment_table(self) -> None:
        table = self.replenishment_table
        self._populating_table = True
        table.setRowCount(len(self.current_rows))
        checked_count = 0
        for row_index, stock in enumerate(self.current_rows):
            check = QTableWidgetItem()
            check.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            check.setCheckState(Qt.CheckState.Unchecked)
            check.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_index, 0, check)

            product = QLabel(
                f'<span style="color:{TEAL};font-weight:600">'
                f"[{html.escape(stock.sku)}]</span> "
                f"{html.escape(stock.product_name)}"
            )
            product.setToolTip(f"{stock.sku} — {stock.product_name}")
            table.setCellWidget(row_index, 1, product)
            self._set_cell(table, row_index, 2, stock.location_name, left=True)
            self._set_cell(table, row_index, 3, quantity(stock.on_hand))
            self._set_cell(table, row_index, 4, quantity(stock.forecast))
            self._set_cell(table, row_index, 5, stock.route, left=True)
            self._set_cell(table, row_index, 6, quantity(stock.minimum))
            self._set_cell(table, row_index, 7, quantity(stock.maximum))
            order_text = (
                f"Snoozed · {stock.snoozed_until}"
                if stock.snoozed_until
                else quantity(stock.to_order)
            )
            self._set_cell(table, row_index, 8, order_text)
            actions = self._row_actions(stock)
            table.setCellWidget(row_index, 9, actions)
            if table.item(row_index, 0).checkState() == Qt.CheckState.Checked:
                checked_count += 1
        self._populating_table = False
        self.result_label.setText(f"{len(self.current_rows)} records")
        self.selection_label.setText(f"{checked_count} selected")

    def _row_actions(self, stock: Replenishment) -> QWidget:
        panel = QWidget()
        row = QHBoxLayout(panel)
        row.setContentsMargins(2, 1, 2, 1)
        row.setSpacing(1)
        order = self._row_action("↪ Order Once")
        order.setEnabled(stock.to_order > 0)
        order.setToolTip(f"Create a replenishment for {quantity(stock.to_order)}.")
        order.clicked.connect(lambda checked=False, item=stock: self._order_rows([item]))
        row.addWidget(order)
        toggle = self._row_action("✓ Automate" if stock.trigger == "manual" else "Manual")
        toggle.setToolTip("Switch this stock rule between Auto and Manual.")
        toggle.clicked.connect(
            lambda checked=False, item=stock: self._toggle_trigger(item)
        )
        row.addWidget(toggle)
        snooze = self._row_action("◴ Snooze")
        snooze.clicked.connect(
            lambda checked=False, item=stock: self._snooze_rows([item])
        )
        row.addWidget(snooze)
        return panel

    @staticmethod
    def _row_action(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("rowAction")
        return button

    @staticmethod
    def _set_cell(
        table: QTableWidget,
        row: int,
        column: int,
        value: str,
        left: bool = False,
    ) -> None:
        item = QTableWidgetItem(value)
        alignment = Qt.AlignmentFlag.AlignVCenter
        alignment |= Qt.AlignmentFlag.AlignLeft if left else Qt.AlignmentFlag.AlignRight
        item.setTextAlignment(alignment)
        table.setItem(row, column, item)

    def _selection_changed(self, _item: QTableWidgetItem) -> None:
        if self._populating_table:
            return
        selected = self._selected_ids()
        self.selection_label.setText(f"{len(selected)} selected")

    def _selected_ids(self) -> list[int]:
        selected: list[int] = []
        for row in range(self.replenishment_table.rowCount()):
            item = self.replenishment_table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                selected.append(self.current_rows[row].id)
        return selected

    def _select_all(self) -> None:
        for row in range(self.replenishment_table.rowCount()):
            item = self.replenishment_table.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked)
        self.selection_label.setText(f"{len(self.current_rows)} selected")

    def _clear_selection(self) -> None:
        for row in range(self.replenishment_table.rowCount()):
            item = self.replenishment_table.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.selection_label.setText("0 selected")

    def _selected_rows(self) -> list[Replenishment]:
        selected_ids = set(self._selected_ids())
        return [row for row in self.current_rows if row.id in selected_ids]

    def _order_selected(self) -> None:
        self._order_rows(self._selected_rows())

    def _order_all_to_max(self) -> None:
        candidates = [
            stock
            for stock in self.current_rows
            if stock.to_order > 0 and not stock.snoozed_until
        ]
        self._order_rows(candidates)

    def _order_rows(self, rows: list[Replenishment]) -> None:
        quantities = {stock.id: stock.to_order for stock in rows if stock.to_order > 0}
        if not quantities:
            self.statusBar().showMessage(
                "Select at least one product that needs replenishment.", 4000
            )
            return
        try:
            reference = self.database.create_order(quantities)
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.critical(self, "Could not create replenishment order", str(error))
            return
        self.refresh()
        self._refresh_operations()
        self.statusBar().showMessage(f"Replenishment {reference} created.", 5000)

    def _snooze_selected(self) -> None:
        rows = self._selected_rows()
        if not rows:
            self.statusBar().showMessage("Select one or more replenishment rules first.", 4000)
            return
        self._snooze_rows(rows)

    def _snooze_rows(self, rows: list[Replenishment]) -> None:
        try:
            self.database.snooze([row.id for row in rows], days=7)
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.critical(self, "Could not snooze replenishment", str(error))
            return
        self.refresh()
        self.statusBar().showMessage("Selected rules snoozed for 7 days.", 4000)

    def _set_selected_trigger(self, trigger: str) -> None:
        ids = self._selected_ids()
        if not ids:
            self.statusBar().showMessage("Select one or more products first.", 4000)
            return
        try:
            self.database.set_trigger(ids, trigger)
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.critical(self, "Could not update replenishment rules", str(error))
            return
        self.refresh()
        self.statusBar().showMessage(
            f"{len(ids)} replenishment rule(s) set to {trigger.title()}.", 4000
        )

    def _toggle_trigger(self, stock: Replenishment) -> None:
        trigger = "auto" if stock.trigger == "manual" else "manual"
        try:
            self.database.set_trigger([stock.id], trigger)
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.critical(self, "Could not update replenishment rule", str(error))
            return
        self.refresh()
        self.statusBar().showMessage(f"Rule set to {trigger.title()}.", 4000)

    def _new_stock_item(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Inventory Item")
        form = QFormLayout(dialog)
        sku = QLineEdit()
        sku.setPlaceholderText("e.g. FURN_8220")
        name = QLineEdit()
        name.setPlaceholderText("Product name")
        location = QComboBox()
        self._locations = self.database.list_locations()
        for item in self._locations:
            location.addItem(item.complete_name, item.id)
        on_hand = self._spinbox(0)
        reserved = self._spinbox(0)
        incoming = self._spinbox(0)
        minimum = self._spinbox(0)
        maximum = self._spinbox(0)
        route = QComboBox()
        route.addItems(["Buy", "Manufacture"])
        trigger = QComboBox()
        trigger.addItem("Manual", "manual")
        trigger.addItem("Auto", "auto")
        form.addRow("Internal Reference", sku)
        form.addRow("Product", name)
        form.addRow("Location", location)
        form.addRow("On Hand", on_hand)
        form.addRow("Reserved", reserved)
        form.addRow("Incoming", incoming)
        form.addRow("Route", route)
        form.addRow("Minimum", minimum)
        form.addRow("Maximum", maximum)
        form.addRow("Trigger", trigger)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.database.add_stock_item(
                sku=sku.text(),
                name=name.text(),
                location_id=int(location.currentData()),
                on_hand=on_hand.value(),
                reserved=reserved.value(),
                incoming=incoming.value(),
                route=route.currentText(),
                minimum=minimum.value(),
                maximum=maximum.value(),
                trigger=str(trigger.currentData()),
            )
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.critical(self, "Could not add inventory item", str(error))
            return
        self._populate_location_tree()
        self.refresh()
        self.statusBar().showMessage(f"Product {sku.text().strip()} added.", 4000)

    @staticmethod
    def _spinbox(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 999999999)
        spin.setDecimals(2)
        spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        spin.setValue(value)
        return spin

    def _refresh_summary_pages(self) -> None:
        rows = self.database.list_replenishments()
        active = [row for row in rows if not row.snoozed_until]
        auto_rows = [row for row in active if row.trigger == "auto"]
        manual_rows = [row for row in active if row.trigger == "manual"]
        self._clear_layout(self.overview_cards)
        self.overview_cards.addWidget(self._stat_card("Stock Locations", str(len(rows))))
        self.overview_cards.addWidget(
            self._stat_card("Needs Replenishment", str(len(active)))
        )
        self.overview_cards.addWidget(
            self._stat_card("Units To Order", quantity(sum(row.to_order for row in active)))
        )
        self.overview_cards.addWidget(
            self._stat_card("Automatic Rules", str(len(auto_rows)))
        )
        self.overview_table.setRowCount(min(10, len(active)))
        for index, stock in enumerate(active[:10]):
            self._set_cell(
                self.overview_table, index, 0, f"[{stock.sku}] {stock.product_name}", left=True
            )
            self._set_cell(self.overview_table, index, 1, stock.location_name, left=True)
            self._set_cell(self.overview_table, index, 2, quantity(stock.forecast))
            self._set_cell(self.overview_table, index, 3, quantity(stock.to_order))
            self._set_cell(self.overview_table, index, 4, stock.trigger.title(), left=True)

        self.products_table.setRowCount(0)
        products = self.database.list_products()
        self.products_table.setRowCount(len(products))
        for index, product in enumerate(products):
            self._set_cell(self.products_table, index, 0, product["sku"])
            self._set_cell(self.products_table, index, 1, product["name"], left=True)
            self._set_cell(self.products_table, index, 2, str(product["location_count"]))
            self._set_cell(self.products_table, index, 3, quantity(product["on_hand"]))
            self._set_cell(
                self.products_table,
                index,
                4,
                quantity(product["reserved"]),
            )
            self._set_cell(
                self.products_table,
                index,
                5,
                quantity(product["incoming"]),
            )
        self._refresh_operations()
        self._refresh_reporting(active, auto_rows, manual_rows)

    def _refresh_operations(self) -> None:
        if not hasattr(self, "orders_table"):
            return
        orders = self.database.list_orders()
        self.orders_table.setRowCount(len(orders))
        for index, order in enumerate(orders):
            self._set_cell(self.orders_table, index, 0, order.reference)
            self._set_cell(self.orders_table, index, 1, order.product_name, left=True)
            self._set_cell(self.orders_table, index, 2, order.location_name, left=True)
            self._set_cell(self.orders_table, index, 3, quantity(order.quantity))
            self._set_cell(self.orders_table, index, 4, order.route)
            self._set_cell(self.orders_table, index, 5, order.status)
            self._set_cell(self.orders_table, index, 6, order.created_at)

    def _refresh_reporting(
        self,
        active: list[Replenishment],
        auto_rows: list[Replenishment],
        manual_rows: list[Replenishment],
    ) -> None:
        groups = [("Auto", auto_rows), ("Manual", manual_rows), ("All", active)]
        self.reporting_table.setRowCount(len(groups))
        for index, (name, items) in enumerate(groups):
            self._set_cell(self.reporting_table, index, 0, name, left=True)
            self._set_cell(self.reporting_table, index, 1, str(len(items)))
            self._set_cell(
                self.reporting_table,
                index,
                2,
                str(sum(item.to_order > 0 for item in items)),
            )
            self._set_cell(
                self.reporting_table,
                index,
                3,
                quantity(sum(item.to_order for item in items)),
            )

    @staticmethod
    def _clear_layout(layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _stat_card(title: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        label = QLabel(title)
        label.setObjectName("muted")
        amount = QLabel(value)
        amount.setObjectName("statValue")
        card_layout.addWidget(label)
        card_layout.addWidget(amount)
        card.setMinimumHeight(88)
        return card

    def _save_configuration(self) -> None:
        company = self.company_edit.text().strip()
        self.database.set_setting("company_name", company or "A")
        self.company_label.setText(company or "A")
        self.statusBar().showMessage("Configuration saved.", 4000)
