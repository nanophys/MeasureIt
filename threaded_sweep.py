#threaded_sweeps.py

import time, math
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import qcodes as qc
from qcodes.dataset.measurements import Measurement
from qcodes.dataset.database import initialise_or_create_database_at
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from collections import deque
from mpl_toolkits.axes_grid1 import make_axes_locatable
from util import _autorange_srs


class BaseSweep(QObject):
    """
    This is the base class for the 0D (tracking) sweep class and the 1D sweep class. Each of these functions
    is used by both classes.
    """
    def __init__(self, set_param = None, inter_delay = 0.01, save_data = True, plot_data = True, x_axis=1, datasaver = None):
        """
        Initializer for both classes, called by super().__init__() in Sweep0D and Sweep1D classes.
        Simply initializes the variables and flags.
        
        Arguments:
            set_param - QCoDeS Parameter to be swept
            inter_delay - Time (in seconds) to wait between data points
            save_data - Flag used to determine if the data should be saved or not
            plot_data - Flag to determine if we should live-plot data
        """
        self._params = []
        self._srs = []
        self.set_param = set_param
        self.inter_delay = inter_delay
        self.save_data = save_data
        self.plot_data = plot_data
        self.x_axis = x_axis
        
        self.is_running = False
        self.t0 = time.monotonic()
        
        self.datasaver = datasaver
        
        QObject.__init__(self)
        
    def follow_param(self, *p):
        """
        This function saves parameters to be tracked, for both saving and plotting data.
        The parameters must be followed before '_create_measurement()' is called.
        
        Arguments:
            *p - Variable number of arguments, each of which must be a QCoDeS Parameter
                 that you want the sweep to follow
        """
        for param in p:
            if isinstance(param, list):
                for l in param:
                    self._params.append(l)
            else:
                self._params.append(param)
        
      
    def follow_srs(self, l, name, gain=1.0):
        """
        Adds an SRS lock-in to ensure that the range is kept correctly.
        
        Arguments:
            l - lockin instrument
            name - name of instrument
            gain - current gain value
        """
        self._srs.append((l, name, gain))
        
        
    def _create_measurement(self):
        """
        Creates a QCoDeS Measurement object. This controls the saving of data by registering
        QCoDeS Parameter objects, which this function does. Registers all 'tracked' parameters, 
        Returns the measurement object.
        This function will register only parameters that are followed BEFORE this function is
        called.
        """
        
        # First, create time parameter
        self.meas = Measurement()
        self.meas.register_custom_parameter('time', label='Time', unit='s')
        
        # Check if we are 'setting' a parameter, and register it
        if self.set_param is not None:
            self.meas.register_parameter(self.set_param)
        # Register all parameters we are following
        for p in self._params:
            self.meas.register_parameter(p)
            
        return self.meas
    
    
    def stop(self):
        """
        Stops/pauses the program from running by setting the 'is_running' flag to false. This is
        the flag that the children threads check in their loop to determine if they should
        continue running.
        """
        self.is_running = False
        
        
    def check_running(self):
        """
        Returns the status of the sweep.
        """
        return self.is_running
    
    
    def start(self, persist_data=None):
        """
        Starts the sweep by creating and running the worker threads. Used to both start the 
        program and unpause after calling 'stop()'
        """
        
        # If we don't have a plotter yet want to plot, create it and the figures
        if self.plotter is None and self.plot_data is True:
            self.plotter = PlotterThread(self)
            self.plotter.create_figs()
        
        # If we don't have a runner, create it and tell it of the plotter,
        # which is where it will send data to be plotted
        if self.runner is None:
            self.runner = RunnerThread(self)
            self.datasaver = self.runner.datasaver
            self.runner.add_plotter(self.plotter)
        
        # Flag that we are now running.
        self.is_running = True
        
        # Save persistent data from 2D sweep
        self.persist_data = persist_data
        
        # Tells the threads to begin
        self.plotter.start()
        self.runner.start()
        
        
    def update_values(self):
        """
        Iterates our data points, changing our setpoint if we are sweeping, and refreshing
        the values of all our followed parameters. If we are saving data, it happens here,
        and the data is returned.
        
        Returns:
            data - A list of tuples with the new data. Each tuple is of the format 
                   (<QCoDeS Parameter>, measurement value). The tuples are passed in order of
                   time, then set_param (if applicable), then all the followed params.
        """
        t = time.monotonic() - self.t0

        data = []
        data.append(('time', t))

        if self.set_param is not None:
            data.append(self.step_param())
        
        persist_param = None
        if self.persist_data is not None:
            data.append(self.persist_data)
            persist_param = self.persist_data[0]
        
        for i, (l, _, gain) in enumerate(self._srs):
            _autorange_srs(l, 3)
                    
        for i,p in enumerate(self._params):
            if p is not persist_param:
                v = p.get()
                data.append((p, v))
    
        if self.save_data and self.is_running:
            self.runner.datasaver.add_result(*data)
        
        return data
    
    
    def clear_plot(self):
        """
        Clears the currently showing plots.
        """
        self.plotter.reset()
        
    
    def no_change(self, *args):
        """
        This function is passed when we don't need to connect a function when the 
        sweep is completed.
        """
        pass
    
    
    def __del__(self):
        if self.datasaver is not None:
            self.datasaver.__exit__()
        


