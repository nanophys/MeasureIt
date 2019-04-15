#threaded_sweeps.py

import time
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import qcodes as qc
from qcodes.dataset.measurements import Measurement
from qcodes.dataset.database import initialise_or_create_database_at
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from collections import deque


class BaseSweep(QObject):
    """
    This is the base class for the 0D (tracking) sweep class and the 1D sweep class. Each of these functions
    is used by both classes.
    """
    def __init__(self, set_param = None, inter_delay = 0.01, save_data = False, plot_data = True):
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
        self.set_param = set_param
        self.inter_delay = inter_delay
        self.save_data = save_data
        self.plot_data = plot_data
        
        self.is_running = False
        self.t0 = time.monotonic()
        
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
    
    
    def start(self):
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
            self.runner.add_plotter(self.plotter)
        
        # Flag that we are now running.
        self.is_running = True
        
        # Tells the threads to begin
        self.plotter.start()
        self.runner.start()
        
        
    def update_values(self, datasaver = None):
        """
        Iterates our data points, changing our setpoint if we are sweeping, and refreshing
        the values of all our followed parameters. If we are saving data, it happens here,
        and the data is returned.
        
        Arguments:
            datasaver (optional) - Data saving object-- usually an instance of Measurement.run()
                                   from a runner thread
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
            
        for i,p in enumerate(self._params):
            v = p.get()
            data.append((p, v))
    
        if self.save_data and self.is_running:
            datasaver.add_result(*data)
        
        return data
        


class Sweep0D(BaseSweep):
    """
    Class for the following/live plotting, i.e. "0-D sweep" class. As of now, is just an extension of
    BaseSweep, but has been separated for future convenience.
    """
    def __init__(self, runner = None, plotter = None, set_param = None, inter_delay = 0.01, save_data = False, plot_data = True):
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
    
    def __init__(self, set_param, start, stop, step, bidirectional = False, runner = None, plotter = None, 
                 inter_delay = 0.01, save_data = False, plot_data = True, complete_func = None):
        """
        Initializes the sweep. There are only 5 new arguments to read in.
        
        New arguments:
            set param - parameter to be swept
            start - value to start the sweep at
            stop - value to stop the sweep at
            step - step spacing for each measurement
            complete_func - optional function to be called when the sweep is finished
        """
        # Initialize the BaseSweep
        super().__init__(set_param=set_param, inter_delay=inter_delay, save_data=save_data)
        
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
        
        # Set the function to call when we are finished
        if complete_func == None:
            complete_func = self.no_change
        self.completed.connect(complete_func)
    
    
    def start(self):
        """
        Starts the sweep. Runs from the BaseSweep start() function.
        """
        print(f"Ramping {self.set_param.label} to {self.end} {self.set_param.unit}")
        print(self.setpoint)
        print(self.begin)
        print(self.end)
        print(self.step)
        super().start()
        
        
    def step_param(self):
        """
        Iterates the parameter.
        """
        # If we aren't at the end, keep going
        print(self.setpoint)
        
        if abs(self.setpoint - self.end) > abs(self.step/2):
            self.setpoint = self.setpoint + self.step
            self.set_param.set(self.setpoint)
            return (self.set_param, self.set_param.get())
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
    
    
    def ramp_to_zero(self):
        """
        Ramps the set_param to 0, at the same rate as already specified.
        """
        self.end = 0
        if self.setpoint - self.end > 0:
            self.step = (-1) * abs(self.step)
        else:
            self.step = abs(self.step)
        
        print(f'Ramping {self.set_param.label} to 0 . . . ')
        self.start()
    
    
    def set_complete_func(self, func):
        """
        Defines the function to call when finished.
        
        Arguments:
            func - function to call
        """
        self.completed.connect(func)
        
        
    def no_change(self):
        """
        This function is passed when we don't need to connect a function when the 
        sweep is completed.
        """
        pass
    
    
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
    
    def __init__(self, in_params, out_params, runner = None, plotter = None, 
                 inter_delay = 0.01, save_data = False, plot_data = True, complete_func = None):
        """
        Initializes the sweep. There are only 5 new arguments to read in.
        
        New arguments:
            set param - parameter to be swept
            start - value to start the sweep at
            stop - value to stop the sweep at
            step - step spacing for each measurement
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
        
        if (self.in_stop - self.in_start) > 0:
            self.in_step = abs(self.in_step)
        else:
            self.in_step = (-1) * abs(self.in_step)
            
        self.set_param = out_params[0]
        self.out_start = out_params[1]
        self.out_stop = out_params[2]
        self.out_step = out_params[3]
        
        if (self.out_stop - self.out_start) > 0:
            self.out_step = abs(self.out_step)
        else:
            self.out_step = (-1) * abs(self.out_step)
        
        # Initialize the BaseSweep
        super().__init__(self.set_param, inter_delay, save_data, plot_data)
        
        # Create the inner sweep object
        self.in_sweep = Sweep1D(self.in_param, self.in_start, self.in_stop, self.in_step, bidirectional=True,
                                inter_delay = self.inter_delay, save_data = self.save_data, plot_data = plot_data)
        self.in_sweep.follow_param(self.set_param)
        self.in_sweep.set_complete_func(self.update_values)
        
        self.runner = runner
        self.plotter = plotter
        self.direction = 0    
        
        # Set the function to call when we are finished
        if complete_func is None:
            complete_func = self.no_change
        self.completed.connect(complete_func)
        
        
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
                        self.in_sweep._params.append(l)
                    else:
                        self.in_sweep._params.append(param)
        
        
        def _create_measurement(self):
            self.meas = self.in_sweep._create_measurement()
            return self.meas
        
        
        def start(self):
            print(f"Starting the 2D Sweep. Ramping {self.set_param.label} to {self.end} {self.set_param.unit}, \
                  while sweeping {self.in_param.label} between {self.in_start} {self.in_param.unit} and \
                  {self.in_stop} {self.in_param.unit}")
            
            self.out_setpoint = self.out_start
            self.set_param.set(self.out_setpoint)
            
            self.in_sweep.start()
         
            
        def stop(self):
            self.is_running = False
            self.in_sweep.stop()
            
            
        def update_values(self):
            """
            Iterates the parameter.
            """
            # If we aren't at the end, keep going
            if abs(self.out_setpoint - self.out_stop) > abs(self.out_step/2):
                self.out_setpoint = self.out_setpoint + self.out_step
                printf(f"Setting {self.set_param.label} to {self.out_setpoint} {self.set_param.unit}")
                self.set_param.set(self.out_setpoint)
                self.in_sweep.plotter.reset()
                self.in_sweep.start()
            # If neither of the above are triggered, it means we are at the end of the sweep
            else:
                self.is_running = False
                print(f"Done with the sweep, {self.set_param.label}={self.setpoint}")
                self.completed.emit()
        
        
            
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
        # Check if we want to save the data
        if self.sweep.save_data is True:
            # Create the datasaver
            with self.sweep.meas.run() as datasaver:
                # Check if we are still running
                while self.sweep.is_running is True:
                    t = time.monotonic()
                    
                    # Get the new data
                    data = self.sweep.update_values(datasaver)
                    # Send it to the plotter if we are going
                    # Note: we check again if running, because we won't know if we are
                    # done until we try to step the parameter once more
                    if self.sweep.is_running is True and self.plotter is not None:
                        self.plotter.add_data_to_queue(data)
                    # Smart sleep, by checking if the whole process has taken longer than
                    # our sleep time
                    sleep_time = self.sweep.inter_delay - (time.monotonic() - t)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
        # Do the same thing, without saving the data
        else:    
            while self.sweep.is_running is True:  
                t = time.monotonic()
                
                data = self.sweep.update_values()
                if self.sweep.is_running is True and self.plotter is not None:
                    self.plotter.add_data_to_queue(data)
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
            
            
    def add_data_to_queue(self, data):
        """
        Grabs the data to plot.
        
        Arguments:
            data - list of tuples to plot
        """
        self.data_queue.append(data)
        
        
    def run(self):
        """
        Actual function to run, that controls the plotting of the data.
        """
        # Run while the sweep is running
        while self.sweep.is_running is True:
            t = time.monotonic()
            
            # Remove all the data points from the deque
            while len(self.data_queue) > 0:
                data = deque(self.data_queue.popleft())
                
                # Grab the time data 
                time_data = data.popleft()
                
                # Grab and plot the set_param if we are driving one
                if self.sweep.set_param is not None:
                    set_param_data = data.popleft()
                    # Plot as a function of time
                    self.setaxline.set_xdata(np.append(self.setaxline.get_xdata(), time_data[1]))
                    self.setaxline.set_ydata(np.append(self.setaxline.get_ydata(), set_param_data[1]))
                    self.setax.relim()
                    self.setax.autoscale_view()
                    
                # Now, grab the rest of the following param data
                for i,data_pair in enumerate(data):                
                    self.axesline[i][self.sweep.direction].set_xdata(np.append(self.axesline[i][self.sweep.direction].get_xdata(), time_data[1]))
                    self.axesline[i][self.sweep.direction].set_ydata(np.append(self.axesline[i][self.sweep.direction].get_ydata(), data_pair[1]))
                    self.axes[i].relim()
                    self.axes[i].autoscale_view()
    
            self.fig.tight_layout()
            self.fig.canvas.draw()
            # Smart sleep, by checking if the whole process has taken longer than
            # our sleep time
            sleep_time = self.sweep.inter_delay/2 - (time.monotonic() - t)
            if sleep_time > 0:
                time.sleep(sleep_time)


    def reset(self):
        """
        Resets all the plots
        """
        self.setaxline.set_xdata(np.array([]))
        self.setaxline.set_ydata(np.array([]))
        self.setax.relim()
        self.setax.autoscale_view()
        
        for i,p in enumerate(self.sweep._params):
            self.axes[i].set_xdata(np.array([]))
            self.axes[i].set_ydata(np.array([]))
            self.axes[i].relim()
            self.axes[i].autoscale_view()

    
    
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
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        