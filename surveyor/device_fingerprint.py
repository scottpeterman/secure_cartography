import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from typing import Dict, List

from surveyor.ssh.device_fingerprint import DeviceFingerprinter


def surveyor_fingerprint_device(device: Dict, credentials: Dict, verbose: bool) -> Dict:
    """Individual device fingerprinting function for multiprocessing"""
    print(f"fingerprint_device: {device}")
    fingerprinter = DeviceFingerprinter(verbose=verbose)
    # if 'usrv-p1map-lan-sw-01' not in device['name']:
    #     return None
    try:
        result = fingerprinter.fingerprint_device(
            host=device['ip'],
            username=credentials['username'],
            password=credentials['password']
        )
        print(f"Worker received result keys: {result.keys() if result else 'None'}")
        if result.get('success'):
            return_data = {
                'name': device['name'],
                'ip': device['ip'],
                'platform': device['platform'],
                'device_info': result['device_info']
            }
            print(f"Worker success return keys: {return_data.keys()}")
            return return_data

        return_data = {
            'name': device['name'],
            'ip': device['ip'],
            'platform': device['platform'],
            'error': result.get('error', 'Unknown error during fingerprinting')
        }
        print(f"Worker error return keys: {return_data.keys()}")
        return return_data
    except Exception as e:
        print(f"Failure in parent loop: {str(e)}")
        traceback.print_exc()
        return {
            'name': device['name'],
            'ip': device['ip'],
            'platform': device['platform'],
            'error': str(e)
        }
class EnhancedFingerprinter:
    def __init__(self, topology_file: str, credentials: Dict[str, str], max_workers: int = 5, verbose: bool = False):
        self.topology_file = topology_file
        self.credentials = credentials
        self.verbose = verbose
        self.max_workers = max_workers
        self.topology_data = self._load_topology()

    def _load_topology(self) -> Dict:
        with open(self.topology_file, 'r') as f:
            return json.load(f)

    def _extract_devices(self) -> List[Dict]:
        devices = {}
        for node, data in self.topology_data.items():
            if 'node_details' in data:
                devices[node] = {
                    'name': node,
                    'ip': data['node_details']['ip'],
                    'platform': data['node_details']['platform']
                }
            if 'peers' in data:
                for peer, peer_data in data['peers'].items():
                    if peer not in devices:
                        devices[peer] = {
                            'name': peer,
                            'ip': peer_data['ip'],
                            'platform': peer_data['platform']
                        }
        return list(devices.values())

    def fingerprint_network(self) -> Dict:
        devices = self._extract_devices()
        total_devices = len(devices)
        device_chunks = [devices[i:i + self.max_workers] for i in range(0, len(devices), self.max_workers)]
        total_chunks = len(device_chunks)
        completed = 0
        chunk_count = 0
        final_results = {'successful': {}, 'failed': {}}

        for chunk in device_chunks:
            chunk_count += 1
            futures = []

            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                try:
                    futures = [
                        executor.submit(surveyor_fingerprint_device, device, self.credentials, self.verbose)
                        for device in chunk
                    ]

                    for future in as_completed(futures):
                        completed += 1
                        try:
                            result = future.result()  # This will raise any exception from the worker
                            device_name = result['name']

                            if 'error' in result:
                                final_results['failed'][device_name] = result
                                print(f"Inner error: result: {result}")
                            else:
                                final_results['successful'][device_name] = result
                                print(f"Inner Success: {result}")  # Changed device to result

                        except Exception as e:
                            # Get the device that caused this future to fail
                            for f, d in zip(futures, chunk):
                                if f == future:
                                    device_name = d['name']
                                    final_results['failed'][device_name] = {
                                        'name': device_name,
                                        'ip': d['ip'],
                                        'platform': d['platform'],
                                        'error': f"Worker process failed: {str(e)}"
                                    }
                                    break

                        print(
                            f"\rChunk [{chunk_count}/{total_chunks}] Progress: {completed}/{total_devices} devices processed ({(completed / total_devices) * 100:.1f}%)",
                            end='', flush=True
                        )
                except ConnectionError as e:
                    print(e, "Connection failed")
                    return {"error": f"Connection failed: {str(e)}"}
                except ValueError as e:
                    print(e, "Unexpected SSH error")
                    return {"error": str(e)}
                except Exception as e:
                    print(f"\nError processing chunk {chunk_count}: {str(e)}")
                    # Add all devices in this chunk to failed results
                    for device in chunk:
                        final_results['failed'][device['name']] = {
                            'name': device['name'],
                            'ip': device['ip'],
                            'platform': device['platform'],
                            'error': f"Chunk processing failed: {str(e)}"
                        }

        print()  # New line after progress
        return final_results
    def save_results(self, results: Dict, output_file: str):
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Enhanced Network Device Fingerprinting Tool')
    parser.add_argument('--topology', required=True, help='Path to topology JSON file')
    parser.add_argument('--username', required=True, help='SSH username')
    parser.add_argument('--password', required=True, help='SSH password')
    parser.add_argument('--output', default='fingerprint_results.json', help='Output file path')
    parser.add_argument('--max-workers', type=int, default=10, help='Maximum concurrent sessions')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()
    credentials = {'username': args.username, 'password': args.password}

    fingerprinter = EnhancedFingerprinter(
        topology_file=args.topology,
        credentials=credentials,
        max_workers=args.max_workers,
        verbose=args.verbose
    )

    results = fingerprinter.fingerprint_network()
    fingerprinter.save_results(results, args.output)

    print("\nFingerprinting Summary:")
    print(f"Successfully fingerprinted: {len(results['successful'])} devices")
    print(f"Failed fingerprinting: {len(results['failed'])} devices")

    if results['failed']:
        print("\nFailed devices:")
        for device, data in results['failed'].items():
            print(f"  {device}: {data.get('error', 'Unknown error')}")

    print(f"\nDetailed results saved to: {args.output}")


if __name__ == "__main__":
    main()