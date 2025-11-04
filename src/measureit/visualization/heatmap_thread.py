# heatmap_thread.py

import math
from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QObject, QTimer, pyqtSlot  # moved to visualization
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Configure PyQtGraph for better performance
pg.setConfigOptions(
    antialias=False,  # Disable antialiasing for better performance
    useOpenGL=False,  # Don't use OpenGL - can cause issues
    crashWarning=True,  # Show warnings for debugging
)
pg.setConfigOption("background", "w")  # White background
pg.setConfigOption("foreground", "k")  # Black foreground


class Heatmap(QObject):
    """PyQtGraph-based heatmap plotter for Sweep2D.

    Provides high-performance real-time 2D visualization using PyQtGraph ImageView.
    Maintains the same API as the original matplotlib Heatmap class for compatibility.

    Attributes:
    ---------
    sweep:
        The parent sweep object.
    data_to_add:
        Queue to store heatmap data updates.
    param_surfaces:
        Dict mapping param_index -> surface dict with keys:
            'data' (2D np.array), 'dict' (nested dict of values), 'min', 'max'.
    figs_set:
        Changes to true after figures have been created.
    widget:
        Main QWidget containing the heatmap layout.
    layout_widget:
        PyQtGraph GraphicsLayoutWidget to host plot + colorbar.
    plot_item:
        PyQtGraph PlotItem used as the main view with axes.
    heatmap_data:
        2D numpy array containing the heatmap data.
    heatmap_dict:
        Dictionary mapping outer/inner parameter values to data.
    hist_item:
        HistogramLUTItem providing an interactive colorbar.
    cmap_box:
        QComboBox to pick colormap.
    auto_levels_chk:
        QCheckBox to toggle auto color scaling.
    param_box:
        QComboBox to pick which followed parameter to visualize.
    info_label:
        QLabel displaying current heatmap parameter.

    Methods:
    ---------
    create_figs()
        Creates the PyQtGraph heatmap figure for Sweep2D.
    add_data(data_dict)
        Adds data dictionary to be plotted on the heatmap.
    update_heatmap()
        Updates the heatmap with new data from the queue.
    clear()
        Closes all active figures.
    """

    def __init__(self, sweep, update_interval=200):
        """Initializes the PyQtGraph heatmap thread.

        Parameters
        ---------
        sweep:
            The parent sweep object.
        update_interval:
            Update interval in milliseconds (default 200ms = 5 FPS).
        """
        QObject.__init__(self)

        self.sweep = sweep
        self.data_to_add = deque([])
        self.param_surfaces = {}
        self.count = (
            0  # maintained for backward-compat, not relied upon when out_value provided
        )
        self.figs_set = False

        # PyQtGraph-specific attributes
        self.widget = None
        self.layout_widget = None
        self.plot_item = None
        self.image_item = None
        self.hist_item = None
        self.heatmap_data = None
        self.heatmap_dict = {}
        self.out_keys = []
        self.in_keys = []
        self.info_label = None
        self.progress_bar = None
        self.elapsed_label = None
        self.remaining_label = None

        # Timer for regular heatmap updates (5 FPS)
        self.update_timer = None
        self.update_interval = update_interval  # milliseconds
        self.needs_refresh = False
        self.max_items_per_update = 10  # Process max 10 items per timer tick

        # UI controls
        self.cmap_box = None
        self.auto_levels_chk = None
        self._auto_levels_enabled = True
        self.param_box = None
        self._param_indices = []  # Map combobox rows to in_sweep._params indices

    def handle_close(self, event):
        """Handle widget close event."""
        self.clear()
        event.accept()

    def handle_key_press(self, event):
        """Handle keyboard shortcuts for sweep control from heatmap window."""
        try:
            key = event.key()
            if key == pg.QtCore.Qt.Key_Escape:
                # Pause the 2D sweep gracefully
                try:
                    self.sweep.pause()
                except Exception:
                    pass
            elif key == pg.QtCore.Qt.Key_Return or key == pg.QtCore.Qt.Key_Enter:
                try:
                    self.sweep.resume()
                except Exception:
                    pass
            elif key == pg.QtCore.Qt.Key_Space:
                try:
                    # Flip the inner sweep direction
                    if (
                        hasattr(self.sweep, "in_sweep")
                        and self.sweep.in_sweep is not None
                    ):
                        self.sweep.in_sweep.flip_direction()
                except Exception:
                    pass
        except Exception:
            pass

    def create_figs(self):
        """Creates the PyQtGraph heatmap figure for the 2D sweep."""
        try:
            if self.figs_set:
                return

            # First, determine the resolution on each axis
            self.res_in = (
                math.ceil(
                    abs((self.sweep.in_stop - self.sweep.in_start) / self.sweep.in_step)
                )
                + 1
            )
            self.res_out = (
                math.ceil(
                    abs(
                        (self.sweep.out_stop - self.sweep.out_start)
                        / self.sweep.out_step
                    )
                )
                + 1
            )

            # Create the heatmap data matrix - initially as all 0s
            self.heatmap_dict = {}
            self.out_keys = []
            self.in_keys = []
            self.out_step = self.sweep.out_step
            self.in_step = self.sweep.in_step

            for x_out in np.linspace(
                self.sweep.out_start,
                self.sweep.out_stop,
                int(
                    abs(self.sweep.out_stop - self.sweep.out_start)
                    / abs(self.sweep.out_step)
                    + 1
                ),
                endpoint=True,
            ):
                self.heatmap_dict[x_out] = {}
                self.out_keys.append(x_out)
                for x_in in np.linspace(
                    self.sweep.in_start,
                    self.sweep.in_stop,
                    int(
                        abs(self.sweep.in_stop - self.sweep.in_start)
                        / abs(self.sweep.in_step)
                        + 1
                    ),
                    endpoint=True,
                ):
                    self.heatmap_dict[x_out][x_in] = 0
                    if x_in not in self.in_keys:
                        self.in_keys.append(x_in)

            self.out_keys = sorted(self.out_keys)
            self.in_keys = sorted(self.in_keys)

            # Initialize surfaces store and the current displayed surface
            self.param_surfaces = {}
            self.count = 0

            # Ensure a QApplication exists (safe in scripts and in notebooks once ensure_qt() has been called)
            try:
                pg.mkQApp()
            except Exception:
                pass

            # Create main widget and layout
            self.widget = QWidget()
            self.widget.setWindowTitle("MeasureIt - 2D Heatmap")
            self.widget.resize(800, 600)

            main_layout = QVBoxLayout(self.widget)

            # Add parameter info label
            plot_para = self.sweep.in_sweep._params[self.sweep.heatmap_ind]
            self.info_label = QLabel(
                f"2D Heatmap: {plot_para.label} ({plot_para.unit})"
            )
            self.info_label.setFont(QFont("Arial", 12))
            self.info_label.setStyleSheet(
                "QLabel { background-color: #f0f0f0; padding: 5px; }"
            )
            main_layout.addWidget(self.info_label)

            state = getattr(self.sweep, "progressState", None)
            if state is not None and getattr(state, "progress", None) is not None:
                progress_info = QHBoxLayout()
                progress_info.setContentsMargins(0, 0, 0, 0)
                progress_info.setSpacing(8)

                self.elapsed_label = QLabel("Elapsed: --")
                self.remaining_label = QLabel("Remaining: --")

                progress_info.addWidget(self.elapsed_label)
                progress_info.addStretch(1)
                progress_info.addWidget(self.remaining_label)

                self.progress_bar = QProgressBar()
                self.progress_bar.setRange(0, 1000)
                self.progress_bar.setValue(0)
                self.progress_bar.setTextVisible(True)

                main_layout.addLayout(progress_info)
                main_layout.addWidget(self.progress_bar)
                self._update_progress_widgets()

            # Controls row (colormap picker, auto-levels, reset)
            controls = QHBoxLayout()
            controls.setContentsMargins(0, 0, 0, 0)
            controls.setSpacing(8)
            controls.addWidget(QLabel("Colormap:"))
            self.cmap_box = QComboBox()
            # Prefer common scientific colormaps; filter by availability
            available_maps = []
            try:
                available_maps = list(pg.colormap.listMaps())
            except Exception:
                available_maps = []
            preferred = [
                "viridis",
                "plasma",
                "inferno",
                "magma",
                "cividis",
                "turbo",
                "gray",
                "grays",
                "jet",
                "hot",
                "coolwarm",
            ]
            cmaps = (
                [m for m in preferred if m in available_maps]
                or available_maps
                or ["viridis"]
            )
            for m in cmaps:
                self.cmap_box.addItem(m)
            self.cmap_box.setCurrentText("viridis" if "viridis" in cmaps else cmaps[0])
            self.cmap_box.currentTextChanged.connect(self._apply_colormap)
            controls.addWidget(self.cmap_box)

            self.auto_levels_chk = QCheckBox("Auto levels")
            self.auto_levels_chk.setChecked(True)
            self.auto_levels_chk.toggled.connect(self._toggle_auto_levels)
            controls.addWidget(self.auto_levels_chk)

            reset_btn = QPushButton("Reset view")
            reset_btn.clicked.connect(self._reset_view)
            controls.addWidget(reset_btn)

            # Parameter selector (followed params, excluding outer set_param)
            controls.addWidget(QLabel("Signal:"))
            self.param_box = QComboBox()
            self._rebuild_param_box()
            self.param_box.currentIndexChanged.connect(self._on_param_selected)
            controls.addWidget(self.param_box)

            controls.addStretch(1)
            main_layout.addLayout(controls)

            # Create GraphicsLayout with a PlotItem (left) and HistogramLUTItem (right)
            self.layout_widget = pg.GraphicsLayoutWidget()
            main_layout.addWidget(self.layout_widget)

            self.plot_item = self.layout_widget.addPlot(row=0, col=0)
            self.plot_item.setLabel(
                "bottom", f"{self.sweep.in_param.label}", units=self.sweep.in_param.unit
            )
            self.plot_item.setLabel(
                "left", f"{self.sweep.set_param.label}", units=self.sweep.set_param.unit
            )
            self.plot_item.showGrid(x=True, y=True, alpha=0.3)

            # Create ImageItem for the heatmap data
            self.image_item = pg.ImageItem()
            self.plot_item.addItem(self.image_item)

            # Add interactive colorbar/histogram
            try:
                self.hist_item = pg.HistogramLUTItem()
                self.hist_item.setImageItem(self.image_item)
                self.layout_widget.addItem(self.hist_item, row=0, col=1)
            except Exception:
                self.hist_item = None  # fallback silently if unavailable

            # Store coordinate transform parameters for updates
            self.pos = [self.sweep.in_start, self.sweep.out_start]
            self.scale = [
                (self.sweep.in_stop - self.sweep.in_start) / self.res_in,
                (self.sweep.out_stop - self.sweep.out_start) / self.res_out,
            ]

            # Ensure an initial surface for the currently selected parameter
            self._ensure_surface(self.sweep.heatmap_ind)
            self.heatmap_data = self.param_surfaces[self.sweep.heatmap_ind]["data"]
            # Set up the initial image with proper scaling
            self.image_item.setImage(self.heatmap_data)

            # Set the coordinate transformation for proper axis scaling
            # Use setRect as the primary method (more reliable than transform)
            try:
                from PyQt5.QtCore import QRectF
                # setRect takes (x, y, width, height) in data coordinates
                self.image_item.setRect(
                    QRectF(
                        self.sweep.in_start,
                        self.sweep.out_start,
                        self.sweep.in_stop - self.sweep.in_start,   # Total width
                        self.sweep.out_stop - self.sweep.out_start, # Total height
                    )
                )
            except Exception:
                # Fallback: use transform if setRect fails
                try:
                    transform = pg.QtGui.QTransform()
                    transform.translate(self.pos[0], self.pos[1])
                    # Use (N-1) for correct pixel spacing
                    transform.scale(
                        (self.sweep.in_stop - self.sweep.in_start) / (self.res_in - 1),
                        (self.sweep.out_stop - self.sweep.out_start) / (self.res_out - 1)
                    )
                    self.image_item.setTransform(transform)
                except Exception:
                    pass

            # Connect close and keyboard events
            self.widget.closeEvent = self.handle_close
            self.widget.keyPressEvent = self.handle_key_press
            self.widget.setFocusPolicy(pg.QtCore.Qt.StrongFocus)

            # Show the widget
            self.widget.show()

            # Start the update timer for regular heatmap refreshes
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_heatmap)
            self.update_timer.start(self.update_interval)

            # Apply initial colormap
            self._apply_colormap(
                self.cmap_box.currentText() if self.cmap_box is not None else "viridis"
            )

            self.figs_set = True

            self._update_progress_widgets()

        except Exception as e:
            print(f"Error creating heatmap figures: {e}")
            import traceback

            traceback.print_exc()
            self.figs_set = False

    @pyqtSlot(object)
    def add_data(self, data_dict):
        """Feeds the thread data dictionary to add to the heatmap.

        Parameters
        ---------
        data_dict:
            Dictionary containing 'forward' and 'backward' data tuples (x_data, y_data)
            from the plotter thread.
        """
        try:
            if data_dict is None:
                self.data_to_add.append(None)
            else:
                # Accept legacy payloads (only 'forward'/'backward') or new ones with 'param_index' and 'out_value'
                if "param_index" not in data_dict:
                    data_dict = dict(data_dict)  # shallow copy
                    data_dict["param_index"] = getattr(self.sweep, "heatmap_ind", 0)
                if "out_value" not in data_dict:
                    data_dict["out_value"] = getattr(self.sweep, "out_setpoint", None)
                self.data_to_add.append(data_dict)
        except Exception as e:
            print(f"Error in heatmap add_data: {e}")
            import traceback

            traceback.print_exc()

    def add_to_heatmap(self, data_dict):
        """Processes data dictionary for one complete inner sweep and updates heatmap data.

        Parameters
        ---------
        data_dict:
            Dictionary with 'forward' and 'backward' data tuples (x_data, y_data).
        """
        if "forward" not in data_dict:
            return

        # Determine target param and out value
        param_index = data_dict.get(
            "param_index", getattr(self.sweep, "heatmap_ind", 0)
        )
        out_value = data_dict.get(
            "out_value", getattr(self.sweep, "out_setpoint", None)
        )
        self._ensure_surface(param_index)

        # Get the complete inner sweep data
        x_data, y_data = data_dict["forward"]

        if len(x_data) == 0 or len(y_data) == 0:
            return

        # Remove NaN values
        valid_mask = ~(np.isnan(x_data) | np.isnan(y_data))
        x_clean = x_data[valid_mask]
        y_clean = y_data[valid_mask]

        if len(x_clean) == 0:
            return

        # Determine row based on provided out_value if available; otherwise fall back to current count index
        if out_value is not None:
            current_out_key = min(self.out_keys, key=lambda k: abs(k - out_value))
            out_index = self.out_keys.index(current_out_key)
        else:
            if self.count >= len(self.out_keys):
                print(
                    f"Warning: heatmap count {self.count} exceeds out_keys length {len(self.out_keys)}"
                )
                return
            current_out_key = self.out_keys[self.count]
            out_index = self.count

        # Map inner sweep data to heatmap grid
        for x_val, y_val in zip(x_clean, y_clean):
            # Find closest in_key for this x value
            closest_in_key = min(self.in_keys, key=lambda k: abs(k - x_val))
            self.param_surfaces[param_index]["dict"][current_out_key][
                closest_in_key
            ] = y_val

            # Track min/max values per param
            if y_val > self.param_surfaces[param_index]["max"]:
                self.param_surfaces[param_index]["max"] = y_val
            if y_val < self.param_surfaces[param_index]["min"]:
                self.param_surfaces[param_index]["min"] = y_val

        # Update the data array row
        row_idx = self.res_out - out_index - 1  # Flip for proper orientation
        for i, in_key in enumerate(self.in_keys):
            if i < self.res_in:
                self.param_surfaces[param_index]["data"][row_idx][i] = (
                    self.param_surfaces[param_index]["dict"][current_out_key][in_key]
                )

        # Mark that this param surface has new data
        if not hasattr(self, "_dirty_params"):
            self._dirty_params = set()
        self._dirty_params.add(param_index)
        self.needs_refresh = True

    def update_heatmap(self):
        """Updates the heatmap with new data from the queue using batch processing."""
        if not self.figs_set:
            return

        # Process limited batch of data to prevent UI blocking
        items_processed = 0
        while len(self.data_to_add) > 0 and items_processed < self.max_items_per_update:
            data_dict = self.data_to_add.popleft()
            if data_dict is None:
                break
            self.add_to_heatmap(data_dict)
            items_processed += 1
            self.needs_refresh = True

        self._update_progress_widgets()
        # Update display with proper scaling while preserving view
        if self.image_item is not None and (self.needs_refresh or items_processed > 0):
            # Remember current view state
            view_box = self.plot_item.getViewBox()
            view_range = view_box.viewRange()

            # Update the image data
            # Ensure our current display surface points to the selected param
            current_idx = getattr(self.sweep, "heatmap_ind", 0)
            self._ensure_surface(current_idx)
            self.heatmap_data = self.param_surfaces[current_idx]["data"]
            self.image_item.setImage(self.heatmap_data)

            # Set color levels: auto or leave to user via histogram LUT
            if self._auto_levels_enabled:
                try:
                    # Robust percentiles if data available; fallback to min/max trackers
                    finite = self.heatmap_data[np.isfinite(self.heatmap_data)]
                    if finite.size > 0:
                        lo, hi = np.nanpercentile(finite, [1, 99])
                        if hi > lo:
                            if self.hist_item is not None:
                                self.hist_item.setLevels(lo, hi)
                            else:
                                self.image_item.setLevels([lo, hi])
                        else:
                            stats = self.param_surfaces[current_idx]
                            if self.hist_item is not None:
                                self.hist_item.setLevels(stats["min"], stats["max"])
                            else:
                                self.image_item.setLevels([stats["min"], stats["max"]])
                    else:
                        stats = self.param_surfaces[current_idx]
                        if self.hist_item is not None:
                            self.hist_item.setLevels(stats["min"], stats["max"])
                        else:
                            self.image_item.setLevels([stats["min"], stats["max"]])
                except Exception:
                    # Last resort: use tracked min/max
                    stats = self.param_surfaces[current_idx]
                    if self.hist_item is not None:
                        self.hist_item.setLevels(stats["min"], stats["max"])
                    else:
                        self.image_item.setLevels([stats["min"], stats["max"]])

            # Restore view range to preserve user zoom/pan
            view_box.setRange(xRange=view_range[0], yRange=view_range[1], padding=0)

            self.needs_refresh = False

    def _rebuild_param_box(self):
        """Populate the parameter selector with followed measurement parameters."""
        try:
            if self.param_box is None:
                return
            self.param_box.blockSignals(True)
            self.param_box.clear()
            self._param_indices = []
            # Choose candidates: prefer user-provided list on the sweep
            indices = getattr(self.sweep, "heatmap_param_indices", None)
            candidates = []
            if isinstance(indices, list) and len(indices) > 0:
                for idx in indices:
                    if 0 <= idx < len(self.sweep.in_sweep._params):
                        p = self.sweep.in_sweep._params[idx]
                        if p is not self.sweep.set_param:
                            candidates.append((idx, p))
            # Fallback to all followed params except outer set_param
            if len(candidates) == 0:
                for idx, p in enumerate(self.sweep.in_sweep._params):
                    if p is not self.sweep.set_param:
                        candidates.append((idx, p))
            for idx, p in candidates:
                lab = p.label if getattr(p, "label", None) else p.name
                txt = f"{lab} ({p.unit})" if getattr(p, "unit", None) else lab
                self.param_box.addItem(txt)
                self._param_indices.append(idx)
            # Set current selection to match sweep.heatmap_ind
            try:
                current = self._param_indices.index(self.sweep.heatmap_ind)
            except ValueError:
                current = 0 if self._param_indices else -1
            if current >= 0:
                self.param_box.setCurrentIndex(current)
            self.param_box.blockSignals(False)
        except Exception:
            self.param_box.blockSignals(False)

    @pyqtSlot()
    def refresh_param_list(self):
        """Public slot to rebuild parameter selector from Sweep2D configuration."""
        try:
            self._rebuild_param_box()
            # Also update info label text in case the current param changed
            try:
                p = self.sweep.in_sweep._params[self.sweep.heatmap_ind]
                lab = p.label if getattr(p, "label", None) else p.name
                txt = f"2D Heatmap: {lab} ({p.unit})"
                if self.info_label is not None:
                    self.info_label.setText(txt)
            except Exception:
                pass
        except Exception:
            pass

    def _on_param_selected(self, combo_index: int):
        """Handle selection change: update sweep heatmap index and reset content."""
        try:
            if combo_index < 0 or combo_index >= len(self._param_indices):
                return
            real_index = self._param_indices[combo_index]
            # Update Sweep2D selection using existing helper
            try:
                target_param = self.sweep.in_sweep._params[real_index]
                self.sweep.follow_heatmap_param(target_param)
            except Exception:
                self.sweep.heatmap_ind = real_index
            # Update label and reset displayed data
            try:
                p = self.sweep.in_sweep._params[self.sweep.heatmap_ind]
                lab = p.label if getattr(p, "label", None) else p.name
                txt = f"2D Heatmap: {lab} ({p.unit})"
                if self.info_label is not None:
                    self.info_label.setText(txt)
            except Exception:
                pass
            # Switch the displayed surface without clearing accumulated data
            self._ensure_surface(self.sweep.heatmap_ind)
            self.heatmap_data = self.param_surfaces[self.sweep.heatmap_ind]["data"]
            # Refresh the image to show the newly selected surface
            view_box = self.plot_item.getViewBox()
            view_range = view_box.viewRange()
            self.image_item.setImage(self.heatmap_data)

            # Re-apply coordinate transformation after setImage (critical for correct axis scaling)
            try:
                from PyQt5.QtCore import QRectF
                self.image_item.setRect(
                    QRectF(
                        self.sweep.in_start,
                        self.sweep.out_start,
                        self.sweep.in_stop - self.sweep.in_start,
                        self.sweep.out_stop - self.sweep.out_start,
                    )
                )
            except Exception:
                # Fallback: use transform if setRect fails
                try:
                    transform = pg.QtGui.QTransform()
                    transform.translate(self.pos[0], self.pos[1])
                    transform.scale(
                        (self.sweep.in_stop - self.sweep.in_start) / (self.res_in - 1),
                        (self.sweep.out_stop - self.sweep.out_start) / (self.res_out - 1)
                    )
                    self.image_item.setTransform(transform)
                except Exception:
                    pass

            # Update color levels for the newly selected parameter
            if self._auto_levels_enabled:
                try:
                    current_idx = self.sweep.heatmap_ind
                    finite = self.heatmap_data[np.isfinite(self.heatmap_data)]
                    if finite.size > 0:
                        lo, hi = np.nanpercentile(finite, [1, 99])
                        if hi > lo:
                            if self.hist_item is not None:
                                self.hist_item.setLevels(lo, hi)
                            else:
                                self.image_item.setLevels([lo, hi])
                        else:
                            stats = self.param_surfaces[current_idx]
                            if self.hist_item is not None:
                                self.hist_item.setLevels(stats["min"], stats["max"])
                            else:
                                self.image_item.setLevels([stats["min"], stats["max"]])
                    else:
                        stats = self.param_surfaces[current_idx]
                        if self.hist_item is not None:
                            self.hist_item.setLevels(stats["min"], stats["max"])
                        else:
                            self.image_item.setLevels([stats["min"], stats["max"]])
                except Exception:
                    pass

            # Restore view
            view_box.setRange(xRange=view_range[0], yRange=view_range[1], padding=0)

            # Mark as needing refresh to ensure display updates on Windows
            self.needs_refresh = True
        except Exception:
            pass

    def _reset_content(self):
        """Reset incoming queue and counters; keep accumulated surfaces."""
        try:
            self.data_to_add.clear()
            # Do not zero stored data; only reset per-row fallback counter
            self.count = 0
            self.needs_refresh = False
        except Exception:
            pass

    def _ensure_surface(self, param_index: int):
        """Ensure that a surface store exists for the given parameter index."""
        if param_index not in self.param_surfaces:
            # Create fresh 2D array and dict for this param
            arr = np.zeros((self.res_out, self.res_in))
            val_dict = {}
            for x_out in self.out_keys:
                val_dict[x_out] = {}
                for x_in in self.in_keys:
                    val_dict[x_out][x_in] = 0
            self.param_surfaces[param_index] = {
                "data": arr,
                "dict": val_dict,
                "min": float("inf"),
                "max": float("-inf"),
            }

    def _apply_colormap(self, name: str):
        """Apply selected colormap to image and histogram."""
        try:
            cmap = None
            try:
                cmap = pg.colormap.get(name)
            except Exception:
                pass

            if cmap is not None:
                # Apply to histogram if available (preferred)
                if self.hist_item is not None and hasattr(
                    self.hist_item, "setColorMap"
                ):
                    self.hist_item.setColorMap(cmap)
                # Also apply LUT to the image for consistency
                try:
                    lut = cmap.getLookupTable(alpha=False)
                    self.image_item.setLookupTable(lut)
                except Exception:
                    pass
            else:
                # Fallback: simple grayscale LUT
                lut = np.stack([np.linspace(0, 255, 256)] * 3, axis=1)
                self.image_item.setLookupTable(lut)
        except Exception:
            pass

    def _toggle_auto_levels(self, checked: bool):
        self._auto_levels_enabled = bool(checked)

    def _update_progress_widgets(self):
        if self.progress_bar is None:
            return

        state = getattr(self.sweep, "progressState", None)
        if state is None:
            return

        progress = getattr(state, "progress", None)
        if progress is None:
            self.progress_bar.setFormat("Progress: --")
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setFormat("Progress: %p%")
            progress_value = int(max(0.0, min(1.0, progress)) * 1000)
            self.progress_bar.setValue(progress_value)

        def _format_seconds(value):
            if value is None:
                return "--"
            try:
                if math.isinf(value):
                    return "∞"
            except TypeError:
                return "--"
            return f"{max(0.0, value):.1f} s"

        if self.elapsed_label is not None:
            self.elapsed_label.setText(
                f"Elapsed: {_format_seconds(state.time_elapsed)}"
            )
        if self.remaining_label is not None:
            self.remaining_label.setText(
                f"Remaining: {_format_seconds(state.time_remaining)}"
            )

    def _reset_view(self):
        try:
            if self.plot_item is not None:
                self.plot_item.enableAutoRange(x=True, y=True)
        except Exception:
            pass

    def clear(self):
        """Closes all active figures."""
        if self.figs_set:
            # Stop the update timer
            if self.update_timer is not None:
                self.update_timer.stop()
                self.update_timer = None

            self.figs_set = False
            self.needs_refresh = False
            if self.widget is not None:
                self.widget.close()
                self.widget = None
                self.layout_widget = None
                self.plot_item = None
                self.image_item = None
                self.hist_item = None
                self.heatmap_data = None
                self.heatmap_dict = {}
                self.out_keys = []
                self.in_keys = []
