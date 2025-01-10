#!/usr/bin/env python3
import json
import sqlite3
import logging
import traceback
import time
from typing import Dict
from concurrent.futures import ProcessPoolExecutor, as_completed
from surveyor.ssh.pysshpass import ssh_client
from datetime import datetime


def collect_device_config(device_data: Dict, credentials: Dict, verbose: bool) -> Dict:
    """Individual device config collection function for multiprocessing"""
    logger = logging.getLogger(f"collector.{device_data['name']}")
    log_level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(log_level)

    # Command mappings and enable requirements for different vendors
    vendor_config = {
        'cisco': {
            'enable_required': True,
            'enable_command': 'enable\n',
            'config_command': 'show running-config'
        },
        'nxos': {
            'enable_required': False,  # NX-OS typically doesn't require enable
            'config_command': 'show running-config'
        },
        'arista': {
            'enable_required': True,
            'enable_command': 'enable\n',
            'config_command': 'show running-config'
        }
    }

    try:
        vendor = device_data['device_info']['detected_vendor']
        if vendor not in vendor_config:
            raise ValueError(f"Unsupported vendor: {vendor}")

        logger.info(f"Connecting to {device_data['name']} ({device_data['ip']})")
        client = ssh_client(
            host=device_data['ip'],
            user=credentials['username'],
            password=credentials['password'],
            cmds="",
            invoke_shell=True,
            prompt=device_data['device_info']['detected_prompt'],
            timeout=30,
            disable_auto_add_policy=False,
            look_for_keys=False,
            connect_only=True,
            prompt_count=1,
            inter_command_time=.5
        )

        channel = client.invoke_shell()
        if not channel:
            raise Exception("Failed to create interactive shell")

        logger.debug("Configuring terminal settings")
        # Execute paging commands
        for cmd_set in device_data['device_info']['paging_commands']:
            channel.send(f"{cmd_set[1]}\n")
            output = collect_command_output(
                channel,
                device_data['device_info']['detected_prompt']
            )
            logger.debug(f"Paging command response: {output}")

        # Handle privilege escalation if required
        vendor_settings = vendor_config[vendor]
        if vendor_settings.get('enable_required'):
            logger.debug("Entering privileged mode")
            channel.send(vendor_settings['enable_command'])
            prompt_response = collect_command_output(
                channel,
                device_data['device_info']['detected_prompt'].replace('>', '#')
            )
            logger.debug(f"Enable response: {prompt_response}")
            # Update prompt for subsequent commands
            device_data['device_info']['detected_prompt'] = device_data['device_info']['detected_prompt'].replace('>',
                                                                                                                  '#')

        logger.info("Collecting configuration")
        channel.send(f"{vendor_settings['config_command']}\n")
        config = collect_command_output(
            channel,
            device_data['device_info']['detected_prompt']
        )

        return {
            "name": device_data['name'],
            "ip": device_data['ip'],
            "config": config,
            "success": True
        }

    except Exception as e:
        logger.error(f"Error collecting config: {str(e)}")
        logger.debug(traceback.format_exc())
        return {
            "name": device_data['name'],
            "ip": device_data['ip'],
            "error": str(e)
        }
    finally:
        if 'client' in locals():
            client.close()


def collect_command_output(channel, prompt, timeout=30):
    """Collect command output with proper buffering and timeout."""
    output = ""
    start_time = time.time()
    buffer_time = 0.1  # 100ms between buffer checks

    while True:
        if channel.recv_ready():
            chunk = channel.recv(4096).decode('utf-8', errors='replace')
            output += chunk
            start_time = time.time()
        else:
            if time.time() - start_time > timeout:
                break
            time.sleep(buffer_time)

        if output.strip().endswith(prompt):
            break

    return output.strip()


