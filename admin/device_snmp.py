#!/usr/bin/env python3
import json
import yaml
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from hnmp import SNMP
from pysnmp.hlapi import (
    SnmpEngine, CommunityData, UsmUserData,
    UdpTransportTarget, ContextData, ObjectType,
    ObjectIdentity, getCmd, nextCmd, usmHMACSHAAuthProtocol,
    usmHMACMD5AuthProtocol, usmAesCfb128Protocol,
    usmAesCfb192Protocol, usmAesCfb256Protocol,
    usmDESPrivProtocol
)


@dataclass
class SNMPv3Credentials:
    """Container for SNMPv3 credentials."""
    username: str
    auth_protocol: str  # sha or md5
    auth_key: str
    priv_protocol: str  # aes128, aes192, aes256, or des
    priv_key: str

    def get_auth_protocol(self):
        """Convert auth protocol string to pysnmp object."""
        protocols = {
            'sha': usmHMACSHAAuthProtocol,
            'sha1': usmHMACSHAAuthProtocol,
            'md5': usmHMACMD5AuthProtocol
        }
        return protocols.get(self.auth_protocol.lower(), usmHMACSHAAuthProtocol)

    def get_priv_protocol(self):
        """Convert privacy protocol string to pysnmp object."""
        protocols = {
            'aes': usmAesCfb128Protocol,
            'aes128': usmAesCfb128Protocol,
            'aes192': usmAesCfb192Protocol,
            'aes256': usmAesCfb256Protocol,
            'des': usmDESPrivProtocol
        }
        return protocols.get(self.priv_protocol.lower(), usmAesCfb128Protocol)


@dataclass
class SNMPConfig:
    """Container for SNMP configuration."""
    v2_communities: List[str]
    v3_credentials: List[SNMPv3Credentials]
    timeout: int = 2
    retries: int = 1
    max_threads: int = 5

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'SNMPConfig':
        """Create SNMPConfig from YAML file."""
        with open(yaml_path) as f:
            config = yaml.safe_load(f)

        v3_creds = []
        for cred in config.get('snmpv3', []):
            v3_creds.append(SNMPv3Credentials(
                username=cred['username'],
                auth_protocol=cred['auth_protocol'],
                auth_key=cred['auth_key'],
                priv_protocol=cred['priv_protocol'],
                priv_key=cred['priv_key']
            ))

        return cls(
            v2_communities=config.get('communities', []),
            v3_credentials=v3_creds,
            timeout=config.get('timeout', 2),
            retries=config.get('retries', 1),
            max_threads=config.get('max_threads', 5)
        )


