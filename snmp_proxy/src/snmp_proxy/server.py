"""
FastAPI server for SNMP Proxy

Provides REST API for submitting and monitoring SNMP poll jobs.
"""

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .models import (
    SNMPPollRequest, SNMPGetRequest, SNMPWalkRequest,
    SubmitResponse, StatusResponse, SNMPResponse,
    HealthResponse, JobListResponse,
)
from .jobs import JobManager, JobStatus
from .snmp_ops import snmp_get, snmp_walk


log = logging.getLogger("snmp_proxy.server")


# =============================================================================
# Global State
# =============================================================================

# These are set during startup
_api_key: Optional[str] = None
_job_manager: Optional[JobManager] = None


def set_api_key(key: str):
    """Set the API key (called from __main__)"""
    global _api_key
    _api_key = key


def get_job_manager() -> JobManager:
    """Get the job manager instance"""
    if _job_manager is None:
        raise RuntimeError("Server not started")
    return _job_manager


# =============================================================================
# Lifespan Management
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown"""
    global _job_manager
    
    # Get config from app state
    max_concurrent = getattr(app.state, 'max_concurrent', 6)
    retention_hours = getattr(app.state, 'retention_hours', 1)
    
    # Start job manager
    _job_manager = JobManager(
        max_concurrent=max_concurrent,
        retention_hours=retention_hours,
    )
    await _job_manager.start()
    
    log.info(f"SNMP Proxy v{__version__} started")
    
    yield
    
    # Shutdown
    await _job_manager.stop()
    log.info("SNMP Proxy stopped")


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="SNMP Proxy",
    description="Async ticket-based SNMP proxy for remote device polling",
    version=__version__,
    lifespan=lifespan,
)

# CORS for browser-based clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Authentication
# =============================================================================

async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Verify the API key from header"""
    if _api_key is None:
        # No key set, allow all (for testing)
        return "test"
    
    if not x_api_key:
        log.warning("Request rejected: Missing X-API-Key header")
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    
    if x_api_key != _api_key:
        log.warning(f"Request rejected: Invalid API key")
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return x_api_key


# =============================================================================
# Health & Info Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check - no auth required"""
    jm = get_job_manager()
    return HealthResponse(
        status="ok",
        version=__version__,
        active_jobs=jm.active_count,
        total_jobs=jm.total_count,
        max_concurrent=jm.max_concurrent,
        uptime_seconds=jm.uptime_seconds,
    )


@app.get("/jobs", response_model=JobListResponse, dependencies=[Depends(verify_api_key)])
async def list_jobs(status: Optional[str] = None):
    """List all jobs, optionally filtered by status"""
    jm = get_job_manager()
    
    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    
    jobs = jm.list_jobs(status=status_filter)
    return JobListResponse(
        jobs=[j.to_list_dict() for j in jobs],
        total=len(jobs),
    )


# =============================================================================
# Poll Job Endpoints
# =============================================================================

@app.post("/snmp/poll", response_model=SubmitResponse)
async def submit_poll(
    request: SNMPPollRequest,
    api_key: str = Depends(verify_api_key),
):
    """Submit a poll job and return ticket immediately"""
    jm = get_job_manager()
    ticket = str(uuid.uuid4())
    
    job = await jm.submit(ticket, request)
    
    return SubmitResponse(
        ticket=ticket,
        status=job.status.value,
        target=request.target,
    )


@app.get("/status/{ticket}", response_model=StatusResponse)
async def get_status(
    ticket: str,
    api_key: str = Depends(verify_api_key),
):
    """Check job status and get results when complete"""
    jm = get_job_manager()
    job = jm.get_job(ticket)
    
    if not job:
        raise HTTPException(404, "Unknown ticket")
    
    return StatusResponse(**job.to_status_dict())


@app.delete("/jobs/{ticket}")
async def cancel_or_delete_job(
    ticket: str,
    api_key: str = Depends(verify_api_key),
):
    """Cancel a running job or delete a completed one"""
    jm = get_job_manager()
    job = jm.get_job(ticket)
    
    if not job:
        raise HTTPException(404, "Unknown ticket")
    
    if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
        jm.cancel(ticket)
        return {"status": "cancelling", "ticket": ticket}
    else:
        jm.delete(ticket)
        return {"status": "deleted", "ticket": ticket}


# =============================================================================
# Direct SNMP Endpoints (for simple operations)
# =============================================================================

@app.post("/snmp/get", response_model=SNMPResponse)
async def direct_snmp_get(
    request: SNMPGetRequest,
    api_key: str = Depends(verify_api_key),
):
    """Direct SNMP GET - single OID, immediate response"""
    log.info(f"SNMP GET: {request.target} OID={request.oid}")
    
    success, result, duration = await snmp_get(
        target=request.target,
        oid=request.oid,
        community=request.community,
        version=request.version,
        port=request.port,
        timeout=request.timeout,
        v3_auth=request.v3_auth,
    )
    
    return SNMPResponse(
        success=success,
        data=result if success else None,
        error=None if success else result,
        timing={"get": duration},
    )


@app.post("/snmp/walk", response_model=SNMPResponse)
async def direct_snmp_walk(
    request: SNMPWalkRequest,
    api_key: str = Depends(verify_api_key),
):
    """Direct SNMP WALK - subtree walk, immediate response"""
    log.info(f"SNMP WALK: {request.target} OID={request.oid}")
    
    success, result, duration = await snmp_walk(
        target=request.target,
        oid=request.oid,
        community=request.community,
        version=request.version,
        port=request.port,
        timeout=request.timeout,
        v3_auth=request.v3_auth,
    )
    
    if success:
        # Convert to serializable format
        data = [{'oid': r['oid'], 'value': r['value_str']} for r in result]
        return SNMPResponse(
            success=True,
            data=data,
            timing={"walk": duration},
        )
    else:
        return SNMPResponse(
            success=False,
            error=result,
            timing={"walk": duration},
        )
