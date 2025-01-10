import sqlite3
import os


def generate_schema_file(db_path: str, output_file: str = "cmdb.sql"):
    """
    Generate a SQL schema file from an existing database.
    Includes DROP statements and proper ordering of table creation.
    """
    try:
        # Connect to the database
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()

        # Get all schema objects
        cursor.execute("""
            SELECT name, type, sql 
            FROM sqlite_master 
            WHERE type IN ('table', 'index', 'trigger', 'view') 
            AND name NOT LIKE 'sqlite_%'
            ORDER BY type DESC, name;
        """)
        schema_objects = cursor.fetchall()

        # Collect tables and their foreign keys
        tables = []
        foreign_keys = {}
        dependencies = {}

        for name, obj_type, sql in schema_objects:
            if obj_type == 'table':
                tables.append(name)
                # Get foreign keys for the table
                cursor.execute(f"PRAGMA foreign_key_list('{name}')")
                fks = cursor.fetchall()
                foreign_keys[name] = fks
                # Build dependency graph
                dependencies[name] = set()
                for fk in fks:
                    dependencies[name].add(fk[2])  # Add referenced table

        # Order tables based on dependencies
        ordered_tables = []
        while tables:
            # Find tables with no remaining dependencies
            available = [t for t in tables if not dependencies[t]]
            if not available:
                raise ValueError("Circular dependency detected in database schema")

            # Add tables with no dependencies to the ordered list
            for table in available:
                ordered_tables.append(table)
                tables.remove(table)
                # Remove this table from other tables' dependencies
                for deps in dependencies.values():
                    deps.discard(table)

        # Generate SQL file
        with open(output_file, 'w') as f:
            # Write header
            f.write("-- CMDB Schema Initialization\n")
            f.write("-- Generated SQL schema for clean database setup\n\n")

            # Drop existing objects in reverse order
            f.write("-- Drop existing objects\n")
            for name, obj_type, _ in reversed(schema_objects):
                f.write(f"DROP {obj_type.upper()} IF EXISTS {name};\n")
            f.write("\n")

            # Create tables in dependency order
            f.write("-- Create tables in proper order\n")
            for table in ordered_tables:
                for name, obj_type, sql in schema_objects:
                    if name == table and obj_type == 'table':
                        f.write(f"{sql};\n\n")

            # Create other objects (indexes, triggers, views)
            for name, obj_type, sql in schema_objects:
                if obj_type != 'table' and sql:
                    f.write(f"-- Create {obj_type}: {name}\n")
                    f.write(f"{sql};\n\n")

        print(f"Schema has been written to {output_file}")
        print(f"Found {len(ordered_tables)} tables in dependency order:")
        for i, table in enumerate(ordered_tables, 1):
            print(f"{i}. {table}")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    # Path to your SQLite database
    db_path = "surveyor/cmdb.db"  # Replace with your database path
    output_file = "cmdb.sql"

    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)

    generate_schema_file(db_path, output_file)