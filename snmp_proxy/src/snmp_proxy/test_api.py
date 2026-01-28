#!/usr/bin/env python3
"""
Test script for SNMP Proxy API

Tests the full flow: health check, submit poll, poll status, get results.
"""

import json
import time
import urllib.request
import urllib.error
import sys

# Configuration - adjust as needed
PROXY_URL = "http://localhost:8899"
API_KEY = "7be11975-e040-4285-9a80-e4692e140796"  # Replace with the key from proxy startup

TARGET = "172.17.1.14"
COMMUNITY = "lab"
VERSION = "2c"

COLLECT_INTERFACES = True
COLLECT_ARP = True

POLL_INTERVAL = 1.0  # seconds between status checks
MAX_WAIT = 300  # max seconds to wait for completion


def make_request(method: str, path: str, data: dict = None, auth: bool = True) -> dict:
    """Make HTTP request to proxy"""
    url = f"{PROXY_URL}{path}"

    headers = {"Content-Type": "application/json"}
    if auth:
        headers["X-API-Key"] = API_KEY

    body = json.dumps(data).encode('utf-8') if data else None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e.fp else ""
        print(f"HTTP Error {e.code}: {e.reason}")
        print(f"  Body: {body}")
        raise
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
        raise


def test_health():
    """Test health endpoint (no auth)"""
    print("=" * 60)
    print("Testing /health (no auth)")
    print("=" * 60)

    try:
        result = make_request("GET", "/health", auth=False)
        print(f"✓ Health check passed:")
        print(f"  Status: {result.get('status')}")
        print(f"  Version: {result.get('version')}")
        print(f"  Active jobs: {result.get('active_jobs')}")
        print(f"  Max concurrent: {result.get('max_concurrent')}")
        return True
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False


