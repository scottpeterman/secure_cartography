"""
Local SNMP Service for PyQt6 Applications

Windows-compatible, async-aware, fault-tolerant SNMP operations.
Uses QThread workers to bridge asyncio (pysnmp) with Qt's event loop.

Features:
- Pure Python (pysnmp-lextudio) - no external dependencies
- QThread-based async execution - reliable on Windows
- Circuit breaker pattern for unresponsive targets
- Semaphore-based concurrency limiting
- Automatic retries with exponential backoff
- Progress callbacks for UI updates

Usage:
    service = LocalSNMPService()

    # Connect signals
    service.poll_complete.connect(on_poll_complete)
    service.poll_progress.connect(on_progress)
    service.poll_error.connect(on_error)

    # Start a poll
    ticket = service.poll_device(
        target="192.168.1.1",
        community="public",
        version="2c"
    )

    # Cancel if needed
    service.cancel(ticket)

    # Cleanup on app exit
    service.shutdown()
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Optional, Dict, Any, List, Callable, Tuple

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer, QMutex, QMutexLocker

# pysnmp imports with fallback
try:
    from pysnmp.hlapi.asyncio import (
        SnmpEngine,
        CommunityData,
        UsmUserData,
        UdpTransportTarget,
        ContextData,
        ObjectType,
        ObjectIdentity,
        get_cmd,
        walk_cmd,
        # Auth protocols
        usmHMACMD5AuthProtocol,
        usmHMACSHAAuthProtocol,
        usmHMAC128SHA224AuthProtocol,
        usmHMAC192SHA256AuthProtocol,
        usmHMAC256SHA384AuthProtocol,
        usmHMAC384SHA512AuthProtocol,
        usmNoAuthProtocol,
        # Priv protocols
        usmDESPrivProtocol,
        usm3DESEDEPrivProtocol,
        usmAesCfb128Protocol,
        usmAesCfb192Protocol,
        usmAesCfb256Protocol,
        usmNoPrivProtocol,
    )

    PYSNMP_AVAILABLE = True
except ImportError:
    PYSNMP_AVAILABLE = False

log = logging.getLogger("local_snmp_service")


# =============================================================================
# Constants & Enums
# =============================================================================

class PollStatus(Enum):
    """Poll job lifecycle states"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


# SNMPv3 protocol mappings
AUTH_PROTOCOLS = {
    "MD5": usmHMACMD5AuthProtocol if PYSNMP_AVAILABLE else None,
    "SHA": usmHMACSHAAuthProtocol if PYSNMP_AVAILABLE else None,
    "SHA224": usmHMAC128SHA224AuthProtocol if PYSNMP_AVAILABLE else None,
    "SHA256": usmHMAC192SHA256AuthProtocol if PYSNMP_AVAILABLE else None,
    "SHA384": usmHMAC256SHA384AuthProtocol if PYSNMP_AVAILABLE else None,
    "SHA512": usmHMAC384SHA512AuthProtocol if PYSNMP_AVAILABLE else None,
    "NONE": usmNoAuthProtocol if PYSNMP_AVAILABLE else None,
}

PRIV_PROTOCOLS = {
    "DES": usmDESPrivProtocol if PYSNMP_AVAILABLE else None,
    "3DES": usm3DESEDEPrivProtocol if PYSNMP_AVAILABLE else None,
    "AES": usmAesCfb128Protocol if PYSNMP_AVAILABLE else None,
    "AES128": usmAesCfb128Protocol if PYSNMP_AVAILABLE else None,
    "AES192": usmAesCfb192Protocol if PYSNMP_AVAILABLE else None,
    "AES256": usmAesCfb256Protocol if PYSNMP_AVAILABLE else None,
    "NONE": usmNoPrivProtocol if PYSNMP_AVAILABLE else None,
}

# Standard OIDs
SYSTEM_OIDS = {
    'sysDescr': '1.3.6.1.2.1.1.1.0',
    'sysObjectID': '1.3.6.1.2.1.1.2.0',
    'sysName': '1.3.6.1.2.1.1.5.0',
    'sysContact': '1.3.6.1.2.1.1.4.0',
    'sysLocation': '1.3.6.1.2.1.1.6.0',
    'sysUpTime': '1.3.6.1.2.1.1.3.0',
}

