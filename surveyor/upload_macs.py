#!/usr/bin/env python3
import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional, Dict


class MacTableLoader:
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
        return logging.getLogger("mac_table_loader")

    def _setup_database(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _get_device_id(self, device_name: str) -> Optional[int]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT device_id FROM devices WHERE name = ?",
            (device_name,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def _store_mac_entry(self, device_id: int, entry: Dict, vendor: str):
        cursor = self.conn.cursor()
        sql = """
            INSERT OR REPLACE INTO device_mac_table (
                device_id, vlan_id, mac_address, type,
                interface, moves, last_move, vendor,
                last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        params = (
            device_id,
            entry.get('vlan_id', 0),
            entry.get('mac_address'),
            entry.get('type'),
            entry.get('interface'),
            entry.get('moves', 0),
            entry.get('last_move', 0),
            vendor
        )
        cursor.execute(sql, params)

    def process_mac_file(self, filepath: Path) -> str:
        self.logger.info(f"Processing MAC table file: {filepath}")
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
                    self.conn.execute(
                        "DELETE FROM device_mac_table WHERE device_id = ?",
                        (device_id,)
                    )

                    mac_entries = device_data.get('mac_table', {}).get('entries', [])
                    vendor = device_data.get('vendor', '')

                    for entry in mac_entries:
                        self._store_mac_entry(device_id, entry, vendor)

                    self.conn.commit()
                    success_count += 1
                    self.logger.info(f"Successfully processed MAC table for {device_name}")

                except Exception as e:
                    self.conn.rollback()
                    self.logger.error(f"Error processing device {device_name}: {str(e)}")
                    error_count += 1

            return f"Processed {filepath.name}: {success_count} devices successful, {error_count} failed"

        except Exception as e:
            self.logger.error(f"Error processing file {filepath}: {str(e)}")
            return f"Failed to process {filepath.name}: {str(e)}"

    def close(self):
        if self.conn:
            self.conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Load MAC table data into CMDB')
    parser.add_argument('--db', required=True, help='Path to the SQLite database')
    parser.add_argument('--base-path', required=True, help='Base path containing site folder')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()
    base_path = Path(args.base_path).resolve()

    loader = MacTableLoader(args.db, args.verbose)
    try:
        mac_file = base_path / f"{base_path.name}_macs.json"
        if mac_file.exists():
            result = loader.process_mac_file(mac_file)
            print(result)
        else:
            print(f"MAC file not found: {mac_file}")
    finally:
        loader.close()


if __name__ == "__main__":
    main()