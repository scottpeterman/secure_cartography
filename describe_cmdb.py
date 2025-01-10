import sqlite3


def extract_schema(db_path):
    try:
        # Connect to the database
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()

        # Retrieve all SQL schema objects
        query = """
        SELECT name, type, sql FROM sqlite_master 
        WHERE type IN ('table', 'view', 'index', 'trigger') 
        AND name NOT LIKE 'sqlite_%'
        ORDER BY type DESC, name;
        """
        cursor.execute(query)
        schema = cursor.fetchall()

        # Print CREATE statements
        print("-- Generated CREATE statements for the SQLite database --\n")
        for name, obj_type, sql in schema:
            print(f"-- {obj_type.capitalize()}: {name} --")
            if sql:
                print(sql)
            else:
                print("-- No SQL available --")
            print("\n")

        # Retrieve foreign key constraints for tables
        for name, obj_type, sql in schema:
            if obj_type == "table":
                cursor.execute(f"PRAGMA foreign_key_list('{name}')")
                foreign_keys = cursor.fetchall()
                if foreign_keys:
                    print(f"-- Foreign keys for table: {name} --")
                    for fk in foreign_keys:
                        print(f"Table: {fk[2]}, From: {fk[3]}, To: {fk[4]}, On Delete: {fk[5]}, On Update: {fk[6]}")
                    print("\n")

    except sqlite3.Error as e:
        print(f"Error: {e}")
    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    # Path to your SQLite database
    db_path = "surveyor/cmdb.db"  # Replace with your database file path
    extract_schema(db_path)
