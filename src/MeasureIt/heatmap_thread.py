# heatmap_thread.py

from PyQt5.QtCore import QObject, pyqtSlot, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
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
    image_view:
        PyQtGraph ImageView widget for heatmap display.
    heatmap_data:
        2D numpy array containing the heatmap data.
    heatmap_dict:
        Dictionary mapping outer/inner parameter values to data.

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

    def __init__(self, sweep, update_interval=500):
        """
        Initializes the PyQtGraph heatmap thread.

        Parameters
        ---------
        sweep:
            The parent sweep object.
        update_interval:
            Update interval in milliseconds (default 500ms = 2 FPS).
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
        self.image_view = None
        self.heatmap_data = None
        self.heatmap_dict = {}
        self.out_keys = []
        self.in_keys = []

        # Timer for regular heatmap updates (2 FPS)
        self.update_timer = None
        self.update_interval = update_interval  # milliseconds

    def handle_close(self, event):
        """Handle widget close event."""
        self.clear()
        event.accept()

    def create_figs(self):
        """
        Creates the PyQtGraph heatmap figure for the 2D sweep.
        """

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

        # Create PyQtGraph ImageView with default functionality
        self.image_view = pg.ImageView()
        main_layout.addWidget(self.image_view)

        # Set up the initial image with proper scaling
        self.image_view.setImage(self.heatmap_data,
                                pos=[self.sweep.in_start, self.sweep.out_start],
                                scale=[(self.sweep.in_stop - self.sweep.in_start) / self.res_in,
                                       (self.sweep.out_stop - self.sweep.out_start) / self.res_out])

        # Set axis labels using the ImageView's internal PlotItem
        # Access the PlotItem through the ImageView structure
        try:
            view_box = self.image_view.getView()
            if hasattr(view_box, 'parent'):
                plot_item = view_box.parent()
                if hasattr(plot_item, 'setLabel'):
                    plot_item.setLabel('bottom', f'{self.sweep.in_param.label}', units=self.sweep.in_param.unit)
                    plot_item.setLabel('left', f'{self.sweep.set_param.label}', units=self.sweep.set_param.unit)
        except Exception as e:
            print(f"Could not set axis labels: {e}")
            # Continue without axis labels to preserve functionality

        # Connect close event
        self.widget.closeEvent = self.handle_close

        # Show the widget
        self.widget.show()

        # Start the update timer for regular heatmap refreshes
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_heatmap)
        self.update_timer.start(self.update_interval)

        self.figs_set = True

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
        self.data_to_add.append(data_dict)

    def add_to_heatmap(self, data_dict):
        """
        Processes data dictionary and updates heatmap data.

        Parameters
        ---------
        data_dict:
            Dictionary with 'forward' and 'backward' data tuples (x_data, y_data).
        """
        if 'forward' not in data_dict:
            return

        # Use forward data for heatmap (consistent with original)
        x_data, y_data = data_dict['forward']

        if len(x_data) == 0 or len(y_data) == 0:
            return

        # Remove NaN values
        valid_mask = ~(np.isnan(x_data) | np.isnan(y_data))
        x_clean = x_data[valid_mask]
        y_clean = y_data[valid_mask]

        if len(x_clean) == 0:
            return

        # Find the closest inner parameter key
        in_key = None
        min_distance = float('inf')
        for key in self.in_keys:
            distance = abs(x_clean[0] - key)
            if distance < min_distance:
                min_distance = distance
                in_key = key

        if in_key is None or min_distance > abs(self.in_step / 2):
            return

        start_pt = self.in_keys.index(in_key)

        # Update heatmap dictionary and track min/max values
        for i, (x, y) in enumerate(zip(x_clean, y_clean)):
            if start_pt + i < len(self.in_keys):
                self.heatmap_dict[self.out_keys[self.count]][self.in_keys[start_pt + i]] = y
                if y > self.max_datapt:
                    self.max_datapt = y
                if y < self.min_datapt:
                    self.min_datapt = y

        # Update the data array row
        row_idx = self.res_out - self.count - 1  # Flip for proper orientation
        for i, in_key in enumerate(self.in_keys):
            if i < self.res_in:
                self.heatmap_data[row_idx][i] = self.heatmap_dict[self.out_keys[self.count]][in_key]

        self.count += 1

    def update_heatmap(self):
        """ Updates the heatmap with new data from the queue. """

        if not self.figs_set:
            return

        # Process queued data
        while len(self.data_to_add) > 0:
            data_dict = self.data_to_add.popleft()
            self.add_to_heatmap(data_dict)

        # Update the ImageView with new data
        if self.image_view is not None:
            # Set the image with proper levels
            if self.max_datapt > self.min_datapt:
                self.image_view.setImage(self.heatmap_data,
                                       levels=[self.min_datapt, self.max_datapt],
                                       autoLevels=False)
            else:
                self.image_view.setImage(self.heatmap_data, autoLevels=True)

    def clear(self):
        """ Closes all active figures. """
        if self.figs_set:
            # Stop the update timer
            if self.update_timer is not None:
                self.update_timer.stop()
                self.update_timer = None

            self.figs_set = False
            if self.widget is not None:
                self.widget.close()
                self.widget = None
                self.image_view = None
                self.heatmap_data = None
                self.heatmap_dict = {}
                self.out_keys = []
                self.in_keys = []