class Sweep0D(BaseSweep):
    """
    Class for the following/live plotting, i.e. "0-D sweep" class. As of now, is just an extension of
    BaseSweep, but has been separated for future convenience.
    """
    def __init__(self, runner = None, plotter = None, set_param = None, inter_delay = 0.01, save_data = True, plot_data = True):
        """
        Initialization class. Simply calls the BaseSweep initialization, and saves a few extra variables.
        
        Arguments (distinct from BaseSweep):
            runner - RunnerThread object, if prepared ahead of time, i.e. if a GUI is creating these first.
            plotter - PlotterThread object, passed if a GUI has plots it wants the thread to use instead
                      of creating it's own automatically.
        """
        super().__init__(set_param, inter_delay=inter_delay, save_data=save_data, plot_data=plot_data)
        
        self.runner = runner
        self.plotter = plotter
        # Direction variable, not used here, but kept to maintain consistency with Sweep1D.
        self.direction = 0
 
    
       
class Sweep1D(BaseSweep):
    """
    Class extending BaseSweep to sweep one parameter.
    """
    # Signal for when the sweep is completed
    completed = pyqtSignal()
    
    def __init__(self, set_param, start, stop, step, bidirectional = False, runner = None, plotter = None, datasaver = None,
                 inter_delay = 0.01, save_data = True, plot_data = True, complete_func = None, x_axis_time = 1):
        """
        Initializes the sweep. There are only 5 new arguments to read in.
        
        New arguments:
            set param - parameter to be swept
            start - value to start the sweep at
            stop - value to stop the sweep at
            step - step spacing for each measurement
            complete_func - optional function to be called when the sweep is finished
            x_axis_time - 1 for plotting parameters against time, 0 for set_param
        """
        # Initialize the BaseSweep
        super().__init__(set_param=set_param, inter_delay=inter_delay, save_data=save_data, x_axis=x_axis_time, datasaver=datasaver)
        
        self.begin = start
        self.end = stop
        self.step = step
        
        # Make sure the step is in the right direction
        if (self.end - self.begin) > 0:
            self.step = abs(self.step)
        else:
            self.step = (-1) * abs(self.step)
        
        self.setpoint = self.begin - self.step
        self.bidirectional = bidirectional
        self.runner = runner
        self.plotter = plotter
        self.direction = 0    
        self.is_ramping = False
        self.ramp_sweep = None
        
        # Set the function to call when we are finished
        if complete_func == None:
            complete_func = self.no_change
        self.completed.connect(complete_func)
    
    
    def start(self, persist_data=None, ramp_to_start=True, ramp_multiplier=1):
        """
        Starts the sweep. Runs from the BaseSweep start() function.
        """
        if self.is_ramping == True:
            print(f"Still ramping. Wait until ramp is done to start the sweep.")
            return
        if self.is_running == True:
            print(f"Sweep is already running.")
            return
        
        if ramp_to_start is True:
            print(f"Ramping to our starting setpoint value of {self.begin} {self.set_param.unit}")
            self.ramp_to(self.begin, start_on_finish=True, persist=persist_data, multiplier=ramp_multiplier)
        else:
            print(f"Sweeping {self.set_param.label} to {self.end} {self.set_param.unit}")
            super().start(persist_data)
        
    
    def stop(self):
        if self.is_ramping and self.ramp_sweep is not None:
            print(f"Stopping the ramp.")
            self.ramp_sweep.stop()
        super().stop()
        
        
    def step_param(self):
        """
        Iterates the parameter.
        """
        # If we aren't at the end, keep going
        if abs(self.setpoint - self.end) >= abs(self.step/2):
            self.setpoint = self.setpoint + self.step
            self.set_param.set(self.setpoint)
            return (self.set_param, self.setpoint)
        # If we want to go both ways, we flip the start and stop, and run again
        elif self.bidirectional and self.direction == 0:
            self.flip_direction()
            return self.step_param()
        # If neither of the above are triggered, it means we are at the end of the sweep
        else:
            self.is_running = False
            print(f"Done with the sweep, {self.set_param.label}={self.setpoint}")
            self.flip_direction()
            self.completed.emit()
            return (self.set_param, -1)
             
        
    def flip_direction(self):
        """
        Flips the direction of the sweep, to do bidirectional sweeping.
        """
        temp = self.begin
        self.begin = self.end
        self.end = temp
        self.step = -1 * self.step
        self.setpoint -= self.step
        
        # If backwards, go forwards, and vice versa
        if self.direction:
            self.direction = 0
        else:
            self.direction = 1
    
    
    def ramp_to(self, value, start_on_finish=False, persist=None, multiplier=1):
        """
        Ramps the set_param to a given value, at the same rate as already specified.
        
        Arguments:
            value - setpoint to ramp towards
            start_on_finish - flag if we want to begin the sweep as soon as we are done ramping
            multiplier - multiplier for the step size, to ramp quicker than the sweep speed
        """
        # Ensure we aren't currently running
        if self.is_ramping:
            print(f"Currently ramping. Finish current ramp before starting another.")
            return
        if self.is_running:
            print(f"Already running. Stop the sweep before ramping.")
            return
        
        # Check if we are already at the value
        curr_value = self.set_param.get()
        if abs(value - curr_value) <= self.step/2:
