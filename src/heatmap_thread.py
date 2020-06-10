# heatmap_thread.py

from PyQt5.QtCore import QThread
import math
from collections import deque
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable


class HeatmapThread(QThread):
    """
    Thread to control the plotting of a sweep of class BaseSweep. Gets the data
    from the RunnerThread to plot.
    """

    def __init__(self, sweep):
        """
        Initializes the thread. Takes in the parent sweep and the figure information if you want
        to use an already-created plot.
        
        Arguments:
            sweep - the parent sweep object
        """
        self.sweep = sweep
        # Datastructure to
        self.lines_to_add = deque([])
        self.count = 0
        self.max_datapt = float("-inf")
        self.min_datapt = float("inf")
        self.figs_set = False

        QThread.__init__(self)

    def __del__(self):
        """
        Standard destructor.
        """
        self.wait()

    def create_figs(self):
        """
        Creates the heatmap for the 2D sweep. Creates and initializes new plots
        """
        if self.figs_set == True:
            return

        # First, determine the resolution on each axis
        self.res_in = math.ceil(abs((self.sweep.in_stop - self.sweep.in_start) / self.sweep.in_step)) + 1
        self.res_out = math.ceil(abs((self.sweep.out_stop - self.sweep.out_start) / self.sweep.out_step)) + 1

        # Create the heatmap data matrix - initially as all 0s
        self.heatmap_dict = {}
        self.out_keys = set([])
        self.in_keys = set([])
        self.out_step = self.sweep.out_step
        self.in_step = self.sweep.in_step
        for x_out in np.linspace(self.sweep.out_start, self.sweep.out_stop,
                                 abs(self.sweep.out_stop - self.sweep.out_start) / self.sweep.out_step + 1,
                                 endpoint=True):
            self.heatmap_dict[x_out] = {}
            self.out_keys.add(x_out)
            for x_in in np.linspace(self.sweep.in_start, self.sweep.in_stop,
                                    abs(self.sweep.in_stop - self.sweep.in_start) / self.sweep.in_step + 1,
                                    endpoint=True):
                self.heatmap_dict[x_out][x_in] = 0
                self.in_keys.add(x_in)
        self.out_keys = sorted(self.out_keys)
        self.in_keys = sorted(self.in_keys)

        self.heatmap_data = np.zeros((self.res_out, self.res_in))
        # Create a figure
        self.heat_fig = plt.figure()
        # Use plt.imshow to actually plot the matrix
        self.heatmap = plt.imshow(self.heatmap_data)
        ax = plt.gca()
        self.heat_ax = ax

        # Set our axes and ticks
        plt.ylabel(f'{self.sweep.set_param.label} ({self.sweep.set_param.unit})')
        plt.xlabel(f'{self.sweep.in_param.label} ({self.sweep.in_param.unit})')
        inner_tick_lbls = np.linspace(self.sweep.in_start, self.sweep.in_stop, 5)
        outer_tick_lbls = np.linspace(self.sweep.out_stop, self.sweep.out_start, 5)

        ax.set_xticks(np.linspace(0, self.res_in - 1, 5))
        ax.set_yticks(np.linspace(0, self.res_out - 1, 5))
        ax.set_xticklabels(inner_tick_lbls)
        ax.set_yticklabels(outer_tick_lbls)

        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="5%", pad=0.05)

        # Create our colorbar scale
        cbar = plt.colorbar(self.heatmap, cax=cax)
        cbar.set_label(f'{self.sweep.in_sweep._params[1].label} ({self.sweep.in_sweep._params[1].unit})')

        self.figs_set = True

    def add_lines(self, lines):
        """
        Feed the thread Line2D objects to add to the heatmap.
        
        Arguments:
            lines - tuple of Line2D objects (backwards and forwards) to be added to heatmap
        """
        self.lines_to_add.append(lines)

    def add_to_plot(self, line):
        in_key = 0

        x_raw, y_raw = line.get_data()

        x_data = [i for i in x_raw if not math.isnan(i)]
        y_data = [i for i in y_raw if not math.isnan(i)]

        for key in self.in_keys:
            if abs(x_data[0] - key) < abs(self.in_step / 2):
                in_key = key

        start_pt = self.in_keys.index(in_key)

        for i, x in enumerate(x_data):
            self.heatmap_dict[self.out_keys[self.count]][self.in_keys[start_pt + i]] = y_data[i]
            if y_data[i] > self.max_datapt:
                self.max_datapt = y_data[i]
            if y_data[i] < self.min_datapt:
                self.min_datapt = y_data[i]
        self.update_data(self.res_out - self.count - 1)
        self.count += 1
        # print(f"called heatmap from thread: {QThread.currentThreadId()}")

    def update_data(self, x_out):
        for i, x in enumerate(self.in_keys):
            self.heatmap_data[x_out][i] = self.heatmap_dict[self.out_keys[self.count]][x]

    def run(self):
        # while self.sweep.is_running is True:
        #    t = time.monotonic()

        while len(self.lines_to_add) != 0:
            # Grab the lines to add
            line_pair = self.lines_to_add.popleft()

            forward_line = line_pair[0]
            backward_line = line_pair[1]

            self.add_to_plot(forward_line)

        # Refresh the image!
        self.heatmap.set_data(self.heatmap_data)
        self.heatmap.set_clim(self.min_datapt, self.max_datapt)
        self.heat_fig.canvas.draw()
        self.heat_fig.canvas.flush_events()

        # Smart sleep, by checking if the whole process has taken longer than
        # our sleep time
        #    sleep_time = self.sweep.inter_delay - (time.monotonic() - t)
        #    if sleep_time > 0:
        #        time.sleep(sleep_time)

    def run_dep(self):
        """
        Run function that executes the thread. This takes the lines that have been collected
        and adds them to the heatmap
        """
        while len(self.lines_to_add) != 0:
            # Grab the lines to add
            line_pair = self.lines_to_add.popleft()

            forward_line = line_pair[0]
            backward_line = line_pair[1]

            # Get our data
            x_data_forward = forward_line.get_xdata()
            y_data_forward = forward_line.get_ydata()

            x_data_backward = backward_line.get_xdata()
            y_data_backward = backward_line.get_ydata()

            # Add the data to the heatmap
            for i, x in enumerate(x_data_forward):
                # We need to keep track of where we are in the heatmap, so we use self.count
                # to make sure we are in the right row
                self.heatmap_data[self.res_out - self.count - 1, i] = y_data_forward[i]
                if y_data_forward[i] > self.max_datapt:
                    self.max_datapt = y_data_forward[i]
                if y_data_forward[i] < self.min_datapt:
                    self.min_datapt = y_data_forward[i]

            self.count += 1

        # Refresh the image!
        self.heatmap.set_data(self.heatmap_data)
        self.heatmap.set_clim(self.min_datapt, self.max_datapt)
        self.heat_fig.canvas.draw()
        self.heat_fig.canvas.flush_events()

    def clear(self):
        plt.close(self.heat_fig)
        self.figs_set = False
