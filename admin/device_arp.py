#!/usr/bin/env python3
import json
import traceback
from typing import Dict
import logging
from time import sleep
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from surveyor.ssh.pysshpass import ssh_client
from surveyor.tfsm_fire import TextFSMAutoEngine
from surveyor.normalizers.arp import ARPNormalizer
from importlib import resources
import re


def clean_arp_output(raw_output: str, vendor: str) -> str:
    """Clean ARP output based on vendor format."""
    header_patterns = {
        'cisco': r"Protocol\s+Address\s+Age.*?\s+Hardware\s+Addr\s+Type\s+Interface",
         'nxos': r"IP ARP Table for context.*\nTotal number of entries:.*\nAddress\s+Age\s+MAC Address\s+Interface",
        'arista': r"Address.*Age.*(Hardware|MAC) Addr.*Interface"
    }

    if vendor not in header_patterns:
        raise ValueError(f"Unsupported vendor: {vendor}")

    header_regex = re.compile(header_patterns[vendor], re.IGNORECASE)

    output_lines = raw_output.splitlines()
    clean_lines = []
    data_section = False

    for line in output_lines:
        # Skip empty lines
        if not line.strip():
            continue

        # Detect the start of the ARP table based on the header
        if header_regex.search(line):
            data_section = True
            clean_lines.append(line)
            continue

        # If we're in the data section, stop if we hit a known prompt or end marker
        if data_section and (line.strip().endswith(("#", ">")) or any(marker in line for marker in ['Total', 'Load for'])):
            break

        # Only collect lines from the data section
        if data_section:
            clean_lines.append(line)

    if not clean_lines:
        raise ValueError(f"No ARP table data found for vendor {vendor}. Raw output:\n{raw_output}")

    return '\n'.join(clean_lines)


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

        if output.strip().endswith(prompt):
            break

    return output.strip()


def get_template_hint(device_data: Dict) -> str:
    """Determine the correct template based on vendor and platform."""
    vendor = device_data['device_info']['detected_vendor']
    platform = device_data.get('platform', '').lower()

    if vendor == 'arista':
        return 'arista_eos_show_ip_arp'
    elif vendor == 'cisco':
        if 'nexus' in platform:
            return 'cisco_nxos_show_ip_arp'
        else:
            return 'cisco_ios_show_arp'
    else:
        raise ValueError(f"Unsupported vendor: {vendor}")


def collect_device_arp(device_data: Dict, credentials: Dict, verbose: bool) -> Dict:
    """Individual device ARP collection function for multiprocessing"""
    logger = logging.getLogger(f"collector.{device_data['name']}")
    log_level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(log_level)

    vendor = device_data['device_info']['detected_vendor']
    template_mappings = {
        'arista': 'arista_eos_show_ip_arp',
        'cisco': 'cisco_ios_show_arp',
        'nxos': 'cisco_nxos_show_ip_arp'
    }

    # template_hint = template_mappings.get(vendor)
    template_hint = get_template_hint(device_data)

    if not template_hint:
        raise ValueError(f"Unsupported vendor: {vendor}")

    try:
        # Connect and collect ARP data
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

        # Configure terminal settings
        for cmd_set in device_data['device_info']['paging_commands']:
            channel.send(f"{cmd_set[1]}\n")
            response = collect_command_output(
                channel,
                device_data['device_info']['detected_prompt']
            )
            logger.debug(f"Paging command response: {response}")

        # Collect ARP data
        print(device_data['platform'])
        if not "ISR" in device_data['platform'] and "WS-" not in device_data['platform'] and "C9" not in device_data['platform']:
            channel.send("show ip arp vrf all\n")
        else:
            channel.send("show ip arp\n")
        raw_output = collect_command_output(
            channel,
            device_data['device_info']['detected_prompt']
        )

        logger.debug(f"Raw ARP output:\n{raw_output}")

        # Normalize data using TTP
        normalizer = ARPNormalizer()
        normalized_data = normalizer.normalize(raw_output, template_hint)

        return {
            "name": device_data['name'],
            "ip": device_data['ip'],
            "success": True,
            "arp_table": normalized_data,
            "template": template_hint
        }

    except Exception as e:
        logger.error(f"Error collecting ARP: {str(e)}")
        logger.debug(traceback.format_exc())
        return {
            "name": device_data['name'],
            "ip": device_data['ip'],
            "error": str(e)
        }
    finally:
        if 'client' in locals():
            client.close()

class EnhancedARPCollector:
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
        return logging.getLogger("collector.main")

    def _load_fingerprint(self) -> Dict:
        self.logger.info(f"Loading fingerprint data from {self.fingerprint_file}")
        with open(self.fingerprint_file) as f:
            return json.load(f)

    def collect_arp(self) -> Dict:
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

        final_results = {'successful': {}, 'failed': {}}

        self.logger.info(f"Starting ARP collection for {total_devices} devices")
        start_time = time.time()

        for chunk in device_chunks:
            chunk_count += 1
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_device = {
                    executor.submit(
                        collect_device_arp,
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
    parser = argparse.ArgumentParser(description='Enhanced Network ARP Collection Tool')
    parser.add_argument('--fingerprint', required=True, help='Path to fingerprint JSON file')
    parser.add_argument('--username', required=True, help='SSH username')
    parser.add_argument('--password', required=True, help='SSH password')
    parser.add_argument('--output', default='arp_results.json', help='Output file path')
    parser.add_argument('--max-workers', type=int, default=5, help='Maximum concurrent sessions')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()
    credentials = {'username': args.username, 'password': args.password}

    collector = EnhancedARPCollector(
        fingerprint_file=args.fingerprint,
        credentials=credentials,
        max_workers=args.max_workers,
        verbose=args.verbose
    )

    results = collector.collect_arp()
    collector.save_results(results, args.output)

    print("\nARP Collection Summary:")
    print(f"Successfully collected: {len(results['successful'])} devices")
    print(f"Failed collection: {len(results['failed'])} devices")

    if results['failed']:
        print("\nFailed devices:")
        for device, data in results['failed'].items():
            print(f"  {device}: {data.get('error', 'Unknown error')}")

    print(f"\nDetailed results saved to: {args.output}")


if __name__ == "__main__":
    main()