#            print(f"Already within {self.step} of the desired ramp value. Current value: {curr_value}, ramp setpoint: {value}.\nSetting our setpoint directly to the ramp value.")
            self.done_ramping(value, start_on_finish)
            return
        
        # Create a new sweep to ramp our outer parameter to zero
        self.ramp_sweep = Sweep1D(self.set_param, curr_value, value, multiplier*self.step, inter_delay = self.inter_delay, 
                             complete_func = lambda: self.done_ramping(value, start_on_finish, persist), save_data = False, plot_data = False)
        self.is_running = True
        self.is_ramping = True
        self.ramp_sweep.start(ramp_to_start=False)
        
        print(f'Ramping {self.set_param.label} to {value} . . . ')
        
        
    def ramp_to_zero(self):
        """
        Deprecated. Ramps the set_param to 0, at the same rate as already specified.
        """
        self.end = 0
        if self.setpoint - self.end > 0:
            self.step = (-1) * abs(self.step)
        else:
            self.step = abs(self.step)
        
        print(f'Ramping {self.set_param.label} to 0 . . . ')
        self.start()
    
    
    def done_ramping(self, value, start_on_finish=False, pd=None):
        self.is_ramping = False
        self.is_running = False
        print(f'Done ramping {self.set_param.label} to {value}')
        self.set_param.set(value)
        self.setpoint = value - self.step
        
        if start_on_finish == True:
            self.start(ramp_to_start=False, persist_data=pd)
        
        
    def get_param_setpoint(self):
        """
        Utility function to get the current value of the setpoint
        """
        return f'{self.set_param.label} = {self.set_param.get()} {self.set_param.unit}'
    
    
    def set_complete_func(self, func):
        """
        Defines the function to call when finished.
        
        Arguments:
            func - function to call
        """
        self.completed.connect(func)
    
    
    def reset(self, new_params=None):
        """
        Resets the Sweep1D to reuse the same object with the same plots.
        
        Arguments:
            new_params - list of 4 values to determine how we sweep. In order, 
                         must be [ start value, stop value, step, frequency ]
        """
        
        # Set our new values if desired
        if new_params is not None:
            self.begin = new_params[0]
            self.end = new_params[1]
            self.step = new_params[2]
            self.inter_delay = 1/new_params[3]

        # Reset our setpoint
        self.setpoint = self.begin - self.step
        
        # Reset our plots
        self.plotter = None
        self.runner = None
        
        
        
