from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

from Odoo_inv2.models import Location, Replenishment, ReplenishmentOrder


class InventoryDatabase:
    """Local SQLite storage for inventory and replenishment operations."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            data_root = Path(os.environ.get("LOCALAPPDATA", Path.home()))
            path = data_root / "Odoo_inv2" / "inventory.sqlite3"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    complete_name TEXT NOT NULL UNIQUE,
                    parent_id INTEGER REFERENCES locations(id),
                    usage TEXT NOT NULL DEFAULT 'internal'
                );
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS stock_levels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL REFERENCES products(id),
                    location_id INTEGER NOT NULL REFERENCES locations(id),
                    on_hand REAL NOT NULL DEFAULT 0,
                    reserved REAL NOT NULL DEFAULT 0,
                    incoming REAL NOT NULL DEFAULT 0,
                    route TEXT NOT NULL DEFAULT 'Buy',
                    minimum REAL NOT NULL DEFAULT 0,
                    maximum REAL NOT NULL DEFAULT 0,
                    trigger_mode TEXT NOT NULL DEFAULT 'manual'
                        CHECK(trigger_mode IN ('auto', 'manual')),
                    snoozed_until TEXT,
                    UNIQUE(product_id, location_id)
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'Ordered',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS order_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL REFERENCES orders(id),
                    stock_level_id INTEGER NOT NULL REFERENCES stock_levels(id),
                    quantity REAL NOT NULL CHECK(quantity > 0),
                    route TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            if connection.execute("SELECT COUNT(*) FROM locations").fetchone()[0] == 0:
                self._seed_demo(connection)

    @staticmethod
    def _seed_demo(connection: sqlite3.Connection) -> None:
        def add_location(
            name: str, complete_name: str, parent_id: int | None
        ) -> int:
            cursor = connection.execute(
                """
                INSERT INTO locations(name, complete_name, parent_id)
                VALUES (?, ?, ?)
                """,
                (name, complete_name, parent_id),
            )
            return int(cursor.lastrowid)

        warehouse = add_location("WH", "WH", None)
        stock = add_location("Stock", "WH/Stock", warehouse)
        shelf = add_location("Shelf", "WH/Stock/Shelf 1", stock)
        flat_pack = add_location("Flat Pack", "WH/Stock/Flat Pack", stock)
        assembly = add_location("Assembly", "WH/Stock/Assembly", stock)

        demo_rows = [
            ("E-COM06", "Corner Desk", stock, 4, 5, 0, "Manufacture", 0, 0, "manual"),
            ("E-COM09", "Large Desk", stock, 1, 5, 0, "Buy", 0, 0, "auto"),
            ("FURN_9001", "Flipover", stock, 5, 11, 0, "Buy", 0, 0, "auto"),
            ("FURN_9666", "Table", stock, 2, 0, 0, "Manufacture", 5, 10, "manual"),
            ("FURN_7777", "Office Chair", assembly, 4, 0, 0, "Buy", 5, 10, "manual"),
            ("FURN_8888", "Office Lamp", assembly, 8, 0, 0, "Buy", 10, 10, "auto"),
            ("FURN_8900", "Drawer Black", assembly, 12, 0, 0, "Manufacture", 0, 0, "manual"),
            ("FURN_9001", "Flipover", assembly, 5, 0, 0, "Buy", 0, 0, "manual"),
            ("E-COM06", "Corner Desk", flat_pack, 4, 0, 0, "Manufacture", 0, 0, "manual"),
            ("E-COM09", "Large Desk", flat_pack, 1, 0, 0, "Buy", 2, 2, "manual"),
            ("FURN_9666", "Table", flat_pack, 2, 0, 0, "Manufacture", 5, 10, "manual"),
        ]
        for sku, name, location_id, on_hand, reserved, incoming, route, minimum, maximum, trigger in demo_rows:
            product = connection.execute(
                "SELECT id FROM products WHERE sku = ?", (sku,)
            ).fetchone()
            if product is None:
                product_id = connection.execute(
                    "INSERT INTO products(sku, name) VALUES (?, ?)",
                    (sku, name),
                ).lastrowid
            else:
                product_id = product["id"]
            connection.execute(
                """
                INSERT INTO stock_levels(
                    product_id, location_id, on_hand, reserved, incoming,
                    route, minimum, maximum, trigger_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    location_id,
                    on_hand,
                    reserved,
                    incoming,
                    route,
                    minimum,
                    maximum,
                    trigger,
                ),
            )

    def list_locations(self) -> list[Location]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, name, complete_name, parent_id, usage FROM locations "
                "ORDER BY complete_name"
            ).fetchall()
        return [
            Location(
                id=row["id"],
                name=row["name"],
                complete_name=row["complete_name"],
                parent_id=row["parent_id"],
                usage=row["usage"],
            )
            for row in rows
        ]

    def add_stock_item(
        self,
        *,
        sku: str,
        name: str,
        location_id: int,
        on_hand: float,
        reserved: float,
        incoming: float,
        route: str,
        minimum: float,
        maximum: float,
        trigger: str,
    ) -> int:
        if not sku.strip() or not name.strip():
            raise ValueError("Product code and name are required.")
        if trigger not in ("auto", "manual"):
            raise ValueError(f"Unsupported replenishment trigger: {trigger}")
        if min(on_hand, reserved, incoming, minimum, maximum) < 0:
            raise ValueError("Stock and replenishment quantities cannot be negative.")
        if maximum < minimum:
            raise ValueError("Maximum stock must be greater than or equal to minimum.")
        with self._connection() as connection:
            location = connection.execute(
                "SELECT id FROM locations WHERE id = ?", (location_id,)
            ).fetchone()
            if location is None:
                raise ValueError("Select an existing stock location.")
            product = connection.execute(
                "SELECT id, name FROM products WHERE sku = ?", (sku.strip(),)
            ).fetchone()
            if product is None:
                product_id = connection.execute(
                    "INSERT INTO products(sku, name) VALUES (?, ?)",
                    (sku.strip(), name.strip()),
                ).lastrowid
            else:
                product_id = product["id"]
                if product["name"] != name.strip():
                    connection.execute(
                        "UPDATE products SET name = ? WHERE id = ?",
                        (name.strip(), product_id),
                    )
            cursor = connection.execute(
                """
                INSERT INTO stock_levels (
                    product_id, location_id, on_hand, reserved, incoming, route,
                    minimum, maximum, trigger_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    location_id,
                    on_hand,
                    reserved,
                    incoming,
                    route,
                    minimum,
                    maximum,
                    trigger,
                ),
            )
            return int(cursor.lastrowid)

    def list_products(self) -> list[sqlite3.Row]:
        with self._connection() as connection:
            return connection.execute(
                """
                SELECT p.id, p.sku, p.name, COUNT(sl.id) AS location_count,
                       COALESCE(SUM(sl.on_hand), 0) AS on_hand,
                       COALESCE(SUM(sl.incoming), 0) AS incoming,
                       COALESCE(SUM(sl.reserved), 0) AS reserved
                FROM products p
                LEFT JOIN stock_levels sl ON sl.product_id = p.id
                WHERE p.active = 1
                GROUP BY p.id
                ORDER BY p.sku
                """
            ).fetchall()

    def list_replenishments(
        self,
        location_id: int | None = None,
        trigger: str = "all",
        search: str = "",
    ) -> list[Replenishment]:
        clauses = ["p.active = 1"]
        params: list[object] = []
        if location_id is not None:
            with self._connection() as connection:
                location = connection.execute(
                    "SELECT complete_name FROM locations WHERE id = ?",
                    (location_id,),
                ).fetchone()
                if location is None:
                    return []
                prefix = location["complete_name"]
                descendant_ids = [
                    row["id"]
                    for row in connection.execute(
                        "SELECT id FROM locations WHERE complete_name = ? "
                        "OR complete_name LIKE ?",
                        (prefix, f"{prefix}/%"),
                    ).fetchall()
                ]
            if not descendant_ids:
                return []
            clauses.append(
                f"sl.location_id IN ({','.join('?' for _ in descendant_ids)})"
            )
            params.extend(descendant_ids)
        if trigger in ("auto", "manual"):
            clauses.append("sl.trigger_mode = ?")
            params.append(trigger)
        if search.strip():
            clauses.append("(p.sku LIKE ? OR p.name LIKE ? OR l.complete_name LIKE ?)")
            pattern = f"%{search.strip()}%"
            params.extend([pattern, pattern, pattern])
        query = f"""
            SELECT sl.id, p.id AS product_id, p.sku, p.name AS product_name,
                   l.id AS location_id, l.complete_name AS location_name,
                   sl.on_hand, sl.reserved, sl.incoming, sl.route, sl.minimum,
                   sl.maximum, sl.trigger_mode, sl.snoozed_until
            FROM stock_levels sl
            JOIN products p ON p.id = sl.product_id
            JOIN locations l ON l.id = sl.location_id
            WHERE {' AND '.join(clauses)}
            ORDER BY l.complete_name, p.sku
        """
        with self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            Replenishment(
                id=row["id"],
                product_id=row["product_id"],
                sku=row["sku"],
                product_name=row["product_name"],
                location_id=row["location_id"],
                location_name=row["location_name"],
                on_hand=row["on_hand"],
                reserved=row["reserved"],
                incoming=row["incoming"],
                route=row["route"],
                minimum=row["minimum"],
                maximum=row["maximum"],
                trigger=row["trigger_mode"],
                snoozed_until=(
                    row["snoozed_until"]
                    if row["snoozed_until"] and row["snoozed_until"] >= date.today().isoformat()
                    else None
                ),
            )
            for row in rows
        ]

    def set_trigger(self, level_ids: list[int], trigger: str) -> None:
        if trigger not in ("auto", "manual"):
            raise ValueError(f"Unsupported replenishment trigger: {trigger}")
        if not level_ids:
            return
        placeholders = ",".join("?" for _ in level_ids)
        with self._connection() as connection:
            connection.execute(
                f"UPDATE stock_levels SET trigger_mode = ?, snoozed_until = NULL "
                f"WHERE id IN ({placeholders})",
                [trigger, *level_ids],
            )

    def snooze(self, level_ids: list[int], days: int = 7) -> None:
        if days < 1:
            raise ValueError("Snooze duration must be at least one day.")
        if not level_ids:
            return
        placeholders = ",".join("?" for _ in level_ids)
        until = (date.today() + timedelta(days=days)).isoformat()
        with self._connection() as connection:
            connection.execute(
                f"UPDATE stock_levels SET snoozed_until = ? "
                f"WHERE id IN ({placeholders})",
                [until, *level_ids],
            )

    def create_order(self, level_quantities: dict[int, float]) -> str:
        orders = {
            level_id: round(quantity, 2)
            for level_id, quantity in level_quantities.items()
            if quantity > 0
        }
        if not orders:
            raise ValueError("There is no quantity to replenish.")
        with self._connection() as connection:
            next_number = connection.execute(
                "SELECT COUNT(*) + 1 FROM orders"
            ).fetchone()[0]
            reference = f"WH/IN/{next_number:05d}"
            cursor = connection.execute(
                "INSERT INTO orders(reference) VALUES (?)", (reference,)
            )
            order_id = cursor.lastrowid
            for level_id, quantity in orders.items():
                row = connection.execute(
                    "SELECT route FROM stock_levels WHERE id = ?", (level_id,)
                ).fetchone()
                if row is None:
                    raise ValueError(f"Inventory record {level_id} does not exist.")
                connection.execute(
                    "INSERT INTO order_lines(order_id, stock_level_id, quantity, route) "
                    "VALUES (?, ?, ?, ?)",
                    (order_id, level_id, quantity, row["route"]),
                )
                connection.execute(
                    "UPDATE stock_levels SET incoming = incoming + ?, "
                    "snoozed_until = NULL WHERE id = ?",
                    (quantity, level_id),
                )
        return reference

    def list_orders(self) -> list[ReplenishmentOrder]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT o.id, o.reference, p.name AS product_name,
                       l.complete_name AS location_name, ol.quantity, ol.route,
                       o.status, o.created_at
                FROM orders o
                JOIN order_lines ol ON ol.order_id = o.id
                JOIN stock_levels sl ON sl.id = ol.stock_level_id
                JOIN products p ON p.id = sl.product_id
                JOIN locations l ON l.id = sl.location_id
                ORDER BY o.id DESC, ol.id
                """
            ).fetchall()
        return [
            ReplenishmentOrder(
                id=row["id"],
                reference=row["reference"],
                product_name=row["product_name"],
                location_name=row["location_name"],
                quantity=row["quantity"],
                route=row["route"],
                status=row["status"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def set_setting(self, key: str, value: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row is not None else default
