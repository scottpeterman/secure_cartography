"""
SecureCartography NG - SNMP Table Walker.

Async SNMP GETBULK implementation for efficient table walks.
Extracted from production VelocityMaps code.

Features:
- Async/await with pysnmp.hlapi.v3arch.asyncio
- Automatic prefix-based table boundary detection
- Configurable bulk size and iteration limits
- Support for both named MIB objects and numeric OIDs
- Fallback from MIB-resolved to numeric OIDs

Usage:
    from sc2.scng.discovery.snmp.walker import SNMPWalker
    
    walker = SNMPWalker(engine, auth)
    
    # Walk a table
    results = await walker.walk("192.168.1.1", "1.3.6.1.2.1.31.1.1.1.1")
    
    # Get a single value
    value = await walker.get("192.168.1.1", "1.3.6.1.2.1.1.1.0")
"""

import asyncio
from datetime import datetime
from typing import List, Tuple, Optional, Any, Union

from pysnmp.hlapi.v3arch.asyncio import (
    bulk_cmd, get_cmd,
    SnmpEngine, CommunityData, UsmUserData,
    UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity,
)

# Type aliases
AuthData = Union[CommunityData, UsmUserData]
WalkResult = List[Tuple[str, Any]]


class SNMPWalker:
    """
    Async SNMP table walker.
    
    Wraps pysnmp's bulk_cmd for efficient table walking with
    automatic boundary detection and error handling.
    
    Attributes:
        engine: pysnmp SnmpEngine instance
        auth: CommunityData (v2c) or UsmUserData (v3)
        default_timeout: Default timeout in seconds
        default_retries: Default retry count
        bulk_size: Number of OIDs per GETBULK request
        max_iterations: Safety limit for walk iterations
        verbose: Enable verbose logging
    """
    
    def __init__(
        self,
        engine: Optional[SnmpEngine] = None,
        auth: Optional[AuthData] = None,
        default_timeout: float = 3.0,
        default_retries: int = 1,
        bulk_size: int = 25,
        max_iterations: int = 1500,
        verbose: bool = False,
    ):
        """
        Initialize SNMP walker.
        
        Args:
            engine: pysnmp SnmpEngine (created if not provided)
            auth: Authentication data (can be set later per-device)
            default_timeout: Timeout per request in seconds
            default_retries: Number of retries on timeout
            bulk_size: Max-repetitions for GETBULK
            max_iterations: Max iterations to prevent infinite loops
            verbose: Print debug messages
        """
        self.engine = engine or SnmpEngine()
        self.auth = auth
        self.default_timeout = default_timeout
        self.default_retries = default_retries
        self.bulk_size = bulk_size
        self.max_iterations = max_iterations
        self.verbose = verbose
    
    def _vprint(self, message: str, level: int = 1):
        """Print verbose message if enabled."""
        if self.verbose:
            indent = "  " * level
            print(f"{indent}[SNMP] {message}")
    
    async def walk(
        self,
        target: str,
        oid: Union[str, ObjectIdentity],
        auth: Optional[AuthData] = None,
        port: int = 161,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
        max_iterations: Optional[int] = None,
    ) -> WalkResult:
        """
        Walk an SNMP table using GETBULK.
        
        Walks all OIDs under the given base OID until leaving
        the table (OID no longer starts with base).
        
        Args:
            target: Target IP address or hostname
            oid: Base OID (numeric string or ObjectIdentity)
            auth: Override auth for this request
            port: SNMP port (default 161)
            timeout: Override timeout
            retries: Override retries
            max_iterations: Override max iterations
        
        Returns:
            List of (oid_string, value) tuples
        
        Example:
            results = await walker.walk("192.168.1.1", "1.3.6.1.2.1.31.1.1.1.1")
            for oid, value in results:
                if_index = oid.split('.')[-1]
                if_name = str(value)
        """
        auth = auth or self.auth
        if not auth:
            raise ValueError("No auth data provided")
        
        timeout = timeout or self.default_timeout
        retries = retries if retries is not None else self.default_retries
        max_iterations = max_iterations or self.max_iterations
        
        results: WalkResult = []
        
        # Determine base OID for boundary checking
        if isinstance(oid, str):
            base_oid = oid
        else:
            try:
                base_oid = str(oid)
            except Exception:
                try:
                    base_oid = oid.prettyPrint()
                except Exception:
                    base_oid = repr(oid)
        
        if base_oid is None:
            base_oid = ""
        
        self._vprint(f"Walking OID: {base_oid} on {target}", 1)
        start_time = datetime.now()
        
        # Track last OID for continuation
        last_oid = oid
        
        for iteration in range(max_iterations):
            try:
                self._vprint(f"Iteration {iteration + 1}, timeout={timeout}s", 2)
                
                # Ensure we have an ObjectIdentity
                if isinstance(last_oid, str):
                    last_oid_obj = ObjectIdentity(last_oid)
                else:
                    last_oid_obj = last_oid
                
                # Create transport target
                transport = await UdpTransportTarget.create(
                    (target, port),
                    timeout=timeout,
                    retries=retries
                )
                
                # Execute GETBULK
                error_indication, error_status, error_index, var_binds = await asyncio.wait_for(
                    bulk_cmd(
                        self.engine,
                        auth,
                        transport,
                        ContextData(),
                        0,  # non-repeaters
                        self.bulk_size,  # max-repetitions
                        ObjectType(last_oid_obj),
                        lexicographicMode=False
                    ),
                    timeout=timeout + 2  # Extra time for network
                )
                
                if error_indication:
                    if iteration == 0:
                        self._vprint(f"Error on {base_oid}: {error_indication}", 1)
                    break
                
                if error_status:
                    if iteration == 0:
                        self._vprint(f"Status error on {base_oid}: {error_status.prettyPrint()}", 1)
                    break
                
                if not var_binds:
                    self._vprint("No var_binds returned, ending walk", 2)
                    break
                
                in_table = False
                count_in_table = 0
                
                # Process results
                for var_bind in var_binds:
                    oid_str = str(var_bind[0])
                    
                    if oid_str.startswith(base_oid):
                        results.append((oid_str, var_bind[1]))
                        # Update last_oid for next iteration
                        last_oid = var_bind[0]
                        in_table = True
                        count_in_table += 1
                
                self._vprint(f"Got {len(var_binds)} var_binds, {count_in_table} in table", 2)
                
                if not in_table:
                    self._vprint("Left table scope, ending walk", 2)
                    break
                
                if len(var_binds) < self.bulk_size:
                    self._vprint(f"Received less than {self.bulk_size} results, ending walk", 2)
                    break
            
            except asyncio.TimeoutError:
                if iteration == 0:
                    self._vprint(f"Timeout on {base_oid}", 1)
                break
            
            except Exception as e:
                if iteration == 0:
                    self._vprint(f"Exception on {base_oid}: {type(e).__name__}: {e}", 1)
                break
        
        elapsed = (datetime.now() - start_time).total_seconds()
        self._vprint(f"Walk complete: {len(results)} results in {elapsed:.2f}s ({iteration + 1} iterations)", 1)
        
        return results
    
    async def walk_with_fallback(
        self,
        target: str,
        mib_name: str,
        mib_object: str,
        numeric_oid: str,
        auth: Optional[AuthData] = None,
        **kwargs
    ) -> Tuple[WalkResult, bool]:
        """
        Walk table with MIB resolution fallback to numeric OID.
        
        Tries to resolve the MIB object first. If that fails or returns
        no results, falls back to the numeric OID.
        
        Args:
            target: Target IP address
            mib_name: MIB name (e.g., "LLDP-MIB")
            mib_object: Object name (e.g., "lldpRemTable")
            numeric_oid: Fallback numeric OID
            auth: Override auth
            **kwargs: Passed to walk()
        
        Returns:
            Tuple of (results, used_fallback)
        """
        auth = auth or self.auth
        
        self._vprint(f"Trying MIB {mib_name}::{mib_object}", 1)
        
        # Try MIB-based query first
        try:
            obj_identity = ObjectIdentity(mib_name, mib_object)
            # Note: MIB resolution may require loadMibs() on the engine
            
            results = await self.walk(target, obj_identity, auth, **kwargs)
            
            if results:
                self._vprint(f"MIB query returned {len(results)} results", 1)
                return results, False
            
            self._vprint(f"MIB query returned no results, trying numeric fallback", 1)
        
        except Exception as e:
            self._vprint(f"MIB resolution failed: {e}, using numeric fallback", 1)
        
        # Fallback to numeric OID
        results = await self.walk(target, numeric_oid, auth, **kwargs)
        return results, True
    
    async def get(
        self,
        target: str,
        oid: Union[str, ObjectIdentity],
        auth: Optional[AuthData] = None,
        port: int = 161,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> Optional[Any]:
        """
        Get a single SNMP value.
        
        Args:
            target: Target IP address
            oid: OID to get (should end in .0 for scalars)
            auth: Override auth
            port: SNMP port
            timeout: Override timeout
            retries: Override retries
        
        Returns:
            Value or None on error
        """
        auth = auth or self.auth
        if not auth:
            raise ValueError("No auth data provided")
        
        timeout = timeout or self.default_timeout
        retries = retries if retries is not None else self.default_retries
        
        # Ensure ObjectIdentity
        if isinstance(oid, str):
            oid_obj = ObjectIdentity(oid)
        else:
            oid_obj = oid
        
        try:
            transport = await UdpTransportTarget.create(
                (target, port),
                timeout=timeout,
                retries=retries
            )
            
            error_indication, error_status, error_index, var_binds = await asyncio.wait_for(
                get_cmd(
                    self.engine,
                    auth,
                    transport,
                    ContextData(),
                    ObjectType(oid_obj)
                ),
                timeout=timeout + 2
            )
            
            if error_indication or error_status:
                return None
            
            if var_binds:
                return var_binds[0][1]
            
            return None
        
        except Exception:
            return None
    
    async def get_multiple(
        self,
        target: str,
        oids: List[Union[str, ObjectIdentity]],
        auth: Optional[AuthData] = None,
        port: int = 161,
        timeout: Optional[float] = None,
    ) -> List[Optional[Any]]:
        """
        Get multiple SNMP values in one request.
        
        Args:
            target: Target IP address
            oids: List of OIDs to get
            auth: Override auth
            port: SNMP port
            timeout: Override timeout
        
        Returns:
            List of values (None for failed OIDs)
        """
        auth = auth or self.auth
        if not auth:
            raise ValueError("No auth data provided")
        
        timeout = timeout or self.default_timeout
        
        # Build ObjectTypes
        object_types = []
        for oid in oids:
            if isinstance(oid, str):
                object_types.append(ObjectType(ObjectIdentity(oid)))
            else:
                object_types.append(ObjectType(oid))
        
        try:
            transport = await UdpTransportTarget.create(
                (target, port),
                timeout=timeout,
                retries=self.default_retries
            )
            
            error_indication, error_status, error_index, var_binds = await asyncio.wait_for(
                get_cmd(
                    self.engine,
                    auth,
                    transport,
                    ContextData(),
                    *object_types
                ),
                timeout=timeout + 2
            )
            
            if error_indication or error_status:
                return [None] * len(oids)
            
            return [vb[1] if vb else None for vb in var_binds]
        
        except Exception:
            return [None] * len(oids)


# =============================================================================
# Convenience Functions
# =============================================================================

async def snmp_walk(
    target: str,
    oid: str,
    auth: AuthData,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 3.0,
    verbose: bool = False,
) -> WalkResult:
    """
    Convenience function for one-off SNMP walks.
    
    Example:
        results = await snmp_walk(
            "192.168.1.1",
            "1.3.6.1.2.1.31.1.1.1.1",
            CommunityData("public", mpModel=1)
        )
    """
    walker = SNMPWalker(
        engine=engine,
        auth=auth,
        default_timeout=timeout,
        verbose=verbose
    )
    return await walker.walk(target, oid)


async def snmp_get(
    target: str,
    oid: str,
    auth: AuthData,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 3.0,
) -> Optional[Any]:
    """
    Convenience function for one-off SNMP gets.
    
    Example:
        sys_descr = await snmp_get(
            "192.168.1.1",
            "1.3.6.1.2.1.1.1.0",
            CommunityData("public", mpModel=1)
        )
    """
    walker = SNMPWalker(
        engine=engine,
        auth=auth,
        default_timeout=timeout
    )
    return await walker.get(target, oid)