class Sweep2D(BaseSweep):
    """
    A 2-D Sweep of QCoDeS Parameters. This class runs by setting its outside parameter, then running
    an inner Sweep1D object, which handles all the saving of data and communications through the
    Thread objects. 
    """
    completed = pyqtSignal()
    
    def __init__(self, in_params, out_params, runner = None, plotter = None, inter_delay = 0.01, 
                 outer_delay = 1, save_data = True, plot_data = True, complete_func = None, update_func = None):
        """
        Initializes the sweep. It reads in the settings for each of the sweeps, as well
        as the standard BaseSweep arguments.
        
        The inner_sweep_parameters and outer_sweep_parameters MUST be a list, conforming to the 
        following standard:
        
            [ <QCoDeS Parameter>, <start value>, <stop value>, <step size> ]
            
        New arguments: 
            inner_sweep_parameters - list conforming to above standard for the inner sweep
            outer_sweep_parameters - list conforming to above standard for the inner sweep
            complete_func - optional function to be called when the sweep is finished
        """
        # Ensure that the inputs were passed (at least somewhat) correctly
        if len(in_params) != 4 or len(out_params) != 4:
            raise TypeError('For 2D Sweep, must pass list of 4 object for each sweep parameter, \
                             in order: [ <QCoDeS Parameter>, <start value>, <stop value>, <step size> ]')
            
        # Save our input variables
        self.in_param = in_params[0]
        self.in_start = in_params[1]
        self.in_stop = in_params[2]
        self.in_step = in_params[3]
        
        # Ensure that the step has the right sign
        if (self.in_stop - self.in_start) > 0:
            self.in_step = abs(self.in_step)
        else:
            self.in_step = (-1) * abs(self.in_step)
            
        self.set_param = out_params[0]
        self.out_start = out_params[1]
        self.out_stop = out_params[2]
        self.out_step = out_params[3]
        self.out_setpoint = self.out_start
        
        if (self.out_stop - self.out_start) > 0:
            self.out_step = abs(self.out_step)
        else:
            self.out_step = (-1) * abs(self.out_step)
        
        # Initialize the BaseSweep
        super().__init__(self.set_param, inter_delay, save_data, plot_data)
        
        # Create the inner sweep object
        self.in_sweep = Sweep1D(self.in_param, self.in_start, self.in_stop, self.in_step, bidirectional=True,
                                inter_delay = self.inter_delay, save_data = self.save_data, plot_data = plot_data)
        # We set our outer sweep parameter as a follow param for the inner sweep, so that
        # it is always read and saved with the rest of our data
        self.in_sweep.follow_param(self.set_param)
        # Our update_values() function iterates the outer sweep, so when the inner sweep
        # is done, call that function automatically
        self.in_sweep.set_complete_func(self.update_values)
        
        self.runner = runner
        self.plotter = plotter
        self.direction = 0    
        self.outer_delay = outer_delay
        
        # Flags for ramping to zero
        self.inner_ramp_to_zero = False
        self.outer_ramp_to_zero = False
        
        # Set the function to call when the 2D sweep is finished
        if complete_func is None:
            complete_func = self.no_change
        self.completed.connect(complete_func)
        # Set the fucntion to call when the inner sweep finishes
        if update_func is None:
            self.update_rule = self.no_change
        
        # Initialize our heatmap plotting thread
        self.heatmap_plotter = HeatmapThread(self)
        
        
    def follow_param(self, *p):
        """
        This function saves parameters to be tracked, for both saving and plotting data.
        Since the data saving is always handled by the inner Sweep1D object, we actually
        register all Parameters in the inner Sweep1D object.
        
        The parameters must be followed before '_create_measurement()' is called.
            
        Arguments:
            *p - Variable number of arguments, each of which must be a QCoDeS Parameter
                 or a list of QCoDeS Parameters that you want the sweep to follow
        """
        for param in p:
            if isinstance(param, list):
                for l in param:
                    self.in_sweep._params.append(l)
            else:
                self.in_sweep._params.append(param)
        
      
    def follow_srs(self, l, name, gain=1.0):
        """
        Adds an SRS lock-in to ensure that the range is kept correctly.
        
        Arguments:
            l - lockin instrument
            name - name of instrument
            gain - current gain value
        """
        self.in_sweep.follow_srs((l, name, gain))
        
        
    def _create_measurement(self):
        """
        Creates the measurement object for the sweep. Again, everything is actually run and saved
        through the Sweep1D object, so we create the measurement object from there.
        
        Returns:
            self.meas - the Measurement object that runs the sweep
        """
        self.meas = self.in_sweep._create_measurement()
        
        return self.meas
        
        
    def start(self):
        """
        Extends the start() function of BaseSweep(). We set our first outer sweep setpoint, then
        start the inner sweep, and let it control the run from there.
        """
        print(f"Starting the 2D Sweep. Ramping {self.set_param.label} to {self.out_stop} {self.set_param.unit}, while sweeping {self.in_param.label} between {self.in_start} {self.in_param.unit} and {self.in_stop} {self.in_param.unit}")
            
        self.set_param.set(self.out_setpoint)
        
        time.sleep(self.outer_delay)
        
        self.is_running = True
        self.in_sweep.start()
        self.heatmap_plotter.create_figs()
        self.heatmap_plotter.start()
        
        self.plotter = self.in_sweep.plotter
        self.runner = self.in_sweep.runner
     
            
    def stop(self):
        """
        Stops the sweeping of both the inner and outer sweep.
        """
        self.is_running = False
        self.in_sweep.stop()
            
            
    def update_values(self):
        """
        Iterates the outer parameter and then restarts the inner loop. We also check for our stop
        condition, and if it is reached, we emit our completed signal and stop running. This is
        the function attached to the finishing of the inner sweep, so it will be automatically called
        when our inner sweep is finished.
        """
        # If this function was called from a ramp down to 0, a special case of sweeping, deal with that
        # independently
        if self.in_sweep.is_ramping == True:
            # We are no longer ramping to zero
            
            self.inner_ramp_to_zero = False
            # Check if our outer ramp to zero is still going, and if not, then officially end
            # our ramping to zero
            if self.outer_ramp_to_zero == False:
                self.is_running = False
                self.inner_sweep.is_running = False
                print("Done ramping both parameters to zero")
            # Stop the function from running any further, as we don't want to check anything else
            return
        
        # Update our heatmap!
        lines = self.plotter.axes[2].get_lines()
        self.heatmap_plotter.add_lines(lines)
