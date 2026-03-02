# array_plot_thread.py

from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QObject, QTimer, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..logging_utils import get_sweep_logger

# Configure PyQtGraph for better performance
pg.setConfigOptions(
    antialias=False,
    useOpenGL=False,
    crashWarning=True,
)
pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")


class ArrayPlotThread(QObject):
    """PyQtGraph-based array parameter plotter for real-time visualization.

    Displays array-valued parameters (e.g., spectrometer spectra, VNA traces)
    in two panels:
    - Line plot: current spectrum/trace vs internal axis (pixel, frequency, etc.)
    - 2D heatmap: buildup of spectra over time (Sweep0D) or sweep parameter (Sweep1D)

    Runs in addition to the existing scalar Plotter and Sweep2D Heatmap.

    Attributes:
    ----------
    sweep:
        The parent sweep object.
    array_param:
        The ParameterWithSetpoints to visualize.
    internal_axis:
        Cached 1D numpy array from array_param.setpoints[0].get().
    data_queue:
        Incoming raw arrays waiting to be displayed.
    heatmap_rows:
        List of 1D arrays for 2D heatmap buildup.
    sweep_axis_values:
        X-axis values for heatmap rows (time or sweep param value).
    figs_set:
        True after figures have been created.
    """

    def __init__(self, sweep, array_param, update_interval=200):
        """Initialize the array plot thread.

        Parameters
        ----------
        sweep:
            The parent sweep object.
        array_param:
            A ParameterWithSetpoints to visualize.
        update_interval:
            Update interval in milliseconds (default 200ms = 5 FPS).
        """
        QObject.__init__(self)

        self.sweep = sweep
        self.array_param = array_param
        self.update_interval = update_interval

        # Cache the internal axis from the setpoints parameter
        self.internal_axis = array_param.setpoints[0].get()
        sp0 = array_param.setpoints[0]
        self.internal_label = getattr(sp0, "label", sp0.name)
        self.internal_unit = getattr(sp0, "unit", "")

        # Data buffers
        self.data_queue = deque([])
        self.heatmap_rows = []
        self.sweep_axis_values = []

        self.figs_set = False
        self.max_items_per_update = 10
        self._disabled = False

        # Widget refs
        self.widget = None
        self.layout_widget = None
        self.line_plot = None
        self.line_curve = None
        self.heatmap_plot = None
        self.image_item = None
        self.hist_item = None
        self.update_timer = None

        # UI controls
        self.cmap_box = None
        self.auto_levels_chk = None
        self._auto_levels_enabled = True

        self.logger = getattr(sweep, "logger", None) or get_sweep_logger("array_plot")

    def create_figs(self):
        """Create the PyQtGraph array plot figure with line plot and heatmap panels."""
        try:
            if self.figs_set:
                return

            # Ensure a QApplication exists
            try:
                pg.mkQApp()
            except Exception:
                pass

            # Create main widget
            self.widget = QWidget()
            param_label = getattr(self.array_param, "label", self.array_param.name)
            param_unit = getattr(self.array_param, "unit", "")
            self.widget.setWindowTitle(f"MeasureIt - Array Plot: {param_label}")
            self.widget.resize(800, 700)

            main_layout = QVBoxLayout(self.widget)

            # Info label
            info_label = QLabel(f"Array Plot: {param_label} ({param_unit})")
            info_label.setFont(QFont("Arial", 12))
            info_label.setStyleSheet(
                "QLabel { background-color: #f0f0f0; padding: 5px; }"
            )
            main_layout.addWidget(info_label)

            # Controls row
            controls = QHBoxLayout()
            controls.setContentsMargins(0, 0, 0, 0)
            controls.setSpacing(8)

            controls.addWidget(QLabel("Colormap:"))
            self.cmap_box = QComboBox()
            available_maps = []
            try:
                available_maps = list(pg.colormap.listMaps())
            except Exception:
                available_maps = []
            preferred = [
                "viridis", "plasma", "inferno", "magma",
                "cividis", "turbo", "gray", "grays",
                "jet", "hot", "coolwarm",
            ]
            cmaps = (
                [m for m in preferred if m in available_maps]
                or available_maps
                or ["viridis"]
            )
            for m in cmaps:
                self.cmap_box.addItem(m)
            self.cmap_box.setCurrentText(
                "viridis" if "viridis" in cmaps else cmaps[0]
            )
            self.cmap_box.currentTextChanged.connect(self._apply_colormap)
            controls.addWidget(self.cmap_box)

            self.auto_levels_chk = QCheckBox("Auto levels")
            self.auto_levels_chk.setChecked(True)
            self.auto_levels_chk.toggled.connect(self._toggle_auto_levels)
            controls.addWidget(self.auto_levels_chk)

            reset_btn = QPushButton("Reset view")
            reset_btn.clicked.connect(self._reset_view)
            controls.addWidget(reset_btn)

            controls.addStretch(1)
            main_layout.addLayout(controls)

            # Create GraphicsLayoutWidget with two rows
            self.layout_widget = pg.GraphicsLayoutWidget()
            main_layout.addWidget(self.layout_widget)

            # Row 0: Line plot (current spectrum)
            self.line_plot = self.layout_widget.addPlot(row=0, col=0)
            self.line_plot.setLabel("bottom", self.internal_label, units=self.internal_unit)
            self.line_plot.setLabel("left", param_label, units=param_unit)
            self.line_plot.showGrid(x=True, y=True, alpha=0.3)
            self.line_curve = self.line_plot.plot(pen=pg.mkPen("b", width=1.5))

            # Row 1: Heatmap (buildup over sweep)
            self.heatmap_plot = self.layout_widget.addPlot(row=1, col=0)
            self.heatmap_plot.setLabel("bottom", self.internal_label, units=self.internal_unit)

            # Determine y-axis label for heatmap
            sweep_set_param = getattr(self.sweep, "set_param", None)
            if sweep_set_param is not None:
                y_label = getattr(sweep_set_param, "label", sweep_set_param.name)
                y_unit = getattr(sweep_set_param, "unit", "")
            else:
                y_label = "Time"
                y_unit = "s"
            self.heatmap_plot.setLabel("left", y_label, units=y_unit)
            self.heatmap_plot.showGrid(x=True, y=True, alpha=0.3)

            self.image_item = pg.ImageItem()
            self.heatmap_plot.addItem(self.image_item)

            # Add histogram/colorbar
            try:
                self.hist_item = pg.HistogramLUTItem()
                self.hist_item.setImageItem(self.image_item)
                self.layout_widget.addItem(self.hist_item, row=1, col=1)
            except Exception:
                self.hist_item = None

            # Connect close event
            self.widget.closeEvent = self._handle_close

            # Show the widget
            self.widget.show()

            # Start update timer
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_display)
            self.update_timer.start(self.update_interval)

            # Apply initial colormap
            self._apply_colormap(
                self.cmap_box.currentText() if self.cmap_box is not None else "viridis"
            )

            self.figs_set = True

        except Exception as e:
            self._disable_plotting(f"Error creating array plot figures: {e}")
            self.figs_set = False

    @pyqtSlot(object, int)
    def add_data(self, data_list, direction):
        """Extract array data from the runner's send_data signal.

        Connected to runner.send_data signal alongside the scalar Plotter.

        Parameters
        ----------
        data_list:
            List of (param_or_name, value) tuples from update_values().
        direction:
            Sweep direction (0 for Sweep0D, ±1 for Sweep1D).
        """
        try:
            if self._disabled or data_list is None:
                return

            # Determine the sweep x-axis value
            # data_list format: [("time", t), (set_param, value), ..., (param, value), ...]
            sweep_x_value = None
            array_value = None

            for name_or_param, value in data_list:
                if name_or_param is self.array_param:
                    array_value = value
                elif name_or_param == "time":
                    # Default to time; may be overridden by set_param below
                    if sweep_x_value is None:
                        sweep_x_value = value
                elif (
                    name_or_param is getattr(self.sweep, "set_param", None)
                    and name_or_param is not None
                ):
                    sweep_x_value = value

            if array_value is not None and sweep_x_value is not None:
                self.data_queue.append((sweep_x_value, np.asarray(array_value)))
        except Exception as e:
            self._disable_plotting(f"Error in array plot add_data: {e}")

    def update_display(self):
        """Timer callback to update line plot and heatmap from queued data."""
        if not self.figs_set or self._disabled:
            return

        try:
            items_processed = 0
            while len(self.data_queue) > 0 and items_processed < self.max_items_per_update:
                sweep_x, array_data = self.data_queue.popleft()
                items_processed += 1

                # Update line plot with latest spectrum
                self.line_curve.setData(self.internal_axis, array_data)

                # Append to heatmap buildup
                self.heatmap_rows.append(array_data)
                self.sweep_axis_values.append(sweep_x)

            if items_processed == 0:
                return

            # Build 2D array and update heatmap
            n_rows = len(self.heatmap_rows)
            if n_rows < 1:
                return

            data_2d = np.array(self.heatmap_rows)  # shape (n_rows, n_internal)

            # Remember current view state
            view_box = self.heatmap_plot.getViewBox()
            view_range = view_box.viewRange()

            # Update image (transposed: PyQtGraph ImageItem expects [x, y])
            self.image_item.setImage(data_2d.T)

            # Compute coordinate rect
            x_min = self.internal_axis[0]
            x_max = self.internal_axis[-1]
            y_min = self.sweep_axis_values[0]
            y_max = self.sweep_axis_values[-1]

            # Avoid zero-height rect when only one row
            if n_rows == 1 or y_min == y_max:
                y_span = 1.0
            else:
                y_span = y_max - y_min

            from PyQt5.QtCore import QRectF

            self.image_item.setRect(
                QRectF(x_min, y_min, x_max - x_min, y_span)
            )

            # Auto-levels
            if self._auto_levels_enabled:
                try:
                    finite = data_2d[np.isfinite(data_2d)]
                    if finite.size > 0:
                        lo, hi = np.nanpercentile(finite, [1, 99])
                        if hi > lo:
                            if self.hist_item is not None:
                                self.hist_item.setLevels(lo, hi)
                            else:
                                self.image_item.setLevels([lo, hi])
                except Exception:
                    pass

            # Restore view range
            view_box.setRange(
                xRange=view_range[0], yRange=view_range[1], padding=0
            )

        except Exception as e:
            self._disable_plotting(f"Error updating array plot: {e}")

    def reset(self):
        """Reset data buffers between inner sweep iterations (e.g., in Sweep2D)."""
        self.data_queue.clear()
        self.heatmap_rows.clear()
        self.sweep_axis_values.clear()
        if self.line_curve is not None:
            self.line_curve.setData([], [])
        if self.image_item is not None:
            self.image_item.clear()

    def clear(self):
        """Stop timer, close widget, release resources."""
        if self.figs_set:
            if self.update_timer is not None:
                self.update_timer.stop()
                self.update_timer = None

            self.figs_set = False
            if self.widget is not None:
                self.widget.close()
                self.widget = None
                self.layout_widget = None
                self.line_plot = None
                self.line_curve = None
                self.heatmap_plot = None
                self.image_item = None
                self.hist_item = None

    def _handle_close(self, event):
        """Handle widget close event."""
        self.clear()
        event.accept()

    def _apply_colormap(self, name: str):
        """Apply selected colormap to heatmap image and histogram."""
        try:
            cmap = None
            try:
                cmap = pg.colormap.get(name)
            except Exception:
                pass

            if cmap is not None:
                if self.hist_item is not None and hasattr(self.hist_item, "setColorMap"):
                    self.hist_item.setColorMap(cmap)
                try:
                    lut = cmap.getLookupTable(alpha=False)
                    self.image_item.setLookupTable(lut)
                except Exception:
                    pass
            else:
                lut = np.stack([np.linspace(0, 255, 256)] * 3, axis=1)
                self.image_item.setLookupTable(lut)
        except Exception:
            pass

    def _toggle_auto_levels(self, checked: bool):
        """Toggle automatic color level adjustment."""
        self._auto_levels_enabled = bool(checked)

    def _reset_view(self):
        """Reset view to auto-range on both plots."""
        try:
            if self.line_plot is not None:
                self.line_plot.enableAutoRange(x=True, y=True)
            if self.heatmap_plot is not None:
                self.heatmap_plot.enableAutoRange(x=True, y=True)
        except Exception:
            pass

    def _disable_plotting(self, reason: str):
        """Disable plotting after an exception and log the error."""
        try:
            self.logger.error(reason, exc_info=True)
        except Exception:
            pass
        self._disabled = True
        try:
            self.clear()
        except Exception:
            pass
