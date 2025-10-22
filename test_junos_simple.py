#!/usr/bin/env python3
"""
Simple test script for Junos integration - checks code modifications
"""
import re

def test_driver_discovery_modifications():
    """Check that driver_discovery.py has been properly modified"""
    print("="*60)
    print("Testing driver_discovery.py Modifications")
    print("="*60)

    with open('/home/user/network-discovery/secure_cartography/driver_discovery.py', 'r') as f:
        content = f.read()

    tests = [
        ("'junos'" in content, "Contains 'junos' string"),
        ("platform == 'junos'" in content, "Has Junos platform check"),
        ("platform not in ['eos', 'junos']" in content, "Excludes Junos from CDP"),
        ("juniper_junos_show_lldp_neighbors_detail" in content, "References Junos LLDP template"),
        ("_detect_platform_from_capabilities" in content, "Has capabilities detection method"),
        ("'Juniper' in facts['vendor']" in content, "Checks for Juniper vendor"),
        ("'JUNOS' in facts['os_version']" in content, "Checks for JUNOS version"),
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


def test_interface_normalizer_modifications():
    """Check that enh_int_normalizer.py has been properly modified"""
    print("\n" + "="*60)
    print("Testing enh_int_normalizer.py Modifications")
    print("="*60)

    with open('/home/user/network-discovery/secure_cartography/enh_int_normalizer.py', 'r') as f:
        content = f.read()

    tests = [
        ("JUNIPER = auto()" in content, "Has JUNIPER platform enum"),
        ("ge[-_]" in content, "Has Juniper GE interface pattern"),
        ("xe[-_]" in content, "Has Juniper XE interface pattern"),
        ("et[-_]" in content, "Has Juniper ET interface pattern"),
        (r"(?:ae)" in content, "Has Juniper AE interface pattern"),
        (r"(?:fxp|em|me)" in content, "Has Juniper management interface pattern"),
        (r"(?:irb)" in content, "Has Juniper IRB interface pattern"),
        ("[Platform.JUNIPER]" in content, "References JUNIPER platform in specs"),
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


def test_textfsm_template():
    """Check that TextFSM template exists and is valid"""
    print("\n" + "="*60)
    print("Testing Junos LLDP TextFSM Template")
    print("="*60)

    template_path = '/home/user/network-discovery/textfsm_templates/juniper_junos_show_lldp_neighbors_detail.textfsm'

    try:
        with open(template_path, 'r') as f:
            content = f.read()

        tests = [
            ("Value Required LOCAL_INTERFACE" in content, "Has LOCAL_INTERFACE value"),
            ("Value CHASSIS_ID" in content, "Has CHASSIS_ID value"),
            ("Value NEIGHBOR_PORT_ID" in content, "Has NEIGHBOR_PORT_ID value"),
            ("Value PORT_ID" in content, "Has PORT_ID value"),
            ("Value NEIGHBOR_NAME" in content, "Has NEIGHBOR_NAME value"),
            ("Value MGMT_ADDRESS" in content, "Has MGMT_ADDRESS value"),
            ("Value CAPABILITIES" in content, "Has CAPABILITIES value"),
            ("Start" in content, "Has Start state"),
            ("Detail" in content, "Has Detail state"),
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

    except FileNotFoundError:
        print(f"✗ Template file not found: {template_path}")
        return False


def test_database_template():
    """Check that template is in database"""
    print("\n" + "="*60)
    print("Testing Template in Database")
    print("="*60)

    import sqlite3

    try:
        conn = sqlite3.connect('/home/user/network-discovery/secure_cartography/tfsm_templates.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT cli_command, length(textfsm_content) as content_length
            FROM templates
            WHERE cli_command = 'juniper_junos_show_lldp_neighbors_detail'
        """)

        result = cursor.fetchone()
        conn.close()

        if result:
            cli_command, content_length = result
            print(f"✓ Template found in database")
            print(f"  - Command: {cli_command}")
            print(f"  - Content length: {content_length} bytes")
            return True
        else:
            print("✗ Template not found in database")
            return False

    except Exception as e:
        print(f"✗ Error checking database: {e}")
        return False


def main():
    """Run all simple tests"""
    print("\n" + "="*60)
    print("JUNOS INTEGRATION VERIFICATION")
    print("="*60 + "\n")

    all_passed = True

    # Run all tests
    all_passed &= test_driver_discovery_modifications()
    all_passed &= test_interface_normalizer_modifications()
    all_passed &= test_textfsm_template()
    all_passed &= test_database_template()

    # Summary
    print("\n" + "="*60)
    print("FINAL RESULT")
    print("="*60)
    if all_passed:
        print("✓ ALL VERIFICATION CHECKS PASSED!")
        print("\nJunos/Juniper support has been successfully integrated.")
        print("\n" + "="*60)
        print("INTEGRATION SUMMARY")
        print("="*60)
        print("\nModified Files:")
        print("  1. secure_cartography/driver_discovery.py")
        print("     - Added 'junos' to supported drivers")
        print("     - Added Junos platform validation")
        print("     - Updated neighbor discovery for Junos LLDP")
        print("     - Added capabilities-based platform detection")
        print("")
        print("  2. secure_cartography/enh_int_normalizer.py")
        print("     - Added Platform.JUNIPER enum")
        print("     - Added Junos interface patterns (ge-, xe-, et-, ae, etc.)")
        print("")
        print("  3. textfsm_templates/juniper_junos_show_lldp_neighbors_detail.textfsm")
        print("     - Created Junos LLDP parsing template")
        print("")
        print("  4. secure_cartography/tfsm_templates.db")
        print("     - Added Junos LLDP template to database")
        print("\n" + "="*60)
        print("NEXT STEPS")
        print("="*60)
        print("\nTo test with a real Juniper device:")
        print("  1. Create a test configuration file:")
        print("     cat > junos_test.yaml << EOF")
        print("     seed_ip: <JUNIPER_DEVICE_IP>")
        print("     username: <USERNAME>")
        print("     password: <PASSWORD>")
        print("     max_devices: 10")
        print("     output_dir: ./output_junos")
        print("     map_name: junos_network")
        print("     EOF")
        print("")
        print("  2. Run discovery:")
        print("     python -m secure_cartography.sc --config junos_test.yaml")
        print("")
        print("  3. Check output files:")
        print("     ls -la ./output_junos/")
        print("")
        return 0
    else:
        print("✗ SOME VERIFICATION CHECKS FAILED")
        print("\nPlease review the failures above.")
        return 1


if __name__ == '__main__':
    exit(main())