#        self.heatmap_plotter.start()
        
        # Check our update condition
        self.update_rule(self.in_sweep, lines)
#        self.in_sweep.ramp_to(self.in_sweep.begin, start_on_finish=False)
        
#        while self.in_sweep.is_ramping == True:
#            time.sleep(0.5)
        
        # If we aren't at the end, keep going
        if abs(self.out_setpoint - self.out_stop) >= abs(self.out_step/2):
            self.out_setpoint = self.out_setpoint + self.out_step
            time.sleep(self.outer_delay)
            print(f"Setting {self.set_param.label} to {self.out_setpoint} {self.set_param.unit}")
            self.set_param.set(self.out_setpoint)
            time.sleep(self.outer_delay)
            # Reset our plots
            self.in_sweep.plotter.reset()
            self.in_sweep.start(persist_data=(self.set_param, self.out_setpoint))
        # If neither of the above are triggered, it means we are at the end of the sweep
        else:
            self.is_running = False
            print(f"Done with the sweep, {self.set_param.label}={self.setpoint}")
            self.completed.emit()
    
    
    def get_param_setpoint(self):
        """
        Utility function to get the current value of the setpoint
        """
        s = f"{self.set_param.label} = {self.set_param.get()} {self.set_param.unit} \
        \n{self.inner_sweep.set_param.label} = {self.inner_sweep.set_param.get()} {self.inner_sweep.set_param.unit}"
        return s
    
    
    def set_update_rule(self, func):
        """
        Sets the update rule for in between inner sweeps, for example for peak tracking
        
        Arguments:
            func - function handle for update function. Must take in two arguments: the sweep to be updated,
                   and the previous data
        """
        self.update_rule = func
        
        
    def ramp_to_zero(self):
        """
        Ramp our set parameters down to zero.
        """
        # Ramp our inner sweep parameter to zero
        self.inner_ramp_to_zero = True
        self.in_sweep.ramp_to(0)
        
        # Check our step sign
        if self.out_setpoint > 0:
            self.out_step = (-1) * abs(self.out_step)
        else:
            self.out_step = abs(self.out_step)
        
        # Create a new sweep to ramp our outer parameter to zero
        zero_sweep = Sweep1D(self.set_param, self.setpoint, 0, self.step, inter_delay = self.inter_delay, complete_func = self.done_ramping_to_zero)
        self.is_running = True
        self.outer_ramp_to_zero = True
        zero_sweep.start()
        
        
    def done_ramping_to_zero(self):
        """
        Function called when our outer sweep parameter has finished ramping to zero. Checks if both parameters
        are done, then tells the system we have finished.
        """
        # Our outer parameter has finished ramping
        self.outer_ramp_to_zero = False
        # Check if our inner parameter has finished
        while self.in_sweep.is_ramping == True:
            time.sleep(0.5)
            
        # If so, tell the system we are done
        self.is_running = False
        print("Done ramping both parameters to zero")
    
                
            
