# base_sweep.py
import importlib
import time
import json
from functools import partial
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from qcodes.dataset.measurements import Measurement
from qcodes import Station

from .runner_thread import RunnerThread
from .plotter_thread import Plotter
from .util import _autorange_srs, safe_get


class BaseSweep(QObject):
    """
    The parent class for the 0D, 1D and 2D sweep classes. 
    
    The default independent variable for BaseSweep and Sweep0D Measurements is time.
    Creating an object in a sweep class results in data acquisition and plotting of 
    all followed parameters individually measured against the independent variable. 
    The measured data is transferred in real-time (through QObject slot and signal 
    connections) from the Sweep classes to the Runner and Plotter Threads to organize, 
    save, and live-plot the tracked parameters.
    
    Attributes:
    -----------
    _params: 
        Defaults as blank list. Desired QCoDeS parameters should be added using 
        follow_param method.
    _srs: 
        Defaults as blank list. Used to incorporate lock-in amplifier with 
        measurement.
    set_param: 
        QCoDeS Parameter to be swept, defaults to None for 0D sweep.
    inter_delay: 
        Time (in seconds) to wait between data points.
    save_data: 
        Flag used to determine if the data should be saved or not.
    plot_data: 
        Flag to determine whether or not to live-plot data
    x_axis: 
        Defaults to 1 to set as time for 0D; defaults to 0 in 1D.
    meas: 
        Measurement class from QCoDeS, used to register and follow desired 
        parameters. Default is None until a measurement is created using 
        the create_measurement method.
    dataset: 
        Stores the data obtained during the measurement.
    continuous: 
        No effect on Sweep0D. Defaults to False for Sweep1D.
    plot_bin: 
        Defaults to 1. Used to plot data that has been sent to the 
        data_queue list in the Plotter Thread.
    is_running: 
        Flag to determine whether or not sweep is currently running.
    t0: 
         Set to monotonic time when creating Runner Thread.
    persist_data: 
        Always none except in Sweep2D, takes one set_param, allows sweeping of 2 parameters.
    datasaver: 
        Initiated by Runner Thread to enable saving and export of data.
    
    Methods
    ---------
    follow_param(*p)
        Adds QCoDes parameters from imported drivers to be tracked.            
    remove_param(*p)
        Removes parameters that have been assigned to be tracked.
    follow_srs(l, name, gain)
        Adds SRS lock-in amplifier to keep range consistent.
    create_measurement()
        Creates a QCoDeS Measurement Object
    stop()
        Stops/pauses the sweep.
    kill()
        Ends all threads and closes any active plots.
    check_running()
        Returns the status of the sweep.
    start(persist_data=None, ramp_to_start = False)
        Creates QCoDeS Measurement, Runner and Plotter Threads, and begins sweep.            
    resume()
        Restarts the sweep using the start method.            
    get_dataset()
        Retrieves collected data.
    receive_dataset(ds_dict)
        Slot to receive data in dictionary form, reemits received data.            
    update_values()
        Returns dictionary of updated [parameter:value] pairs, default parameter is time.       
    send_updates()
        Emits signal containing dictionary of parameter, setpoint, direction, and status.
        If running Sweep0D, will default to time at one second intervals.   
    clear_plot()
        Clears any displayed plots.            
    set_plot_bin(pb)
        Sets value for the Plotter Thread plot bin.   
    set_complete_func(func)
        Sets function to call when sweep is completed.            
    no_change(*args, **kwargs)
        Does nothing when sweep is completed.            
    check_params_are_correct()
        Compares the followed parameters to the previously created measurement parameters.            
    export_json(fn=None)
        Saves all sweep information, attributes, and parameters of QCoDeS Station as
        JSON dictionary.     
    import_json(json_dict, station=Station())
        Loads previously saved experimental setup.
    """
    
    update_signal = pyqtSignal(dict)
    dataset_signal = pyqtSignal(dict)
    reset_plot = pyqtSignal()
    add_break = pyqtSignal(int)
    completed = pyqtSignal()
    print_main = pyqtSignal(str)

    def __init__(self, set_param=None, inter_delay=0.1, save_data=True, plot_data=True, x_axis_time=1,
                 datasaver=None, complete_func=None, plot_bin=1, back_multiplier=1, suppress_output=False):
        """
        Initializer for both classes, called by BaseSweep.__init__() in Sweep0D and Sweep1D classes.
        
        Parameters:
        ---------
        _params: 
            Defaults as blank list. Desired QCoDeS parameters should be added using 
            follow_param method.
        _srs: 
            Defaults as blank list. Used to incorporate lock-in amplifier with 
            measurement.
        set_param: 
            QCoDeS Parameter to be swept, defaults to None for 0D sweep.
        inter_delay: 
            Time (in seconds) to wait between data points.
        save_data: 
            Flag used to determine if the data should be saved or not.
        plot_data: 
            Flag to determine whether or not to live-plot data
        x_axis: 
            Defaults to 1 to set as time for 0D; defaults to 0 in 1D.
        meas: 
            Measurement class from QCoDeS, used to register and follow desired 
            parameters. Default is None until a measurement is created using 
            the create_measurement method.
        dataset: 
            Stores the data obtained during the measurement.
        continuous: 
            No effect on Sweep0D. Defaults to False for Sweep1D.
        plot_bin: 
            Sets the number of data points taken between updates of the plot. Defaults to 1.
        is_running: 
            Flag to determine whether or not sweep is currently running.
        t0: 
             Set to monotonic time when creating Runner Thread.
        persist_data: 
            Always none except in Sweep2D, takes one set_param, allows sweeping of 2 parameters.
        datasaver: 
            Initiated by Runner Thread to enable saving and export of data.
            
        """
        QObject.__init__(self)

        self._params = []
        self._srs = []
        self.set_param = set_param
        if inter_delay is None or inter_delay < 0:
            inter_delay = 0
        self.inter_delay = inter_delay
        self.save_data = save_data
        self.plot_data = plot_data
        self.x_axis = x_axis_time
        self.back_multiplier = back_multiplier
        self.direction = 0
        self.meas = None
        self.dataset = None
        self.suppress_output = suppress_output

        self.continuous = False
        self.plot_bin = plot_bin

        self.is_running = False
        self.t0 = 0

        self.persist_data = None
        self.datasaver = datasaver

        # Set the function to call when we are finished
        self.complete_func = complete_func
        if complete_func is None:
            complete_func = self.no_change
        self.completed.connect(complete_func)

        self.print_main.connect(self.print_msg)

        self.plotter = None
        self.plotter_thread = None
        self.runner = None

    @classmethod
    def init_from_json(cls, fn, station):
        """ Initializes QCoDeS station from previously saved setup. """
        with open(fn) as json_file:
            data = json.load(json_file)
            return BaseSweep.import_json(data, station)

    def follow_param(self, *p):
        """
        Saves parameters to be tracked, for both saving and plotting data.
        
        The parameters must be followed before '_create_measurement()' is called.
        
        Parameters:
            *p: 
                Variable number of arguments, each of which must be a QCoDeS Parameter
                that is desired to be followed.
        """
        
        if self.is_running:
            self.print_main.emit("Cannot update the parameter list while the sweep is running.")

        for param in p:
            if isinstance(param, list):
                for l in param:
                    if l not in self._params:
                        self._params.append(l)
            else:
                if param not in self._params:
                    self._params.append(param)

    def remove_param(self, *p):
        """
        Removes parameters that were previously followed.
        
        Parameters:
            *p - Variable number of arguments, each of which must be a QCoDeS Parameter
                 that is currently being tracked.
        """
        
        if self.is_running:
            self.print_main.emit("Cannot update the parameter list while the sweep is running.")

        for param in p:
            if isinstance(param, list):
                for l in param:
                    self._params.remove(l)
            else:
                self._params.remove(param)

    def follow_srs(self, l, name, gain=1.0):
        """
        Adds an SRS lock-in to ensure that the range is kept correctly.
        
        Parameters:
            l:
                The lock-in instrument. 
            name:
                The name of the instrument to be followed.
            gain:
                The current gain value.
        """
        
        if self.is_running:
            self.print_main.emit("Cannot update the srs list while the sweep is running.")

        if (l, name, gain) not in self._srs:
            self._srs.append((l, name, gain))

    def _create_measurement(self):
        """
        Creates a QCoDeS Measurement object. 
        
        Controls the saving of data by registering QCoDeS Parameter objects.
        Registers all desired parameters to be followed. This function will 
        register only parameters that are followed BEFORE this function is
        called.
        
        Returns
        ---------
        The measurement object with the parameters to be followed.
        
        """

        # First, create time parameter
        self.meas = Measurement()

        # Check if we are 'setting' a parameter, and register it
        if self.set_param is not None:
            self.meas.register_parameter(self.set_param)
            self.meas.register_custom_parameter('time', label='time', unit='s', setpoints=(self.set_param,))
        else:
            self.meas.register_custom_parameter('time', label='time', unit='s')

            # Register all parameters we are following
        for p in self._params:
            if self.set_param is None:
                self.meas.register_parameter(p, setpoints=('time',))
            else:
                self.meas.register_parameter(p, setpoints=(self.set_param,))

        return self.meas

    def stop(self):
        """
        Stops/pauses the program from running by setting the is_running flag to false. 
        
        The is_running flag is checked in every thread's loop to determine whether or 
        not to continue running. When sweep is stopped, all data is updated a final time
        to ensure all completed measurements are stored.
        """
        
        if self.save_data and self.runner is not None:
            self.runner.flush_flag = True

        if not self.is_running:
            self.print_main.emit("Sweep not currently running. Nothing to stop.")
        self.is_running = False
        self.send_updates()

    def kill(self):
        """ Ends the threads spawned by the sweep and closes any active plots. """
        
        # Stop any data-taking
        self.is_running = False

        # Gently shut down the runner
        if self.runner is not None:
            self.runner.flush_flag = True
            self.runner.kill_flag = True
            #self.runner.quit()
            if not self.runner.wait(1000):
                self.runner.terminate()
                self.print_main.emit('forced runner to terminate')
            self.runner = None
            self.send_updates()
        # Gently shut down the plotter
        if self.plotter is not None:
            self.plotter_thread.quit()
            if not self.plotter_thread.wait(1000):
                self.plotter_thread.terminate()
                self.print_main.emit('forced plotter to terminate')
            self.close_plots()
            self.plotter = None

    def check_running(self):
        """ Returns the status of the sweep. """
        
        return self.is_running

    def start(self, persist_data=None, ramp_to_start=False):
        """
        Starts the sweep by creating and running the worker threads.
        
        Can be used to both start the program and unpause after calling 'stop()'.
        
        Parameters
        ---------
        persist_data:
            Optional argument which allows Sweep2D to sweep two paramters.
        ramp_to_start:
            Optional argument which gradually ramps each parameter to the starting
            point of its sweep. Default is true for Sweep1D and Sweep2D.
        """

        if self.is_running:
            self.print_main.emit("We are already running, can't start while running.")
            return

        # Check if we have a measurement object
        if self.meas is None:
            self._create_measurement()
        # Check if our list of parameters is out of date- meaning we started, stopped, updated params, and restarted
        elif not self.check_params_are_correct():
            self._create_measurement()
            if self.plotter is not None and self.plotter.figs_set is True:
                self.plotter.clear()
                # self.print_main.emit("reset figs")
                self.plotter.create_figs()

        # If we don't have a plotter yet want to plot, create it and the figures
        if self.plotter is None and self.plot_data is True:
            self.plotter = Plotter(self, self.plot_bin)
            self.plotter_thread = QThread()
            self.plotter.moveToThread(self.plotter_thread)
            self.plotter.create_figs()

            self.add_break.connect(self.plotter.add_break)
            self.reset_plot.connect(self.plotter.reset)

        # If we don't have a runner, create it and tell it of the plotter,
        # which is where it will send data to be plotted
        if self.runner is None:
            self.runner = RunnerThread(self)
            self.runner.get_dataset.connect(self.receive_dataset)
            self.t0 = time.monotonic()

            if self.plot_data is True:
                self.runner.add_plotter(self.plotter)

        # Flag that we are now running.
        self.is_running = True

        # Save persistent data from 2D sweep
        self.persist_data = persist_data

        # Tells the threads to begin
        if self.plot_data is True and self.plotter_thread.isRunning() is False:
            self.plotter_thread.start()
        elif self.plot_data is True and self.plotter.figs_set is False:
            # self.print_main.emit("somehow here")
            self.plotter.create_figs()
        if not self.runner.isRunning():
            self.runner.kill_flag = False
            self.runner.start()

    def resume(self):
        """ Restarts the sweep after it has been paused. """
        
        if self.is_running is False:
            self.start(ramp_to_start=False)
        self.send_updates(no_sp=True)

    def get_dataset(self):
        """ Returns the dataset object which contains the collected data. """

        return self.dataset

    @pyqtSlot(dict)
    def receive_dataset(self, ds_dict):
        """
        Connects the dataset of Runner Thread to the dataset object of the sweep.
        
        Parameters
        ---------
        ds_dict:
            Dataset dictionary passed between Runner Thread and sweep.
        """
        
        self.dataset = ds_dict
        self.dataset_signal.emit(ds_dict)

    def update_values(self):
        """
        Called as Runner Thread loops to update parameter values.
        
        Verifies the data to be updated depending on type of sweep.
        Iterates through data point intervals, assigning collected values to 
        their respective parameters. If data is to be saved, it happens here,
        and the updated data is emitted to all connected slots.
        
        Returns
        ---------
        data: 
            A dictionary of tuples with the updated data. Each tuple is of the format 
            (<QCoDeS Parameter>, measurement value). The tuples are passed in order of
            time, then set_param (if applicable), then all the followed params.
        """
        
        t = time.monotonic() - self.t0

        data = [('time', t)]

        if self.set_param is not None:
            sp_data = self.step_param()
            if sp_data is not None:
                data += sp_data
            else:
                return None

        persist_param = None
        if self.persist_data is not None:
            data.append(self.persist_data)
            persist_param = self.persist_data[0]

        for i, (l, _, gain) in enumerate(self._srs):
            _autorange_srs(l, 3)

        for i, p in enumerate(self._params):
            if p is not persist_param:
                v = safe_get(p)
                data.append((p, v))

        if self.save_data and self.is_running:
            self.runner.datasaver.add_result(*data)

        self.send_updates()

        return data

    def send_updates(self, no_sp=False):
        """
        Emits the signal after dictionary values are updated by 'update_values'.
        
        Parameters
        ---------
        no_sp:
            Represents a 'no setpoints' boolean. Default is False, when true it
            sets the setpoint key to None in the updated dictionary.
        """
        
        update_dict = {}
        if self.set_param is None:
            update_dict['set_param'] = 'time'
            update_dict['setpoint'] = time.monotonic() - self.t0
            update_dict['direction'] = 0
        else:
            update_dict['set_param'] = self.set_param
            if not no_sp:
                update_dict['setpoint'] = self.setpoint
            else:
                update_dict['setpoint'] = None
            update_dict['direction'] = self.direction
        update_dict['status'] = self.is_running

        self.update_signal.emit(update_dict)

    def reset_plots(self):
        """ Clears the currently displayed plots. """
        
        if self.plotter is not None:
            self.reset_plot.emit()

    def close_plots(self):
        """ Resets the plotter and closes all displayed plots. """

        if self.plotter is not None:
            self.plotter.clear()

    def set_plot_bin(self, pb):
        """
        Sets value for the Plotter Thread plot bin.
        
        Parameters
        ---------
        pb:
            Integer value which determines the amount of data to remain in 
            Plotter's data_queue while sweeping. The data queue is only 
            emptied completely when force is set to True in 'update_plots'.
        """
        
        self.plot_bin = pb
        if self.plotter is not None:
            self.plotter.plot_bin = pb

    def set_complete_func(self, func, *args, **kwargs):
        """
        Sets a function to be called whenever the sweep is finished.
        
        Connects to completed signal for Sweep0D, Sweep1D, and Sweep2D.
        
        Parameters
        ---------
        func:
            The function to be called upon completion of the sweep.
        *args:
            Arbitrary arguments to be passed to the callback function
        **kwargs:
            Arbitrary keyword arguments to be passed to the callback function
        """

        self.complete_func = partial(func, *args, **kwargs)
        self.completed.connect(self.complete_func)

    @pyqtSlot(str)
    def print_msg(self, msg):
        """
        Prints messages from the RunnerThread from the sweep, ensuring it is printed from the main thread

        Parameters
        ---------
        msg:
            The object to be printed
        """

        if self.suppress_output is False:
            print(msg)

    @pyqtSlot()
    def no_change(self, *args, **kwargs):
        """
        Passed when there is no function to be called on completion.
        
        Simply allows the sweep to end when 'complete_func' is set to None.
        """
        pass

    def check_params_are_correct(self):
        """
        Compares the followed parameters to the measurement parameters.
        
        Pulls paramaters from object _params, compares list to parameters
        found in QCoDeS measurement dictionary.
        
        Returns
        ---------
        Boolean value for whether or not each followed parameter is a QCoDeS
        parameter associated with the measurement instrument.
        """
        
        p_list = []
        meas_list = []
        # self.print_main.emit("our params list")
        for p in self._params:
            # self.print_main.emit(str(p))
            p_list.append(str(p))
        p_list.append("time")
        if self.set_param is not None:
            p_list.append(str(self.set_param))
        # self.print_main.emit("measurement param list")
        for key, val in self.meas.parameters.items():
            # self.print_main.emit(str(key))
            meas_list.append(key)

        return set(p_list) == set(meas_list)

    def export_json(self, fn=None):
        """
        Saves sweep attributes and parameters of QCoDeS Station as JSON dictionary.
        
        Called to save experimental setup to avoid repetitive setup of commonly
        used measurement instruments.
        
        Parameters
        ---------
        fn:
            Represents optional filename to be opened. A copy of the station
            information will be saved in this file.
            
        Returns
        ---------
        Dictionary containing all current instruments, parameters, and sweep 
        attributes.
        """
        
        json_dict = {}
        json_dict['class'] = str(self.__class__.__name__)
        json_dict['module'] = str(self.__class__.__module__)

        json_dict['attributes'] = {}
        json_dict['attributes']['inter_delay'] = self.inter_delay
        json_dict['attributes']['save_data'] = self.save_data
        json_dict['attributes']['plot_data'] = self.plot_data
        json_dict['attributes']['plot_bin'] = self.plot_bin

        if 'Sweep0D' in json_dict['class']:
            json_dict['set_param'] = None
            json_dict['attributes']['max_time'] = self.max_time
        elif 'Sweep1D' in json_dict['class']:
            json_dict['set_param'] = {}
            json_dict['set_param']['param'] = self.set_param.name
            json_dict['set_param']['instr_module'] = self.set_param.instrument.__class__.__module__
            json_dict['set_param']['instr_class'] = self.set_param.instrument.__class__.__name__
            json_dict['set_param']['instr_name'] = self.set_param.instrument.name
            json_dict['set_param']['start'] = self.begin
            json_dict['set_param']['stop'] = self.end
            json_dict['set_param']['step'] = self.step
            json_dict['attributes']['bidirectional'] = self.bidirectional
            json_dict['attributes']['continual'] = self.continuous
            json_dict['attributes']['x_axis_time'] = self.x_axis
        elif 'Sweep2D' in json_dict['class']:
            json_dict['attributes']['outer_delay'] = self.outer_delay
            json_dict['inner_sweep'] = {}
            json_dict['inner_sweep']['param'] = self.in_param.name
            json_dict['inner_sweep']['instr_module'] = self.in_param.instrument.__class__.__module__
            json_dict['inner_sweep']['instr_class'] = self.in_param.instrument.__class__.__name__
            json_dict['inner_sweep']['instr_name'] = self.in_param.instrument.name
            json_dict['inner_sweep']['start'] = self.in_start
            json_dict['inner_sweep']['stop'] = self.in_stop
            json_dict['inner_sweep']['step'] = self.in_step
            json_dict['outer_sweep'] = {}
            json_dict['outer_sweep']['param'] = self.set_param.name
            json_dict['outer_sweep']['instr_module'] = self.set_param.instrument.__class__.__module__
            json_dict['outer_sweep']['instr_class'] = self.set_param.instrument.__class__.__name__
            json_dict['outer_sweep']['instr_name'] = self.set_param.instrument.name
            json_dict['outer_sweep']['start'] = self.out_start
            json_dict['outer_sweep']['stop'] = self.out_stop
            json_dict['outer_sweep']['step'] = self.out_step
        elif 'SimulSweep' in json_dict['class']:
            json_dict['attributes']['bidirectional'] = self.bidirectional
            json_dict['attributes']['continual'] = self.continuous

            json_dict['set_params'] = {}
            for p, items in self.set_params_dict.items():
                json_dict['set_params'][p.name] = items
                json_dict['set_params'][p.name]['instr_module'] = p.instrument.__class__.__module__
                json_dict['set_params'][p.name]['instr_class'] = p.instrument.__class__.__name__
                json_dict['set_params'][p.name]['instr_name'] = p.instrument.name

        json_dict['follow_params'] = {}

        for p in self._params:
            json_dict['follow_params'][p.name] = (p.instrument.name, p.instrument.__class__.__module__,
                                                  p.instrument.__class__.__name__)

        if fn is not None:
            with open(fn, 'w') as outfile:
                json.dump(json_dict, outfile)

        return json_dict

    @classmethod
    def import_json(cls, json_dict, station=Station()):
        """
        Loads previously exported Station setup.
        
        Reassigns all dictionary values exported as JSON to their appropriate
        objects.
        """
        
        def load_parameter(name, instr_name, instr_type, station):
            if instr_name in station.components.keys():
                if isinstance(station.components[instr_name], instr_type):
                    return station.components[instr_name].parameters[name]

            for i_name, instr in station.components.items():
                if isinstance(instr, instr_type):
                    return instr.parameters[name]

        sweep_class = json_dict['class']
        sweep_module = json_dict['module']

        if 'Sweep1D' in sweep_class:
            sp = json_dict['set_param']

            module = importlib.import_module(sweep_module)
            sc = getattr(module, sweep_class)
            instr_module = importlib.import_module(sp['instr_module'])
            instrument = getattr(instr_module, sp['instr_class'])

            set_param = load_parameter(sp['param'], sp['instr_name'], instrument, station)
            sweep = sc(set_param, sp['start'], sp['stop'], sp['step'], **json_dict['attributes'])
        elif 'Sweep0D' in sweep_class:
            module = importlib.import_module(sweep_module)
            sc = getattr(module, sweep_class)
            sweep = sc(**json_dict['attributes'])
        elif 'Sweep2D' in sweep_class:
            module = importlib.import_module(sweep_module)
            sc = getattr(module, sweep_class)

            in_param = json_dict['inner_sweep']
            in_instr_module = importlib.import_module(in_param['instr_module'])
            in_instrument = getattr(in_instr_module, in_param['instr_class'])
            inner_param = load_parameter(in_param['param'], in_param['instr_name'], in_instrument, station)

            out_param = json_dict['outer_sweep']
            out_instr_module = importlib.import_module(out_param['instr_module'])
            out_instrument = getattr(out_instr_module, out_param['instr_class'])
            outer_param = load_parameter(out_param['param'], out_param['instr_name'], out_instrument, station)

            inner_list = [inner_param, in_param['start'], in_param['stop'], in_param['step']]
            outer_list = [outer_param, out_param['start'], out_param['stop'], out_param['step']]

            sweep = sc(inner_list, outer_list, **json_dict['attributes'])
        elif 'SimulSweep' in sweep_class:
            module = importlib.import_module(sweep_module)
            sc = getattr(module, sweep_class)

            set_params_dict = {}
            for p, items in json_dict['set_params'].items():
                instr_module = importlib.import_module(items['instr_module'])
                instrument = getattr(instr_module, items['instr_class'])

                param = load_parameter(p, items['instr_name'], instrument, station)
                set_params_dict[param] = {}
                set_params_dict[param]['start'] = items['start']
                set_params_dict[param]['stop'] = items['stop']
                set_params_dict[param]['step'] = items['step']

            sweep = sc(set_params_dict, **json_dict['attributes'])
        else:
            return

        for p, instr in json_dict['follow_params'].items():
            instr_module = importlib.import_module(instr[1])
            instrument = getattr(instr_module, instr[2])

            param = load_parameter(p, instr[0], instrument, station)
            sweep.follow_param(param)

        return sweep

    def estimate_time(self, verbose=True):
        """
        Returns an estimate of the amount of time the sweep will take to complete.

        Parameters
        ----------
        verbose:
            Controls whether the function will print out the estimate in the form hh:mm:ss (default True)

        Returns
        -------
        Time estimate for the sweep, in seconds
        """

        return 0

    def __del__(self):
        """ Deletes all child threads and closes all figures. """
        
        self.kill()
