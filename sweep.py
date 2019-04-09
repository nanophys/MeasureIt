import io
import time
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
from mpl_toolkits.axes_grid1 import make_axes_locatable
import qcodes as qc
from qcodes.dataset.measurements import Measurement
from IPython import display
from PyQt5.QtCore import QThread, pyqtSignal
import matplotlib.ticker as plticker

class Sweep1D(object):
    """
    Class to control sweeping along 1 parameter, while tracking multiple other parameters.
    It has functionality to live plot, or not, and one can create their own figures (e.g. in a GUI)
    or have the class create its own matplotlib figues. Follows QCoDeS data-taking methods.
    Adapted from Joe Finney's code.
    
    SR830s are not currently implemented.
    """
    
    def __init__(self, set_param, start, stop, step, freq, bidirectional=False, meas=None, plot=False, auto_figs=False):
        """
        Initializes the Sweep object. Takes in the parameter to be swept (set_param), the 
        value to start and stop sweeping at (start/stop, respectively), the step spacing (step),
        and the frequency of measurements. Can turn plotting off through 'plot', also tells 
        system whether to create it's own plots or use given ones through 'auto_figs'.
        """
        # Save our input variables
        self.set_param = set_param
        self.start = start
        self.stop = stop
        self.step = step
        
        if (self.stop - self.start) > 0:
            self.step = abs(self.step)
        else:
            self.step = (-1) * abs(self.step)
            
        self.inter_delay = 1/freq
        self.t0 = time.monotonic()
        self.setpoint = self.start - self.step
        self.bidirectional = bidirectional
        self.direction=0 #Forward
        
        d = (stop-start)/step*self.inter_delay
        h, m, s = int(d/3600), int(d/60) % 60, int(d) % 60
        print(f'Minimum duration: {h}h {m}m {s}s')
        
        # Either mark or save the measurement object
        if meas is not None:
            self.meas = meas
            
        # Saves our plotting flags
        self.plot = plot
        self.auto_figs = auto_figs
        # Sets a flag to ensure that the figures have been created before trying to plot
        self.figs_set = False
        self.pause = False
        self._sr830s = []
        self._params = []
    
    def follow_param(self, p):
        """
        This function takes in a QCoDeS Parameter p, and tracks it through each sweep.
        """
        self._params.append(p)

    def follow_sr830(self, l, name, gain=1.0):
        """
        This function adds an SR830, but (as of now) does not do anything with it.
        """
        self._sr830s.append((l, name, gain))

    def _create_measurement(self, *set_params):
        """
        Creates a QCoDeS Measurement object. This controls the saving of data by registering
        QCoDeS Parameter objects, which this function does. Registers all 'sweeping' parameters
        (set_params), and all 'tracked' parameters, 'self._params'. Returns the measurement
        object.
        """
        self.meas = Measurement()
        for p in set_params:
            self.meas.register_parameter(p)
        self.meas.register_custom_parameter('time', label='Time', unit='s')
        for p in self._params:
            self.meas.register_parameter(p, setpoints=(*set_params, 'time',))
        for l, _, _ in self._sr830s:
            self.meas.register_parameter(l.X, setpoints=(*set_params, 'time',))
            self.meas.register_parameter(l.Y, setpoints=(*set_params, 'time',))
            
        return self.meas
        
    def create_figs(self):
        """
        Creates default figures for each of the parameters. Plots them in a new, separate window.
        """
        self.fig = plt.figure(figsize=(4*(2 + len(self._params) + len(self._sr830s)),4))
        self.grid = plt.GridSpec(4, 1 + len(self._params) + len(self._sr830s), hspace=0)
        self.setax = self.fig.add_subplot(self.grid[:, 0])
        # First, create a plot of the sweeping parameters value against time
        self.setax.set_xlabel('Time (s)')
        self.setax.set_ylabel(f'{self.set_param.label} ({self.set_param.unit})')
        self.setaxline = self.setax.plot([], [])[0]
        
        self.plines = []
        self.axes = []
        # Now create a plot for every tracked parameter as a function of sweeping parameter
        for i, p in enumerate(self._params):
            self.axes.append(self.fig.add_subplot(self.grid[:, 1 + i]))
            self.axes[i].set_xlabel(f'{self.set_param.label} ({self.set_param.unit})')
            self.axes[i].set_ylabel(f'{p.label} ({p.unit})')
            
            forward_line = matplotlib.lines.Line2D([],[])
            forward_line.set_color('b')
            backward_line = matplotlib.lines.Line2D([],[])
            backward_line.set_color('r')
            self.axes[i].add_line(forward_line)
            self.axes[i].add_line(backward_line)
            self.plines.append((forward_line, backward_line))
            
        self.figs_set = True
            
    def set_figs(self, fig, setax, axes):
        """
        Give a figure and plots for both the sweeping parameter and the tracked parameters
        for the program to update. fig is of type matplotlib Figure, setax is a (sub)plot, 
        and axes is an array of subplots.
        """
        self.figs_set = True
        self.fig = fig
        self.setax = setax
        self.axes = axes
    
        # Initializes sweeping plot
        self.setax.set_xlabel('Time (s)')
        self.setax.set_ylabel(f'{self.set_param.label} ({self.set_param.unit})')
        self.setaxline = setax.plot([], [])[0]
        
        self.plines = []
        # Initializes tracking plots
        for i, p in enumerate(self._params):
            self.axes[i].set_xlabel(f'{self.set_param.label} ({self.set_param.unit})')
            self.axes[i].set_ylabel(f'{p.label} ({p.unit})')
            
            forward_line = matplotlib.lines.Line2D([],[])
            forward_line.set_color('b')
            backward_line = matplotlib.lines.Line2D([],[])
            backward_line.set_color('r')
            self.axes[i].add_line(forward_line)
            self.axes[i].add_line(backward_line)
            self.plines.append((forward_line, backward_line))
    
    def autorun(self, datasaver=None, persist_data=None):
        """
        Run a sweep through this class. Makes call to create_figs if needed.
        Calls self.iterate to move through each data point.
        """
        # Checks to see if it needs to generate its own figures
        if self.plot and self.auto_figs and not self.figs_set:
            self.create_figs()
        
        # If plots should have been set but are not, return 0
        if self.plot is True and self.figs_set is False:
            return 0
        
        # Run the loop
        if datasaver is None:
            with self.meas.run() as datasaver:
                # Check if we are within the stopping condition
                while abs(self.setpoint - self.stop) > abs(self.step/2):
                    self.iterate(datasaver)
                
                # If we want to go both ways, we flip the start and stop, and run again
                if self.bidirectional:
                    self.flip_direction()
                    while abs(self.setpoint - self.stop) > abs(self.step/2):
                        self.iterate(datasaver)
                    self.flip_direction()
        else:
            # Check if we are within the stopping condition
            while abs(self.setpoint - self.stop) > abs(self.step/2):
                self.iterate(datasaver, persist_data)
                
            # If we want to go both ways, we flip the start and stop, and run again
            if self.bidirectional:
                self.flip_direction()
                while abs(self.setpoint - self.stop) > abs(self.step/2):
                    self.iterate(datasaver, persist_data)
                self.flip_direction()
                
        return 1
            
    def iterate(self, datasaver=None, persist_data=None):
        """
        Runs one 'step' in the sweep. Takes in only the datasaver object, which is always
        a Measurement object's run() function (see autorun()). Iterate will update the 
        sweeping parameter, read each of the tracking parameters, and update the plots
        if plotting is enabled. Returns all values as a list of tuples, in the form of
        (parameter_name, parameter_value).
        """
        t = time.monotonic() - self.t0
        # Step the setpoint, and update the value
        self.setpoint = self.step + self.setpoint
        self.set_param.set(self.setpoint)
               
        # Update the sweeping parameter plot
        if self.plot is True:
            self.setaxline.set_xdata(np.append(self.setaxline.get_xdata(), t))
            self.setaxline.set_ydata(np.append(self.setaxline.get_ydata(), self.setpoint))
            self.setax.relim()
            self.setax.autoscale_view()
        
        # Pause if desired
        if self.inter_delay is not None:
            time.sleep(self.inter_delay)

        # Create our data storage object, which is a list of tuples of the parameter
        # and its value
        data = []
        if persist_data is not None:
            data.append(persist_data)
        data.append((self.set_param, self.setpoint))
        data.append(('time', t))
        
        
        # Loop through each of the tracking parameters
        for i, p in enumerate(self._params):
            # Update their values, and add them to the data object
            v = p.get()
            data.append((p, v))
            # Update each of the plots for the tracking parameters
            if self.plot is True:
                self.plines[i][self.direction].set_xdata(np.append(self.plines[i][self.direction].get_xdata(), self.setpoint))
                self.plines[i][self.direction].set_ydata(np.append(self.plines[i][self.direction].get_ydata(), v))
                self.axes[i].relim()
                self.axes[i].autoscale_view()
        
        # Add this point to the dataset
        if datasaver is not None:
            datasaver.add_result(*data)
        
        # Set the plots
        if self.plot is True:        
            self.fig.tight_layout()
            self.fig.canvas.draw()
            plt.pause(0.001)
            
        # Finally return all data
        return data
    
    def pause_run(self):
        self.pause = not self.pause
        
    def is_paused(self):
        return self.pause
        
    def ramp_to_zero(self):
        self.stop = 0
        if self.setpoint - self.step > 0:
            self.step = (-1) * abs(self.step)
        else:
            self.step = abs(self.step)
        
        print(f'Ramping {self.set_param.label} to 0 . . . ')
        while abs(self.setpoint - self.stop) > abs(self.step/2):
            self.iterate()
            
        self.set_param.set(0)
        print(f'Done ramping {self.set_param.label} to 0!')
        
    def flip_direction(self):
        """
        Flips the direction of the sweep, to do bidirectional sweeping.
        """
        temp = self.start
        self.start = self.stop
        self.stop = temp
        self.step = -1 * self.step
        self.setpoint -= self.step
        
        # If backwards, go forwards, and vice versa
        if self.direction:
            self.direction = 0
        else:
            self.direction = 1
    
    def reset(self, new_params=None):
        """
        Resets the Sweep1D to reuse the same object with the same plots.
        
        Arguments:
            new_params - list of 4 values to determine how we sweep. In order, 
                         must be [ start value, stop value, step, frequency ]
        """
        # Set our new values if desired
        if new_params is not None:
            self.start = new_params[0]
            self.stop = new_params[1]
            self.step = new_params[2]
            self.inter_delay = 1/new_params[3]

        # Reset our setpoint
        self.setpoint = self.start - self.step
        
        # Reset our plots
        if self.plot is True:
            self.setaxline.set_xdata(np.array([]))
            self.setaxline.set_ydata(np.array([]))
            self.setax.relim()
            self.setax.autoscale_view()
        
            for i, p in enumerate(self._params):    
                self.plines[i][0].set_xdata(np.array([]))
                self.plines[i][0].set_ydata(np.array([]))
                self.plines[i][1].set_xdata(np.array([]))
                self.plines[i][1].set_ydata(np.array([]))
                self.axes[i].relim()
                self.axes[i].autoscale_view()
        
    def get_measurement(self):
        """
        Returns the measurement object.
        """
        return self.meas
    
    def save(self):
        """
        Saves the plots as a png
        (may not work? untested)
        """
        b = io.BytesIO()
        self.fig.savefig(b, format='png')


