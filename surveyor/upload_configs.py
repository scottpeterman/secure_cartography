#!/usr/bin/env python3
import json
import sqlite3
import traceback
import logging
from typing import Dict
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from surveyor.ssh.pysshpass import ssh_client
from pathlib import Path


def collect_command_output(channel, prompt, timeout=30):
    """Collect command output with proper buffering and timeout."""
    output = ""
    start_time = time.time()
    buffer_time = 0.1  # 100ms between buffer checks

    while True:
        if channel.recv_ready():
            chunk = channel.recv(4096).decode('utf-8', errors='replace')
            output += chunk
            # Reset timer when we receive data
            start_time = time.time()
        else:
            if time.time() - start_time > timeout:
                break
            time.sleep(buffer_time)

        # Check for command prompt to know we're done
        if output.strip().endswith(prompt):
            break

    return output.strip()


def collect_device_config(device_data: Dict, credentials: Dict, verbose: bool) -> Dict:
    """Individual device config collection function for multiprocessing"""
    logger = logging.getLogger(f"collector.{device_data['name']}")
    log_level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(log_level)

    try:
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
        # Execute paging commands with verification
        for cmd_set in device_data['device_info']['paging_commands']:
            channel.send(f"{cmd_set[1]}\n")
            response = collect_command_output(
                channel,
                device_data['device_info']['detected_prompt']
            )
            logger.debug(f"Paging command response: {response}")

        logger.info("Collecting running configuration")
        channel.send("show running-config\n")
        config = collect_command_output(
            channel,
            device_data['device_info']['detected_prompt']
        )

        return {
            "name": device_data['name'],
            "ip": device_data['ip'],
            "success": True,
            "config": config
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


class ConfigCollector:
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
        return logging.getLogger("collector.main")

    def _load_fingerprint(self) -> Dict:
        self.logger.info(f"Loading fingerprint data from {self.fingerprint_file}")
        with open(self.fingerprint_file) as f:
            return json.load(f)

    def _get_device_id(self, device_name: str, conn: sqlite3.Connection) -> int:
        """Get device ID from database."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT device_id FROM devices WHERE name = ?",
            (device_name,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def _store_config(self, device_id: int, config: str, conn: sqlite3.Connection):
        """Store or update device configuration in database."""
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION")

            # Check if config exists
            cursor.execute(
                "SELECT config_id FROM device_configs WHERE device_id = ?",
                (device_id,)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE device_configs 
                    SET config = ?, collected_at = CURRENT_TIMESTAMP
                    WHERE device_id = ?
                """, (config, device_id))
            else:
                cursor.execute("""
                    INSERT INTO device_configs (device_id, config)
                    VALUES (?, ?)
                """, (device_id, config))

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise e

    def process_results(self, results: Dict):
        """Process collected configs and store in database"""
        self.logger.info("Processing collected configurations")

        # Use a single database connection for the main process
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")

        try:
            for device_name, result in results['successful'].items():
                try:
                    device_id = self._get_device_id(device_name, conn)
                    if device_id:
                        self._store_config(device_id, result['config'], conn)
                        self.logger.info(f"Stored config for {device_name}")
                    else:
                        self.logger.error(f"Device {device_name} not found in database")
                except Exception as e:
                    self.logger.error(f"Error storing config for {device_name}: {str(e)}")

        finally:
            conn.close()

    def collect_configs(self) -> Dict:
        # Filter for supported vendors
        devices = [
            {**data, 'name': name}
            for name, data in self.fingerprint_data['successful'].items()
            if data.get('device_info', {}).get('detected_vendor', '').lower() in ['cisco', 'arista', 'nxos']
        ]

        total_devices = len(devices)
        device_chunks = [
            devices[i:i + self.max_workers]
            for i in range(0, len(devices), self.max_workers)
        ]
        total_chunks = len(device_chunks)
        completed = 0
        chunk_count = 0

        final_results = {'successful': {}, 'failed': {}}

        self.logger.info(f"Starting config collection for {total_devices} devices")
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
                        final_results['failed'][device_name] = result
                        self.logger.error(f"Failed collecting {device_name}: {result['error']}")
                    else:
                        final_results['successful'][device_name] = result
                        self.logger.info(f"Successfully collected {device_name}")

                    print(
                        f"\rChunk [{chunk_count}/{total_chunks}] "
                        f"Progress: {completed}/{total_devices} devices processed "
                        f"({(completed / total_devices) * 100:.1f}%)",
                        end='',
                        flush=True
                    )

        elapsed_time = time.time() - start_time
        self.logger.info(f"\nCollection completed in {elapsed_time:.1f} seconds")
        return final_results


def process_site_folder(site_path: Path, db_path: str, credentials: Dict, max_workers: int, verbose: bool):
    """Process a single site folder"""
    fingerprint_file = site_path / f"{site_path.name}_fingerprint.json"
    if not fingerprint_file.exists():
        return f"No fingerprint file found in {site_path}"

    try:
        collector = ConfigCollector(
            db_path=db_path,
            fingerprint_file=str(fingerprint_file),
            credentials=credentials,
            max_workers=max_workers,
            verbose=verbose
        )

        results = collector.collect_configs()
        collector.process_results(results)

        return f"Site {site_path.name}: Success={len(results['successful'])} Failed={len(results['failed'])}"
    except Exception as e:
        return f"Error processing site {site_path.name}: {str(e)}"


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Network Config Collection Tool')
    parser.add_argument('--db', required=True, help='Path to SQLite database')
    parser.add_argument('--base-path', required=True, help='Base path containing site folders')
    parser.add_argument('--username', required=True, help='SSH username')
    parser.add_argument('--password', required=True, help='SSH password')
    parser.add_argument('--max-workers', type=int, default=5,
                        help='Maximum concurrent sessions per site')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()
    credentials = {'username': args.username, 'password': args.password}
    base_path = Path(args.base_path)

    # Process each site folder
    for site_dir in base_path.iterdir():
        if site_dir.is_dir():
            result = process_site_folder(
                site_dir,
                args.db,
                credentials,
                args.max_workers,
                args.verbose
            )
            print(result)


if __name__ == "__main__":
    main()