#!/usr/bin/env python
"""Verify SweepQueue log for skipped entries."""

from __future__ import annotations

import argparse
import re
from collections import deque
from pathlib import Path
from typing import Iterable

BEGIN_RE = re.compile(
    r"measureit\.sweeps\.queue \| DEBUG \| begin_next\(\) called, queue length: (\d+)"
)
PROCESS_RE = re.compile(r"measureit\.sweeps\.queue \| DEBUG \| Processing: (\w+)")
FINISH_MAP = {
    re.compile(r"Finished sweep of "): "Sweep1D",
    re.compile(r"Finished 0D Sweep"): "Sweep0D",
    re.compile(r"Finished SimulSweep"): "SimulSweep",
}


def parse_blocks(lines: Iterable[str]):
    blocks = []
    current = None
    for line in lines:
        begin = BEGIN_RE.search(line)
        if begin:
            if current:
                blocks.append(current)
            current = {
                "length": int(begin.group(1)),
                "processings": [],
                "lines": [line.strip()],
            }
            continue
        if current is None:
            continue
        current["lines"].append(line.strip())
        proc = PROCESS_RE.search(line)
        if proc:
            current["processings"].append(proc.group(1))
    if current:
        blocks.append(current)
    return blocks


def check_log(path: Path) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    notes: list[str] = []
    content = path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()

    blocks = parse_blocks(lines)
    if not blocks:
        problems.append("No begin_next() entries found – is this a SweepQueue log?")
        return problems, notes

    for idx, block in enumerate(blocks[:-1]):
        current_len = block["length"]
        next_len = blocks[idx + 1]["length"]
        delta = current_len - next_len
        if delta != len(block["processings"]):
            problems.append(
                f"Queue length dropped from {current_len} to {next_len} while processing {len(block['processings'])} items."
            )

    pending: deque[str] = deque()
    unmatched_finishes = 0
    for line in lines:
        proc = PROCESS_RE.search(line)
        if proc:
            action = proc.group(1)
            if action != "DatabaseEntry":
                pending.append(action)
            continue

        for pattern, action_type in FINISH_MAP.items():
            if pattern.search(line):
                if not pending:
                    unmatched_finishes += 1
                else:
                    expected = pending.popleft()
                    if expected != action_type:
                        problems.append(
                            f"Finished {action_type} but expected {expected}."
                        )
                break

    if unmatched_finishes > 1:
        problems.append(
            f"Observed {unmatched_finishes} completion logs with no matching pending action."
        )
    elif unmatched_finishes == 1:
        notes.append(
            "One completion without a matching start (likely the initial sweep started before logging)."
        )

    if pending:
        notes.append("Log ends with pending actions: " + ", ".join(pending))

    return problems, notes


def main():
    parser = argparse.ArgumentParser(
        description="Check MeasureIt SweepQueue log for skipped entries."
    )
    parser.add_argument("log_path", type=Path, help="Path to the sweep log")
    args = parser.parse_args()

    problems, notes = check_log(args.log_path)
    if problems:
        print("❌ Issues detected:")
        for msg in problems:
            print("  -", msg)
    else:
        print("✅ Queue log passes structural checks.")
    for note in notes:
        print("ℹ️ ", note)


if __name__ == "__main__":
    main()