class Sweep2D(object):
    
    def __init__(self, inner_sweep_parameters, outer_sweep_parameters, freq, follow_param):
        """
        We initialize our 2D sweep by taking in the parameters for each sweep, and the frequency.
        The inner_sweep_parameters and outer_sweep_parameters MUST be a list, conforming to the 
        following standard:
        
            [ <QCoDeS Parameter>, <start value>, <stop value>, <step size> ]
            
        Arguments: 
            inner_sweep_parameters - list conforming to above standard for the inner sweep
            outer_sweep_parameters - list conforming to above standard for the inner sweep
            freq - the frequency of measurement
            follow_param - the parameter to be tracked while other two are swept
        """
        
        # Ensure that the inputs were passed (at least somewhat) correctly
        if len(inner_sweep_parameters) != 4 or len(outer_sweep_parameters) != 4:
            raise TypeError('For 2D Sweep, must pass list of 4 object for each sweep parameter, \
                             in order: [ <QCoDeS Parameter>, <start value>, <stop value>, <step size> ]')
            
        # Save our input variables
        self.in_param = inner_sweep_parameters[0]
        self.in_start = inner_sweep_parameters[1]
        self.in_stop = inner_sweep_parameters[2]
        self.in_step = inner_sweep_parameters[3]
        
        if (self.in_stop - self.in_start) > 0:
            self.in_step = abs(self.in_step)
        else:
            self.in_step = (-1) * abs(self.in_step)
            
        self.out_param = outer_sweep_parameters[0]
        self.out_start = outer_sweep_parameters[1]
        self.out_stop = outer_sweep_parameters[2]
        self.out_step = outer_sweep_parameters[3]
        
        if (self.out_stop - self.out_start) > 0:
            self.out_step = abs(self.out_step)
        else:
            self.out_step = (-1) * abs(self.out_step)
        
        self.out_setpoint = self.out_start - self.out_step
        
        self.inter_delay = 1/freq
            
        # Sets a flag to ensure that the figures have been created before trying to plot
        self.figs_set = False
        self._params = []
        self._sr830s = []
        
        # Add the tracking parameter, and create the measurement
        self.follow_param(follow_param) 
        self.meas = self._create_measurement(self.out_param, self.in_param)
        
        # Create the inner sweep
        self.inner_sweep = Sweep1D(self.in_param, self.in_start, self.in_stop, self.in_step, freq, 
                                   meas=self.meas, bidirectional=True, plot=True, auto_figs=False)
        # Make sure the inner sweep knows what parameter it should be reading
        self.inner_sweep._params.append(follow_param)
        
        # Deal with creating the figures
        self.create_figs()
        self.inner_sweep.set_figs(self.fig, self.setax, self.axes)
        
        self.t0 = time.monotonic()
        # The origin of the plot is top left, we want it to be bottom left,
        # so we keep count of what number sweep we are at to put it into the
        # matrix backwards
        self.count = 0
        
        # We want to track the max and min values seen to autorange the heatmap
        self.max_datapt = float("-inf")
        self.min_datapt = float("inf")
        
        self.pause = False
    
    def autorun(self, update_rule=None):
        """
        Run the 2D Sweep. Creates the datasaver and passes it to the iterate function.
        Updates the plots, and then updates the inner sweep if desired.
        
        Arguments:
            update_rule - function to call, accepting the Sweep1D object as an argument,
                          to determine how the next inner sweep should behave
        """
        # If there is not an update_rule passed, then call our own no_change function
        # to run the same sweep again
        if update_rule is None:
            update_rule=self.no_change
            
        
        with self.meas.run() as datasaver:            
            # Loop until we are done
            while abs(self.out_setpoint - self.out_stop) > abs(self.out_step/2) and self.pause is False:
                self.iterate(datasaver)
                
                self.update_heatmap(self.count)
                
                update_rule(self.inner_sweep)
                self.count += 1
                
            datasaver.flush_data_to_database()
            # Make the plots persist after finishing plotting
            plt.show()
        
    def iterate(self, datasaver):
        """
        This function is one iteration of the outer sweep, which steps the outer parameter,
        and then runs the inner sweep.
        
        Arguments:
            datasaver - the Runner object created from calling Measurement.run()
        """
        # Step the setpoint, and update the value
        self.out_setpoint = self.out_step + self.out_setpoint
        self.out_param.set(self.out_setpoint)
        
        # Pause if desired
        if self.inter_delay is not None:
            time.sleep(self.inter_delay)
            
        # Create our data storage object, which is a list of tuples of the parameter
        # and its value
        data = (self.out_param, self.out_setpoint)
        
        # We pass to the inner sweep the datasaver, and pass it the information about
        # the outer sweep parameter
        self.inner_sweep.autorun(datasaver, data)
        
    def ramp_to_zero(self):
        """
        Ramps the parameter down to 0.
        """
        self.out_stop = 0
        if self.out_setpoint - self.out_step > 0:
            self.out_step = (-1) * abs(self.out_step)
        else:
            self.out_step = abs(self.out_step)
        
        self.inner_sweep.ramp_to_zero()
        
        print(f'Ramping {self.out_param.label} to 0 . . . ')
        
        while abs(self.out_setpoint - self.out_stop) > abs(self.out_step/2):
            # Step the setpoint, and update the value
            self.out_setpoint = self.out_step + self.out_setpoint
            self.out_param.set(self.out_setpoint)
    
            # Pause if desired
            if self.inter_delay is not None:
                time.sleep(self.inter_delay)
        
        print(f'Done ramping {self.out_param.label} to 0!')
    
    def pause_run(self):
        if self.pause is False:
            self.pause = True
        else:
            self.pause = False
        
    def create_figs(self):
        """
        Creates default figures for each of the parameters. Plots them in a new, separate window.
        Also creates a 2D heatmap of the data.
        """
        self.fig = plt.figure(figsize=(4*(2 + len(self._params) + len(self._sr830s)),4))
        self.grid = plt.GridSpec(4, 1 + len(self._params) + len(self._sr830s), hspace=0)
        self.setax = self.fig.add_subplot(self.grid[:, 0])
        # First, create a plot of the sweeping parameters value against time
        self.setax.set_xlabel('Time (s)')
        self.setax.set_ylabel(f'{self.in_param.label} ({self.in_param.unit})')
        self.setaxline = self.setax.plot([], [])[0]
        
        self.axes = []
        # Now create a plot for every tracked parameter as a function of sweeping parameter
        for i, p in enumerate(self._params):
            self.axes.append(self.fig.add_subplot(self.grid[:, 1 + i]))
            self.axes[i].set_xlabel(f'{self.in_param.label} ({self.in_param.unit})')
            self.axes[i].set_ylabel(f'{p.label} ({p.unit})')
            
        # Create the heatmap
        # First, determine the resolution on each axis
        self.res_in = abs(int((self.in_stop-self.in_start)/self.in_step))+1
        self.res_out = abs(int((self.out_stop-self.out_start)/self.out_step))+1
        
        self.heatmap_data = np.zeros((self.res_out, self.res_in))
        self.heat_fig = plt.figure(2)
        self.heatmap = plt.imshow(self.heatmap_data)
        ax = plt.gca()
        self.heat_ax = ax
        
        plt.ylabel(f'{self.out_param.label} ({self.out_param.unit})')
        plt.xlabel(f'{self.in_param.label} ({self.in_param.unit})')
        inner_tick_lbls = np.linspace(self.in_start, self.in_stop, 5)
        outer_tick_lbls = np.linspace(self.out_stop, self.out_start, 5)
        
        ax.set_xticks(np.linspace(0, self.res_in-1, 5))
        ax.set_yticks(np.linspace(0, self.res_out-1, 5))
        ax.set_xticklabels(inner_tick_lbls)
        ax.set_yticklabels(outer_tick_lbls)

        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="5%", pad=0.05)

        cbar = plt.colorbar(self.heatmap, cax=cax)
        cbar.set_label(f'{self._params[0].label} ({self._params[0].unit})')
        
        self.figs_set = True
       
    def update_heatmap(self, count):
        # GRAB THE X AND Y DATA HERE
        forward_line = self.axes[0].get_lines()[0]
        backward_line = self.axes[0].get_lines()[1]
        
        x_data_forward = forward_line.get_xdata()
        y_data_forward = forward_line.get_ydata()
        
        x_data_backward = backward_line.get_xdata()
        y_data_backward = backward_line.get_ydata()
        
        # ADD THE DATA TO THE HEATMAP
        for i,x in enumerate(x_data_forward):
            self.heatmap_data[self.res_out-count-1,i]=y_data_forward[i]
            if y_data_forward[i] > self.max_datapt:
                self.max_datapt = y_data_forward[i]
            if y_data_forward[i] < self.min_datapt:
                self.min_datapt = y_data_forward[i]
        
        self.heatmap.set_data(self.heatmap_data)
        self.heatmap.set_clim(self.min_datapt, self.max_datapt)
        self.heat_fig.canvas.draw()
        self.heat_fig.canvas.flush_events()
        
    def no_change(self, sweep):
        """
        This function is the default update_rule function. It simply runs the same sweep over again.
        """
        sweep.reset()
    
    def follow_param(self, p):
        """
        This function takes in a QCoDeS Parameter p, and tracks it through each sweep.
        """
        self._params.append(p)

    def follow_sr830(self, l, name, gain=1.0):
        """
        This function adds an SR830, but (as of now) does not do anything with it.
        """
        self._sr830s.append((l, name, gain))

    def _create_measurement(self, *set_params):
        """
        Creates a QCoDeS Measurement object. This controls the saving of data by registering
        QCoDeS Parameter objects, which this function does. Registers all 'sweeping' parameters
        (set_params), and all 'tracked' parameters, 'self._params'. Returns the measurement
        object.
        """
        self.meas = Measurement()
        for p in set_params:
            self.meas.register_parameter(p)
        self.meas.register_custom_parameter('time', label='Time', unit='s')
        for p in self._params:
            self.meas.register_parameter(p, setpoints=(*set_params, 'time',))
        for l, _, _ in self._sr830s:
            self.meas.register_parameter(l.X, setpoints=(*set_params, 'time',))
            self.meas.register_parameter(l.Y, setpoints=(*set_params, 'time',))
        
        return self.meas
        
    
