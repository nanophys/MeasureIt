# plotter_thread.py

import math
from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QObject, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

# Configure PyQtGraph for better performance
pg.setConfigOptions(
    antialias=False,  # Disable antialiasing for better performance
    useOpenGL=False,  # Don't use OpenGL - can cause issues
    crashWarning=True,  # Show warnings for debugging
)
pg.setConfigOption("background", "w")  # White background
pg.setConfigOption("foreground", "k")  # Black foreground


class Plotter(QObject):  # moved to _internal
    """PyQtGraph-based plotter for MeasureIt sweeps.

    Provides high-performance real-time plotting using PyQtGraph.

    Attributes:
    ---------
    sweep:
        Defines the specific parent sweep (Sweep1D, Sweep2D, etc.).
    data_queue:
        Double-ended queue to store data from Runner Thread.
    plot_bin:
        Determines the minimum amount of data to be stored in the queue.
    widget:
        Main QWidget containing the plot layout.
    layout_widget:
        PyQtGraph GraphicsLayoutWidget for organizing plots.
    plots:
        List of PlotWidget objects for each parameter.
    plot_items:
        Dictionary mapping parameters to their PlotDataItem objects.
    set_plot:
        PlotWidget for the set parameter vs time.
    set_plot_item:
        PlotDataItem for the set parameter.

    Methods:
    ---------
    create_figs()
        Creates PyQtGraph plot widgets for each parameter.
    add_data(data, direction)
        Slot to receive data from the Runner Thread.
    update_plots(force=False)
        Updates all plots with new data from the queue.
    handle_key_press(event)
        Handles keyboard shortcuts for sweep control.
    run()
        Creates figures if they have not already been set.
    reset()
        Resets all plots by clearing data.
    clear()
        Resets plots and closes the widget.
    """

    def __init__(self, sweep, plot_bin=1):
        """Initializes the PyQtGraph plotter.

        Parameters
        ---------
        sweep:
            Defines the specific parent sweep (Sweep1D, Sweep2D, etc.).
        plot_bin:
            Determines the minimum amount of data to be stored in the queue.
        """
        QObject.__init__(self)

        self.sweep = sweep
        self.data_queue = deque([])
        self.plot_bin = plot_bin
        self.finished = False
        self.last_pass = False
        self.figs_set = False
        self.kill_flag = False

        # PyQtGraph-specific attributes
        self.widget = None
        self.layout_widget = None
        self.plots = []
        self.plot_items = {}  # Maps parameters to (forward_item, backward_item)
        self.set_plot = None
        self.set_plot_item = None
        self.progress_bar = None
        self.elapsed_label = None
        self.remaining_label = None

        # Performance optimization: store data arrays for efficient updates
        # Use lists for fast appending, convert to numpy arrays only when plotting
        self.data_arrays = {}  # Maps parameters to {'forward': {'x': [], 'y': []}, 'backward': {'x': [], 'y': []}}
        self.set_data_arrays = {"x": [], "y": []}

    def handle_close(self, event):
        """Handle widget close event."""
        self.clear()
        event.accept()

    def key_pressed(self, event):
        """Handle keyboard shortcuts for sweep control.
        Legacy method name for compatibility.

        Parameters
        ---------
        event:
            Qt KeyEvent containing the pressed key.
        """
        self.handle_key_press(event)

    def handle_key_press(self, event):
        """Handle keyboard shortcuts for sweep control.

        Parameters
        ---------
        event:
            Qt KeyEvent containing the pressed key.
        """
        key = event.key()

        if key == pg.QtCore.Qt.Key_Space:
            self.sweep.flip_direction()
        elif key == pg.QtCore.Qt.Key_Escape:
            self.sweep.pause()
        elif key == pg.QtCore.Qt.Key_Return or key == pg.QtCore.Qt.Key_Enter:
            self.sweep.resume()

    @pyqtSlot(int)
    def add_break(self, direction):
        """Creates break in data by setting all parameters to have no assigned
        value simultaneously.

        Parameters
        ---------
        direction:
            The direction of the sweep (0 or 1).
        """
        break_data = [("time", np.nan)]
        if self.sweep.set_param is not None:
            break_data.append((self.sweep.set_param, np.nan))
        for p in self.sweep._params:
            break_data.append((p, np.nan))
        self.data_queue.append((break_data, direction))

    def create_figs(self):
        """Creates PyQtGraph plot widgets for each parameter."""
        if self.figs_set:
            print("figs already set. returning.")
            return

        self.figs_set = True
        num_plots = len(self.sweep._params)
        if self.sweep.set_param is not None:
            num_plots += 1

        # Calculate grid layout
        columns = math.ceil(math.sqrt(num_plots))
        rows = math.ceil(num_plots / columns)

        # Create main widget and layout
        self.widget = QWidget()
        self.widget.setWindowTitle("MeasureIt - Real-time Plots")
        self.widget.resize(1200, 800)

        main_layout = QVBoxLayout(self.widget)

        # Add keyboard shortcuts info
        info_label = QLabel(
            "Keyboard Shortcuts: ESC: pause | Enter: resume | Spacebar: flip direction"
        )
        info_label.setFont(QFont("Arial", 10))
        info_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 5px; }")
        main_layout.addWidget(info_label)

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
            self.update_progress_widgets()

        # Create PyQtGraph layout widget
        self.layout_widget = pg.GraphicsLayoutWidget()
        main_layout.addWidget(self.layout_widget)

        # Set up keyboard event handling
        self.widget.keyPressEvent = self.handle_key_press
        self.widget.setFocusPolicy(pg.QtCore.Qt.StrongFocus)

        self.plots = []
        self.plot_items = {}

        current_row = 0
        current_col = 0

        # Create set parameter plot (vs time) if we have one
        if self.sweep.set_param is not None:
            self.set_plot = self.layout_widget.addPlot(
                row=current_row,
                col=current_col,
                title=f"{self.sweep.set_param.label} vs Time",
            )
            self.set_plot.setLabel(
                "left", f"{self.sweep.set_param.label}", units=self.sweep.set_param.unit
            )
            self.set_plot.setLabel("bottom", "Time", units="s")
            self.set_plot.showGrid(x=True, y=True, alpha=0.3)

            # Create plot item for set parameter
            self.set_plot_item = self.set_plot.plot(pen=pg.mkPen(color="blue", width=2))

            current_col += 1
            if current_col >= columns:
                current_col = 0
                current_row += 1

        # Initialize data arrays for parameters
        for param in self.sweep._params:
            self.data_arrays[param] = {
                "forward": {"x": [], "y": []},
                "backward": {"x": [], "y": []},
            }

        # Create plots for followed parameters
        for i, param in enumerate(self.sweep._params):
            plot = self.layout_widget.addPlot(
                row=current_row,
                col=current_col,
                title=f"{param.label} vs {self.sweep.set_param.label if not self.sweep.x_axis else 'Time'}",
            )

            # Set axis labels
            plot.setLabel("left", f"{param.label}", units=param.unit)
            if self.sweep.x_axis:
                plot.setLabel("bottom", "Time", units="s")
            else:
                plot.setLabel(
                    "bottom",
                    f"{self.sweep.set_param.label}",
                    units=self.sweep.set_param.unit,
                )

            plot.showGrid(x=True, y=True, alpha=0.3)

            # Create forward and backward plot items
            forward_item = plot.plot(
                pen=pg.mkPen(color="blue", width=2), name="Forward"
            )
            backward_item = plot.plot(
                pen=pg.mkPen(color="red", width=2), name="Backward"
            )

            self.plots.append(plot)
            self.plot_items[param] = (forward_item, backward_item)

            current_col += 1
            if current_col >= columns:
                current_col = 0
                current_row += 1

        # Connect close event
        self.widget.closeEvent = self.handle_close

        # Show the widget
        self.widget.show()

    @pyqtSlot(object, int)
    def add_data(self, data, direction):
        """Receives data from the Runner Thread.

        Parameters
        ---------
        data:
            List of (parameter, value) tuples, or None if sweep is finished.
        direction:
            The direction of the sweep (0 or 1).
        """
        self.data_queue.append((data, direction))

        # Only update plots when we have enough data points or it's been a while
        # This prevents excessive update calls that slow down the plotting
        self.update_plots(force=data is None)

    @pyqtSlot(bool)
    def update_plots(self, force=False):
        """Updates all plots with new data from the queue.
        Optimized for high-frequency updates.

        Parameters
        ---------
        force:
            If True, process all queued data immediately.
        """
        if not self.figs_set:
            return

        # Check if we should update - either we have enough data or force is True
        if len(self.data_queue) < self.plot_bin and not force:
            return

        # Process all queued data at once for better performance
        while len(self.data_queue) > 0:
            temp = self.data_queue.popleft()
            if temp[0] is None:
                break
            data = deque(temp[0])
            direction = temp[1]

            # Get time data
            time_data = data.popleft()

            # Handle set parameter plot
            set_param_data = None
            if self.sweep.set_param is not None:
                set_param_data = data.popleft()

                # Add to set parameter data arrays
                # Ensure scalars by flattening any arrays
                time_val = time_data[1]
                if hasattr(time_val, "flatten"):
                    time_val = float(np.array(time_val).flatten()[0])

                set_val = set_param_data[1]
                if hasattr(set_val, "flatten"):
                    set_val = float(np.array(set_val).flatten()[0])

                self.set_data_arrays["x"].append(time_val)
                self.set_data_arrays["y"].append(set_val)

            # Determine x-axis data for followed parameters
            x_data_value = (
                time_data[1]
                if self.sweep.x_axis == 1
                else (
                    set_param_data[1]
                    if self.sweep.set_param is not None
                    else time_data[1]
                )
            )
            # Ensure x_data_value is scalar
            if hasattr(x_data_value, "flatten"):
                x_data_value = float(np.array(x_data_value).flatten()[0])

            # Add data to arrays for followed parameters
            for i, data_pair in enumerate(data):
                param = self.sweep._params[i]

                if param in self.data_arrays:
                    direction_key = "forward" if direction == 0 else "backward"

                    # Ensure y_data is scalar
                    y_value = data_pair[1]
                    if hasattr(y_value, "flatten"):
                        y_value = float(np.array(y_value).flatten()[0])

                    self.data_arrays[param][direction_key]["x"].append(x_data_value)
                    self.data_arrays[param][direction_key]["y"].append(y_value)

        # Now update all plots at once (much more efficient)
        self._update_plot_displays()
        self.update_progress_widgets()

    def _update_plot_displays(self):
        """Efficiently updates all plot displays using stored data arrays.
        Optimized for large datasets - converts to numpy arrays efficiently.
        """
        # Update set parameter plot
        if self.sweep.set_param is not None and self.set_plot_item is not None:
            if self.set_data_arrays["x"] and self.set_data_arrays["y"]:
                # Convert to numpy arrays for efficient plotting
                x_data = np.array(self.set_data_arrays["x"], dtype=np.float64)
                y_data = np.array(self.set_data_arrays["y"], dtype=np.float64)
                self.set_plot_item.setData(x_data, y_data)

        # Update followed parameter plots
        for param in self.sweep._params:
            if param in self.plot_items and param in self.data_arrays:
                forward_item, backward_item = self.plot_items[param]

                # Update forward direction
                forward_data = self.data_arrays[param]["forward"]
                if forward_data["x"] and forward_data["y"]:
                    x_data = np.array(forward_data["x"], dtype=np.float64)
                    y_data = np.array(forward_data["y"], dtype=np.float64)
                    forward_item.setData(x_data, y_data)

                # Update backward direction
                backward_data = self.data_arrays[param]["backward"]
                if backward_data["x"] and backward_data["y"]:
                    x_data = np.array(backward_data["x"], dtype=np.float64)
                    y_data = np.array(backward_data["y"], dtype=np.float64)
                    backward_item.setData(x_data, y_data)

    def update_progress_widgets(self):
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

    def get_plot_data(self, param_index):
        """Get x,y data arrays for a specific parameter.
        Used by Sweep2D for heatmap visualization.

        Parameters
        ---------
        param_index:
            Index of the parameter in self.sweep._params

        Returns:
        ---------
        dict or None:
            Dictionary with 'forward' and 'backward' data tuples (x_data, y_data)
            or None if parameter not found
        """
        if param_index < len(self.sweep._params):
            param = self.sweep._params[param_index]
            if param in self.plot_items:
                forward_item, backward_item = self.plot_items[param]

                # Get data arrays, handling None case
                forward_x = (
                    forward_item.xData
                    if forward_item.xData is not None
                    else np.array([])
                )
                forward_y = (
                    forward_item.yData
                    if forward_item.yData is not None
                    else np.array([])
                )
                backward_x = (
                    backward_item.xData
                    if backward_item.xData is not None
                    else np.array([])
                )
                backward_y = (
                    backward_item.yData
                    if backward_item.yData is not None
                    else np.array([])
                )

                return {
                    "forward": (forward_x, forward_y),
                    "backward": (backward_x, backward_y),
                }
        return None

    @pyqtSlot()
    def run(self):
        """Creates figures if they have not already been set."""
        if not self.figs_set:
            self.create_figs()

    @pyqtSlot()
    def reset(self):
        """Resets all plots by clearing data."""
        if not self.figs_set:
            return

        # Clear data arrays
        self.set_data_arrays = {"x": [], "y": []}
        for param in self.sweep._params:
            if param in self.data_arrays:
                self.data_arrays[param] = {
                    "forward": {"x": [], "y": []},
                    "backward": {"x": [], "y": []},
                }

        # Reset set parameter plot
        if self.set_plot_item is not None:
            self.set_plot_item.setData([], [])

        # Reset followed parameter plots
        for param in self.sweep._params:
            if param in self.plot_items:
                forward_item, backward_item = self.plot_items[param]
                forward_item.setData([], [])
                backward_item.setData([], [])

    def clear(self):
        """Resets plots and closes the widget."""
        if self.figs_set:
            self.reset()
            self.figs_set = False
            if self.widget is not None:
                self.widget.close()
                self.widget = None
                self.layout_widget = None
                self.plots = []
                self.plot_items = {}
                self.set_plot = None
                self.set_plot_item = None
