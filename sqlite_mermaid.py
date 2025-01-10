import click
import sqlite3
from pathlib import Path


class SchemaAnalyzer:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def get_tables(self):
        self.cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY 
                CASE WHEN name = 'devices' THEN 1 ELSE 2 END,
                name
        """)
        return [row[0] for row in self.cursor.fetchall()]

    def get_columns(self, table_name):
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        return [(row[1], row[2], row[5] == 1, row[3] != 0) for row in self.cursor.fetchall()]

    def get_foreign_keys(self, table_name):
        self.cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        return [(row[3], row[2], row[4]) for row in self.cursor.fetchall()]

    def sanitize_name(self, name):
        return name.replace('-', '_').replace(' ', '_')

    def format_type(self, sql_type):
        type_map = {
            'INTEGER': 'int',
            'TEXT': 'string',
            'REAL': 'float',
            'BLOB': 'blob',
            'BOOLEAN': 'bool',
            'DATETIME': 'date'
        }
        base_type = sql_type.split('(')[0].upper()
        return type_map.get(base_type, sql_type.lower())

    def generate_mermaid(self):
        mermaid_lines = [
            "erDiagram",
            "%% Entity Relationship Diagram",
            "    %%{init: {'theme': 'neutral', 'themeVariables': { 'primaryColor': '#3498db', 'lineColor': '#3498db', 'fontSize': '16px'}}}%%"
        ]
        tables = self.get_tables()

        for table in tables:
            safe_table = self.sanitize_name(table)
            columns = self.get_columns(table)

            mermaid_lines.append(f"{safe_table} {{")
            for col_name, col_type, is_pk, not_null in columns:
                safe_col = self.sanitize_name(col_name)
                formatted_type = self.format_type(col_type)

                attributes = []
                if is_pk:
                    attributes.append("PK")
                if not_null and not is_pk:
                    attributes.append("NOT NULL")

                attr_str = f" {' '.join(attributes)}" if attributes else ""
                mermaid_lines.append(f"    {formatted_type} {safe_col}{attr_str}")
            mermaid_lines.append("}")
            mermaid_lines.append("")  # Add blank line between tables

        # Add relationships after all tables
        for table in tables:
            safe_table = self.sanitize_name(table)
            foreign_keys = self.get_foreign_keys(table)
            for from_col, to_table, to_col in foreign_keys:
                safe_to_table = self.sanitize_name(to_table)
                relationship = f"{safe_to_table} ||--o{{ {safe_table} : has"
                mermaid_lines.append(relationship)

        return "\n".join(mermaid_lines)


@click.command()
@click.argument('db_path', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output file path', default='schema.mermaid')
def generate_diagram(db_path, output):
    """Generate Mermaid ER diagram from SQLite database."""
    analyzer = SchemaAnalyzer(db_path)
    mermaid = analyzer.generate_mermaid()

    output_path = Path(output)
    output_path.write_text(mermaid)
    click.echo(f"Diagram written to {output_path}")


if __name__ == '__main__':
    generate_diagram()


# import click
# import sqlite3
# from pathlib import Path
#
#
# class SchemaAnalyzer:
#     def __init__(self, db_path):
#         self.conn = sqlite3.connect(db_path)
#         self.cursor = self.conn.cursor()
#
#     def get_tables(self):
#         self.cursor.execute("""
#             SELECT name FROM sqlite_master
#             WHERE type='table' AND name NOT LIKE 'sqlite_%'
#         """)
#         return [row[0] for row in self.cursor.fetchall()]
#
#     def get_columns(self, table_name):
#         self.cursor.execute(f"PRAGMA table_info({table_name})")
#         return [(row[1], row[2], row[5] == 1) for row in self.cursor.fetchall()]
#
#     def get_foreign_keys(self, table_name):
#         self.cursor.execute(f"PRAGMA foreign_key_list({table_name})")
#         return [(row[3], row[2], row[4]) for row in self.cursor.fetchall()]
#
#     def sanitize_name(self, name):
#         return name.replace('-', '_').replace(' ', '_')
#
#     def generate_mermaid(self):
#         mermaid_lines = ["erDiagram"]
#         tables = self.get_tables()
#
#         for table in tables:
#             safe_table = self.sanitize_name(table)
#             columns = self.get_columns(table)
#             column_defs = []
#             for col_name, col_type, is_pk in columns:
#                 safe_col = self.sanitize_name(col_name)
#                 pk_indicator = "PK" if is_pk else ""
#                 column_defs.append(f"{safe_col} {col_type} {pk_indicator}")
#
#             mermaid_lines.append(f"{safe_table} {{")
#             for col_def in column_defs:
#                 mermaid_lines.append(f"    {col_def}")
#             mermaid_lines.append("}")
#
#         for table in tables:
#             safe_table = self.sanitize_name(table)
#             foreign_keys = self.get_foreign_keys(table)
#             for from_col, to_table, to_col in foreign_keys:
#                 safe_to_table = self.sanitize_name(to_table)
#                 relationship = f"{safe_table} ||--o{{ {safe_to_table} : FK"
#                 mermaid_lines.append(relationship)
#
#         return "\n".join(mermaid_lines)
#
#
# @click.command()
# @click.argument('db_path', type=click.Path(exists=True))
# @click.option('--output', '-o', help='Output file path', default='schema.mermaid')
# def generate_diagram(db_path, output):
#     """Generate Mermaid ER diagram from SQLite database."""
#     analyzer = SchemaAnalyzer(db_path)
#     mermaid = analyzer.generate_mermaid()
#
#     output_path = Path(output)
#     output_path.write_text(mermaid)
#     click.echo(f"Diagram written to {output_path}")
#
#
# if __name__ == '__main__':
#     generate_diagram()