class SweepThread(QThread):
    """
    SweepThread uses QThread to separate data taking from the GUI, in order to still run.
    Written specifically for use in Sweep1DWindow.
    """
    # Two distinct signals created - one when thread is completed, one when the
    # plots ought to be updated in the GUI
    completed = pyqtSignal()
    update_plot = pyqtSignal()
    
    def __init__(self, parent, s):
        """
        Initializes the thread. Takes in the parent (which is generally Sweep1DWindow), and the
        Sweep1D object which is to be used.
        """
        self.parent = parent
        self.s = s
        self.data = []
        QThread.__init__(self)
        # Connect our signals to the functions in Sweep1DWindow
        self.completed.connect(self.parent.thread_finished)
        self.update_plot.connect(lambda: self.parent.update_plot(self.data))
        
    def __del__(self):
        """
        Standard destructor.
        """
        self.wait()
        
    def run(self):
        """
        Function to run the thread, and thus the sweep.
        """
        with self.parent.meas.run() as datasaver:
            # Always check to ensure that we want to continue running, aka we haven't paused
            while self.parent.running is True: 
                # Iterate the sweep
                self.data = self.s.iterate(datasaver)
                # Tell our parent what the data is, and tell it to update the plot
                self.parent.curr_val = self.data[0][1]
                self.update_plot.emit()
                # Check to see if our break condition has been met.
                if abs(self.parent.curr_val - self.parent.v_end) <= abs(self.parent.v_step/2):
                    # See if we want to do a bidirectional scan
                    if self.s.bidirectional: 
                        self.s.flip_direction()
                    else:
                        self.completed.emit()
                        break

