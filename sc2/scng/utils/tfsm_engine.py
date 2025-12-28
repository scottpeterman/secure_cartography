"""
TextFSM Validation Engine - Wrapper around tfsm_fire.TextFSMAutoEngine.

Validates collected output against TextFSM templates.
Only output with score > 0 is considered valid.

Usage:
    engine = ValidationEngine(db_path="path/to/tfsm_templates.db")
    result = engine.validate(output, filter_string="cisco_ios_show_version")

    if result.is_valid:
        print(f"Template: {result.template}")
        print(f"Score: {result.score}")
        print(f"Records: {len(result.parsed_data)}")
    else:
        print("Invalid output - no matching template")
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Import the actual engine from core
from tfsm_fire import TextFSMAutoEngine


@dataclass
class ValidationResult:
    """Result of output validation."""
    is_valid: bool
    template: Optional[str] = None
    parsed_data: Optional[List[Dict]] = None
    score: float = 0.0
    error: Optional[str] = None

    @property
    def record_count(self) -> int:
        """Number of records parsed."""
        return len(self.parsed_data) if self.parsed_data else 0


class ValidationEngine:
    """
    TextFSM-based output validation engine.

    Wraps tfsm_fire.TextFSMAutoEngine for use in the collection pipeline.
    Output must achieve a score > 0 to be considered valid (no cruft).

    Attributes:
        db_path: Path to TextFSM templates database
        min_score: Minimum score for valid output (default: 0.01)
        verbose: Enable verbose logging
    """

    def __init__(
            self,
            db_path: Optional[str] = None,
            min_score: float = 0.01,
            verbose: bool = False,
    ):
        """
        Initialize validation engine.

        Args:
            db_path: Path to tfsm_templates.db. If None, uses default location.
            min_score: Minimum score to consider output valid.
            verbose: Enable verbose output.
        """
        # Default database location - check multiple places
        if db_path is None:
            possible_paths = [
                Path(__file__).parent.parent / "core" / "tfsm_templates.db",
                Path.home() / ".vcollector" / "tfsm_templates.db",
            ]
            for p in possible_paths:
                if p.exists():
                    db_path = str(p)
                    break
            else:
                raise FileNotFoundError(
                    f"TextFSM template database not found. Searched:\n"
                    f"  - {possible_paths[0]}\n"
                    f"  - {possible_paths[1]}\n"
                )

        self.db_path = db_path
        self.min_score = min_score
        self.verbose = verbose

        # Verify database exists
        if not Path(db_path).exists():
            raise FileNotFoundError(f"TextFSM template database not found: {db_path}")

        # Initialize the actual engine
        self._engine = TextFSMAutoEngine(db_path, verbose=verbose)

    def _clean_output(self, raw_output: str) -> str:
        """
        Clean raw CLI output for TextFSM parsing.

        Removes:
        - Preamble lines (terminal length, pagination messages)
        - Command echo (hostname#show command)
        - Trailing prompts

        Args:
            raw_output: Raw output from SSH session

        Returns:
            Cleaned output suitable for TextFSM parsing
        """
        import re

        lines = raw_output.split('\n')
        cleaned_lines = []
        found_output_start = False

        # Common preamble patterns to skip
        preamble_patterns = [
            r'^terminal\s+(length|width)',
            r'^pagination\s+disabled',
            r'^screen-length\s+disable',
            r'^\s*$',  # Empty lines at start
        ]

        # Command echo pattern: hostname#command or hostname>command
        # Also matches: hostname(config)#, hostname(config-if)#, etc.
        command_echo_pattern = r'^[\w\-\.]+[\#\>\$\)].*?(show|display|get)\s+'

        # Trailing prompt pattern
        trailing_prompt_pattern = r'^[\w\-\.]+[\#\>\$\)]\s*$'

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines at the start
            if not found_output_start and not line_stripped:
                continue

            # Skip preamble lines
            if not found_output_start:
                is_preamble = False
                for pattern in preamble_patterns:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        is_preamble = True
                        break

                if is_preamble:
                    continue

                # Check for command echo line
                if re.match(command_echo_pattern, line_stripped, re.IGNORECASE):
                    found_output_start = True
                    continue  # Skip the command echo itself

                # If we get here without matching preamble or command echo,
                # this is probably the start of actual output
                found_output_start = True

            # Skip trailing prompts
            if re.match(trailing_prompt_pattern, line_stripped):
                continue

            cleaned_lines.append(line)

        # Remove trailing empty lines
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()

        return '\n'.join(cleaned_lines)

    def validate(
            self,
            device_output: str,
            filter_string: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate device output against TextFSM templates.

        Args:
            device_output: Raw CLI output from device.
            filter_string: Template filter (e.g., "cisco_ios_show_version").

        Returns:
            ValidationResult with validation status and parsed data.
        """
        if not device_output or not device_output.strip():
            return ValidationResult(
                is_valid=False,
                error="Empty output"
            )

        try:
            # Clean the output before validation
            cleaned_output = self._clean_output(device_output)

            if self.verbose:
                print(f"[VALIDATION] Cleaned output ({len(cleaned_output)} chars):")
                print(cleaned_output[:500] + "..." if len(cleaned_output) > 500 else cleaned_output)

            # Use tfsm_fire engine to find best template
            template, parsed_data, score = self._engine.find_best_template(
                cleaned_output, filter_string
            )

            is_valid = score >= self.min_score and parsed_data is not None

            return ValidationResult(
                is_valid=is_valid,
                template=template,
                parsed_data=parsed_data,
                score=score,
            )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error=str(e)
            )

    def list_templates(self, filter_string: Optional[str] = None) -> List[str]:
        """List available templates matching filter."""
        with self._engine.connection_manager.get_connection() as conn:
            templates = self._engine.get_filtered_templates(conn, filter_string)
            return [t['cli_command'] for t in templates]


# Convenience function for simple validation
def validate_output(
        output: str,
        filter_string: str,
        db_path: Optional[str] = None,
) -> ValidationResult:
    """
    Validate device output against TextFSM templates.

    Args:
        output: Raw CLI output from device.
        filter_string: Template filter (e.g., "cisco_ios_show_version").
        db_path: Path to template database (optional).

    Returns:
        ValidationResult with validation status.
    """
    engine = ValidationEngine(db_path=db_path)
    return engine.validate(output, filter_string)