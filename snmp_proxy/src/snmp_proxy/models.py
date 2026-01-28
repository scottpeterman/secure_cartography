"""
Pydantic models for API request/response
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class JobStatus(Enum):
    """Job lifecycle states"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# Request Models
# =============================================================================

class SNMPv3Auth(BaseModel):
    """SNMPv3 authentication parameters"""
    username: str = Field(..., description="SNMPv3 username")
    auth_protocol: str = Field(default="SHA", description="Auth protocol: MD5, SHA, SHA224, SHA256, SHA384, SHA512")
    auth_password: Optional[str] = Field(default=None, description="Auth password")
    priv_protocol: str = Field(default="AES", description="Privacy protocol: DES, 3DES, AES, AES192, AES256")
    priv_password: Optional[str] = Field(default=None, description="Privacy password")


class SNMPPollRequest(BaseModel):
    """Request to poll a device via SNMP"""
    target: str = Field(..., description="Target IP address or hostname")
    community: str = Field(default="public", description="SNMP community string (v1/v2c)")
    version: str = Field(default="2c", description="SNMP version: 1, 2c, or 3")
    port: int = Field(default=161, description="SNMP port")
    
    # SNMPv3 auth (optional, only used when version=3)
    v3_auth: Optional[SNMPv3Auth] = Field(default=None, description="SNMPv3 authentication")
    
    # Collection options
    collect_interfaces: bool = Field(default=True, description="Collect interface table")
    collect_arp: bool = Field(default=True, description="Collect ARP/neighbor table")
    
    # Timeouts
    get_timeout: int = Field(default=10, ge=1, le=60, description="Timeout for GET operations")
    walk_timeout: int = Field(default=120, ge=10, le=600, description="Timeout for WALK operations")


class SNMPGetRequest(BaseModel):
    """Request for single SNMP GET"""
    target: str = Field(..., description="Target IP address")
    community: str = Field(default="public")
    version: str = Field(default="2c")
    port: int = Field(default=161)
    oid: str = Field(..., description="OID to retrieve")
    timeout: int = Field(default=10, ge=1, le=60)
    v3_auth: Optional[SNMPv3Auth] = None


class SNMPWalkRequest(BaseModel):
    """Request for SNMP WALK"""
    target: str = Field(..., description="Target IP address")
    community: str = Field(default="public")
    version: str = Field(default="2c")
    port: int = Field(default=161)
    oid: str = Field(..., description="Base OID to walk")
    timeout: int = Field(default=120, ge=10, le=600)
    v3_auth: Optional[SNMPv3Auth] = None


# =============================================================================
# Response Models
# =============================================================================

class SubmitResponse(BaseModel):
    """Response when submitting a poll job"""
    ticket: str = Field(..., description="Job ticket UUID")
    status: str = Field(..., description="Initial job status")
    target: str = Field(..., description="Target being polled")


class ProgressDetail(BaseModel):
    """Detailed progress information"""
    system_oids: Optional[int] = None
    interfaces_walked: Optional[int] = None
    interfaces_total: Optional[int] = None
    arp_walked: Optional[int] = None
    arp_total: Optional[int] = None


class StatusResponse(BaseModel):
    """Response for job status check"""
    ticket: str
    target: str
    status: str
    progress: str = ""
    progress_detail: Dict[str, Any] = {}
    elapsed_seconds: Optional[float] = None
    
    # Only present when complete
    data: Optional[Dict[str, Any]] = None
    timing: Optional[Dict[str, float]] = None
    
    # Only present when failed
    error: Optional[str] = None


class SNMPResponse(BaseModel):
    """Generic SNMP operation response (for direct get/walk)"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    timing: Optional[Dict[str, float]] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    active_jobs: int
    total_jobs: int
    max_concurrent: int
    uptime_seconds: float


class JobListResponse(BaseModel):
    """List of jobs"""
    jobs: List[Dict[str, Any]]
    total: int