class SweepThreadGeneric(QThread):
    """
    SweepThread uses QThread to separate data taking from the GUI, in order to still run.
    Written specifically for use in Sweep1DWindow.
    """
    # One signal created for when thread is completed
    completed = pyqtSignal()
    
    def __init__(self, sweep, signal_finished_func, datasaver=None, update_func=None):
        """
        Initializes the thread. Takes in the parent (which is generally Sweep1DWindow), and the
        Sweep1D object which is to be used.
        """
        self.s = sweep
        self.ds = datasaver
        self.update_func = update_func
        
        QThread.__init__(self)
        # Connect our signals to the functions in Sweep1DWindow
        self.completed.connect(signal_finished_func)
        
    def __del__(self):
        """
        Standard destructor.
        """
        self.wait()
        
    def run(self):
        """
        Function to run the thread, and thus the sweep.
        """
        # Always check to ensure that we want to continue running, aka we haven't paused
        while self.s.is_paused() is False: 
            # Iterate the sweep
            data = self.s.iterate(datasaver)
            # Tell our parent what the data is, and tell it to update the plot
            if self.update_func is not None:
                self.update_func(data[0][1])
            
            # Check to see if our break condition has been met.
            if abs(self.s.setpoint - self.s.stop) <= abs(self.s.step/2):
                # See if we want to do a bidirectional scan
                if self.s.bidirectional: 
                    self.s.flip_direction()
                else:
                    self.completed.emit()
                    break

