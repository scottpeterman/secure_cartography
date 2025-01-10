#!/usr/bin/env python3
import json
import sqlite3
import argparse
from datetime import datetime
from typing import Dict, Any


class FingerprintLoader:
    def __init__(self, db_path: str):
        """Initialize database connection and enable foreign keys."""
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.cursor = self.conn.cursor()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def _insert_device(self, device_data: Dict[str, Any]) -> int:
        """Insert basic device information and return the device_id."""
        device_info = device_data['device_info']

        # First try to get existing device id
        self.cursor.execute("SELECT device_id FROM devices WHERE name = ?", (device_data['name'],))
        result = self.cursor.fetchone()

        if result:
            # Update existing device
            sql = """
            UPDATE devices SET
                ip_address = ?,
                platform = ?,
                vendor = ?,
                model = ?,
                hostname = ?,
                detected_prompt = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE device_id = ?
            """

            params = (
                device_data['ip'],
                device_data['platform'],
                device_info.get('detected_vendor'),
                device_info['hardware'].get('model'),
                device_info['system'].get('hostname'),
                device_info.get('detected_prompt'),
                result[0]
            )

            self.cursor.execute(sql, params)
            return result[0]
        else:
            # Insert new device
            sql = """
            INSERT INTO devices (
                name, ip_address, platform, vendor, model, hostname, detected_prompt
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """

            params = (
                device_data['name'],
                device_data['ip'],
                device_data['platform'],
                device_info.get('detected_vendor'),
                device_info['hardware'].get('model'),
                device_info['system'].get('hostname'),
                device_info.get('detected_prompt')
            )

            self.cursor.execute(sql, params)
            return self.cursor.lastrowid

    def _insert_system_info(self, device_id: int, device_info: Dict[str, Any]):
        """Insert system information for a device."""
        system = device_info['system']
        software = device_info['software']

        # Check if system info exists
        self.cursor.execute("SELECT 1 FROM device_system_info WHERE device_id = ?", (device_id,))
        exists = self.cursor.fetchone()

        if exists:
            sql = """
            UPDATE device_system_info SET
                software_version = ?,
                software_image = ?,
                running_image = ?,
                rommon_version = ?,
                boot_reason = ?,
                config_register = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE device_id = ?
            """
        else:
            sql = """
            INSERT INTO device_system_info (
                device_id, software_version, software_image, running_image,
                rommon_version, boot_reason, config_register
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        # Try to get config register from metadata if available
        config_register = None
        if '_metadata' in device_info and 'tfsm_data' in device_info['_metadata']:
            config_register = device_info['_metadata']['tfsm_data'].get('CONFIG_REGISTER')

        params = (
            device_id,
            system.get('version') or software.get('version'),
            software.get('image'),
            system.get('image'),
            software.get('rommon'),
            system.get('boot_reason'),
            config_register
        )

        self.cursor.execute(sql, params)

    def _insert_hardware_info(self, device_id: int, hardware: Dict[str, Any]):
        """Insert hardware information for a device."""
        # Check if hardware info exists
        self.cursor.execute("SELECT 1 FROM device_hardware WHERE device_id = ?", (device_id,))
        exists = self.cursor.fetchone()

        if exists:
            sql = """
            UPDATE device_hardware SET
                total_memory = ?,
                free_memory = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE device_id = ?
            """
        else:
            sql = """
            INSERT INTO device_hardware (
                device_id, total_memory, free_memory
            ) VALUES (?, ?, ?)
        """

        memory = hardware.get('memory', {})
        params = (
            device_id,
            memory.get('total'),
            memory.get('free')
        )

        self.cursor.execute(sql, params)

    def _insert_serial_numbers(self, device_id: int, serial_numbers: list):
        """Insert serial numbers for a device."""
        # First, remove existing serial numbers for this device
        self.cursor.execute("DELETE FROM device_serial_numbers WHERE device_id = ?", (device_id,))

        # Insert new serial numbers
        sql = "INSERT INTO device_serial_numbers (device_id, serial_number) VALUES (?, ?)"
        self.cursor.executemany(sql, [(device_id, sn) for sn in serial_numbers])

    def _insert_mac_addresses(self, device_id: int, mac_addresses: list):
        """Insert MAC addresses for a device."""
        # First, remove existing MAC addresses for this device
        self.cursor.execute("DELETE FROM device_mac_addresses WHERE device_id = ?", (device_id,))

        # Insert new MAC addresses
        sql = "INSERT INTO device_mac_addresses (device_id, mac_address) VALUES (?, ?)"
        self.cursor.executemany(sql, [(device_id, mac) for mac in mac_addresses])

    def _insert_uptime(self, device_id: int, uptime: Dict[str, int]):
        """Insert uptime information for a device."""
        sql = """
        INSERT INTO device_uptime (
            device_id, years, weeks, days, hours, minutes
        ) VALUES (?, ?, ?, ?, ?, ?)
        """

        params = (
            device_id,
            uptime.get('years', 0),
            uptime.get('weeks', 0),
            uptime.get('days', 0),
            uptime.get('hours', 0),
            uptime.get('minutes', 0)
        )

        self.cursor.execute(sql, params)

    def load_fingerprint_data(self, fingerprint_file: str):
        """Load device fingerprint data from a JSON file into the database."""
        try:
            # Load and parse JSON data
            with open(fingerprint_file, 'r') as f:
                data = json.load(f)

            # Process successful devices
            for device_name, device_data in data.get('successful', {}).items():
                try:
                    # Begin transaction for each device
                    self.cursor.execute("BEGIN TRANSACTION")

                    # Insert device and get device_id
                    device_id = self._insert_device(device_data)

                    # Insert related information
                    device_info = device_data['device_info']
                    self._insert_system_info(device_id, device_info)
                    self._insert_hardware_info(device_id, device_info['hardware'])

                    if device_info['hardware'].get('serial_numbers'):
                        self._insert_serial_numbers(device_id, device_info['hardware']['serial_numbers'])

                    if device_info['hardware'].get('mac_addresses'):
                        self._insert_mac_addresses(device_id, device_info['hardware']['mac_addresses'])

                    if device_info['system'].get('uptime'):
                        self._insert_uptime(device_id, device_info['system']['uptime'])

                    self.conn.commit()
                    print(f"Successfully processed device: {device_name}")

                except Exception as e:
                    self.conn.rollback()
                    print(f"Error processing device {device_name}: {str(e)}")

        except Exception as e:
            print(f"Error loading fingerprint data: {str(e)}")
            raise
        finally:
            if self.conn:
                self.conn.commit()


def main():
    parser = argparse.ArgumentParser(description='Load network device fingerprint data into CMDB')
    parser.add_argument('--db', required=True, help='Path to the SQLite database')
    parser.add_argument('--fingerprint', required=True, help='Path to the fingerprint JSON file')

    args = parser.parse_args()

    loader = FingerprintLoader(args.db)
    try:
        loader.load_fingerprint_data(args.fingerprint)
        print("Fingerprint data loaded successfully")
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)
    finally:
        loader.close()


if __name__ == '__main__':
    main()