class RunnerThread(QThread):
    """
    Class to separate to a new thread the communications with the instruments.
    """
    
    def __init__(self, sweep):
        """
        Initializes the object by taking in the parent sweep object, initializing the 
        plotter object, and calling the QThread initialization.
        
        Arguments:
            sweep - Object of type BaseSweep (or its children) that is controlling
                    this thread
        """
        self.sweep = sweep
        self.plotter = None
        self.datasaver = None
        self.db_set = False
        
        QThread.__init__(self)
        
        
    def __del__(self):
        """
        Standard destructor.
        """
        self.wait()
    
    
    def add_plotter(self, plotter):
        """
        Adds the PlotterThread object, so the Runner knows where to send the new
        data for plotting.
        
        Arguments:
            plotter - PlotterThread object, should be same plotter created by parent
                      sweep
        """
        self.plotter = plotter
        
        
    def _set_parent(self, sweep):
        """
        Function to tell the runner who the parent is, if created independently.
        
        Arguments:
            sweep - Object of type BaseSweep, that Runner will be taking data for
        """
        self.sweep = sweep
        
        
    def run(self):
        """
        Function that is called when new thread is created. NOTE: start() is called
        externally to start the thread, but run() defines the behavior of the thread.
        Iterates the sweep, then hands the data to the plotter for live plotting.
        """
        # Check database status
        if self.db_set == False and self.sweep.save_data == True:
            self.datasaver = self.sweep.meas.run().__enter__()
            
        # Check if we are still running
        while self.sweep.is_running is True:
            t = time.monotonic()
            
            # Get the new data
            data = self.sweep.update_values()
            # Send it to the plotter if we are going
            # Note: we check again if running, because we won't know if we are
            # done until we try to step the parameter once more
            if self.sweep.is_running is True and self.plotter is not None:
                self.plotter.add_data_to_queue(data, self.sweep.direction)
            # Smart sleep, by checking if the whole process has taken longer than
            # our sleep time
            sleep_time = self.sweep.inter_delay - (time.monotonic() - t)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    
    
