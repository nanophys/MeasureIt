# heatmap_thread.py

from PyQt5.QtCore import QObject, pyqtSlot
import math
from collections import deque
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable


class Heatmap(QObject):
    """
    Thread to control the plotting for Sweep2D. 
    
    Gathers data from the RunnerThread. For Sweep2D, in addition to plotting
    the followed parameters against the set parameter, the heatmap thread 
    creates a 3D representation of the followed parameter against an inner
    and outer set parameter, using color to represent the third dimension.
    
    Attributes
    ---------
    sweep:
        The parent sweep object.
    lines_to_add:
        Stores Line2D objects to be added to the heatmap.
    count:
        Used to index the heatmap plotting dictionary.
    max_datapt:
        The maximum value of the 'set_param' data (y).
    min_datapt:
        The minimum value of the 'set_param' data (y).
    figs_set:
        Changes to true after figures have been created.
        
    Methods
    ---------
    create_figs()
        Creates the heatmap figure for Sweep2D.
    add_lines(lines)
        Adds Line2D objects to be plotted on the heatmap.
    add_to_plot(line)
        Plots the Line2D objects set to be added.
    update_data(x_out)
        Updates outer parameter data for all inner parameters. 
    update_heatmap()
        Prepares lines to be added for plotting.
    clear()
        Closes all active figures.
    """

    def __init__(self, sweep):
        """
        Initializes the thread. 
        
        Takes in the parent sweep and the figure information
        to use previously obtained plot if desired.
        """
        
        self.sweep = sweep
        # Datastructure to
        self.lines_to_add = deque([])
        self.count = 0
        self.max_datapt = float("-inf")
        self.min_datapt = float("inf")
        self.figs_set = False

        QObject.__init__(self)

    def create_figs(self):
        """ 
        Creates the heatmap figure for the 2D sweep. 
        
        If parent sweep has been previously plotted, this thread will use
        the previously created figures.
        """
        
        if self.figs_set is True:
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
                                 int(abs(self.sweep.out_stop - self.sweep.out_start) / abs(self.sweep.out_step) + 1),
                                 endpoint=True):
            self.heatmap_dict[x_out] = {}
            self.out_keys.add(x_out)
            for x_in in np.linspace(self.sweep.in_start, self.sweep.in_stop,
                                    int(abs(self.sweep.in_stop - self.sweep.in_start) / abs(self.sweep.in_step) + 1),
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

    @pyqtSlot(list)
    def add_lines(self, lines):
        """
        Feeds the thread Line2D objects to add to the heatmap.
        
        Parameters
        ---------
        lines:
            A  dictionary of Line2D objects (backwards and forwards) 
            to be added to the heatmap.
        """
        
        self.lines_to_add.append(lines)
        try:
            self.update_heatmap()
        except Exception as e:
            print("Failed to update the heatmap: ", e)
            
    def add_to_plot(self, line):
        """
        Plots forward Line2D objects from lines dictionary ('add_lines').
        
        Parameters
        ---------
        line:
            Set in 'update_heatmap' as the forward line to be added; each point
            of these lines represents two independent parameter values.
        """
        
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
        """ Updates outer parameter data for all inner parameters. """
        
        for i, x in enumerate(self.in_keys):
            self.heatmap_data[x_out][i] = self.heatmap_dict[self.out_keys[self.count]][x]

    def update_heatmap(self):
        """ Prepares lines to be added for plotting. """
        
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

    def clear(self):
        """ Closes all active figures. """
        plt.close(self.heat_fig)
        self.figs_set = False
