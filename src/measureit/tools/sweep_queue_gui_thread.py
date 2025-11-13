# sweep_queue_gui_thread.py

from functools import partial
from typing import Any

from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .._internal.progress_display import (
    create_progress_controls,
    update_progress_controls,
)
from ..sweep.abstract_sweep import ProgressState, SweepState
from ..sweep.base_sweep import BaseSweep

_PROGRESS_SUFFIX_MAP = {
    SweepState.RAMPING: "Ramping",
    SweepState.PAUSED: "Paused",
    SweepState.DONE: "Done",
}


class SweepQueueGuiThread(QThread):
    """Background thread emitting ticks to refresh the SweepQueue GUI."""

    tick = pyqtSignal()

    def __init__(self, interval_ms: int = 200, parent: QWidget | None = None):
        super().__init__(parent)
        self._interval_ms = interval_ms
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        self._stop = False
        while not self._stop:
            self.tick.emit()
            self.msleep(self._interval_ms)


class QueueGuiWindow(QWidget):
    """Simple Qt widget visualising SweepQueue progress and actions."""

    def __init__(self, queue: Any, on_close=None):
        super().__init__()
        self._queue = queue
        self._on_close = on_close
        self._info_label = None
        self._queue_elapsed = None
        self._queue_remaining = None
        self._queue_progress = None
        self._list_layout = None
        self._list_container = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self.setWindowTitle("MeasureIt - Sweep Queue")
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._info_label = QLabel("Keyboard Shortcuts: ESC pause | Enter resume")
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        # Queue summary
        queue_title = QLabel("Queue")
        queue_title.setStyleSheet("font-weight: bold")
        layout.addWidget(queue_title)

        self._queue_controls = create_progress_controls(layout)
        self._queue_elapsed = self._queue_controls.elapsed_label
        self._queue_remaining = self._queue_controls.remaining_label
        self._queue_progress = self._queue_controls.progress_bar

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        layout.addWidget(divider)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll, 1)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 8, 0, 8)
        self._list_layout.setSpacing(8)
        self._list_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        scroll.setWidget(self._list_container)

        layout.addStretch(0)

    @pyqtSlot()
    def refresh(self) -> None:
        queue = self._queue
        self._update_queue_summary(queue)
        self._rebuild_progress_list()

    def _update_queue_summary(self, queue):
        update_progress_controls(
            self._queue_controls,
            queue.progress_state,
            suffix_map=_PROGRESS_SUFFIX_MAP,
        )

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self._queue.pause()
            event.accept()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._queue.resume()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if callable(self._on_close):
            self._on_close()
        super().closeEvent(event)

    def _rebuild_progress_list(self) -> None:
        self._clear_layout(self._list_layout)
        queue = self._queue

        if not queue:
            placeholder = QLabel("No actions queued")
            placeholder.setStyleSheet("color: #666")
            self._list_layout.addWidget(placeholder)
            self._list_layout.setAlignment(placeholder, Qt.AlignTop)
            return

        ordered = list(reversed(queue.past_actions))
        curr_index = len(ordered)
        current = queue.current_action
        if current is not None:
            ordered.append(current)
        ordered.extend(queue.future_actions)

        for i in range(len(ordered)):
            if isinstance(ordered[i], BaseSweep):
                row = self._create_sweep_row(ordered[i], i - curr_index)
            else:
                row = self._create_nonsweep_row(ordered[i], i - curr_index)
            self._list_layout.addWidget(row)
            self._list_layout.setAlignment(row, Qt.AlignTop)

    def _create_sweep_row(self, sweep: BaseSweep, pos: int) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignTop)

        indicator = QLabel("▶" if pos == 0 else "")
        indicator.setFixedWidth(15)
        indicator.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
        layout.addWidget(indicator)

        desc = sweep.__class__.__name__
        set_param = getattr(sweep, "set_param", None)
        if set_param is not None:
            label = getattr(set_param, "label", None) or str(set_param)
            desc = f"{desc} – {label}"

        label = QLabel(desc)
        label.setMinimumWidth(100)
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(label, 0)

        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setSpacing(8)

        parent_queue = self._queue
        controls = create_progress_controls(
            progress_layout,
            show_elapsed=sweep is parent_queue.current_action
            or sweep in parent_queue.past_actions,
            show_remaining=sweep is parent_queue.current_action
            or sweep in parent_queue.future_actions,
        )
        progress = controls.progress_bar
        progress.setAlignment(Qt.AlignLeft)

        state = sweep.progress_state
        if pos < 0:
            update_progress_controls(
                controls,
                ProgressState(SweepState.DONE, state.time_elapsed, 0, 1),
                suffix_map={SweepState.DONE: "Done"},
            )
        elif pos == 0:
            update_progress_controls(controls, state, suffix_map=_PROGRESS_SUFFIX_MAP)
        else:
            update_progress_controls(
                controls, ProgressState(SweepState.READY, 0, state.time_remaining, 0)
            )

        progress_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(progress_widget, 1)
        layout.setAlignment(progress_widget, Qt.AlignTop)

        return widget

    def _create_nonsweep_row(self, action, pos: int) -> QWidget:
        desc = str(action)
        if action is None:
            desc = "--"
        elif isinstance(action, partial):
            fn_name = getattr(action.func, "__name__", repr(action.func))
            desc = f"Callable {fn_name}"
        elif callable(action):
            desc = f"Callable {getattr(action, '__name__', repr(action))}"

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)

        indicator = QLabel("▶" if pos == 0 else "")
        indicator.setFixedWidth(15)
        layout.addWidget(indicator)

        label = QLabel(desc)
        label.setWordWrap(True)
        label.setStyleSheet("color: #444")
        layout.addWidget(label)

        return widget

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            widget = child.widget()
            inner_layout = child.layout()
            if widget is not None:
                widget.deleteLater()
            if inner_layout is not None:
                self._clear_layout(inner_layout)


__all__ = ["SweepQueueGuiThread", "QueueGuiWindow"]
