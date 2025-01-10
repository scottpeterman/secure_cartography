#!/usr/bin/env python3
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Optional


class BaseLoader:
    def __init__(self, db_path: str, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.logger = self._setup_logger()
        self.conn = self._setup_database()

    def _setup_logger(self):
        log_level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(self.__class__.__name__.lower())

    def _setup_database(self) -> sqlite3.Connection:
        self.logger.info(f"Connecting to database: {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _get_device_id(self, device_name: str) -> Optional[int]:
        cursor = self.conn.cursor()
        sql = "SELECT device_id FROM devices WHERE name = ?"
        self.logger.debug(f"Looking up device ID for: {device_name}")
        cursor.execute(sql, (device_name,))
        result = cursor.fetchone()
        return result[0] if result else None

    def close(self):
        if self.conn:
            self.conn.close()


class InventoryLoader(BaseLoader):
    def _store_inventory_item(self, device_id: int, inventory_data: Dict):
        cursor = self.conn.cursor()

        sql = """
            INSERT OR REPLACE INTO device_inventory (
                device_id, name, description, serial_number,
                version_id, product_id, port, vendor,
                last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """

        params = (
            device_id,
            inventory_data.get('name'),
            inventory_data.get('description'),
            inventory_data.get('serial'),  # Assuming 'serial' maps to serial_number
            inventory_data.get('vid'),  # Assuming 'vid' maps to version_id
            inventory_data.get('pid'),  # Assuming 'pid' maps to product_id
            inventory_data.get('port'),
            inventory_data.get('vendor')
        )

        cursor.execute(sql, params)

    def process_inventory_file(self, filepath: Path) -> str:
        self.logger.info(f"Processing inventory file: {filepath}")
        try:
            with open(filepath) as f:
                data = json.load(f)

            success_count = 0
            error_count = 0

            for device_name, device_data in data.get('successful', {}).items():
                try:
                    device_id = self._get_device_id(device_name)
                    if not device_id:
                        self.logger.error(f"Device {device_name} not found in database")
                        error_count += 1
                        continue

                    self.conn.execute("BEGIN TRANSACTION")

                    # Clear existing inventory entries for this device
                    self.conn.execute(
                        "DELETE FROM device_inventory WHERE device_id = ?",
                        (device_id,)
                    )

                    # Process each inventory item
                    inventory_items = device_data.get('inventory', {}).get('components', [])
                    self.logger.debug(f"Processing {len(inventory_items)} inventory items for device {device_name}")

                    for item in inventory_items:
                        self._store_inventory_item(device_id, item)

                    self.conn.commit()
                    success_count += 1
                    self.logger.info(f"Successfully processed inventory for {device_name}")

                except Exception as e:
                    self.conn.rollback()
                    self.logger.error(f"Error processing device {device_name}: {str(e)}")
                    error_count += 1

            return f"Processed {filepath.name}: {success_count} devices successful, {error_count} failed"

        except Exception as e:
            self.logger.error(f"Error processing file {filepath}: {str(e)}")
            return f"Failed to process {filepath.name}: {str(e)}"


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Load inventory data into CMDB')
    parser.add_argument('--db', required=True, help='Path to the SQLite database')
    parser.add_argument('--base-path', required=True, help='Base path containing site folders')
    parser.add_argument('--site', help='Process specific site (optional)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()
    base_path = Path(args.base_path)
    loader = InventoryLoader(args.db, args.verbose)

    try:
        if args.site:
            # Process single site
            site_dir = base_path / args.site
            if not site_dir.is_dir():
                print(f"Site directory not found: {site_dir}")
                return
            inventory_file = site_dir / f"{args.site}_inventory.json"
            if inventory_file.exists():
                result = loader.process_inventory_file(inventory_file)
                print(result)
            else:
                print(f"Inventory file not found: {inventory_file}")
        else:
            # Check for inventory file directly in base path
            base_path = Path(base_path).resolve()
            inventory_file = base_path / "home_inventory.json"
            print(f"Looking for inventory file: {inventory_file}")
            if inventory_file.exists():
                print(f"Found inventory file: {inventory_file}")
                result = loader.process_inventory_file(inventory_file)
                print(result)
            else:
                print(f"Inventory file not found: {inventory_file}")
    finally:
        loader.close()


if __name__ == '__main__':
    main()