def test_direct_get():
    """Test direct SNMP GET endpoint"""
    print("\n" + "=" * 60)
    print("Testing /snmp/get (direct GET)")
    print("=" * 60)

    try:
        result = make_request("POST", "/snmp/get", {
            "target": TARGET,
            "community": COMMUNITY,
            "version": VERSION,
            "oid": "1.3.6.1.2.1.1.5.0",  # sysName
            "timeout": 10
        })

        if result.get("success"):
            print(f"✓ Direct GET succeeded:")
            print(f"  sysName: {result.get('data')}")
            print(f"  Timing: {result.get('timing')}")
            return True
        else:
            print(f"✗ Direct GET failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"✗ Direct GET exception: {e}")
        return False


def test_poll_job():
    """Test full poll job flow"""
    print("\n" + "=" * 60)
    print("Testing /snmp/poll (submit job)")
    print("=" * 60)

    # Submit job
    try:
        submit_result = make_request("POST", "/snmp/poll", {
            "target": TARGET,
            "community": COMMUNITY,
            "version": VERSION,
            "collect_interfaces": COLLECT_INTERFACES,
            "collect_arp": COLLECT_ARP,
            "get_timeout": 10,
            "walk_timeout": 120
        })

        ticket = submit_result.get("ticket")
        if not ticket:
            print(f"✗ No ticket returned: {submit_result}")
            return False

        print(f"✓ Job submitted:")
        print(f"  Ticket: {ticket}")
        print(f"  Status: {submit_result.get('status')}")

    except Exception as e:
        print(f"✗ Submit failed: {e}")
        return False

    # Poll for status
    print("\n" + "-" * 60)
    print("Polling for status...")
    print("-" * 60)

    start_time = time.time()
    last_progress = ""

    while True:
        elapsed = time.time() - start_time

        if elapsed > MAX_WAIT:
            print(f"\n✗ Timeout after {MAX_WAIT}s")
            return False

        try:
            status = make_request("GET", f"/status/{ticket}")
        except Exception as e:
            print(f"\n✗ Status check failed: {e}")
            return False

        job_status = status.get("status")
        progress = status.get("progress", "")
        progress_detail = status.get("progress_detail", {})
        job_elapsed = status.get("elapsed_seconds", 0)

        # Show progress updates
        if progress != last_progress:
            detail_str = ""
            if progress_detail:
                parts = []
                if "interfaces_walked" in progress_detail:
                    parts.append(f"if:{progress_detail['interfaces_walked']}")
                if "arp_walked" in progress_detail:
                    parts.append(f"arp:{progress_detail['arp_walked']}")
                if parts:
                    detail_str = f" [{', '.join(parts)}]"

            print(f"  [{job_elapsed:6.1f}s] {job_status}: {progress}{detail_str}")
            last_progress = progress

        # Check terminal states
        if job_status == "complete":
            print("\n" + "=" * 60)
            print("✓ Poll completed successfully!")
            print("=" * 60)

            data = status.get("data", {})
            timing = status.get("timing", {})

            # System info
            snmp_data = data.get("snmp_data", {})
            print(f"\nSystem Info ({len(snmp_data)} OIDs):")
            for key, value in snmp_data.items():
                # Truncate long values
                display = value[:60] + "..." if len(str(value)) > 60 else value
                print(f"  {key}: {display}")

            # Interfaces
            interfaces = data.get("interfaces", [])
            print(f"\nInterfaces: {len(interfaces)} total")
            if interfaces:
                print("  First 5:")
                for iface in interfaces[:5]:
                    mac = iface.get('mac', 'no-mac')
                    print(f"    - {iface.get('description', 'unknown')}: {mac}")
                if len(interfaces) > 5:
                    print(f"    ... and {len(interfaces) - 5} more")

            # ARP
            arp = data.get("arp_table", [])
            print(f"\nARP Table: {len(arp)} entries")
            if arp:
                print("  First 5:")
                for entry in arp[:5]:
                    print(f"    - {entry.get('ip', '?')}: {entry.get('mac', '?')}")
                if len(arp) > 5:
                    print(f"    ... and {len(arp) - 5} more")

            # Timing
            print(f"\nTiming:")
            for phase, duration in timing.items():
                print(f"  {phase}: {duration:.2f}s")

            return True

        elif job_status == "failed":
            print(f"\n✗ Poll failed: {status.get('error')}")
            return False

        elif job_status == "cancelled":
            print(f"\n✗ Poll was cancelled")
            return False

        time.sleep(POLL_INTERVAL)


def test_list_jobs():
    """Test job listing"""
    print("\n" + "=" * 60)
    print("Testing /jobs (list jobs)")
    print("=" * 60)

    try:
        result = make_request("GET", "/jobs")
        jobs = result.get("jobs", [])
        print(f"✓ Listed {len(jobs)} jobs:")
        for job in jobs[:5]:
            print(f"  - {job.get('ticket', '?')[:8]}... {job.get('target')} [{job.get('status')}]")
        return True
    except Exception as e:
        print(f"✗ List jobs failed: {e}")
        return False


def main():
    print("SNMP Proxy API Test")
    print(f"Proxy: {PROXY_URL}")
    print(f"Target: {TARGET}")
    print(f"API Key: {API_KEY[:8]}..." if len(API_KEY) > 8 else f"API Key: {API_KEY}")
    print()

    if API_KEY == "YOUR_API_KEY_HERE":
        print("⚠️  WARNING: Update API_KEY at the top of this script!")
        print("   Copy the key from the proxy startup output.")
        print()

    results = {}

    # Run tests
    results["health"] = test_health()

    if not results["health"]:
        print("\n❌ Health check failed - is the proxy running?")
        sys.exit(1)

    results["direct_get"] = test_direct_get()

    if not results["direct_get"]:
        print("\n❌ Direct GET failed - check target/community/network")
        sys.exit(1)

    results["poll_job"] = test_poll_job()
    results["list_jobs"] = test_list_jobs()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = True
    for test, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()