class SNMPCollector:
    def __init__(self, snmp_config: SNMPConfig, db_path: Optional[str] = None, verbose: bool = False):
        """Initialize the SNMP collector with optional database connection."""
        self.db_path = db_path
        self.snmp_config = snmp_config
        self.verbose = verbose
        self.logger = self._setup_logger()
        self.conn = self._setup_database() if db_path else None

    def _setup_logger(self):
        """Configure logging."""
        log_level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger("snmp_collector")

    def _setup_database(self) -> sqlite3.Connection:
        """Setup database connection and create tables."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS device_snmp (
                device_id INTEGER,
                sys_name TEXT,
                sys_descr TEXT,
                sys_uptime INTEGER,
                sys_contact TEXT,
                sys_location TEXT,
                snmp_version TEXT,
                auth_info TEXT,
                last_updated TIMESTAMP,
                PRIMARY KEY (device_id),
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            )
        """)

        return conn

    def _get_device_id(self, device_name: str) -> Optional[int]:
        """Get device ID from database."""
        if not self.conn:
            return None

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT device_id FROM devices WHERE name = ?",
            (device_name,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def _get_snmp(self, oid):
        """Convert SNMP value to Python primitive type."""
        if hasattr(oid, 'prettyPrint'):
            return oid.prettyPrint()
        return str(oid)

    def _try_snmp_v2c(self, ip_address: str, community: str) -> Optional[Dict]:
        """Attempt SNMPv2c collection with a single community string."""
        try:
            engine = SnmpEngine()
            auth_data = CommunityData(community, mpModel=1)
            target = UdpTransportTarget((ip_address, 161),
                                        timeout=self.snmp_config.timeout,
                                        retries=self.snmp_config.retries)
            context = ContextData()

            # Collect system information
            system_data = {}
            for obj_name, oid in [
                ('sys_name', '1.3.6.1.2.1.1.5.0'),
                ('sys_descr', '1.3.6.1.2.1.1.1.0'),
                ('sys_uptime', '1.3.6.1.2.1.1.3.0'),
                ('sys_contact', '1.3.6.1.2.1.1.4.0'),
                ('sys_location', '1.3.6.1.2.1.1.6.0')
            ]:
                error_indication, error_status, error_index, var_binds = next(
                    getCmd(engine, auth_data, target, context,
                           ObjectType(ObjectIdentity(oid)))
                )
                if error_indication or error_status:
                    return None
                system_data[obj_name] = self._get_snmp(var_binds[0][1])

            # Convert uptime to integer
            system_data['sys_uptime'] = int(system_data['sys_uptime'])
            system_data['snmp_version'] = 'v2c'
            system_data['auth_info'] = json.dumps({'community': community})

            return {
                'success': True,
                'system': system_data
            }

        except Exception as e:
            self.logger.debug(f"SNMPv2c failed with community '{community}': {str(e)}")
            return None

    def _try_snmp_v3(self, ip_address: str, creds: SNMPv3Credentials) -> Optional[Dict]:
        """Attempt SNMPv3 collection with a single set of credentials."""
        try:
            snmp = SNMP(
                ip_address,
                version=3,
                username=creds.username,
                authproto=creds.auth_protocol,
                authkey=creds.auth_key,
                privproto=creds.priv_protocol,
                privkey=creds.priv_key,
                timeout=self.snmp_config.timeout,
                retries=self.snmp_config.retries
            )

            # Test connection with sysName
            sys_name = snmp.get('1.3.6.1.2.1.1.5.0')
            if not sys_name:
                return None

            # Collect system information
            system_data = {
                'sys_name': str(snmp.get('1.3.6.1.2.1.1.5.0')),
                'sys_descr': str(snmp.get('1.3.6.1.2.1.1.1.0')),
                'sys_uptime': int(str(snmp.get('1.3.6.1.2.1.1.3.0')).split()[0]),
                'sys_contact': str(snmp.get('1.3.6.1.2.1.1.4.0')),
                'sys_location': str(snmp.get('1.3.6.1.2.1.1.6.0')),
                'snmp_version': 'v3',
                'auth_info': json.dumps({
                    'username': creds.username,
                    'auth_protocol': creds.auth_protocol,
                    'priv_protocol': creds.priv_protocol
                })
            }

            return {
                'success': True,
                'system': system_data
            }

        except Exception as e:
            self.logger.debug(f"SNMPv3 failed for user '{creds.username}': {str(e)}")
            return None

    def collect_device_data(self, device_name: str, ip_address: str) -> Dict:
        """Try to collect SNMP data using all configured credentials."""
        # Try SNMPv3 credentials first
        for creds in self.snmp_config.v3_credentials:
            try:
                result = self._try_snmp_v3(ip_address, creds)
                if result:
                    self.logger.debug(f"Successfully connected to {device_name} using SNMPv3 user '{creds.username}'")
                    return result
            except Exception as e:
                self.logger.debug(f"SNMPv3 failed for user '{creds.username}': {str(e)}")
                continue

        # If SNMPv3 fails, try SNMPv2c communities
        for community in self.snmp_config.v2_communities:
            try:
                result = self._try_snmp_v2c(ip_address, community)
                if result:
                    self.logger.debug(f"Successfully connected to {device_name} using SNMPv2c community")
                    return result
            except Exception as e:
                self.logger.debug(f"SNMPv2c failed with community: {str(e)}")
                continue

        return {
            'success': False,
            'error': 'All authentication attempts failed'
        }

    def store_device_data(self, device_id: int, snmp_data: Dict) -> bool:
        """Store SNMP data for a device in the database."""
        if not self.conn:
            return False

        cursor = self.conn.cursor()

        try:
            self.conn.execute("BEGIN TRANSACTION")

            cursor.execute("""
                INSERT OR REPLACE INTO device_snmp (
                    device_id, sys_name, sys_descr, sys_uptime,
                    sys_contact, sys_location, snmp_version,
                    auth_info, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                device_id,
                snmp_data['system']['sys_name'],
                snmp_data['system']['sys_descr'],
                snmp_data['system']['sys_uptime'],
                snmp_data['system']['sys_contact'],
                snmp_data['system']['sys_location'],
                snmp_data['system']['snmp_version'],
                snmp_data['system']['auth_info']
            ))

            # Commit transaction
            self.conn.commit()
            return True

        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error storing device data: {str(e)}")
            return False

    def process_topology(self, topology_file: Path, collect_only: bool = False) -> Dict:
        """Process topology file and collect SNMP data.

        Args:
            topology_file: Path to topology JSON file
            collect_only: If True, only collect data without storing in DB

        Returns:
            Dict containing results and collected data
        """
        results = {
            'successful': [],
            'failed': [],
            'collected_data': {}
        }

        try:
            with open(topology_file) as f:
                topology = json.load(f)

            for device_name, device_data in topology.items():
                if not collect_only:
                    device_id = self._get_device_id(device_name)
                    if not device_id:
                        self.logger.error(f"Device {device_name} not found in database")
                        results['failed'].append(device_name)
                        continue

                ip_address = device_data['node_details']['ip']
                self.logger.info(f"Collecting SNMP data from {device_name} ({ip_address})")

                snmp_data = self.collect_device_data(device_name, ip_address)

                if snmp_data['success']:
                    if collect_only:
                        results['collected_data'][device_name] = snmp_data
                        results['successful'].append(device_name)
                    else:
                        if self.store_device_data(device_id, snmp_data):
                            results['successful'].append(device_name)
                        else:
                            results['failed'].append(device_name)
                else:
                    results['failed'].append(device_name)

        except Exception as e:
            self.logger.error(f"Error processing topology file: {str(e)}")

        return results

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Collect SNMP data from network devices')

    # Required arguments
    parser.add_argument('--topology', required=True, help='Path to topology JSON file')
    parser.add_argument('--config', required=True, help='Path to SNMP configuration YAML file')

    # Operation mode group
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--collect-only', action='store_true',
                            help='Only collect SNMP data and save to JSON file')
    mode_group.add_argument('--store', action='store_true',
                            help='Collect SNMP data and store in database')

    # Optional arguments
    parser.add_argument('--db', help='Path to the SQLite database (only required with --store)')
    parser.add_argument('--output', default='snmp_results.json',
                        help='Output JSON file for collected data (used with --collect-only)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')

    args = parser.parse_args()

    # Validate arguments
    if args.store and not args.db:
        parser.error("--db is required when using --store")

    # Load SNMP configuration from YAML
    snmp_config = SNMPConfig.from_yaml(args.config)

    # Initialize collector
    collector = SNMPCollector(snmp_config, db_path=args.db if args.store else None, verbose=args.verbose)

    try:
        # Process topology
        results = collector.process_topology(
            Path(args.topology),
            collect_only=args.collect_only
        )

        # Save collected data if in collect-only mode
        if args.collect_only:
            with open(args.output, 'w') as f:
                json.dump(results['collected_data'], f, indent=2)
            print(f"\nCollected data saved to: {args.output}")

        # Print summary
        print("\nSNMP Collection Summary:")
        print(f"Successfully collected: {len(results['successful'])} devices")
        print(f"Failed collection: {len(results['failed'])} devices")

        if results['failed']:
            print("\nFailed devices:")
            for device in results['failed']:
                print(f"  {device}")

    finally:
        if args.store:
            collector.close()


if __name__ == "__main__":
    main()
    #--collect-only --topology csc\cal\cal.json --config snmp_config.yaml --output cal_snmp_results.json -v