class PlotterThread(QThread):
    """
    Thread to control the plotting of a sweep of class BaseSweep. Gets the data
    from the RunnerThread to plot.
    """
    def __init__(self, sweep, setaxline=None, setax=None, axesline=None, axes=[]):
        """
        Initializes the thread. Takes in the parent sweep and the figure information if you want
        to use an already-created plot.
        
        Arguments:
            sweep - the parent sweep object
            setaxline - optional argument (Line2D) for a plot that already exists that you want to use
            setax - optional argument of type subplot for the setaxes
            axesline - same as above for following params
            axes - same as above for following params
        """
        self.sweep = sweep
        self.data_queue = deque([])
        self.setaxline = setaxline
        self.setax = setax
        self.axesline = axesline
        self.axes = axes
        self.finished = False
        self.last_pass = False
        
        QThread.__init__(self)
        
        
    def __del__(self):
        """
        Standard destructor.
        """
        self.wait()
    
    
    def create_figs(self):
        """
        Creates default figures for each of the parameters. Plots them in a new, separate window.
        """
        self.fig = plt.figure(figsize=(4*(2 + len(self.sweep._params)),4))
        self.grid = plt.GridSpec(4, 1 + len(self.sweep._params), hspace=0)
        self.axes = []
        self.axesline=[]
        
        # Create the set_param plots 
        if self.sweep.set_param is not None:
            self.setax = self.fig.add_subplot(self.grid[:,0])
            self.setax.set_xlabel('Time (s)')
            self.setax.set_ylabel(f'{self.sweep.set_param.label} ({self.sweep.set_param.unit})')
            self.setaxline = self.setax.plot([], [])[0]
            
        # Create the following params plots
        for i, p in enumerate(self.sweep._params):
            pos = i
            if self.sweep.set_param is not None:
                pos += 1
            self.axes.append(self.fig.add_subplot(self.grid[:, pos]))
            # Create a plot of the sweeping parameters value against time
            self.axes[i].set_xlabel('Time (s)')
            self.axes[i].set_ylabel(f'{p.label} ({p.unit})')
            forward_line = matplotlib.lines.Line2D([],[])
            forward_line.set_color('b')
            backward_line = matplotlib.lines.Line2D([],[])
            backward_line.set_color('r')
            self.axes[i].add_line(forward_line)
            self.axes[i].add_line(backward_line)
            self.axesline.append((forward_line, backward_line))
            
            
    def add_data_to_queue(self, data, direction):
        """
        Grabs the data to plot.
        
        Arguments:
            data - list of tuples to plot
        """
        self.data_queue.append((data,direction))
        
        
    def run(self):
        """
        Actual function to run, that controls the plotting of the data.
        """
        # Run while the sweep is running
        while self.sweep.is_running is True:
            t = time.monotonic()
            
            # Remove all the data points from the deque
            while len(self.data_queue) > 0:
                temp = self.data_queue.popleft()
                data = deque(temp[0])
                direction = temp[1]
                
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
                
                x_data=0
                if self.sweep.x_axis == 1:
                    x_data = time_data[1]
                elif self.sweep.x_axis == 0:
                    x_data = set_param_data[1]
                    
                # Now, grab the rest of the following param data
                for i,data_pair in enumerate(data):                
                    self.axesline[i][direction].set_xdata(np.append(self.axesline[i][direction].get_xdata(), x_data))
                    self.axesline[i][direction].set_ydata(np.append(self.axesline[i][direction].get_ydata(), data_pair[1]))
                    self.axes[i].relim()
                    self.axes[i].autoscale()
    
            self.fig.tight_layout()
            self.fig.canvas.draw()
            
            # Smart sleep, by checking if the whole process has taken longer than
            # our sleep time
            sleep_time = self.sweep.inter_delay/4 - (time.monotonic() - t)
            if sleep_time > 0:
                time.sleep(sleep_time)
            if self.sweep.is_running is False:
                # Remove all the data points from the deque
                while len(self.data_queue) > 0:
                    temp = self.data_queue.popleft()
                    data = deque(temp[0])
                    direction = temp[1]
                
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
                
                    x_data=0
                    if self.sweep.x_axis == 1:
                        x_data = time_data[1]
                    elif self.sweep.x_axis == 0:
                        x_data = set_param_data[1]
                    
                    # Now, grab the rest of the following param data
                    for i,data_pair in enumerate(data):                
                        self.axesline[i][direction].set_xdata(np.append(self.axesline[i][direction].get_xdata(), x_data))
                        self.axesline[i][direction].set_ydata(np.append(self.axesline[i][direction].get_ydata(), data_pair[1]))
                        self.axes[i].relim()
                        self.axes[i].autoscale()
    
                self.fig.tight_layout()
                self.fig.canvas.draw()


    def reset(self):
        """
        Resets all the plots
        """
        if self.sweep.set_param is not None:
            self.setaxline.set_xdata(np.array([]))
            self.setaxline.set_ydata(np.array([]))
            self.setax.relim()
            self.setax.autoscale()
        
        for i,p in enumerate(self.sweep._params):
            self.axesline[i][0].set_xdata(np.array([]))
            self.axesline[i][0].set_ydata(np.array([]))
            self.axesline[i][1].set_xdata(np.array([]))
            self.axesline[i][1].set_ydata(np.array([]))
            self.axes[i].relim()
            self.axes[i].autoscale()



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
        self.res_in = math.ceil(abs((self.sweep.in_stop-self.sweep.in_start)/self.sweep.in_step))+1
        self.res_out = math.ceil(abs((self.sweep.out_stop-self.sweep.out_start)/self.sweep.out_step))+1
        
        # Create the heatmap data matrix - initially as all 0s
        self.heatmap_dict = {}
        self.out_keys = set([])
        self.in_keys = set([])
        self.out_step = self.sweep.out_step
        self.in_step = self.sweep.in_step
        for x_out in np.linspace(self.sweep.out_start, self.sweep.out_stop, 
                                 abs(self.sweep.out_stop-self.sweep.out_start)/self.sweep.out_step+1, endpoint=True):
            self.heatmap_dict[x_out]={}
            self.out_keys.add(x_out)
            for x_in in np.linspace(self.sweep.in_start, self.sweep.in_stop, 
                                 abs(self.sweep.in_stop-self.sweep.in_start)/self.sweep.in_step+1, endpoint=True):
                self.heatmap_dict[x_out][x_in]=0
                self.in_keys.add(x_in)   
        self.out_keys = sorted(self.out_keys)
        self.in_keys = sorted(self.in_keys)
        
        self.heatmap_data = np.zeros((self.res_out, self.res_in))
        # Create a figure
        self.heat_fig = plt.figure(2)
        # Use plt.imshow to actually plot the matrix
        self.heatmap = plt.imshow(self.heatmap_data)
        ax = plt.gca()
        self.heat_ax = ax
         
        # Set our axes and ticks
        plt.ylabel(f'{self.sweep.set_param.label} ({self.sweep.set_param.unit})')
        plt.xlabel(f'{self.sweep.in_param.label} ({self.sweep.in_param.unit})')
        inner_tick_lbls = np.linspace(self.sweep.in_start, self.sweep.in_stop, 5)
        outer_tick_lbls = np.linspace(self.sweep.out_stop, self.sweep.out_start, 5)
        
        ax.set_xticks(np.linspace(0, self.res_in-1, 5))
        ax.set_yticks(np.linspace(0, self.res_out-1, 5))
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
        in_key=0
        
        x_data, y_data = line.get_data()
        
        for key in self.in_keys:
            if abs(x_data[0] - key) < self.in_step/2:
                in_key = key
                
        start_pt = self.in_keys.index(in_key)
        
        for i,x in enumerate(x_data):
            self.heatmap_dict[self.out_keys[self.res_out-self.count-1]][self.in_keys[start_pt+i]]=y_data[i]
            if y_data[i] > self.max_datapt:
                self.max_datapt = y_data[i]
            if y_data[i] < self.min_datapt:
                self.min_datapt = y_data[i]
        self.update_data(self.res_out-self.count-1)
        
        
    def update_data(self, x_out):
        for i,x in enumerate(self.in_keys):
            self.heatmap_data[x_out][i]=self.heatmap_dict[x_out][x]
        
        
    def run(self):
        while self.sweep.is_running is True:
            t = time.monotonic()
            
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
            sleep_time = self.sweep.inter_delay - (time.monotonic() - t)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
        
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
            for i,x in enumerate(x_data_forward):
                # We need to keep track of where we are in the heatmap, so we use self.count
                # to make sure we are in the right row
                self.heatmap_data[self.res_out-self.count-1,i]=y_data_forward[i]
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
    
    
    
