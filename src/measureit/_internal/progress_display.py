"""Shared helpers for building and updating progress bar widgets."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QProgressBar,
    QSizePolicy,
)

from ..sweep.abstract_sweep import ProgressState, SweepState


@dataclass
class ProgressControls:
    """Container holding widgets that make up a progress display."""

    progress_bar: QProgressBar
    elapsed_label: Optional[QLabel]
    remaining_label: Optional[QLabel]


def format_seconds(value: Optional[float]) -> str:
    """Format a time interval in seconds for display purposes."""
    if value is None:
        return "--"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "--"

    if math.isinf(numeric):
        return "∞"
    return f"{max(0.0, numeric):.1f} s"


def create_progress_controls(
    parent_layout: QLayout,
    *,
    show_elapsed: bool = True,
    show_remaining: bool = True,
) -> ProgressControls:
    """Create progress labels and bar and attach them to *parent_layout*."""
    info_layout = QHBoxLayout()
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(8)

    elapsed_label: Optional[QLabel] = None
    remaining_label: Optional[QLabel] = None
    added_any = False

    if show_elapsed:
        elapsed_label = QLabel("Elapsed: --")
        info_layout.addWidget(elapsed_label)
        added_any = True

    if show_remaining:
        info_layout.addStretch(1)
        remaining_label = QLabel("Remaining: --")
        info_layout.addWidget(remaining_label)
        added_any = True

    if added_any:
        parent_layout.addLayout(info_layout)

    progress_bar = QProgressBar()
    progress_bar.setRange(0, 1000)
    progress_bar.setValue(0)
    progress_bar.setTextVisible(True)
    progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    parent_layout.addWidget(progress_bar)

    return ProgressControls(progress_bar, elapsed_label, remaining_label)


def update_progress_controls(
    controls: ProgressControls,
    progress_state: Optional[ProgressState],
    *,
    suffix_map: Optional[Mapping[SweepState, str]] = None,
    progress_label: str = "Progress",
) -> None:
    """Update a progress widget set to reflect the supplied state."""
    progress_bar = controls.progress_bar
    elapsed_label = controls.elapsed_label
    remaining_label = controls.remaining_label

    if progress_state is None:
        if elapsed_label is not None:
            elapsed_label.setText("Elapsed: --")
        if remaining_label is not None:
            remaining_label.setText("Remaining: --")
        progress_bar.setValue(0)
        progress_bar.setFormat(f"{progress_label}: --")
        return

    if elapsed_label is not None:
        elapsed_label.setText(f"Elapsed: {format_seconds(progress_state.time_elapsed)}")
    if remaining_label is not None:
        remaining_label.setText(
            f"Remaining: {format_seconds(progress_state.time_remaining)}"
        )

    display_text = f"{progress_label}: --"
    progress_value = 0

    progress = progress_state.progress
    if progress is not None:
        constrained = max(0.0, min(1.0, float(progress)))
        percent = int(round(constrained * 100))
        display_text = f"{progress_label}: {percent}%"
        progress_value = int(constrained * 1000)

    if suffix_map:
        suffix = suffix_map.get(progress_state.state)
        if suffix:
            display_text = f"{display_text} ({suffix})"

    progress_bar.setFormat(display_text)
    progress_bar.setValue(progress_value)


__all__ = [
    "ProgressControls",
    "create_progress_controls",
    "format_seconds",
    "update_progress_controls",
]
