#!/usr/bin/env python3
import json
import traceback
from typing import Dict, List, Tuple
import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from surveyor.ssh.pysshpass import ssh_client
from surveyor.tfsm_fire import TextFSMAutoEngine
from surveyor.normalizers.mac_table import MacTableNormalizer
from importlib import resources
import re
from ttp import ttp


def clean_json_output(raw_output: str) -> str:
    """Clean CLI artifacts from JSON output."""
    # Find the first '{' and last '}' to extract just the JSON portion
    start = raw_output.find('{')
    end = raw_output.rfind('}') + 1
    if start == -1 or end == 0:
        raise ValueError("No valid JSON found in output")
    return raw_output[start:end]


def collect_device_mac_table(device_data: Dict, credentials: Dict, verbose: bool) -> Dict:
    """Individual device MAC table collection function for multiprocessing"""
    logger = logging.getLogger(f"mac_collector.{device_data['name']}")
    log_level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(log_level)

    # Get basic vendor info
    vendor = device_data['device_info']['detected_vendor']

    # Check if this is actually a Nexus device
    platform = device_data.get('platform', '').lower()
    if 'nexus' in platform.lower() or 'nx-os' in platform.lower():
        vendor = 'nxos'
        logger.debug(f"Detected Nexus platform: {device_data.get('platform')}")

    # Command and parser mappings per vendor
    vendor_commands = {
        'arista': 'show mac address-table | json',
        'cisco': 'show mac address-table',
        'nxos': 'show mac address-table'
    }

    ttp_templates = {
        'cisco': ''' {{ vlan }}    {{mac_addess | MAC }}    {{ learned_type }}      {{ ports | ORPHRASE }}''',
        'nxos': '''{{ entry_type }}    {{ vlan }}     {{ mac_address | MAC }}   {{ learned_type }}   {{ age }}         {{ secure }}      {{ ntfy }}    {{ ports | ORPHRASE }}'''
    }

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
            prompt_count=3,
            inter_command_time=.5
        )

        channel = client.invoke_shell()
        if not channel:
            raise Exception("Failed to create interactive shell")

        # Configure terminal settings
        for cmd_set in device_data['device_info']['paging_commands']:
            channel.send(f"{cmd_set[1]}\n")
            response = collect_command_output(
                channel,
                device_data['device_info']['detected_prompt']
            )
            logger.debug(f"Paging command response: {response}")

        # Get the appropriate command for this vendor
        command = vendor_commands.get(vendor)
        if not command:
            raise ValueError(f"Unsupported vendor: {vendor}")

        # Collect MAC table data
        logger.info("Collecting MAC address table")
        channel.send(f"{command}\n")
        output = collect_command_output(
            channel,
            device_data['device_info']['detected_prompt']
        )

        # Parse based on vendor
        if vendor == 'arista':
            # Clean and parse JSON output
            clean_output = clean_json_output(output)
            parsed_data = json.loads(clean_output)
        else:
            # Use TTP for Cisco/NXOS
            template = ttp_templates.get(vendor)
            parser = ttp(data=output, template=template)
            parser.parse()
            parsed_data = parser.result(format='raw')[0]  # Get first parsing result

        # Normalize the data
        logger.debug("Normalizing MAC table data")
        normalizer = MacTableNormalizer()
        normalized_data = normalizer.normalize(parsed_data, vendor)

        return {
            "name": device_data['name'],
            "ip": device_data['ip'],
            "success": True,
            "mac_table": normalized_data,
            "vendor": vendor
        }

    except Exception as e:
        logger.error(f"Error collecting MAC table: {str(e)}")
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
    buffer_time = 0.1

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


class EnhancedMacTableCollector:
    def __init__(self, fingerprint_file: str, credentials: Dict[str, str], max_workers: int = 5, verbose: bool = False):
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
        return logging.getLogger("mac_collector.main")

    def _load_fingerprint(self) -> Dict:
        self.logger.info(f"Loading fingerprint data from {self.fingerprint_file}")
        with open(self.fingerprint_file) as f:
            return json.load(f)

    def collect_mac_tables(self, device_filter: str = None) -> Dict:
        """
        Collect MAC tables from devices.

        Args:
            device_filter: If provided, only collect from devices whose names contain this string
        """
        devices = [
            {**data, 'name': name}
            for name, data in self.fingerprint_data['successful'].items()
            if not device_filter or device_filter in name
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

        self.logger.info(f"Starting MAC table collection for {total_devices} devices")
        if device_filter:
            self.logger.info(f"Filtering for devices matching: {device_filter}")

        start_time = time.time()

        for chunk in device_chunks:
            chunk_count += 1
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_device = {
                    executor.submit(
                        collect_device_mac_table,
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
    def save_results(self, results: Dict, output_file: str):
        self.logger.info(f"Saving results to {output_file}")
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Enhanced MAC Address Table Collection Tool')
    parser.add_argument('--fingerprint', required=True, help='Path to fingerprint JSON file')
    parser.add_argument('--username', required=True, help='SSH username')
    parser.add_argument('--password', required=True, help='SSH password')
    parser.add_argument('--output', default='mac_table_results.json', help='Output file path')
    parser.add_argument('--max-workers', type=int, default=5, help='Maximum concurrent sessions')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--device', help='Filter to collect from devices matching this name')

    args = parser.parse_args()
    credentials = {'username': args.username, 'password': args.password}

    collector = EnhancedMacTableCollector(
        fingerprint_file=args.fingerprint,
        credentials=credentials,
        max_workers=args.max_workers,
        verbose=args.verbose
    )

    results = collector.collect_mac_tables(device_filter=args.device)
    collector.save_results(results, args.output)

    print("\nMAC Table Collection Summary:")
    print(f"Successfully collected: {len(results['successful'])} devices")
    print(f"Failed collection: {len(results['failed'])} devices")

    if results['failed']:
        print("\nFailed devices:")
        for device, data in results['failed'].items():
            print(f"  {device}: {data.get('error', 'Unknown error')}")

    print(f"\nDetailed results saved to: {args.output}")

if __name__ == "__main__":
    main()