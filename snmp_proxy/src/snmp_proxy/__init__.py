"""
SNMP Proxy - Async ticket-based SNMP proxy for remote device polling

Deploy on a jump host or management server with SNMP access to target devices.
Desktop clients submit poll jobs and retrieve results via REST API.
"""

__version__ = "2.0.0"
__author__ = "Scott Peterman"

from .models import SNMPPollRequest, SubmitResponse, StatusResponse, JobStatus
from .jobs import PollJob, JobManager
from .server import app

__all__ = [
    "app",
    "SNMPPollRequest",
    "SubmitResponse", 
    "StatusResponse",
    "JobStatus",
    "PollJob",
    "JobManager",
]
