"""
Poll Worker - SNMP polling worker thread and supporting classes

This module contains:
- Data classes (PollResult, FingerprintMatch)
- PollWorker QThread for background SNMP polling
- RecogMatcher for device fingerprinting
- OUILookup for MAC vendor identification

Supports both:
- Proxy mode: Ticket-based async polling via SNMP proxy server
- Local mode: Direct SNMP using pysnmp-lextudio (Windows native)
"""

import json
import re
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from threading import Lock

from PyQt6.QtCore import QThread, pyqtSignal

# Import local SNMP operations
from .local_snmp_ops import (
    SNMPConfig, SNMPv3Auth, run_poll_sync, check_snmp_available,
    PYSNMP_AVAILABLE, LocalPollResult
)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FingerprintMatch:
    """Result from Recog pattern matching"""
    matched: str
    params: Dict[str, str] = field(default_factory=dict)
    pattern: str = ""


@dataclass
class PollResult:
    """Results from device poll"""
    ip: str
    success: bool = False
    error: str = ""
    snmp_data: Dict[str, str] = field(default_factory=dict)
    recog_matches: List[FingerprintMatch] = field(default_factory=list)
    oui_lookups: Dict[str, Dict] = field(default_factory=dict)
    interfaces: List[Dict] = field(default_factory=list)
    arp_table: List[Dict] = field(default_factory=list)
    timing: Dict[str, float] = field(default_factory=dict)


# =============================================================================
# Recog Matcher
# =============================================================================

class RecogMatcher:
    """Parse and match against Recog XML fingerprint files"""

    def __init__(self, xml_dir: Path):
        self.xml_dir = xml_dir
        self.fingerprints = {}
        self._load_fingerprints()

    def _load_fingerprints(self):
        for xml_file in self.xml_dir.glob('*.xml'):
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                matches_type = root.get('matches', xml_file.stem)

                fps = []
                for fp in root.findall('fingerprint'):
                    pattern = fp.get('pattern')
                    flags = fp.get('flags', '')
                    description = fp.find('description')
                    desc_text = description.text if description is not None else ''

                    params = []
                    for param in fp.findall('param'):
                        params.append({
                            'pos': int(param.get('pos', 0)),
                            'name': param.get('name'),
                            'value': param.get('value', '')
                        })

                    fps.append({
                        'pattern': pattern,
                        'flags': flags,
                        'description': desc_text,
                        'params': params
                    })

                self.fingerprints[matches_type] = fps
                # Also store under filename stem for compatibility
                if matches_type != xml_file.stem:
                    self.fingerprints[xml_file.stem] = fps

            except Exception:
                pass

    def match(self, value: str, match_type: str) -> List[FingerprintMatch]:
        """Match value against fingerprints of given type"""
        matches = []
        fps = self.fingerprints.get(match_type, [])

        for fp in fps:
            try:
                flags = 0
                if 'i' in fp.get('flags', ''):
                    flags |= re.IGNORECASE

                pattern = fp.get('pattern', '')
                m = re.search(pattern, value, flags)

                if m:
                    # Extract parameters
                    params = {}
                    for param in fp.get('params', []):
                        pos = param.get('pos', 0)
                        name = param.get('name', '')
                        static_value = param.get('value', '')

                        if static_value:
                            params[name] = static_value
                        elif pos > 0 and pos <= len(m.groups()):
                            params[name] = m.group(pos) or ''

                    matches.append(FingerprintMatch(
                        matched=fp.get('description', ''),
                        params=params,
                        pattern=pattern
                    ))

            except re.error:
                pass

        return matches


# =============================================================================
# OUI Lookup
# =============================================================================

