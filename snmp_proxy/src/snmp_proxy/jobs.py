"""
Job management for async SNMP polling

Handles ticket-based job submission, execution, and lifecycle management.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from .models import JobStatus, SNMPPollRequest, SNMPv3Auth
from .snmp_ops import (
    snmp_get, snmp_walk, mac_to_string,
    SYSTEM_OIDS, IF_DESCR_OID, IF_PHYS_ADDR_OID,
    ARP_PHYS_ADDR_OID, ARP_NET_ADDR_OID,
)


log = logging.getLogger("snmp_proxy.jobs")


# =============================================================================
# Poll Job
# =============================================================================

@dataclass
class PollJob:
    """Represents a single poll job"""
    
    # Identity
    ticket: str
    target: str
    
    # SNMP config
    community: str = "public"
    version: str = "2c"
    port: int = 161
    v3_auth: Optional[SNMPv3Auth] = None
    
    # Collection options
    collect_interfaces: bool = True
    collect_arp: bool = True
    get_timeout: int = 10
    walk_timeout: int = 120
    
    # State
    status: JobStatus = JobStatus.QUEUED
    progress: str = ""
    progress_detail: Dict[str, Any] = field(default_factory=dict)
    
    # Results
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timing: Dict[str, float] = field(default_factory=dict)
    
    # Lifecycle
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Cancellation - created lazily to avoid issues with default_factory
    _cancel_event: Optional[asyncio.Event] = field(default=None, repr=False)
    
    @property
    def cancel_event(self) -> asyncio.Event:
        """Lazy creation of cancel event"""
        if self._cancel_event is None:
            self._cancel_event = asyncio.Event()
        return self._cancel_event
    
    def request_cancel(self):
        """Signal cancellation"""
        self.cancel_event.set()
    
    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event is not None and self._cancel_event.is_set()
    
    @property
    def elapsed_seconds(self) -> Optional[float]:
        """Get elapsed time since start"""
        if self.started_at is None:
            return None
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()
    
    def to_status_dict(self) -> Dict[str, Any]:
        """Convert to status response dict"""
        return {
            "ticket": self.ticket,
            "target": self.target,
            "status": self.status.value,
            "progress": self.progress,
            "progress_detail": self.progress_detail,
            "elapsed_seconds": self.elapsed_seconds,
            "data": self.result if self.status == JobStatus.COMPLETE else None,
            "timing": self.timing if self.status == JobStatus.COMPLETE else None,
            "error": self.error if self.status == JobStatus.FAILED else None,
        }
    
    def to_list_dict(self) -> Dict[str, Any]:
        """Convert to job list entry"""
        return {
            "ticket": self.ticket,
            "target": self.target,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "elapsed_seconds": self.elapsed_seconds,
        }


# =============================================================================
# Job Manager
# =============================================================================

class JobManager:
    """
    Manages poll jobs with concurrency control and cleanup.
    """
    
    def __init__(self, max_concurrent: int = 6, retention_hours: int = 1):
        self.max_concurrent = max_concurrent
        self.retention_hours = retention_hours
        
        self._jobs: Dict[str, PollJob] = {}
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._started_at: Optional[datetime] = None
    
    async def start(self):
        """Initialize the job manager"""
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._started_at = datetime.now()
        log.info(f"JobManager started: max_concurrent={self.max_concurrent}")
    
    async def stop(self):
        """Shutdown the job manager"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all running jobs
        for job in self._jobs.values():
            if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                job.request_cancel()
        
        log.info("JobManager stopped")
    
    @property
    def uptime_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        return (datetime.now() - self._started_at).total_seconds()
    
    def get_job(self, ticket: str) -> Optional[PollJob]:
        """Get a job by ticket"""
        return self._jobs.get(ticket)
    
    def list_jobs(self, status: Optional[JobStatus] = None) -> List[PollJob]:
        """List jobs, optionally filtered by status"""
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)
    
    @property
    def active_count(self) -> int:
        """Number of active (queued + running) jobs"""
        return sum(
            1 for j in self._jobs.values()
            if j.status in (JobStatus.QUEUED, JobStatus.RUNNING)
        )
    
    @property
    def total_count(self) -> int:
        """Total number of jobs in memory"""
        return len(self._jobs)
    
    async def submit(self, ticket: str, request: SNMPPollRequest) -> PollJob:
        """Submit a new poll job"""
        job = PollJob(
            ticket=ticket,
            target=request.target,
            community=request.community,
            version=request.version,
            port=request.port,
            v3_auth=request.v3_auth,
            collect_interfaces=request.collect_interfaces,
            collect_arp=request.collect_arp,
            get_timeout=request.get_timeout,
            walk_timeout=request.walk_timeout,
        )
        
        self._jobs[ticket] = job
        
        # Start execution in background
        asyncio.create_task(self._execute_job(ticket))
        
        log.info(f"[{ticket[:8]}] Job submitted for {request.target}")
        return job
    
    def cancel(self, ticket: str) -> bool:
        """Cancel a job"""
        job = self._jobs.get(ticket)
        if not job:
            return False
        
        if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            job.request_cancel()
            log.info(f"[{ticket[:8]}] Cancellation requested")
            return True
        
        return False
    
    def delete(self, ticket: str) -> bool:
        """Delete a completed/failed job"""
        job = self._jobs.get(ticket)
        if not job:
            return False
        
        if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            # Cancel first
            job.request_cancel()
        
        del self._jobs[ticket]
        log.info(f"[{ticket[:8]}] Job deleted")
        return True
    
    async def _execute_job(self, ticket: str):
        """Execute a poll job with semaphore control"""
        job = self._jobs.get(ticket)
        if not job:
            return
        
        async with self._semaphore:
            await self._run_poll(job)
    
    async def _run_poll(self, job: PollJob):
        """Run the actual SNMP poll"""
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        job.progress = "Starting poll..."
        
        log.info(f"[{job.ticket[:8]}] Starting poll for {job.target}")
        
        try:
            result_data = {
                'target': job.target,
                'snmp_data': {},
                'interfaces': [],
                'arp_table': [],
            }
            
            # Check cancellation
            if job.is_cancelled:
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now()
                return
            
            # === System Info ===
            job.progress = "Collecting system information..."
            sys_start = datetime.now()
            
            for name, oid in SYSTEM_OIDS.items():
                if job.is_cancelled:
                    break
                    
                success, value, _ = await snmp_get(
                    job.target, oid,
                    community=job.community,
                    version=job.version,
                    port=job.port,
                    timeout=job.get_timeout,
                    v3_auth=job.v3_auth,
                )
                if success:
                    result_data['snmp_data'][name] = value
            
            job.timing['system_info'] = (datetime.now() - sys_start).total_seconds()
            
            # Verify we got something
            if not result_data['snmp_data']:
                job.status = JobStatus.FAILED
                job.error = f"No SNMP response from {job.target}"
                job.completed_at = datetime.now()
                log.error(f"[{job.ticket[:8]}] No SNMP response from {job.target}")
                return
            
            job.progress_detail['system_oids'] = len(result_data['snmp_data'])
            log.info(f"[{job.ticket[:8]}] System info: {len(result_data['snmp_data'])} OIDs")
            
            # === Interfaces ===
            if job.collect_interfaces and not job.is_cancelled:
                await self._collect_interfaces(job, result_data)
            
            # === ARP Table ===
            if job.collect_arp and not job.is_cancelled:
                await self._collect_arp(job, result_data)
            
            # === Complete ===
            if job.is_cancelled:
                job.status = JobStatus.CANCELLED
            else:
                job.status = JobStatus.COMPLETE
                job.result = result_data
                job.timing['total'] = (datetime.now() - job.started_at).total_seconds()
                job.progress = "Complete"
                log.info(f"[{job.ticket[:8]}] Poll complete in {job.timing['total']:.1f}s")
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            log.exception(f"[{job.ticket[:8]}] Poll failed")
        
        job.completed_at = datetime.now()
    
    async def _collect_interfaces(self, job: PollJob, result_data: Dict):
        """Collect interface table"""
        job.progress = "Walking interface table..."
        iface_start = datetime.now()
        
        def iface_progress(count):
            job.progress = f"Walking interfaces... ({count} entries)"
            job.progress_detail['interfaces_walked'] = count
        
        success, if_descrs, _ = await snmp_walk(
            job.target, IF_DESCR_OID,
            community=job.community,
            version=job.version,
            port=job.port,
            timeout=job.walk_timeout,
            v3_auth=job.v3_auth,
            cancel_event=job.cancel_event,
            progress_callback=iface_progress,
        )
        
        if not success or not if_descrs:
            job.timing['interfaces'] = (datetime.now() - iface_start).total_seconds()
            return
        
        # Get MACs
        job.progress = f"Getting interface MACs for {len(if_descrs)} interfaces..."
        
        _, if_macs, _ = await snmp_walk(
            job.target, IF_PHYS_ADDR_OID,
            community=job.community,
            version=job.version,
            port=job.port,
            timeout=job.walk_timeout,
            v3_auth=job.v3_auth,
            cancel_event=job.cancel_event,
        )
        
        # Build MAC lookup by interface index
        mac_map = {}
        for entry in (if_macs or []):
            # OID format: .1.3.6.1.2.1.2.2.1.6.{ifIndex}
            idx = entry['oid'].split('.')[-1]
            mac_map[idx] = entry['value']
        
        # Combine
        for entry in if_descrs:
            idx = entry['oid'].split('.')[-1]
            iface = {'description': entry['value_str']}
            
            if idx in mac_map:
                mac = mac_to_string(mac_map[idx])
                if mac and len(mac) >= 12 and mac != '00:00:00:00:00:00':
                    iface['mac'] = mac
            
            result_data['interfaces'].append(iface)
        
        job.timing['interfaces'] = (datetime.now() - iface_start).total_seconds()
        job.progress_detail['interfaces_total'] = len(result_data['interfaces'])
        log.info(f"[{job.ticket[:8]}] Interfaces: {len(result_data['interfaces'])} ({job.timing['interfaces']:.1f}s)")
    
    async def _collect_arp(self, job: PollJob, result_data: Dict):
        """Collect ARP/neighbor table"""
        job.progress = "Walking ARP table..."
        arp_start = datetime.now()
        
        def arp_progress(count):
            job.progress = f"Walking ARP table... ({count} entries)"
            job.progress_detail['arp_walked'] = count
        
        success, arp_macs, _ = await snmp_walk(
            job.target, ARP_PHYS_ADDR_OID,
            community=job.community,
            version=job.version,
            port=job.port,
            timeout=job.walk_timeout,
            v3_auth=job.v3_auth,
            cancel_event=job.cancel_event,
            progress_callback=arp_progress,
        )
        
        if not success or not arp_macs:
            job.timing['arp'] = (datetime.now() - arp_start).total_seconds()
            return
        
        # Get IPs
        job.progress = f"Getting ARP IPs for {len(arp_macs)} entries..."
        
        _, arp_ips, _ = await snmp_walk(
            job.target, ARP_NET_ADDR_OID,
            community=job.community,
            version=job.version,
            port=job.port,
            timeout=job.walk_timeout,
            v3_auth=job.v3_auth,
            cancel_event=job.cancel_event,
        )
        
        # Build IP lookup
        # OID format: .1.3.6.1.2.1.4.22.1.3.{ifIndex}.{a}.{b}.{c}.{d}
        ip_map = {}
        for entry in (arp_ips or []):
            # Use last 5 parts as key (ifIndex + IP)
            parts = entry['oid'].split('.')
            if len(parts) >= 5:
                key = '.'.join(parts[-5:])
                ip_map[key] = entry['value_str']
        
        # Combine
        for entry in arp_macs:
            parts = entry['oid'].split('.')
            key = '.'.join(parts[-5:]) if len(parts) >= 5 else ''
            
            mac = mac_to_string(entry['value'])
            arp_entry = {'mac': mac}
            
            if key in ip_map:
                arp_entry['ip'] = ip_map[key]
            
            result_data['arp_table'].append(arp_entry)
        
        job.timing['arp'] = (datetime.now() - arp_start).total_seconds()
        job.progress_detail['arp_total'] = len(result_data['arp_table'])
        log.info(f"[{job.ticket[:8]}] ARP: {len(result_data['arp_table'])} ({job.timing['arp']:.1f}s)")
    
    async def _cleanup_loop(self):
        """Periodically clean up old jobs"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                cutoff = datetime.now() - timedelta(hours=self.retention_hours)
                expired = [
                    ticket for ticket, job in self._jobs.items()
                    if job.completed_at and job.completed_at < cutoff
                ]
                
                for ticket in expired:
                    del self._jobs[ticket]
                
                if expired:
                    log.debug(f"Cleaned up {len(expired)} expired jobs")
                    
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Error in cleanup loop")