class SweepQueue(object):
    """
    SweepQueue is a modifieded double-ended queue (deque) object meant for continuously
    running different sweeps. 
    """
    def __init__(self):
        """
        Initializes the variables needed
        """
        self.queue = deque([])
        # Pointer to the sweep currently running
        self.current_sweep = None
        # Database information. Can be updated for each run.
        self.database = None
        self.exp_name = ""
        self.sample_name = ""
    
    
    def append(self, sweep : BaseSweep):
        """
        Adds a sweep to the queue.
        
        Arguments:
            sweep - BaseSweep object to be added to queue
        """
        # Set the finished signal to call the begin_next() function here
        sweep.set_complete_func(self.begin_next)
        # Add it to the queue
        self.queue.append(sweep)
        
        
    def start(self):
        """
        Starts the sweep. Takes the leftmost object in the queue and starts it.
        """
        # Check that there is something in the queue to run
        if len(self.queue) == 0:
            print("No sweeps loaded!")
            return
        
        print(f"Starting sweeps")
        self.current_sweep = self.queue.popleft()
        # Set the database info
        self.set_database()
        print(f"Starting sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} \
              {self.current_sweep.set_param.unit} to {self.current_sweep.end} {self.current_sweep.set_param.unit}")
        self.current_sweep.start()
        
        
    def begin_next(self):
        """
        Function called when one sweep is finished and we want to run the next sweep.
        Connected to completed pyqtSignals in the sweeps.
        """
        print(f"Finished sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} \
              {self.current_sweep.set_param.unit} to {self.current_sweep.end} {self.current_sweep.set_param.unit}")
        
        if len(self.queue) > 0:
            self.current_sweep = self.queue.popleft()
            self.set_database()
            print(f"Starting sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} \
                  {self.current_sweep.set_param.unit} to {self.current_sweep.end} {self.current_sweep.set_param.unit}")
            self.current_sweep.start()
        else:
            print("Finished all sweeps!")
    
    
    def load_database_info(self, db, exps, samples):
        """
        Loads in database info for each of the sweeps. Can take in either asingle value for each
        of the database, experiment name, and sample name arguments, or a list of values, with
        length equal to the number of sweeps loaded into the queue.
        
        Arguments:
            db - name of the database file you want to run at, either list or string
            exps - name of experiment you want, can either be list or string
            samples - name of sample, can be either list or string
        """
        # Check if db was loaded correctly
        if isinstance(db, list):
            # Convert to a deque for easier popping from the queue
            self.database = deque(db)
        elif isinstance(db, str):
            self.database = db
        else:
            print("Database info loaded incorrectly!")
            
        # Check again for experiments
        if isinstance(exps, list):
            self.exp_name = deque(exps)
        elif isinstance(exps, str):
            self.exp_name = exps
        else:
            print("Database info loaded incorrectly!")
            
        # Check if samples were loaded correctly
        if isinstance(samples, list):
            self.sample_name = deque(samples)
        elif isinstance(samples, str):
            self.sample_name = samples
        else:
            print("Database info loaded incorrectly!")
    
    
    def set_database(self):
        """
        Changes the database for the next run. Pops out the next item in a list, if that
        is what was loaded, or keeps the same string.
        """
        # Grab the next database file name
        db = ""
        if isinstance(self.database, str):
            db = self.database
        elif isinstance(self.database, deque):
            db = self.database.popleft()
            
        # Grab the next sample name
        sample = ""
        if isinstance(self.sample_name, str):
            sample = self.sample_name
        elif isinstance(self.sample_name, deque):
            sample = self.sample_name.popleft()
    
        # Grab the next experiment name
        exp = ""
        if isinstance(self.exp_name, str):
            exp = self.exp_name
        elif isinstance(self.exp_name, deque):
            exp = self.exp_name.popleft()
        
        # Initialize the database
        try:
            initialise_or_create_database_at('C:\\Users\\Nanouser\\Documents\\MeasureIt\\Databases\\' + db + '.db')
            qc.new_experiment(name=exp, sample_name=sample)
        except:
            print("Database info loaded incorrectly!")
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        