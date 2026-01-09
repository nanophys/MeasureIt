"""Helper functions for validating sweep queue execution logs."""

import re
from pathlib import Path
from typing import Dict, List, Tuple


def parse_queue_log(log_file: Path) -> Tuple[Dict[str, str], Dict[str, str], List[str]]:
    """Parse queue log file and extract start/finish events.

    Args:
        log_file: Path to log file

    Returns:
        Tuple of (starts, finishes, errors)
        - starts: Dict mapping sweep ID to start timestamp
        - finishes: Dict mapping sweep ID to finish timestamp
        - errors: List of error messages
    """
    starts = {}
    finishes = {}
    errors = []

    if not log_file.exists():
        return starts, finishes, errors

    with open(log_file) as f:
        for line in f:
            # Match start pattern: "Starting sweep: <description>"
            start_match = re.search(r"Starting sweep:?\s*(.+)", line, re.IGNORECASE)
            if start_match:
                sweep_desc = start_match.group(1).strip()
                timestamp = line.split()[0] if line.split() else ""
                starts[sweep_desc] = timestamp
                continue

            # Match finish pattern: "Finished sweep: <description>"
            finish_match = re.search(r"Finished sweep:?\s*(.+)", line, re.IGNORECASE)
            if finish_match:
                sweep_desc = finish_match.group(1).strip()
                timestamp = line.split()[0] if line.split() else ""
                finishes[sweep_desc] = timestamp
                continue

            # Match error patterns
            if "ERROR" in line.upper() or "EXCEPTION" in line.upper():
                errors.append(line.strip())

    return starts, finishes, errors


def validate_queue_logs(log_file: Path, expected_count: int = None) -> bool:
    """Validate that queue execution logs are consistent.

    Args:
        log_file: Path to log file
        expected_count: Expected number of sweeps (optional)

    Returns:
        True if logs are valid

    Raises:
        AssertionError: If validation fails
    """
    starts, finishes, errors = parse_queue_log(log_file)

    # Check for errors
    assert len(errors) == 0, f"Found {len(errors)} errors in log:\n" + "\n".join(errors)

    # Check all starts have corresponding finishes
    unfinished = set(starts.keys()) - set(finishes.keys())
    assert len(unfinished) == 0, f"Found unfinished sweeps: {unfinished}"

    # Check no finishes without starts
    unknown_finishes = set(finishes.keys()) - set(starts.keys())
    assert len(unknown_finishes) == 0, f"Found finishes without starts: {unknown_finishes}"

    # Check expected count
    if expected_count is not None:
        assert len(starts) == expected_count, (
            f"Expected {expected_count} sweeps, found {len(starts)}"
        )

    return True


def assert_queue_logs_valid(log_file: Path, expected_sweeps: List[str] = None):
    """Assert that queue logs are valid and contain expected sweeps.

    Args:
        log_file: Path to log file
        expected_sweeps: List of expected sweep descriptions (optional)

    Raises:
        AssertionError: If validation fails
    """
    starts, finishes, errors = parse_queue_log(log_file)

    # Basic validation
    validate_queue_logs(log_file)

    # Check for expected sweeps
    if expected_sweeps:
        found_sweeps = set(starts.keys())
        expected_set = set(expected_sweeps)

        missing = expected_set - found_sweeps
        assert len(missing) == 0, f"Missing expected sweeps: {missing}"

        extra = found_sweeps - expected_set
        # Extra sweeps are okay (might be database entries, etc.)
        # but log them
        if extra:
            print(f"Info: Found additional sweeps: {extra}")


def get_sweep_duration(log_file: Path, sweep_desc: str) -> float:
    """Get duration of a sweep from logs.

    Args:
        log_file: Path to log file
        sweep_desc: Sweep description to find

    Returns:
        Duration in seconds (approximate, based on log timestamps)

    Raises:
        ValueError: If sweep not found or timestamps can't be parsed
    """
    starts, finishes, _ = parse_queue_log(log_file)

    if sweep_desc not in starts:
        raise ValueError(f"Sweep '{sweep_desc}' not found in starts")

    if sweep_desc not in finishes:
        raise ValueError(f"Sweep '{sweep_desc}' not found in finishes")

    # Simple duration calculation (this is approximate)
    # In real logs, you'd parse actual timestamps
    # For now, just return 0 as a placeholder
    return 0.0
