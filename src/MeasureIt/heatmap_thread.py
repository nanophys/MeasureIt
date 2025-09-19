# heatmap_thread.py

from PyQt5.QtCore import QObject, pyqtSlot, QTimer
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QCheckBox,
    QPushButton,
)
from PyQt5.QtGui import QFont
import math
from collections import deque
import numpy as np
import pyqtgraph as pg

# Configure PyQtGraph for better performance
pg.setConfigOptions(
    antialias=False,  # Disable antialiasing for better performance
    useOpenGL=False,  # Don't use OpenGL - can cause issues
    crashWarning=True,  # Show warnings for debugging
)
pg.setConfigOption('background', 'w')  # White background
pg.setConfigOption('foreground', 'k')  # Black foreground


class Heatmap(QObject):
    """
    PyQtGraph-based heatmap plotter for Sweep2D.

    Provides high-performance real-time 2D visualization using PyQtGraph ImageView.
    Maintains the same API as the original matplotlib Heatmap class for compatibility.

    Attributes
    ---------
    sweep:
        The parent sweep object.
    data_to_add:
        Queue to store heatmap data updates.
    count:
        Used to index the current outer parameter.
    max_datapt:
        The maximum value of the measured parameter data.
    min_datapt:
        The minimum value of the measured parameter data.
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

    Methods
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
        """
        Initializes the PyQtGraph heatmap thread.

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
        self.count = 0
        self.max_datapt = float("-inf")
        self.min_datapt = float("inf")
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

        # Timer for regular heatmap updates (5 FPS)
        self.update_timer = None
        self.update_interval = update_interval  # milliseconds
        self.needs_refresh = False
        self.max_items_per_update = 10  # Process max 10 items per timer tick

        # UI controls
        self.cmap_box = None
        self.auto_levels_chk = None
        self._auto_levels_enabled = True

    def handle_close(self, event):
        """Handle widget close event."""
        self.clear()
        event.accept()

    def create_figs(self):
        """
        Creates the PyQtGraph heatmap figure for the 2D sweep.
        """
        try:
            if self.figs_set:
                return

            # First, determine the resolution on each axis
            self.res_in = math.ceil(abs((self.sweep.in_stop - self.sweep.in_start) / self.sweep.in_step)) + 1
            self.res_out = math.ceil(abs((self.sweep.out_stop - self.sweep.out_start) / self.sweep.out_step)) + 1

            # Create the heatmap data matrix - initially as all 0s
            self.heatmap_dict = {}
            self.out_keys = []
            self.in_keys = []
            self.out_step = self.sweep.out_step
            self.in_step = self.sweep.in_step

            for x_out in np.linspace(self.sweep.out_start, self.sweep.out_stop,
                                     int(abs(self.sweep.out_stop - self.sweep.out_start) / abs(self.sweep.out_step) + 1),
                                     endpoint=True):
                self.heatmap_dict[x_out] = {}
                self.out_keys.append(x_out)
                for x_in in np.linspace(self.sweep.in_start, self.sweep.in_stop,
                                        int(abs(self.sweep.in_stop - self.sweep.in_start) / abs(self.sweep.in_step) + 1),
                                        endpoint=True):
                    self.heatmap_dict[x_out][x_in] = 0
                    if x_in not in self.in_keys:
                        self.in_keys.append(x_in)

            self.out_keys = sorted(self.out_keys)
            self.in_keys = sorted(self.in_keys)

            # Initialize the heatmap data array
            self.heatmap_data = np.zeros((self.res_out, self.res_in))

            # Reset count for new sweep
            self.count = 0

            # Ensure a QApplication exists (safe in scripts and Jupyter when %gui qt is active)
            try:
                pg.mkQApp()
            except Exception:
                pass

            # Create main widget and layout
            self.widget = QWidget()
            self.widget.setWindowTitle('MeasureIt - 2D Heatmap')
            self.widget.resize(800, 600)

            main_layout = QVBoxLayout(self.widget)

            # Add parameter info label
            plot_para = self.sweep.in_sweep._params[self.sweep.heatmap_ind]
            info_label = QLabel(f"2D Heatmap: {plot_para.label} ({plot_para.unit})")
            info_label.setFont(QFont("Arial", 12))
            info_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 5px; }")
            main_layout.addWidget(info_label)

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
                'viridis', 'plasma', 'inferno', 'magma', 'cividis', 'turbo',
                'gray', 'grays', 'jet', 'hot', 'coolwarm'
            ]
            cmaps = [m for m in preferred if m in available_maps] or available_maps or ['viridis']
            for m in cmaps:
                self.cmap_box.addItem(m)
            self.cmap_box.setCurrentText('viridis' if 'viridis' in cmaps else cmaps[0])
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

            # Create GraphicsLayout with a PlotItem (left) and HistogramLUTItem (right)
            self.layout_widget = pg.GraphicsLayoutWidget()
            main_layout.addWidget(self.layout_widget)

            self.plot_item = self.layout_widget.addPlot(row=0, col=0)
            self.plot_item.setLabel('bottom', f'{self.sweep.in_param.label}', units=self.sweep.in_param.unit)
            self.plot_item.setLabel('left', f'{self.sweep.set_param.label}', units=self.sweep.set_param.unit)
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
            self.scale = [(self.sweep.in_stop - self.sweep.in_start) / self.res_in,
                          (self.sweep.out_stop - self.sweep.out_start) / self.res_out]

            # Set up the initial image with proper scaling
            self.image_item.setImage(self.heatmap_data)

            # Set the coordinate transformation for proper axis scaling
            transform = pg.QtGui.QTransform()
            try:
                transform.translate(self.pos[0], self.pos[1])
                transform.scale(self.scale[0], self.scale[1])
                self.image_item.setTransform(transform)
            except Exception:
                # Fallback: setRect if available (older/newer pyqtgraph versions)
                try:
                    from PyQt5.QtCore import QRectF
                    self.image_item.setRect(QRectF(self.pos[0], self.pos[1],
                                                   self.scale[0] * self.res_in,
                                                   self.scale[1] * self.res_out))
                except Exception:
                    pass

            # Connect close event
            self.widget.closeEvent = self.handle_close

            # Show the widget
            self.widget.show()

            # Start the update timer for regular heatmap refreshes
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_heatmap)
            self.update_timer.start(self.update_interval)

            # Apply initial colormap
            self._apply_colormap(self.cmap_box.currentText() if self.cmap_box is not None else 'viridis')

            self.figs_set = True

        except Exception as e:
            print(f"Error creating heatmap figures: {e}")
            import traceback
            traceback.print_exc()
            self.figs_set = False

    @pyqtSlot(dict)
    def add_data(self, data_dict):
        """
        Feeds the thread data dictionary to add to the heatmap.

        Parameters
        ---------
        data_dict:
            Dictionary containing 'forward' and 'backward' data tuples (x_data, y_data)
            from the plotter thread.
        """
        try:
            if data_dict is not None:
                self.data_to_add.append(data_dict)
        except Exception as e:
            print(f"Error in heatmap add_data: {e}")
            import traceback
            traceback.print_exc()

    def add_to_heatmap(self, data_dict):
        """
        Processes data dictionary for one complete inner sweep and updates heatmap data.

        Parameters
        ---------
        data_dict:
            Dictionary with 'forward' and 'backward' data tuples (x_data, y_data).
        """
        if 'forward' not in data_dict:
            return

        # Get the complete inner sweep data
        x_data, y_data = data_dict['forward']

        if len(x_data) == 0 or len(y_data) == 0:
            return

        # Remove NaN values
        valid_mask = ~(np.isnan(x_data) | np.isnan(y_data))
        x_clean = x_data[valid_mask]
        y_clean = y_data[valid_mask]

        if len(x_clean) == 0:
            return

        # Safety check for count
        if self.count >= len(self.out_keys):
            print(f"Warning: heatmap count {self.count} exceeds out_keys length {len(self.out_keys)}")
            return

        # Update the entire row for this outer parameter value
        current_out_key = self.out_keys[self.count]

        # Map inner sweep data to heatmap grid
        for x_val, y_val in zip(x_clean, y_clean):
            # Find closest in_key for this x value
            closest_in_key = min(self.in_keys, key=lambda k: abs(k - x_val))
            self.heatmap_dict[current_out_key][closest_in_key] = y_val

            # Track min/max values
            if y_val > self.max_datapt:
                self.max_datapt = y_val
            if y_val < self.min_datapt:
                self.min_datapt = y_val

        # Update the data array row
        row_idx = self.res_out - self.count - 1  # Flip for proper orientation
        for i, in_key in enumerate(self.in_keys):
            if i < self.res_in:
                self.heatmap_data[row_idx][i] = self.heatmap_dict[current_out_key][in_key]

        # Increment count for next outer sweep step
        self.count += 1
        self.needs_refresh = True

    def update_heatmap(self):
        """ Updates the heatmap with new data from the queue using batch processing. """

        if not self.figs_set:
            return

        # Process limited batch of data to prevent UI blocking
        items_processed = 0
        while len(self.data_to_add) > 0 and items_processed < self.max_items_per_update:
            data_dict = self.data_to_add.popleft()
            self.add_to_heatmap(data_dict)
            items_processed += 1
            self.needs_refresh = True

        # Update display with proper scaling while preserving view
        if self.image_item is not None and (self.needs_refresh or items_processed > 0):
            # Remember current view state
            view_box = self.plot_item.getViewBox()
            view_range = view_box.viewRange()

            # Update the image data
            self.image_item.setImage(self.heatmap_data)

            # Set color levels: auto or leave to user via histogram LUT
            if self._auto_levels_enabled and self.max_datapt > self.min_datapt:
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
                            if self.hist_item is not None:
                                self.hist_item.setLevels(self.min_datapt, self.max_datapt)
                            else:
                                self.image_item.setLevels([self.min_datapt, self.max_datapt])
                    else:
                        if self.hist_item is not None:
                            self.hist_item.setLevels(self.min_datapt, self.max_datapt)
                        else:
                            self.image_item.setLevels([self.min_datapt, self.max_datapt])
                except Exception:
                    # Last resort: use tracked min/max
                    if self.hist_item is not None:
                        self.hist_item.setLevels(self.min_datapt, self.max_datapt)
                    else:
                        self.image_item.setLevels([self.min_datapt, self.max_datapt])

            # Restore view range to preserve user zoom/pan
            view_box.setRange(xRange=view_range[0], yRange=view_range[1], padding=0)

            self.needs_refresh = False

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
                if self.hist_item is not None and hasattr(self.hist_item, 'setColorMap'):
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

    def _reset_view(self):
        try:
            if self.plot_item is not None:
                self.plot_item.enableAutoRange(x=True, y=True)
        except Exception:
            pass

    def clear(self):
        """ Closes all active figures. """
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
