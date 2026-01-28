#!/usr/bin/env python3
"""
Test script to figure out the correct pysnmp API for the current version.
Run this locally to determine the right way to construct objects.
"""

import asyncio
import sys

# Test target - adjust as needed
TARGET = "172.17.1.14"
COMMUNITY = "lab"
PORT = 161
TIMEOUT = 10
TEST_OID = "1.3.6.1.2.1.1.5.0"  # sysName

print(f"Python: {sys.version}")
print(f"Target: {TARGET}, Community: {COMMUNITY}")
print("=" * 60)

# Import and check version
try:
    import pysnmp

    print(f"pysnmp version: {pysnmp.__version__}")
except Exception as e:
    print(f"pysnmp import error: {e}")
    sys.exit(1)

print("=" * 60)

# Check what's available in hlapi.asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
)

# Try to find get_cmd or getCmd
try:
    from pysnmp.hlapi.asyncio import get_cmd

    print("✓ get_cmd (snake_case) available")
    GET_CMD = get_cmd
except ImportError:
    try:
        from pysnmp.hlapi.asyncio import getCmd

        print("✓ getCmd (camelCase) available")
        GET_CMD = getCmd
    except ImportError:
        print("✗ Neither get_cmd nor getCmd found!")
        GET_CMD = None

# Check UdpTransportTarget
print("\n" + "=" * 60)
print("Testing UdpTransportTarget construction methods:")
print("=" * 60)


# Method 1: Direct constructor with tuple
def test_transport_direct():
    try:
        t = UdpTransportTarget((TARGET, PORT))
        print(f"✓ Method 1 - Direct (host, port): {t}")
        return t
    except Exception as e:
        print(f"✗ Method 1 - Direct (host, port): {e}")
        return None


# Method 2: Direct with timeout/retries kwargs
def test_transport_kwargs():
    try:
        t = UdpTransportTarget((TARGET, PORT), timeout=TIMEOUT, retries=1)
        print(f"✓ Method 2 - kwargs: {t}")
        return t
    except Exception as e:
        print(f"✗ Method 2 - kwargs: {e}")
        return None


# Method 3: 4-tuple (host, port, timeout, retries)
def test_transport_4tuple():
    try:
        t = UdpTransportTarget((TARGET, PORT, TIMEOUT, 1))
        print(f"✓ Method 3 - 4-tuple: {t}")
        return t
    except Exception as e:
        print(f"✗ Method 3 - 4-tuple: {e}")
        return None


# Method 4: .create() factory method (async)
async def test_transport_create():
    try:
        t = await UdpTransportTarget.create((TARGET, PORT), timeout=TIMEOUT, retries=1)
        print(f"✓ Method 4 - await .create() with kwargs: {t}")
        return t
    except Exception as e:
        print(f"✗ Method 4 - await .create() with kwargs: {e}")

    try:
        t = await UdpTransportTarget.create((TARGET, PORT, TIMEOUT, 1))
        print(f"✓ Method 4b - await .create() with 4-tuple: {t}")
        return t
    except Exception as e:
        print(f"✗ Method 4b - await .create() with 4-tuple: {e}")

    return None


# Method 5: Check if there's a sync create
def test_transport_create_sync():
    if hasattr(UdpTransportTarget, 'create'):
        try:
            # Maybe it's not async?
            result = UdpTransportTarget.create((TARGET, PORT), timeout=TIMEOUT, retries=1)
            if asyncio.iscoroutine(result):
                print("  Method 5 - .create() returns coroutine (use await)")
                return None
            print(f"✓ Method 5 - sync .create(): {result}")
            return result
        except Exception as e:
            print(f"✗ Method 5 - sync .create(): {e}")
    else:
        print("✗ Method 5 - no .create() method")
    return None


# Run sync tests
print()
t1 = test_transport_direct()
t2 = test_transport_kwargs()
t3 = test_transport_4tuple()
t5 = test_transport_create_sync()


# Run async tests
async def run_async_tests():
    print("\nAsync transport tests:")
    t4 = await test_transport_create()
    return t4


async def test_actual_snmp(transport):
    """Test actual SNMP query with the given transport"""
    if transport is None:
        print("No transport to test with")
        return

    print(f"\n{'=' * 60}")
    print(f"Testing actual SNMP GET with transport: {type(transport)}")
    print(f"{'=' * 60}")

    if GET_CMD is None:
        print("No get_cmd available")
        return

    try:
        error_indication, error_status, error_index, var_binds = await GET_CMD(
            SnmpEngine(),
            CommunityData(COMMUNITY, mpModel=1),  # mpModel=1 for v2c
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(TEST_OID))
        )

        if error_indication:
            print(f"Error indication: {error_indication}")
        elif error_status:
            print(f"Error status: {error_status.prettyPrint()} at {error_index}")
        else:
            for var_bind in var_binds:
                print(f"✓ SUCCESS: {var_bind[0]} = {var_bind[1].prettyPrint()}")

    except Exception as e:
        print(f"SNMP GET failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    # Test async transport creation
    t4 = await run_async_tests()

    # Find a working transport
    working_transport = None

    # First try the async-created one
    if t4:
        working_transport = t4
        print(f"\nUsing async-created transport")

    # If async .create() works, we need to test SNMP with it
    if working_transport:
        await test_actual_snmp(working_transport)
    else:
        # Try creating transport inside the async context
        print("\n" + "=" * 60)
        print("Trying to create transport and test SNMP in async context:")
        print("=" * 60)

        # Maybe the newer API requires creating transport inside async?
        try:
            transport = await UdpTransportTarget.create(
                (TARGET, PORT),
                timeout=TIMEOUT,
                retries=1
            )
            print(f"✓ Created transport via await .create()")
            await test_actual_snmp(transport)
        except Exception as e:
            print(f"✗ Failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())