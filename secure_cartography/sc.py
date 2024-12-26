import argparse
import json
import yaml
import os
from pathlib import Path
from typing import Dict, Any
from secure_cartography.network_discovery import NetworkDiscovery, DiscoveryConfig
import logging


def get_credentials_from_env() -> Dict[str, str]:
    """Retrieve credentials from environment variables"""
    return {
        'password': os.environ.get('SC_PASSWORD', ''),
        'alt_password': os.environ.get('SC_ALT_PASSWORD', ''),
        'username': os.environ.get('SC_USERNAME', ''),
        'alt_username': os.environ.get('SC_ALT_USERNAME', '')
    }


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def discovery_callback(progress):
    """Handle progress updates from discovery process"""
    if progress['status'] == "complete":
        print("\nDiscovery complete!")
    else:
        print(f"Processing {progress['ip']}: {progress['status']}")
        print(
            f"Discovered: {progress['devices_discovered']}, Failed: {progress['devices_failed']}, Queued: {progress['devices_queued']}")


def load_yaml_config(yaml_path: Path) -> Dict[str, Any]:
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description='Network Discovery CLI Tool')
    parser.add_argument('--yaml', type=Path, help='YAML config file')
    parser.add_argument('--seed-ip', help='Starting IP address')
    parser.add_argument('--username', help='Device username (can also use SC_USERNAME env var)')
    parser.add_argument('--password', help='Device password (can also use SC_PASSWORD env var)')
    parser.add_argument('--alt-username', help='Alternate username (can also use SC_ALT_USERNAME env var)')
    parser.add_argument('--alt-password', help='Alternate password (can also use SC_ALT_PASSWORD env var)')
    parser.add_argument('--domain', help='Domain name')
    parser.add_argument('--exclude', default="", help='Comma-separated exclude strings')
    parser.add_argument('--output-dir', help='Output directory')
    parser.add_argument('--timeout', type=int, default=30, help='Connection timeout')
    parser.add_argument('--max-devices', type=int, default=100, help='Maximum devices to discover')
    parser.add_argument('--map-name', help='Output map name')
    parser.add_argument('--layout', help='Graph layout algorithm')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    # Setup logging first
    setup_logging(args.verbose)

    # Debug environment variables
    logging.debug(f"Environment check - SC_PASSWORD: {'SET' if os.environ.get('SC_PASSWORD') else 'NOT SET'}")
    logging.debug(f"Environment check - SC_USERNAME: {'SET' if os.environ.get('SC_USERNAME') else 'NOT SET'}")

    # Get environment variables
    env_creds = get_credentials_from_env()

    # Start with default values
    config_dict = {
        'seed_ip': None,
        'username': env_creds['username'],
        'password': env_creds['password'],
        'alternate_username': env_creds['alt_username'],
        'alternate_password': env_creds['alt_password'],
        'domain_name': '',
        'exclude_string': '',
        'output_dir': './output',
        'timeout': 30,
        'max_devices': 100,
        'map_name': 'network_map',
        'layout_algo': 'kk',
        'verbose': False
    }

    # Load YAML if provided
    if args.yaml:
        try:
            yaml_config = load_yaml_config(args.yaml)
            if 'output_dir' in yaml_config:
                yaml_config['output_dir'] = str(Path(yaml_config['output_dir']).resolve())
            if 'layout' in yaml_config:
                yaml_config['layout_algo'] = yaml_config.pop('layout')
            if 'verbose' in yaml_config:
                yaml_config['save_debug_info'] = yaml_config['verbose']
            if 'max_devices' in yaml_config:
                yaml_config['max_devices'] = int(yaml_config['max_devices'])
            config_dict.update(yaml_config)
        except yaml.YAMLError as e:
            parser.error(f"YAML parsing error: {e}")
        except FileNotFoundError as e:
            parser.error(f"Config file not found: {e}")
        except Exception as e:
            parser.error(f"Error loading YAML file: {e}")

    # Override with CLI arguments if provided (except None values)
    cli_args = {k: v for k, v in vars(args).items() if v is not None and k != 'yaml'}
    config_dict.update(cli_args)

    # Validate required credentials
    if not config_dict['password']:
        parser.error("Password must be provided either via --password argument or SC_PASSWORD environment variable")
    if not config_dict['username']:
        parser.error("Username must be provided either via --username argument or SC_USERNAME environment variable")
    if config_dict['alternate_username'] and not config_dict['alternate_password']:
        parser.error(
            "Alternate password must be provided via --alt-password or SC_ALT_PASSWORD when using alternate username")

    # Create output directory
    output_path = Path(config_dict['output_dir'])
    output_path.mkdir(parents=True, exist_ok=True)

    config = DiscoveryConfig(
        seed_ip=config_dict['seed_ip'],
        username=config_dict['username'],
        password=config_dict['password'],
        alternate_username=config_dict['alternate_username'],
        alternate_password=config_dict['alternate_password'],
        domain_name=config_dict.get('domain', ""),
        exclude_string=config_dict.get('exclude', ""),
        output_dir=output_path,
        timeout=config_dict.get('timeout', 30),
        max_devices=config_dict.get('max_devices', 100),
        map_name=config_dict.get('map_name', 'network_map'),
        layout_algo=config_dict.get('layout_algo', 'kk'),
        save_debug_info=config_dict.get('verbose', False)
    )

    discovery = NetworkDiscovery(config)
    discovery.set_progress_callback(discovery_callback)

    try:
        network_map = discovery.crawl()
    except KeyboardInterrupt:
        print("\nDiscovery interrupted by user")
    except Exception as e:
        print(f"\nError during discovery: {str(e)}")
        raise


if __name__ == '__main__':
    main()