IF_DESCR_OID = '1.3.6.1.2.1.2.2.1.2'
IF_PHYS_ADDR_OID = '1.3.6.1.2.1.2.2.1.6'
ARP_PHYS_ADDR_OID = '1.3.6.1.2.1.4.22.1.2'
ARP_NET_ADDR_OID = '1.3.6.1.2.1.4.22.1.3'


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SNMPv3Auth:
    """SNMPv3 authentication parameters"""
    username: str
    auth_protocol: str = "SHA"
    auth_password: Optional[str] = None
    priv_protocol: str = "AES"
    priv_password: Optional[str] = None


@dataclass
class PollRequest:
    """SNMP poll request parameters"""
    target: str
    community: str = "public"
    version: str = "2c"
    port: int = 161
    v3_auth: Optional[SNMPv3Auth] = None
    collect_interfaces: bool = True
    collect_arp: bool = True
    get_timeout: int = 10
    walk_timeout: int = 120
    retries: int = 2


@dataclass
class PollResult:
    """SNMP poll result"""
    ticket: str
    target: str
    status: PollStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timing: Dict[str, float] = field(default_factory=dict)
    elapsed: float = 0.0


@dataclass
class CircuitBreaker:
    """Circuit breaker for a target"""
    target: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure: Optional[float] = None
    last_success: Optional[float] = None

    # Thresholds
    failure_threshold: int = 3
    recovery_timeout: float = 60.0  # seconds

    def record_success(self):
        """Record successful operation"""
        self.failure_count = 0
        self.last_success = time.time()
        self.state = CircuitState.CLOSED

    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            log.warning(f"Circuit OPEN for {self.target} after {self.failure_count} failures")

    def can_attempt(self) -> bool:
        """Check if we can attempt an operation"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure and (time.time() - self.last_failure) > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                log.info(f"Circuit HALF_OPEN for {self.target}, testing recovery")
                return True
            return False

        # HALF_OPEN - allow one attempt
        return True


# =============================================================================
# SNMP Worker Thread
# =============================================================================

class SNMPWorker(QThread):
    """
    Worker thread for SNMP operations.

    Runs asyncio event loop in separate thread to avoid blocking Qt.
    """

    # Signals
    progress = pyqtSignal(str, str, dict)  # ticket, message, details
    complete = pyqtSignal(str, object)  # ticket, PollResult

    def __init__(self, ticket: str, request: PollRequest, parent=None):
        super().__init__(parent)
        self.ticket = ticket
        self.request = request
        self._cancelled = False
        self._cancel_event: Optional[asyncio.Event] = None

    def cancel(self):
        """Request cancellation"""
        self._cancelled = True
        if self._cancel_event:
            # Thread-safe way to set event
            try:
                self._cancel_event.set()
            except Exception:
                pass

    def run(self):
        """Execute SNMP poll in worker thread"""
        if not PYSNMP_AVAILABLE:
            result = PollResult(
                ticket=self.ticket,
                target=self.request.target,
                status=PollStatus.FAILED,
                error="pysnmp-lextudio not installed"
            )
            self.complete.emit(self.ticket, result)
            return

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(self._do_poll())
            self.complete.emit(self.ticket, result)
        except Exception as e:
            log.exception(f"Worker error for {self.request.target}")
            result = PollResult(
                ticket=self.ticket,
                target=self.request.target,
                status=PollStatus.FAILED,
                error=str(e)
            )
            self.complete.emit(self.ticket, result)
        finally:
            loop.close()

    async def _do_poll(self) -> PollResult:
        """Perform the actual SNMP poll"""
        start_time = time.time()
        self._cancel_event = asyncio.Event()

        req = self.request
        timing = {}
        data = {}

        # Check for early cancellation
        if self._cancelled:
            return PollResult(
                ticket=self.ticket,
                target=req.target,
                status=PollStatus.CANCELLED
            )

        self.progress.emit(self.ticket, "Connecting...", {})

        try:
            # Build credentials
            credentials = self._build_credentials()

            # Create transport with retry logic
            transport = await self._create_transport_with_retry()
            if not transport:
                return PollResult(
                    ticket=self.ticket,
                    target=req.target,
                    status=PollStatus.FAILED,
                    error=f"Could not connect to {req.target}:{req.port}",
                    elapsed=time.time() - start_time
                )

            # Phase 1: System OIDs
            self.progress.emit(self.ticket, "Getting system info...", {"phase": "system"})
            sys_start = time.time()

            system_data = await self._get_system_oids(credentials, transport)
            timing['system'] = time.time() - sys_start
            data['system'] = system_data

            if self._cancelled:
                return PollResult(
                    ticket=self.ticket,
                    target=req.target,
                    status=PollStatus.CANCELLED,
                    data=data,
                    timing=timing,
                    elapsed=time.time() - start_time
                )

            # Phase 2: Interfaces (optional)
            if req.collect_interfaces:
                self.progress.emit(self.ticket, "Walking interfaces...", {"phase": "interfaces"})
                if_start = time.time()

                interfaces = await self._walk_interfaces(credentials, transport)
                timing['interfaces'] = time.time() - if_start
                data['interfaces'] = interfaces

                self.progress.emit(
                    self.ticket,
                    f"Found {len(interfaces)} interfaces",
                    {"phase": "interfaces", "count": len(interfaces)}
                )

            if self._cancelled:
                return PollResult(
                    ticket=self.ticket,
                    target=req.target,
                    status=PollStatus.CANCELLED,
                    data=data,
                    timing=timing,
                    elapsed=time.time() - start_time
                )

            # Phase 3: ARP/Neighbors (optional)
            if req.collect_arp:
                self.progress.emit(self.ticket, "Walking ARP table...", {"phase": "arp"})
                arp_start = time.time()

                arp_entries = await self._walk_arp(credentials, transport)
                timing['arp'] = time.time() - arp_start
                data['arp'] = arp_entries

                self.progress.emit(
                    self.ticket,
                    f"Found {len(arp_entries)} ARP entries",
                    {"phase": "arp", "count": len(arp_entries)}
                )

            elapsed = time.time() - start_time
            timing['total'] = elapsed

            return PollResult(
                ticket=self.ticket,
                target=req.target,
                status=PollStatus.COMPLETE,
                data=data,
                timing=timing,
                elapsed=elapsed
            )

        except asyncio.CancelledError:
            return PollResult(
                ticket=self.ticket,
                target=req.target,
                status=PollStatus.CANCELLED,
                elapsed=time.time() - start_time
            )
        except Exception as e:
            log.exception(f"Poll failed for {req.target}")
            return PollResult(
                ticket=self.ticket,
                target=req.target,
                status=PollStatus.FAILED,
                error=str(e),
                elapsed=time.time() - start_time
            )

    def _build_credentials(self):
        """Build pysnmp credentials"""
        req = self.request

        if req.version == "3" and req.v3_auth:
            auth = req.v3_auth
            auth_proto = AUTH_PROTOCOLS.get(auth.auth_protocol.upper(), usmHMACSHAAuthProtocol)
            priv_proto = PRIV_PROTOCOLS.get(auth.priv_protocol.upper(), usmAesCfb128Protocol)

            return UsmUserData(
                auth.username,
                authKey=auth.auth_password,
                privKey=auth.priv_password,
                authProtocol=auth_proto,
                privProtocol=priv_proto,
            )
        else:
            mp_model = 1 if req.version == "2c" else 0
            return CommunityData(req.community, mpModel=mp_model)

    async def _create_transport_with_retry(self) -> Optional[UdpTransportTarget]:
        """Create transport with retry logic"""
        req = self.request
        last_error = None

        for attempt in range(req.retries + 1):
            if self._cancelled:
                return None

            try:
                transport = await UdpTransportTarget.create(
                    (req.target, req.port),
                    timeout=req.get_timeout,
                    retries=1
                )
                return transport
            except Exception as e:
                last_error = e
                if attempt < req.retries:
                    # Exponential backoff
                    delay = min(2 ** attempt, 10)
                    log.debug(f"Transport creation failed, retry in {delay}s: {e}")
                    await asyncio.sleep(delay)

        log.warning(f"Transport creation failed after {req.retries + 1} attempts: {last_error}")
        return None

    async def _get_system_oids(self, credentials, transport) -> Dict[str, str]:
        """Get system OIDs with individual error handling"""
        system_data = {}

        for name, oid in SYSTEM_OIDS.items():
            if self._cancelled:
                break

            try:
                error_indication, error_status, error_index, var_binds = await get_cmd(
                    SnmpEngine(),
                    credentials,
                    transport,
                    ContextData(),
                    ObjectType(ObjectIdentity(oid))
                )

                if not error_indication and not error_status and var_binds:
                    value = var_binds[0][1].prettyPrint()
                    if value and "No Such" not in value:
                        system_data[name] = value

            except Exception as e:
                log.debug(f"Failed to get {name}: {e}")
                continue

        return system_data

    async def _walk_interfaces(self, credentials, transport) -> List[Dict[str, Any]]:
        """Walk interface table"""
        interfaces = []

        # Walk ifDescr
        try:
            if_descr = {}
            async for error_indication, error_status, error_index, var_binds in walk_cmd(
                    SnmpEngine(),
                    credentials,
                    transport,
                    ContextData(),
                    ObjectType(ObjectIdentity(IF_DESCR_OID)),
                    lexicographicMode=False,
            ):
                if self._cancelled:
                    break
                if error_indication or error_status:
                    break

                for var_bind in var_binds:
                    oid_str = str(var_bind[0])
                    # Extract index from OID
                    idx = oid_str.split('.')[-1]
                    if_descr[idx] = var_bind[1].prettyPrint()

            # Walk ifPhysAddress (MAC)
            if_mac = {}
            async for error_indication, error_status, error_index, var_binds in walk_cmd(
                    SnmpEngine(),
                    credentials,
                    transport,
                    ContextData(),
                    ObjectType(ObjectIdentity(IF_PHYS_ADDR_OID)),
                    lexicographicMode=False,
            ):
                if self._cancelled:
                    break
                if error_indication or error_status:
                    break

                for var_bind in var_binds:
                    oid_str = str(var_bind[0])
                    idx = oid_str.split('.')[-1]
                    mac = self._normalize_mac(var_bind[1])
                    if mac:
                        if_mac[idx] = mac

            # Combine into interface list
            for idx, descr in if_descr.items():
                interfaces.append({
                    'index': idx,
                    'name': descr,
                    'mac': if_mac.get(idx, '')
                })

        except Exception as e:
            log.warning(f"Interface walk failed: {e}")

        return interfaces

    async def _walk_arp(self, credentials, transport) -> List[Dict[str, str]]:
        """Walk ARP/neighbor table"""
        arp_entries = []

        try:
            # Walk ipNetToMediaPhysAddress
            async for error_indication, error_status, error_index, var_binds in walk_cmd(
                    SnmpEngine(),
                    credentials,
                    transport,
                    ContextData(),
                    ObjectType(ObjectIdentity(ARP_PHYS_ADDR_OID)),
                    lexicographicMode=False,
            ):
                if self._cancelled:
                    break
                if error_indication or error_status:
                    break

                for var_bind in var_binds:
                    oid_str = str(var_bind[0])
                    # OID format: .1.3.6.1.2.1.4.22.1.2.<ifIndex>.<ip.address>
                    parts = oid_str.split('.')
                    if len(parts) >= 4:
                        ip_parts = parts[-4:]
                        ip = '.'.join(ip_parts)
                        mac = self._normalize_mac(var_bind[1])
                        if mac:
                            arp_entries.append({'ip': ip, 'mac': mac})

        except Exception as e:
            log.warning(f"ARP walk failed: {e}")

        return arp_entries

    def _normalize_mac(self, mac_value) -> str:
        """Normalize MAC address to AA:BB:CC:DD:EE:FF format"""
        if mac_value is None:
            return ""

        # Handle pysnmp OctetString
        if hasattr(mac_value, 'asNumbers'):
            octets = mac_value.asNumbers()
            if len(octets) == 6:
                return ':'.join(f'{b:02X}' for b in octets)
            return ""

        # String handling
        clean = str(mac_value).strip()
        if not clean or clean in ('', '""', "''"):
            return ""

        # Various formats
        if clean.startswith('0x'):
            hex_str = clean[2:].replace(' ', '')
            if len(hex_str) >= 12:
                return ':'.join([hex_str[i:i + 2].upper() for i in range(0, 12, 2)])

        if ' ' in clean and ':' not in clean:
            parts = clean.split()
            if len(parts) == 6:
                return ':'.join(p.upper().zfill(2) for p in parts)

        if ':' in clean:
            parts = clean.split(':')
            if len(parts) == 6:
                return ':'.join(p.upper().zfill(2) for p in parts)

        if '-' in clean and len(clean) == 17:
            return clean.upper().replace('-', ':')

        return clean


# =============================================================================
# Local SNMP Service
# =============================================================================

class LocalSNMPService(QObject):
    """
    Local SNMP service for PyQt applications.

    Manages poll jobs, worker threads, and circuit breakers.
    Thread-safe for use from Qt's main thread.

    Signals:
        poll_complete(str, PollResult): Emitted when poll finishes (ticket, result)
        poll_progress(str, str, dict): Progress updates (ticket, message, details)
        poll_error(str, str): Error occurred (ticket, error_message)
    """

    # Signals
    poll_complete = pyqtSignal(str, object)
    poll_progress = pyqtSignal(str, str, dict)
    poll_error = pyqtSignal(str, str)

    def __init__(
            self,
            max_concurrent: int = 4,
            circuit_failure_threshold: int = 3,
            circuit_recovery_timeout: float = 60.0,
            parent=None
    ):
        super().__init__(parent)

        self._max_concurrent = max_concurrent
        self._circuit_failure_threshold = circuit_failure_threshold
        self._circuit_recovery_timeout = circuit_recovery_timeout

        # Thread-safe state
        self._mutex = QMutex()
        self._workers: Dict[str, SNMPWorker] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._pending_requests: List[Tuple[str, PollRequest]] = []

        # Cleanup timer for finished workers
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.timeout.connect(self._cleanup_finished)
        self._cleanup_timer.start(5000)  # Every 5 seconds

    @property
    def active_count(self) -> int:
        """Number of active polls"""
        with QMutexLocker(self._mutex):
            return sum(1 for w in self._workers.values() if w.isRunning())

    @property
    def pending_count(self) -> int:
        """Number of pending polls"""
        with QMutexLocker(self._mutex):
            return len(self._pending_requests)

    def poll_device(
            self,
            target: str,
            community: str = "public",
            version: str = "2c",
            port: int = 161,
            v3_auth: Optional[SNMPv3Auth] = None,
            collect_interfaces: bool = True,
            collect_arp: bool = True,
            get_timeout: int = 10,
            walk_timeout: int = 120,
            retries: int = 2,
    ) -> str:
        """
        Start polling a device.

        Returns ticket ID for tracking.
        """
        if not PYSNMP_AVAILABLE:
            ticket = str(uuid.uuid4())
            # Emit error on next event loop iteration
            QTimer.singleShot(0, lambda: self.poll_error.emit(
                ticket, "pysnmp-lextudio not installed"
            ))
            return ticket

        request = PollRequest(
            target=target,
            community=community,
            version=version,
            port=port,
            v3_auth=v3_auth,
            collect_interfaces=collect_interfaces,
            collect_arp=collect_arp,
            get_timeout=get_timeout,
            walk_timeout=walk_timeout,
            retries=retries,
        )

        ticket = str(uuid.uuid4())

        # Check circuit breaker
        cb = self._get_circuit_breaker(target)
        if not cb.can_attempt():
            # Circuit is open
            log.warning(f"Circuit open for {target}, rejecting poll")
            QTimer.singleShot(0, lambda: self.poll_error.emit(
                ticket, f"Target {target} is unresponsive (circuit open)"
            ))
            return ticket

        # Queue or start
        with QMutexLocker(self._mutex):
            if self.active_count >= self._max_concurrent:
                # Queue for later
                self._pending_requests.append((ticket, request))
                log.debug(f"Queued poll for {target}, {len(self._pending_requests)} pending")
            else:
                self._start_worker(ticket, request)

        return ticket

    def cancel(self, ticket: str) -> bool:
        """Cancel a poll by ticket"""
        with QMutexLocker(self._mutex):
            # Check if running
            if ticket in self._workers:
                worker = self._workers[ticket]
                worker.cancel()
                return True

            # Check if pending
            for i, (t, _) in enumerate(self._pending_requests):
                if t == ticket:
                    self._pending_requests.pop(i)
                    return True

        return False

    def cancel_all(self):
        """Cancel all pending and running polls"""
        with QMutexLocker(self._mutex):
            # Cancel running
            for worker in self._workers.values():
                worker.cancel()

            # Clear pending
            self._pending_requests.clear()

    def get_circuit_state(self, target: str) -> CircuitState:
        """Get circuit breaker state for target"""
        cb = self._get_circuit_breaker(target)
        return cb.state

    def reset_circuit(self, target: str):
        """Reset circuit breaker for target"""
        with QMutexLocker(self._mutex):
            if target in self._circuit_breakers:
                self._circuit_breakers[target] = CircuitBreaker(
                    target=target,
                    failure_threshold=self._circuit_failure_threshold,
                    recovery_timeout=self._circuit_recovery_timeout,
                )

    def shutdown(self):
        """Shutdown service and cleanup"""
        self._cleanup_timer.stop()
        self.cancel_all()

        # Wait for workers to finish (with timeout)
        with QMutexLocker(self._mutex):
            for worker in self._workers.values():
                worker.wait(5000)  # 5 second timeout

    def _get_circuit_breaker(self, target: str) -> CircuitBreaker:
        """Get or create circuit breaker for target"""
        with QMutexLocker(self._mutex):
            if target not in self._circuit_breakers:
                self._circuit_breakers[target] = CircuitBreaker(
                    target=target,
                    failure_threshold=self._circuit_failure_threshold,
                    recovery_timeout=self._circuit_recovery_timeout,
                )
            return self._circuit_breakers[target]

    def _start_worker(self, ticket: str, request: PollRequest):
        """Start a worker thread (must hold mutex)"""
        worker = SNMPWorker(ticket, request, self)
        worker.progress.connect(self._on_worker_progress)
        worker.complete.connect(self._on_worker_complete)

        self._workers[ticket] = worker
        worker.start()

        log.debug(f"Started poll for {request.target}")

    def _on_worker_progress(self, ticket: str, message: str, details: dict):
        """Handle worker progress"""
        self.poll_progress.emit(ticket, message, details)

    def _on_worker_complete(self, ticket: str, result: PollResult):
        """Handle worker completion"""
        # Update circuit breaker
        cb = self._get_circuit_breaker(result.target)
        if result.status == PollStatus.COMPLETE:
            cb.record_success()
        elif result.status == PollStatus.FAILED:
            cb.record_failure()

        # Emit result
        if result.status == PollStatus.FAILED:
            self.poll_error.emit(ticket, result.error or "Unknown error")
        self.poll_complete.emit(ticket, result)

        # Start next pending if any
        self._start_pending()

    def _start_pending(self):
        """Start next pending request if capacity available"""
        with QMutexLocker(self._mutex):
            while self._pending_requests and self.active_count < self._max_concurrent:
                ticket, request = self._pending_requests.pop(0)

                # Re-check circuit breaker
                cb = self._get_circuit_breaker(request.target)
                if cb.can_attempt():
                    self._start_worker(ticket, request)
                else:
                    # Skip this one, circuit still open
                    QTimer.singleShot(0, lambda t=ticket, tgt=request.target:
                    self.poll_error.emit(t, f"Target {tgt} is unresponsive"))

    def _cleanup_finished(self):
        """Clean up finished worker threads"""
        with QMutexLocker(self._mutex):
            finished = [t for t, w in self._workers.items() if w.isFinished()]
            for ticket in finished:
                worker = self._workers.pop(ticket)
                worker.deleteLater()


# =============================================================================
# Convenience Functions
# =============================================================================

_default_service: Optional[LocalSNMPService] = None


def get_snmp_service() -> LocalSNMPService:
    """Get the default SNMP service instance"""
    global _default_service
    if _default_service is None:
        _default_service = LocalSNMPService()
    return _default_service


def poll_device(target: str, **kwargs) -> str:
    """Convenience function to poll a device"""
    return get_snmp_service().poll_device(target, **kwargs)


# =============================================================================
# Test
# =============================================================================

if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    service = LocalSNMPService()


    def on_progress(ticket, message, details):
        print(f"[{ticket[:8]}] {message} {details}")


    def on_complete(ticket, result):
        print(f"[{ticket[:8]}] Complete: {result.status.value}")
        if result.data:
            print(f"  System: {result.data.get('system', {})}")
            print(f"  Interfaces: {len(result.data.get('interfaces', []))}")
            print(f"  ARP: {len(result.data.get('arp', []))}")
        if result.error:
            print(f"  Error: {result.error}")
        print(f"  Timing: {result.timing}")
        app.quit()


    def on_error(ticket, error):
        print(f"[{ticket[:8]}] Error: {error}")


    service.poll_progress.connect(on_progress)
    service.poll_complete.connect(on_complete)
    service.poll_error.connect(on_error)

    # Test with localhost or specify target
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    community = sys.argv[2] if len(sys.argv) > 2 else "public"

    print(f"Polling {target}...")
    ticket = service.poll_device(target, community=community)

    # Timeout after 60 seconds
    QTimer.singleShot(60000, app.quit)

    sys.exit(app.exec())