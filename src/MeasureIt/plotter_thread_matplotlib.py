# plotter_thread.py

from PyQt5.QtCore import QObject, pyqtSlot
from collections import deque
import math
import numpy as np
import matplotlib
import matplotlib.pyplot as plt


class Plotter(QObject):
    """
    Controls the plotting of all sweeps parented by BaseSweep. 
    
    Gathers the data from the RunnerThread, creates evenly spaced figures
    based on the number of followed parameters, and plots the data as it
    is received.
    
    Attributes
    ---------
    sweep:
        Defines the specific parent sweep (Sweep1D, Sweep2D, etc.).
    data_queue:
        Double-ended queue to store data from Runner Thread.
    plot_bin:
        Determines the minimum amount of data to be stored in the queue.
    setaxline:
        Used to plot the set parameter vs. time.
    setax:
        Creates labels for the set parameter vs. time plot.
    axesline:
        Used to plot each followed parameter vs. the set parameter.
    axes:
        Creates labels and sizes axes for the followed vs. set parameter plots. 
        
    Methods
    ---------
    handle_close(evt)
        Resets all plots and closes figure window.
    key_pressed(event)
        Gives user the ability to pause, resume, or change direction of the sweep.
    add_break(direction)
        Sets no value to all parameters to create break in data.
    create_figs()
        Creates a figure containing subplots for each parameter in a new window.
    add_data(data, direction)
        Slot to receive data from the Runner Thread.
    update_plots(force=False)
        Pulls data from data queue in the order it was received and plots it.
    run()
        Creates figure if it has not already been made.
    reset()
        Resets all plots.
    clear()
        Resets the plots and closes the figure window.
    """

    def __init__(self, sweep, plot_bin=1, setaxline=None, setax=None, axesline=None, axes=[]):
        """
        Initializes the thread. 
        
        Takes in the parent sweep and optional figure information to use
        previously created plot if desired.
        
        Parameters
        ---------
        sweep:
            Defines the specific parent sweep (Sweep1D, Sweep2D, etc.).
        data_queue:
            Double-ended queue to store data from Runner Thread.
        plot_bin:
            Determines the minimum amount of data to be stored in the queue.
        setaxline:
            Used to plot the set parameter vs. time.
        setax:
            Creates labels for the set parameter vs. time plot.
        axesline:
            Used to plot each followed parameter vs. the set parameter.
        axes:
            Creates labels and sizes axes for the followed vs. set parameter plots. 
        *finished:
            Flag to raise alert when sweep is finished.
        *last_pass:
            Flag to raise alert during the last pass of the sweep.
        figs_set:
            Flag which is set to True after the figures have been created.
        kill_flag:
            Flag which will end the entire sweep when set to True.
            
        """
        QObject.__init__(self)

        self.sweep = sweep
        self.data_queue = deque([])
        self.setaxline = setaxline
        self.setax = setax
        self.axesline = axesline
        self.axes = axes
        self.finished = False
        self.last_pass = False
        self.figs_set = False
        self.kill_flag = False
        self.plot_bin = plot_bin

    def handle_close(self, evt):
        """ Resets all plots and closes figure window. """
        
        self.clear()

    def key_pressed(self, event):
        """
        Gives user the ability to pause, resume, or change direction
        of the sweep based on user input.
        
        Parameters
        ---------
        event:
            Accepts space, escape, and enter as arguments.
        """
        
        key = event.key

        if key == " ":
            self.sweep.flip_direction()
        elif key == "escape":
            self.sweep.stop()
        elif key == "enter":
            self.sweep.resume()

    @pyqtSlot(int)
    def add_break(self, direction):
        """
        Creates break in data by setting all parameters to have no assigned
        value simultaneously.
        
        Parameters
        ---------
        direction:
            Optional parameter to control the direction of the sweep. Accepts
            0 or 1 as arguments.
        """
        
        break_data = [('time', np.nan)]
        if self.sweep.set_param is not None:
            break_data.append((self.sweep.set_param, np.nan))
        for p in self.sweep._params:
            break_data.append((p, np.nan))
        self.data_queue.append((break_data, direction))

    def create_figs(self):
        """ Creates default figures for each of the parameters. """
        
        if self.figs_set is True:
            print("figs already set. returning.")
            return

        # print("creating figures")
        self.figs_set = True
        num_plots = len(self.sweep._params)
        if self.sweep.set_param is not None:
            num_plots += 1

        columns = math.ceil(math.sqrt(num_plots))
        rows = math.ceil(num_plots / columns)

        existing_fignums = plt.get_fignums()
        if len(existing_fignums) == 0:
            best_fignum = 1
        else:
            best_fignum = max(existing_fignums) + 1
        self.fig = plt.figure(num=best_fignum, figsize=(4 * columns + 1, 4 * rows + 1))
        self.fig.canvas.mpl_connect('close_event', self.handle_close)
        self.grid = plt.GridSpec(4 * rows + 1, columns, hspace=0.15)
        self.axes = []
        self.axesline = []

        # Creating the on-screen text for keyboard shortcuts
        text_ax = self.fig.add_subplot(self.grid[0, :])
        text_ax.axis('off')
        # text_ax.axes.get_xaxis().set_visible(False)
        # text_ax.axes.get_yaxis().set_visible(False)
        plt.text(0.5, 1, 'Keyboard Shortcuts', fontsize=20, ha='center')
        plt.text(0.5, 0.5, "esc: stop\tenter: resume\tspacebar: flip direction".replace("\t", "      "), fontsize=14,
                 ha='center')

        # Create the set_param plots 
        if self.sweep.set_param is not None:
            self.setax = self.fig.add_subplot(self.grid[1:4, 0])
            self.setax.set_xlabel('Time (s)')
            self.setax.set_ylabel(f'{self.sweep.set_param.label} ({self.sweep.set_param.unit})')
            self.setaxline = self.setax.plot([], [])[0]
            plt.grid(visible=True, which='major', color='0.5', linestyle='-')

        # Create the following params plots
        for i, p in enumerate(self.sweep._params):
            pos = i
            if self.sweep.set_param is not None:
                pos += 1

            row = int(pos / columns)
            col = pos % columns

            self.axes.append(self.fig.add_subplot(self.grid[4 * row + 1:4 * (row + 1), col]))
            # Create a plot of the sweeping parameters value against time
            if self.sweep.x_axis:
                self.axes[i].set_xlabel('Time (s)')
            else:
                self.axes[i].set_xlabel(f'{self.sweep.set_param.label} ({self.sweep.set_param.unit})')
            self.axes[i].set_ylabel(f'{p.label} ({p.unit})')
            forward_line = matplotlib.lines.Line2D([], [])
            forward_line.set_color('b')
            backward_line = matplotlib.lines.Line2D([], [])
            backward_line.set_color('r')
            self.axes[i].add_line(forward_line)
            self.axes[i].add_line(backward_line)
            self.axesline.append((forward_line, backward_line))
            plt.grid(visible=True, which='major', color='0.5', linestyle='-')

        plt.subplots_adjust(left=0.2, right=0.9, bottom=0.1, top=0.9, wspace=0.4, hspace=0.4)

        self.cid = self.fig.canvas.mpl_connect('key_press_event', self.key_pressed)

        self.fig.canvas.draw()
        plt.show(block=False)

    @pyqtSlot(list, int)
    def add_data(self, data, direction):
        """
        Receives the data from the Runner Thread.
        
        Parameters
        ---------
        data:
            Dictionary of parameters with their measured values.
        direction:
            The direction of the sweep.
        """
        
        self.data_queue.append((data, direction))
        self.update_plots()

    @pyqtSlot(bool)
    def update_plots(self, force=False):
        """
        Pulls data from the queue for plotting.
        
        Parameters
        ---------
        force:
            Set to true in order to completely clear the queue when the
            sweep is finished.
        """
        
        # Remove all the data points from the deque
        updates = 0

        if (len(self.data_queue) >= self.plot_bin or force is True) and self.figs_set is True:
            while len(self.data_queue) > 0:
                temp = self.data_queue.popleft()
                data = deque(temp[0])
                direction = temp[1]
                updates += 1

                # Grab the time data 
                time_data = data.popleft()

                # Grab and plot the set_param if we are driving one
                if self.sweep.set_param is not None:
                    set_param_data = data.popleft()
                    # Plot as a function of time
                    self.setaxline.set_xdata(np.append(self.setaxline.get_xdata(), time_data[1]))
                    self.setaxline.set_ydata(np.append(self.setaxline.get_ydata(), set_param_data[1]))
                    self.setax.relim()
                    self.setax.autoscale()

                x_data = 0
                if self.sweep.x_axis == 1:
                    x_data = time_data[1]
                elif self.sweep.x_axis == 0:
                    x_data = set_param_data[1]

                # Now, grab the rest of the following param data
                for i, data_pair in enumerate(data):
                    self.axesline[i][direction].set_xdata(np.append(self.axesline[i][direction].get_xdata(), x_data))
                    self.axesline[i][direction].set_ydata(
                        np.append(self.axesline[i][direction].get_ydata(), data_pair[1]))
                    self.axes[i].relim()
                    self.axes[i].autoscale()

            self.fig.canvas.draw()

    @pyqtSlot()
    def run(self):
        """ Creates figures if they have not already been set. """
        
        if self.figs_set is False:
            self.create_figs()

    @pyqtSlot()
    def reset(self):
        """ Resets all the plots. """
        
        if self.sweep.set_param is not None:
            self.setaxline.set_xdata(np.array([]))
            self.setaxline.set_ydata(np.array([]))
            self.setax.relim()
            self.setax.autoscale()

        for i, p in enumerate(self.axesline):
            self.axesline[i][0].set_xdata(np.array([]))
            self.axesline[i][0].set_ydata(np.array([]))
            self.axesline[i][1].set_xdata(np.array([]))
            self.axesline[i][1].set_ydata(np.array([]))
            self.axes[i].relim()
            self.axes[i].autoscale()

    def clear(self):
        """ Resets the plots and closes the figure window. """
        if self.figs_set is True:
            self.reset()
            self.figs_set = False
            matplotlib.pyplot.close(self.fig)

