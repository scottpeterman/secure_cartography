#!/usr/bin/env python3
"""
Script to add Junos LLDP TextFSM template to the database
"""
import sqlite3
import os

def add_junos_template():
    # Database path
    db_path = '/home/user/network-discovery/secure_cartography/tfsm_templates.db'
    template_path = '/home/user/network-discovery/textfsm_templates/juniper_junos_show_lldp_neighbors_detail.textfsm'

    # Read template content
    with open(template_path, 'r') as f:
        template_content = f.read()

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if template already exists
    cursor.execute("""
        SELECT COUNT(*) FROM templates
        WHERE cli_command = ?
    """, ('juniper_junos_show_lldp_neighbors_detail',))

    count = cursor.fetchone()[0]

    if count > 0:
        print("Template already exists in database. Updating...")
        cursor.execute("""
            UPDATE templates
            SET textfsm_content = ?
            WHERE cli_command = ?
        """, (template_content, 'juniper_junos_show_lldp_neighbors_detail'))
    else:
        print("Adding new template to database...")
        # Insert template
        try:
            cursor.execute("""
                INSERT INTO templates (cli_command, textfsm_content, vendor, platform)
                VALUES (?, ?, ?, ?)
            """, (
                'juniper_junos_show_lldp_neighbors_detail',
                template_content,
                'juniper',
                'junos'
            ))
        except sqlite3.Error as e:
            print(f"Error inserting template: {e}")
            # Try without vendor and platform columns
            cursor.execute("""
                INSERT INTO templates (cli_command, textfsm_content)
                VALUES (?, ?)
            """, (
                'juniper_junos_show_lldp_neighbors_detail',
                template_content
            ))

    conn.commit()

    # Verify insertion
    cursor.execute("""
        SELECT cli_command FROM templates
        WHERE cli_command LIKE '%juniper%' OR cli_command LIKE '%junos%'
    """)

    results = cursor.fetchall()
    print(f"\nJuniper/Junos templates in database:")
    for row in results:
        print(f"  - {row[0]}")

    conn.close()
    print("\n✓ Template successfully added to database!")

if __name__ == '__main__':
    add_junos_template()
