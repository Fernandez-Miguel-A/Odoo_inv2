from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from Odoo_inv2.database import InventoryDatabase
from Odoo_inv2.models import Replenishment


class InventoryDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = InventoryDatabase(
            Path(self.temporary_directory.name) / "inventory.sqlite3"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_demo_records_reproduce_replenishment_quantities(self) -> None:
        rows = self.database.list_replenishments()

        self.assertEqual(len(rows), 11)
        corner_desk = next(
            row for row in rows
            if row.sku == "E-COM06" and row.location_name == "WH/Stock"
        )
        table = next(row for row in rows if row.sku == "FURN_9666")
        self.assertEqual(corner_desk.forecast, -1)
        self.assertEqual(corner_desk.to_order, 1)
        self.assertEqual(table.forecast, 2)
        self.assertEqual(table.to_order, 8)

    def test_location_and_trigger_filters(self) -> None:
        locations = self.database.list_locations()
        stock = next(location for location in locations if location.complete_name == "WH/Stock")

        descendants = self.database.list_replenishments(location_id=stock.id)
        automatic = self.database.list_replenishments(trigger="auto")
        self.assertEqual(len(descendants), 11)
        self.assertTrue(all(row.trigger == "auto" for row in automatic))
        self.assertEqual(len(automatic), 3)

    def test_snoozing_temporarily_hides_suggested_order_quantity(self) -> None:
        row = next(
            item
            for item in self.database.list_replenishments()
            if item.sku == "E-COM06" and item.location_name == "WH/Stock"
        )

        self.database.snooze([row.id], days=7)

        snoozed = next(
            item for item in self.database.list_replenishments() if item.id == row.id
        )
        self.assertEqual(snoozed.to_order, 0)
        self.assertIsNotNone(snoozed.snoozed_until)

    def test_replenishment_order_updates_forecast_and_is_persisted(self) -> None:
        row = next(
            item
            for item in self.database.list_replenishments()
            if item.sku == "E-COM06" and item.location_name == "WH/Stock"
        )

        reference = self.database.create_order({row.id: row.to_order})

        updated = next(
            item for item in self.database.list_replenishments() if item.id == row.id
        )
        orders = self.database.list_orders()
        self.assertEqual(reference, "WH/IN/00001")
        self.assertEqual(updated.incoming, 1)
        self.assertEqual(updated.forecast, 0)
        self.assertEqual(updated.to_order, 0)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].reference, reference)

    def test_stock_item_validation_and_creation(self) -> None:
        location = self.database.list_locations()[0]

        with self.assertRaises(ValueError):
            self.database.add_stock_item(
                sku="NEW-1",
                name="Example",
                location_id=location.id,
                on_hand=0,
                reserved=0,
                incoming=0,
                route="Buy",
                minimum=10,
                maximum=5,
                trigger="manual",
            )

        level_id = self.database.add_stock_item(
            sku="NEW-1",
            name="Example Product",
            location_id=location.id,
            on_hand=2,
            reserved=0,
            incoming=0,
            route="Buy",
            minimum=1,
            maximum=5,
            trigger="manual",
        )
        created = next(
            row for row in self.database.list_replenishments() if row.id == level_id
        )
        self.assertIsInstance(created, Replenishment)
        self.assertEqual(created.sku, "NEW-1")
        self.assertEqual(created.to_order, 3)


if __name__ == "__main__":
    unittest.main()