class FollowPlotParams(object):
    
    def __init__(self, params, inter_delay=0.01, save_data=False):
        self._params = []
        self.save_data = save_data
        self.inter_delay = inter_delay
        self.pause = False
        
        for p in params:
            self._params.append(p)
        
        if self.save_data:
            self._create_measurement()
        
        self.create_figs()
        self.t0 = time.monotonic()
        
    def _create_measurement(self):
        """
        Creates a QCoDeS Measurement object. This controls the saving of data by registering
        QCoDeS Parameter objects, which this function does. Registers all 'tracked' parameters, 
        Returns the measurement object.
        """
        
        self.meas.register_custom_parameter('time', label='Time', unit='s')
        for p in self._params:
            self.meas.register_parameter(p, setpoints=('time'))
            
        return self.meas
        
    def create_figs(self):
        """
        Creates default figures for each of the parameters. Plots them in a new, separate window.
        """
        
        self.fig = plt.figure(figsize=(4*(2 + len(self._params)),4))
        self.grid = plt.GridSpec(4, 1 + len(self._params), hspace=0)
        self.setax = []
        self.setaxline=[]
        
        for i, p in enumerate(self._params):
            self.setax.append(self.fig.add_subplot(self.grid[:, i]))
            # First, create a plot of the sweeping parameters value against time
            self.setax[i].set_xlabel('Time (s)')
            self.setax[i].set_ylabel(f'{p.label} ({p.unit})')
            self.setaxline.append(self.setax[i].plot([], [])[0])
            
    def pause_run(self):
        self.pause = not self.pause
        
    def is_paused(self):
        return self.pause
        
    def autorun(self):
        if self.save_data:
            datasaver = self.meas.run()
            
        while self.pause is False:
            t = time.monotonic() - self.t0
            
            data = []
            data.append(('time', t))
            
            for i,p in enumerate(self._params):
                v = p.get()
                data.append((p, v))
                
                self.setaxline[i].set_xdata(np.append(self.setaxline[i].get_xdata(), t))
                self.setaxline[i].set_ydata(np.append(self.setaxline[i].get_ydata(), v))
                self.setax[i].relim()
                self.setax[i].autoscale_view()
                self.setax[i].tight_layout()
                
            if self.save_data:
                datasaver.add_result(*data)
                
            plt.pause(self.inter_delay)
        
        
        
        
        



