import sqlite3
import textfsm
from typing import Dict, List, Tuple, Optional
import io
import time
import click
from multiprocessing import Process, Queue
import multiprocessing
import sys
import threading
from contextlib import contextmanager


class ThreadSafeConnection:
    """Thread-local storage for SQLite connections"""

    def __init__(self, db_path: str, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self._local = threading.local()

    @contextmanager
    def get_connection(self):
        """Get a thread-local connection"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.row_factory = sqlite3.Row
            if self.verbose:
                click.echo(f"Created new connection in thread {threading.get_ident()}")

        try:
            yield self._local.connection
        except Exception as e:
            if hasattr(self._local, 'connection'):
                self._local.connection.close()
                delattr(self._local, 'connection')
            raise e

    def close_all(self):
        """Close connection if it exists for current thread"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')


class TextFSMAutoEngine:
    def __init__(self, db_path: str, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.connection_manager = ThreadSafeConnection(db_path, verbose)

    def _calculate_template_score(
            self,
            parsed_data: List[Dict],
            template: sqlite3.Row,
            raw_output: str
    ) -> float:
        """
        Score template match quality (0-100 scale).

        Factors:
        - Record count (0-30 pts): Did the template find data?
        - Field richness (0-30 pts): How many fields per record?
        - Population rate (0-25 pts): Are fields actually filled?
        - Consistency (0-15 pts): Uniform data across records?
        """
        if not parsed_data:
            return 0.0

        num_records = len(parsed_data)
        num_fields = len(parsed_data[0].keys()) if parsed_data else 0
        is_version_cmd = 'version' in template['cli_command'].lower()

        # === Factor 1: Record Count (0-30 points) ===
        if is_version_cmd:
            # Version commands: expect exactly 1 record
            record_score = 30.0 if num_records == 1 else max(0, 15 - (num_records - 1) * 5)
        else:
            # Diminishing returns: log scale capped at 30
            # 1 rec = 10, 3 rec = 20, 10+ rec = 30
            if num_records >= 10:
                record_score = 30.0
            elif num_records >= 3:
                record_score = 20.0 + (num_records - 3) * (10.0 / 7.0)
            else:
                record_score = num_records * 10.0

        # === Factor 2: Field Richness (0-30 points) ===
        # More fields = richer data extraction
        # 1-2 fields = weak, 3-5 = decent, 6-10 = good, 10+ = excellent
        if num_fields >= 10:
            field_score = 30.0
        elif num_fields >= 6:
            field_score = 20.0 + (num_fields - 6) * 2.5
        elif num_fields >= 3:
            field_score = 10.0 + (num_fields - 3) * (10.0 / 3.0)
        else:
            field_score = num_fields * 5.0

        # === Factor 3: Population Rate (0-25 points) ===
        # What percentage of cells have actual data?
        total_cells = num_records * num_fields
        populated_cells = 0

        for record in parsed_data:
            for value in record.values():
                if value is not None and str(value).strip():
                    populated_cells += 1

        population_rate = populated_cells / total_cells if total_cells > 0 else 0
        population_score = population_rate * 25.0

        # === Factor 4: Consistency (0-15 points) ===
        # Are the same fields populated across all records?
        if num_records > 1:
            # Check which fields are populated in each record
            field_fill_counts = {key: 0 for key in parsed_data[0].keys()}

            for record in parsed_data:
                for key, value in record.items():
                    if value is not None and str(value).strip():
                        field_fill_counts[key] += 1

            # Consistency = fields that are either always filled or never filled
            consistent_fields = sum(
                1 for count in field_fill_counts.values()
                if count == 0 or count == num_records
            )
            consistency_rate = consistent_fields / num_fields if num_fields > 0 else 0
            consistency_score = consistency_rate * 15.0
        else:
            # Single record = perfectly consistent
            consistency_score = 15.0

        total_score = record_score + field_score + population_score + consistency_score

        if self.verbose:
            click.echo(f"    Scoring: records={record_score:.1f}, fields={field_score:.1f}, "
                       f"population={population_score:.1f}, consistency={consistency_score:.1f} "
                       f"-> {total_score:.1f}")

        return total_score

    def find_best_template(self, device_output: str, filter_string: Optional[str] = None) -> Tuple[
        Optional[str], Optional[List[Dict]], float]:


        """Try filtered templates against the output and return the best match."""
        best_template = None
        best_parsed_output = None
        best_score = 0

        # Get filtered templates using thread-safe connection
        with self.connection_manager.get_connection() as conn:
            templates = self.get_filtered_templates(conn, filter_string)
            total_templates = len(templates)

            if self.verbose:
                click.echo(f"Found {total_templates} matching templates for filter: {filter_string}")

            # Try each template
            for idx, template in enumerate(templates, 1):
                if self.verbose:
                    percentage = (idx / total_templates) * 100
                    click.echo(f"\nTemplate {idx}/{total_templates} ({percentage:.1f}%): {template['cli_command']}")

                try:
                    textfsm_template = textfsm.TextFSM(io.StringIO(template['textfsm_content']))
                    parsed = textfsm_template.ParseText(device_output)
                    parsed_dicts = [dict(zip(textfsm_template.header, row)) for row in parsed]
                    score = self._calculate_template_score(parsed_dicts, template, device_output)

                    if self.verbose:
                        click.echo(f" -> Score={score:.2f}, Records={len(parsed_dicts)}")

                    if score > best_score:
                        best_score = score
                        best_template = template['cli_command']
                        best_parsed_output = parsed_dicts
                        if self.verbose:
                            click.echo(click.style("  New best match!", fg='green'))

                except Exception as e:
                    if self.verbose:
                        click.echo(f" -> Failed to parse: {str(e)}")
                    continue

        return best_template, best_parsed_output, best_score

    def get_filtered_templates(self, connection: sqlite3.Connection, filter_string: Optional[str] = None):
        """Get filtered templates from database using provided connection."""
        cursor = connection.cursor()
        if filter_string:
            filter_terms = filter_string.replace('-', '_').split('_')
            query = "SELECT * FROM templates WHERE 1=1"
            params = []
            for term in filter_terms:
                if term and len(term) > 2:
                    query += " AND cli_command LIKE ?"
                    params.append(f"%{term}%")
            cursor.execute(query, params)
        else:
            cursor.execute("SELECT * FROM templates")
        return cursor.fetchall()

    def __del__(self):
        """Clean up connections on deletion"""
        self.connection_manager.close_all()


# Example usage
if __name__ == '__main__':
    multiprocessing.freeze_support()


    # Example of using the engine in multiple threads
    def worker(engine, output, filter_str):
        result = engine.find_best_template(output, filter_str)
        print(f"Thread {threading.get_ident()}: Found template: {result[0]}")


    engine = TextFSMAutoEngine("./secure_cartography/tfsm_templates.db", verbose=True)
    threads = []

    # Create multiple threads
    for i in range(3):
        t = threading.Thread(target=worker, args=(engine, "sample output", "show version"))
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()