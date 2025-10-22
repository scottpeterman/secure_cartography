#!/usr/bin/env python3
"""
Test script for Junos/Juniper device support integration
"""
from pathlib import Path
from secure_cartography.enh_int_normalizer import InterfaceNormalizer, Platform
from secure_cartography.driver_discovery import DriverDiscovery, DeviceInfo

def test_interface_normalization():
    """Test Junos interface normalization"""
    print("="*60)
    print("Testing Junos Interface Normalization")
    print("="*60)

    test_cases = [
        ("ge-0/0/1", "ge-0/0/1"),
        ("ge-1/2/3", "ge-1/2/3"),
        ("xe-0/0/0", "xe-0/0/0"),
        ("et-1/0/5", "et-1/0/5"),
        ("ae0", "ae0"),
        ("ae100", "ae100"),
        ("fxp0", "fxp0"),
        ("em0", "em0"),
        ("me0", "me0"),
        ("lo0", "lo0"),
        ("irb.100", "irb.100"),
        ("irb.200", "irb.200"),
        ("ge-0/0/1.100", "ge-0/0/1.100"),  # VLAN subinterface
    ]

    passed = 0
    failed = 0

    for input_if, expected in test_cases:
        result = InterfaceNormalizer.normalize(input_if, platform=Platform.JUNIPER)
        if result == expected:
            print(f"✓ {input_if:20} -> {result:20}")
            passed += 1
        else:
            print(f"✗ {input_if:20} -> {result:20} (expected {expected})")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_platform_detection():
    """Test platform detection from description strings"""
    print("\n" + "="*60)
    print("Testing Platform Detection")
    print("="*60)

    dd = DriverDiscovery()

    test_cases = [
        ("Juniper Networks MX480", "junos"),
        ("JUNOS 20.4R1.12", "junos"),
        ("Juniper EX4300-48T", "junos"),
        ("Cisco IOS Software", "ios"),
        ("Arista vEOS", "eos"),
    ]

    passed = 0
    failed = 0

    for description, expected_platform in test_cases:
        result = dd._detect_platform_from_desc(description)
        if result == expected_platform:
            print(f"✓ {description:35} -> {result}")
            passed += 1
        else:
            print(f"✗ {description:35} -> {result} (expected {expected_platform})")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_capabilities_detection():
    """Test platform detection from LLDP capabilities"""
    print("\n" + "="*60)
    print("Testing Capabilities Detection")
    print("="*60)

    dd = DriverDiscovery()

    test_cases = [
        ("Bridge, Router", "junos"),
        ("Router", "junos"),
        ("juniper router bridge", "junos"),
        ("", "unknown"),
    ]

    passed = 0
    failed = 0

    for capabilities, expected_platform in test_cases:
        result = dd._detect_platform_from_capabilities(capabilities)
        if result == expected_platform:
            print(f"✓ {capabilities:35} -> {result}")
            passed += 1
        else:
            print(f"✗ {capabilities:35} -> {result} (expected {expected_platform})")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_junos_supported():
    """Test that Junos is in supported drivers"""
    print("\n" + "="*60)
    print("Testing Junos Support Configuration")
    print("="*60)

    dd = DriverDiscovery()

    tests = [
        ('junos' in dd.supported_drivers, "Junos in supported_drivers"),
        ('junos' in dd.napalm_neighbor_capable, "Junos in napalm_neighbor_capable"),
        (Platform.JUNIPER in Platform, "JUNIPER in Platform enum"),
    ]

    passed = 0
    failed = 0

    for test_result, test_name in tests:
        if test_result:
            print(f"✓ {test_name}")
            passed += 1
        else:
            print(f"✗ {test_name}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("JUNOS INTEGRATION TEST SUITE")
    print("="*60 + "\n")

    all_passed = True

    # Run all tests
    all_passed &= test_junos_supported()
    all_passed &= test_interface_normalization()
    all_passed &= test_platform_detection()
    all_passed &= test_capabilities_detection()

    # Summary
    print("\n" + "="*60)
    print("FINAL RESULT")
    print("="*60)
    if all_passed:
        print("✓ ALL TESTS PASSED!")
        print("\nJunos/Juniper support has been successfully integrated.")
        print("\nNext steps:")
        print("  1. Test with real Juniper device using test_junos_discovery.py")
        print("  2. Verify LLDP neighbor discovery")
        print("  3. Check output files for correct formatting")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("\nPlease review the failures above and fix the issues.")
        return 1


if __name__ == '__main__':
    exit(main())
