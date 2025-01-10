#!/usr/bin/env python3
import json
import logging
import sqlite3
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


class SNMPLoader(BaseLoader):
    def _update_device_info(self, device_id: int, snmp_data: Dict):
        """Update device table with hostname from SNMP data"""
        cursor = self.conn.cursor()
        system = snmp_data.get('system', {})

        sql = """
            UPDATE devices 
            SET hostname = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE device_id = ?
        """
        cursor.execute(sql, (system.get('sys_name'), device_id))

    def _update_system_info(self, device_id: int, snmp_data: Dict):
        """Update system_info table with SNMP data"""
        cursor = self.conn.cursor()
        system = snmp_data.get('system', {})

        # Extract software version from sys_descr if possible
        sys_descr = system.get('sys_descr', '')
        version = None
        if 'Version' in sys_descr:
            try:
                version = sys_descr.split('Version')[1].split(',')[0].strip()
            except:
                self.logger.warning("Could not parse version from sys_descr")

        sql = """
            INSERT OR REPLACE INTO device_system_info (
                device_id, software_version, last_updated
            ) VALUES (?, ?, CURRENT_TIMESTAMP)
        """
        cursor.execute(sql, (device_id, version))

    def _update_uptime(self, device_id: int, snmp_data: Dict):
        """Update uptime table with SNMP data"""
        cursor = self.conn.cursor()
        sys_uptime = snmp_data.get('system', {}).get('sys_uptime', 0)

        # Convert uptime (in centiseconds) to different units
        total_minutes = sys_uptime // 6000  # Convert to minutes
        minutes = total_minutes % 60
        total_hours = total_minutes // 60
        hours = total_hours % 24
        total_days = total_hours // 24
        days = total_days % 7
        weeks = total_days // 7
        years = weeks // 52
        weeks = weeks % 52

        sql = """
            INSERT INTO device_uptime (
                device_id, years, weeks, days, hours, minutes, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        cursor.execute(sql, (device_id, years, weeks, days, hours, minutes))

    def process_snmp_file(self, filepath: Path) -> str:
        self.logger.info(f"Processing SNMP file: {filepath}")
        try:
            with open(filepath) as f:
                data = json.load(f)

            success_count = 0
            error_count = 0

            for device_name, device_data in data.items():
                if not device_data.get('success', False):
                    self.logger.warning(f"Skipping failed device: {device_name}")
                    error_count += 1
                    continue

                try:
                    device_id = self._get_device_id(device_name)
                    if not device_id:
                        self.logger.error(f"Device {device_name} not found in database")
                        error_count += 1
                        continue

                    self.conn.execute("BEGIN TRANSACTION")

                    # Update various tables with SNMP data
                    self._update_device_info(device_id, device_data)
                    self._update_system_info(device_id, device_data)
                    self._update_uptime(device_id, device_data)

                    self.conn.commit()
                    success_count += 1
                    self.logger.info(f"Successfully processed SNMP data for {device_name}")

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
    parser = argparse.ArgumentParser(description='Load SNMP data into CMDB')
    parser.add_argument('--db', required=True, help='Path to the SQLite database')
    parser.add_argument('--base-path', required=True, help='Base path containing site folders')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()
    base_path = Path(args.base_path).resolve()

    loader = SNMPLoader(args.db, args.verbose)
    try:
        snmp_file = base_path / f"device_snmp.json"
        if snmp_file.exists():
            result = loader.process_snmp_file(snmp_file)
            print(result)
        else:
            print(f"SNMP file not found: {snmp_file}")
    finally:
        loader.close()


if __name__ == "__main__":
    main()