class OUILookup:
    """Look up MAC address vendor from OUI database"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.oui_db = {}
        self._debug_log = []
        self._load_database()

    def _load_database(self):
        """Load OUI database from Wireshark manuf file or oui.json"""
        # Try manuf.txt first (Wireshark format)
        manuf_file = self.data_dir / 'manuf.txt'
        if manuf_file.exists():
            self._load_manuf(manuf_file)
            return

        # Try oui.json
        oui_file = self.data_dir / 'oui.json'
        if oui_file.exists():
            self._load_oui_json(oui_file)

    def _load_manuf(self, filepath: Path):
        """Load Wireshark manuf file format"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split('\t')
                    if len(parts) >= 2:
                        oui = parts[0].strip().upper()
                        # Normalize OUI format
                        oui = oui.replace('-', ':').replace('.', ':')

                        # Handle /28, /36 masks - just use the base OUI
                        if '/' in oui:
                            oui = oui.split('/')[0]

                        short_name = parts[1].strip() if len(parts) > 1 else ''
                        long_name = parts[2].strip() if len(parts) > 2 else short_name

                        self.oui_db[oui] = {
                            'manufacturer': long_name or short_name,
                            'short': short_name
                        }

        except Exception as e:
            self._debug_log.append(f"Error loading manuf: {e}")

    def _load_oui_json(self, filepath: Path):
        """Load JSON format OUI database"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                for entry in data:
                    oui = entry.get('oui', '').upper()
                    if oui:
                        self.oui_db[oui] = {
                            'manufacturer': entry.get('companyName', ''),
                            'short': entry.get('companyName', '')[:16]
                        }
        except Exception as e:
            self._debug_log.append(f"Error loading oui.json: {e}")

    def lookup(self, mac: str) -> Optional[Dict]:
        """Look up vendor for MAC address"""
        if not mac:
            return None

        # Normalize MAC
        mac = mac.upper().replace('-', ':').replace('.', ':')

        # Extract OUI (first 3 octets)
        parts = mac.split(':')
        if len(parts) < 3:
            return None

        oui = ':'.join(parts[:3])

        if len(self._debug_log) < 20:
            self._debug_log.append(f"Looking up OUI: {oui} from MAC: {mac}")

        if oui in self.oui_db:
            if len(self._debug_log) < 20:
                self._debug_log.append(f"  FOUND: {self.oui_db[oui]}")
            return self.oui_db[oui]

        # Try without separator
        oui_nosep = oui.replace(':', '')
        for key in self.oui_db:
            if key.replace(':', '').replace('-', '') == oui_nosep:
                if len(self._debug_log) < 20:
                    self._debug_log.append(f"  FOUND (nosep match): {self.oui_db[key]}")
                return self.oui_db[key]

        if len(self._debug_log) < 20:
            self._debug_log.append(f"  NOT FOUND")

        return None

    def get_debug_log(self) -> str:
        return '\n'.join(self._debug_log)


# =============================================================================
# Poll Worker Thread
# =============================================================================

class PollWorker(QThread):
    """
    Background worker for SNMP polling.

    Supports both:
    - Proxy mode: Ticket-based async polling via SNMP proxy server
    - Local mode: Direct SNMP using pysnmp-lextudio (Windows native)
    """

    progress = pyqtSignal(str)  # Status message
    finished = pyqtSignal(PollResult)  # Poll results

    def __init__(
        self,
        ip: str,
        community: str,
        data_dir: Path,
        collect_interfaces: bool = True,
        collect_arp: bool = True,
        use_proxy: bool = False,
        proxy_url: str = "",
        proxy_api_key: str = "",
        snmp_version: str = "2c",
        # SNMPv3 parameters (optional)
        v3_username: Optional[str] = None,
        v3_auth_protocol: str = "SHA",
        v3_auth_password: Optional[str] = None,
        v3_priv_protocol: str = "AES",
        v3_priv_password: Optional[str] = None,
        # Timeouts
        get_timeout: int = 10,
        walk_timeout: int = 120,
    ):
        super().__init__()
        self.ip = ip
        self.community = community
        self.data_dir = data_dir
        self.collect_interfaces = collect_interfaces
        self.collect_arp = collect_arp
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url.rstrip('/')
        self.proxy_api_key = proxy_api_key
        self.snmp_version = snmp_version

        # SNMPv3
        self.v3_username = v3_username
        self.v3_auth_protocol = v3_auth_protocol
        self.v3_auth_password = v3_auth_password
        self.v3_priv_protocol = v3_priv_protocol
        self.v3_priv_password = v3_priv_password

        # Timeouts
        self.get_timeout = get_timeout
        self.walk_timeout = walk_timeout

        # Fingerprinting databases (loaded on demand)
        self._recog = None
        self._oui = None

        # Cancellation support (thread-safe)
        self._cancelled = False
        self._cancel_flag = [False]  # Mutable for async cancellation
        self._cancel_lock = Lock()
        self._current_ticket: Optional[str] = None

    def __del__(self):
        """Destructor - ensure thread is stopped before destruction"""
        if self.isRunning():
            self.cancel()
            self.wait(2000)  # Wait up to 2s

    def cancel(self):
        """Request cancellation of the poll"""
        with self._cancel_lock:
            self._cancelled = True
            self._cancel_flag[0] = True

        # If we have an active proxy job, tell the proxy to cancel it
        if self._current_ticket and self.use_proxy:
            try:
                req = urllib.request.Request(
                    f"{self.proxy_url}/jobs/{self._current_ticket}",
                    headers={'X-API-Key': self.proxy_api_key},
                    method='DELETE'
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass  # Best effort cancellation

    def wait_for_finish(self, timeout_ms: int = 5000) -> bool:
        """
        Wait for the thread to finish with timeout.

        Returns True if thread finished, False if timeout.
        Should be called before destroying the worker.
        """
        if self.isRunning():
            return self.wait(timeout_ms)
        return True

    def _is_cancelled(self) -> bool:
        """Thread-safe check for cancellation"""
        with self._cancel_lock:
            return self._cancelled

    def run(self):
        """Main thread entry point"""
        result = PollResult(ip=self.ip)

        try:
            if self.use_proxy:
                self._run_proxy_poll(result)
            else:
                self._run_direct_poll(result)

            # Run fingerprinting on results (same for both modes)
            if result.success and not self._is_cancelled():
                self._run_fingerprinting(result)

        except Exception as e:
            result.error = str(e)

        self.finished.emit(result)

    def _run_direct_poll(self, result: PollResult):
        """
        Poll device directly via local SNMP (pysnmp-lextudio).

        This is the async implementation that works natively on Windows.
        """
        # Check for pysnmp availability
        self.progress.emit("Checking SNMP library...")
        available, msg = check_snmp_available()

        if not available:
            result.error = msg
            return

        # Build SNMP configuration
        v3_auth = None
        if self.snmp_version == "3" and self.v3_username:
            v3_auth = SNMPv3Auth(
                username=self.v3_username,
                auth_protocol=self.v3_auth_protocol,
                auth_password=self.v3_auth_password,
                priv_protocol=self.v3_priv_protocol,
                priv_password=self.v3_priv_password,
            )

        config = SNMPConfig(
            target=self.ip,
            community=self.community,
            version=self.snmp_version,
            port=161,
            v3_auth=v3_auth,
            get_timeout=self.get_timeout,
            walk_timeout=self.walk_timeout,
        )

        # Thread-safe progress callback
        def progress_callback(msg: str):
            if not self._is_cancelled():
                self.progress.emit(msg)

        # Run the async poll synchronously in this thread
        poll_result: LocalPollResult = run_poll_sync(
            config=config,
            collect_interfaces=self.collect_interfaces,
            collect_arp=self.collect_arp,
            cancel_flag=self._cancel_flag,
            progress_callback=progress_callback,
        )

        # Transfer results
        result.success = poll_result.success
        result.error = poll_result.error
        result.snmp_data = poll_result.snmp_data
        result.interfaces = poll_result.interfaces
        result.arp_table = poll_result.arp_table
        result.timing = poll_result.timing

    def _run_proxy_poll(self, result: PollResult):
        """Poll device via async SNMP proxy with ticket system"""

        # === Step 1: Verify proxy is reachable ===
        self.progress.emit(f"Connecting to proxy at {self.proxy_url}...")

        try:
            health_req = urllib.request.Request(f"{self.proxy_url}/health")
            with urllib.request.urlopen(health_req, timeout=5) as resp:
                health = json.loads(resp.read().decode('utf-8'))
                if health.get('status') != 'ok':
                    result.error = "Proxy health check failed"
                    return
        except urllib.error.URLError as e:
            result.error = f"Cannot connect to proxy: {e.reason}"
            return
        except Exception as e:
            result.error = f"Proxy connection error: {e}"
            return

        # === Step 2: Submit poll job ===
        self.progress.emit(f"Submitting poll job for {self.ip}...")

        poll_data = {
            'target': self.ip,
            'community': self.community,
            'version': self.snmp_version,
            'collect_interfaces': self.collect_interfaces,
            'collect_arp': self.collect_arp,
            'get_timeout': self.get_timeout,
            'walk_timeout': self.walk_timeout,
        }

        # Add v3 auth if applicable
        if self.snmp_version == "3" and self.v3_username:
            poll_data['v3_auth'] = {
                'username': self.v3_username,
                'auth_protocol': self.v3_auth_protocol,
                'auth_password': self.v3_auth_password,
                'priv_protocol': self.v3_priv_protocol,
                'priv_password': self.v3_priv_password,
            }

        try:
            req = urllib.request.Request(
                f"{self.proxy_url}/snmp/poll",
                data=json.dumps(poll_data).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': self.proxy_api_key
                },
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                submit_resp = json.loads(response.read().decode('utf-8'))

            ticket = submit_resp.get('ticket')
            if not ticket:
                result.error = "Proxy did not return a ticket"
                return

            self._current_ticket = ticket

        except urllib.error.HTTPError as e:
            if e.code == 401:
                result.error = "Proxy authentication failed - check API key"
            elif e.code == 403:
                result.error = "Proxy access denied - invalid API key"
            else:
                result.error = f"Proxy HTTP error: {e.code} {e.reason}"
            return
        except Exception as e:
            result.error = f"Failed to submit job: {e}"
            return

        # === Step 3: Poll for status until complete ===
        self.progress.emit(f"Polling {self.ip}...")

        poll_interval = 0.5  # Start fast
        max_interval = 2.0   # Back off to this
        status_url = f"{self.proxy_url}/status/{ticket}"

        while not self._is_cancelled():
            try:
                req = urllib.request.Request(
                    status_url,
                    headers={'X-API-Key': self.proxy_api_key}
                )

                with urllib.request.urlopen(req, timeout=10) as response:
                    status = json.loads(response.read().decode('utf-8'))

                job_status = status.get('status')
                progress_msg = status.get('progress', '')
                progress_detail = status.get('progress_detail', {})
                elapsed = status.get('elapsed_seconds')

                # Build informative progress message
                if progress_msg:
                    msg = progress_msg
                    # Add detail counts if available
                    detail_parts = []
                    if progress_detail.get('interfaces_walked'):
                        detail_parts.append(f"if:{progress_detail['interfaces_walked']}")
                    if progress_detail.get('arp_walked'):
                        detail_parts.append(f"arp:{progress_detail['arp_walked']}")
                    if detail_parts:
                        msg += f" [{', '.join(detail_parts)}]"
                    if elapsed:
                        msg += f" ({elapsed:.1f}s)"
                    self.progress.emit(msg)

                # Check terminal states
                if job_status == 'complete':
                    data = status.get('data', {})
                    result.success = True
                    result.snmp_data = data.get('snmp_data', {})
                    result.interfaces = data.get('interfaces', [])
                    result.arp_table = data.get('arp_table', [])
                    result.timing = status.get('timing', {})
                    self._current_ticket = None
                    return

                elif job_status == 'failed':
                    result.error = status.get('error', 'Poll failed')
                    self._current_ticket = None
                    return

                elif job_status == 'cancelled':
                    result.error = "Poll was cancelled"
                    self._current_ticket = None
                    return

                # Still running - wait and poll again
                time.sleep(poll_interval)
                poll_interval = min(poll_interval * 1.2, max_interval)

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    result.error = "Job not found - may have expired"
                else:
                    result.error = f"Status check failed: {e.code}"
                self._current_ticket = None
                return
            except Exception as e:
                result.error = f"Status check error: {e}"
                self._current_ticket = None
                return

        # Cancelled
        result.error = "Poll cancelled by user"
        self._current_ticket = None

    def _run_fingerprinting(self, result: PollResult):
        """Run Recog fingerprinting and OUI lookups"""
        self.progress.emit("Loading fingerprint databases...")
        self._load_databases()

        # Run Recog matching
        self.progress.emit("Fingerprinting device...")
        if 'sysDescr' in result.snmp_data and self._recog:
            matches = self._recog.match(result.snmp_data['sysDescr'], 'snmp.sys_description')
            if not matches:
                matches = self._recog.match(result.snmp_data['sysDescr'], 'snmp_sysdescr')
            result.recog_matches.extend(matches)

        if 'sysObjectID' in result.snmp_data and self._recog:
            matches = self._recog.match(result.snmp_data['sysObjectID'], 'snmp.sys_object_id')
            if not matches:
                matches = self._recog.match(result.snmp_data['sysObjectID'], 'snmp_sysobjid')
            result.recog_matches.extend(matches)

        # OUI lookups
        self.progress.emit("Looking up MAC vendors...")
        if self._oui:
            all_macs = set()
            for iface in result.interfaces:
                if 'mac' in iface:
                    all_macs.add(iface['mac'])
            for arp in result.arp_table:
                if 'mac' in arp:
                    all_macs.add(arp['mac'])

            for mac in all_macs:
                vendor = self._oui.lookup(mac)
                if vendor:
                    result.oui_lookups[mac] = vendor

        self.progress.emit("Done!")

    def _load_databases(self):
        """Load Recog and OUI databases"""
        recog_dir = self.data_dir / 'recog'
        self._ensure_data_files(recog_dir)

        if recog_dir.exists():
            self._recog = RecogMatcher(recog_dir)

        self._oui = OUILookup(self.data_dir)

    def _ensure_data_files(self, recog_dir: Path):
        """Download data files if not present"""
        import ssl

        self.data_dir.mkdir(parents=True, exist_ok=True)
        recog_dir.mkdir(exist_ok=True)

        # Create SSL context that doesn't verify certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        recog_files = {
            'snmp_sysdescr.xml': 'https://raw.githubusercontent.com/rapid7/recog/main/xml/snmp_sysdescr.xml',
            'snmp_sysobjid.xml': 'https://raw.githubusercontent.com/rapid7/recog/main/xml/snmp_sysobjid.xml',
        }

        for fname, url in recog_files.items():
            fpath = recog_dir / fname
            if not fpath.exists():
                try:
                    with urllib.request.urlopen(url, context=ssl_context) as response:
                        with open(fpath, 'wb') as f:
                            f.write(response.read())
                except Exception:
                    pass

        manuf_file = self.data_dir / 'manuf.txt'
        if not manuf_file.exists():
            url = 'https://www.wireshark.org/download/automated/data/manuf'
            try:
                with urllib.request.urlopen(url, context=ssl_context) as response:
                    with open(manuf_file, 'wb') as f:
                        f.write(response.read())
            except Exception:
                pass