class ConfigBackupManager:
    def __init__(self, db_path: str, fingerprint_file: str, credentials: Dict[str, str],
                 max_workers: int = 5, verbose: bool = False):
        self.db_path = db_path
        self.fingerprint_file = fingerprint_file
        self.credentials = credentials
        self.max_workers = max_workers
        self.verbose = verbose
        self.logger = self._setup_logger()
        self.fingerprint_data = self._load_fingerprint()

    def _setup_logger(self):
        log_level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger("backup.main")

    def _load_fingerprint(self) -> Dict:
        self.logger.info(f"Loading fingerprint data from {self.fingerprint_file}")
        with open(self.fingerprint_file) as f:
            return json.load(f)

    def _save_config_to_db(self, device_name: str, config: str) -> None:
        """Thread-safe function to save config to database"""
        # Create a new connection for this process
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()

            try:
                # Get device_id
                cursor.execute("SELECT device_id FROM devices WHERE name = ?", (device_name,))
                result = cursor.fetchone()
                if not result:
                    raise ValueError(f"Device {device_name} not found in database")

                device_id = result[0]

                # Delete any existing config for this device
                cursor.execute("DELETE FROM device_configs WHERE device_id = ?", (device_id,))

                # Insert new config
                cursor.execute("""
                    INSERT INTO device_configs (device_id, config, collected_at)
                    VALUES (?, ?, ?)
                """, (device_id, config, datetime.now().isoformat()))

                conn.commit()

            except Exception as e:
                conn.rollback()
                raise e

    def backup_configs(self) -> Dict:
        devices = [
            {**data, 'name': name}
            for name, data in self.fingerprint_data['successful'].items()
        ]

        total_devices = len(devices)
        device_chunks = [
            devices[i:i + self.max_workers]
            for i in range(0, len(devices), self.max_workers)
        ]
        total_chunks = len(device_chunks)
        completed = 0
        chunk_count = 0

        results = {'successful': {}, 'failed': {}}

        self.logger.info(f"Starting config backup for {total_devices} devices")
        start_time = time.time()

        for chunk in device_chunks:
            chunk_count += 1
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_device = {
                    executor.submit(
                        collect_device_config,
                        device,
                        self.credentials,
                        self.verbose
                    ): device
                    for device in chunk
                }

                for future in as_completed(future_to_device):
                    completed += 1
                    result = future.result()
                    device_name = result['name']

                    if 'error' in result:
                        results['failed'][device_name] = result
                        self.logger.error(f"Failed backing up {device_name}: {result['error']}")
                    else:
                        # Save config to database
                        try:
                            self._save_config_to_db(device_name, result['config'])
                            results['successful'][device_name] = {
                                "name": device_name,
                                "ip": result['ip'],
                                "timestamp": datetime.now().isoformat()
                            }
                            self.logger.info(f"Successfully backed up {device_name}")
                        except Exception as e:
                            results['failed'][device_name] = {
                                "name": device_name,
                                "ip": result['ip'],
                                "error": f"Database error: {str(e)}"
                            }
                            self.logger.error(f"Database error for {device_name}: {str(e)}")

                    print(
                        f"\rChunk [{chunk_count}/{total_chunks}] "
                        f"Progress: {completed}/{total_devices} devices processed "
                        f"({(completed / total_devices) * 100:.1f}%)",
                        end='',
                        flush=True
                    )

        elapsed_time = time.time() - start_time
        self.logger.info(f"\nBackup completed in {elapsed_time:.1f} seconds")
        return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Network Configuration Backup Tool')
    parser.add_argument('--db', required=True, help='Path to the SQLite database')
    parser.add_argument('--fingerprint', required=True, help='Path to fingerprint JSON file')
    parser.add_argument('--username', required=True, help='SSH username')
    parser.add_argument('--password', required=True, help='SSH password')
    parser.add_argument('--max-workers', type=int, default=5, help='Maximum concurrent sessions')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()
    credentials = {'username': args.username, 'password': args.password}

    backup_manager = ConfigBackupManager(
        db_path=args.db,
        fingerprint_file=args.fingerprint,
        credentials=credentials,
        max_workers=args.max_workers,
        verbose=args.verbose
    )

    results = backup_manager.backup_configs()

    print("\nConfiguration Backup Summary:")
    print(f"Successfully backed up: {len(results['successful'])} devices")
    print(f"Failed backups: {len(results['failed'])} devices")

    if results['failed']:
        print("\nFailed devices:")
        for device, data in results['failed'].items():
            print(f"  {device}: {data.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()