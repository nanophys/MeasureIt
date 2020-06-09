# base_sweep.py
import importlib
import time, json
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from qcodes.dataset.measurements import Measurement
from qcodes import Station
from src.runner_thread import RunnerThread
from src.plotter_thread import PlotterThread
from src.util import _autorange_srs
from qcodes.dataset.data_set import DataSet


class BaseSweep(QObject):
    """
    This is the base class for the 0D (tracking) sweep class and the 1D sweep class. Each of these functions
    is used by both classes.
    """
    update_signal = pyqtSignal(dict)
    dataset_signal = pyqtSignal(dict)

    def __init__(self, set_param=None, inter_delay=0.01, save_data=True, complete_func=None,
                 plot_data=True, x_axis_time=1, datasaver=None, parent=None, plot_bin=1):
        """
        Initializer for both classes, called by super().__init__() in Sweep0D and Sweep1D classes.
        Simply initializes the variables and flags.
        
        Arguments:
            set_param - QCoDeS Parameter to be swept
            inter_delay - Time (in seconds) to wait between data points
            save_data - Flag used to determine if the data should be saved or not
            plot_data - Flag to determine if we should live-plot data
        """
        super(QObject, self).__init__()
        self._params = []
        self._srs = []
        self.set_param = set_param
        if inter_delay is None or inter_delay < 0:
            inter_delay = 0
        self.inter_delay = inter_delay
        self.save_data = save_data
        self.plot_data = plot_data
        self.x_axis = x_axis_time
        self.meas = None
        self.dataset = None

        self.continuous = False
        self.plot_bin = plot_bin

        self.is_running = False
        self.t0 = 0

        self.datasaver = datasaver

        QObject.__init__(self)

    @classmethod
    def init_from_json(cls, fn, station):
        with open(fn) as json_file:
            data = json.load(json_file)
            return BaseSweep.import_json(data, station)

    def follow_param(self, *p):
        """
        This function saves parameters to be tracked, for both saving and plotting data.
        The parameters must be followed before '_create_measurement()' is called.
        
        Arguments:
            *p - Variable number of arguments, each of which must be a QCoDeS Parameter
                 that you want the sweep to follow
        """
        if self.is_running:
            print("Cannot update the parameter list while the sweep is running.")

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
        This function removes parameters to be tracked, for both saving and plotting data.
        The parameters must be followed before '_create_measurement()' is called.
        
        Arguments:
            *p - Variable number of arguments, each of which must be a QCoDeS Parameter
                 that you want the sweep to remove from its list
        """
        if self.is_running:
            print("Cannot update the parameter list while the sweep is running.")

        for param in p:
            if isinstance(param, list):
                for l in param:
                    self._params.remove(l)
            else:
                self._params.remove(param)

    def follow_srs(self, l, name, gain=1.0):
        """
        Adds an SRS lock-in to ensure that the range is kept correctly.
        
        Arguments:
            l - lockin instrument
            name - name of instrument
            gain - current gain value
        """
        if self.is_running:
            print("Cannot update the srs list while the sweep is running.")

        if (l, name, gain) not in self._srs:
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
        Stops/pauses the program from running by setting the 'is_running' flag to false. This is
        the flag that the children threads check in their loop to determine if they should
        continue running.
        """
        if self.save_data and self.runner is not None:
            self.runner.flush_flag = True

        if not self.is_running:
            print("Sweep not currently running. Nothing to stop.")
        self.is_running = False
        self.send_updates()

    def kill(self):
        """
        Ends the threads spawned by the sweep and closes any active plots.
        """
        # Stop any data-taking
        self.is_running = False

        # Gently shut down the runner
        if self.runner is not None:
            self.runner.flush_flag = True
            self.runner.kill_flag = True
            if not self.runner.wait(1000):
                self.runner.terminate()
                print('forced runner to terminate')
                self.runner = None
            self.send_updates()
        # Gently shut down the plotter
        if self.plotter is not None:
            self.plotter.kill_flag = True
            if not self.plotter.wait(1000):
                self.plotter.terminate()
                print('forced plotter to terminate')
            self.plotter.clear()
            self.plotter = None

    def check_running(self):
        """
        Returns the status of the sweep.
        """
        return self.is_running

    def start(self, persist_data=None, ramp_to_start=False):
        """
        Starts the sweep by creating and running the worker threads. Used to both start the 
        program and unpause after calling 'stop()'
        """

        if self.is_running:
            print("We are already running, can't start while running.")
            return

        # Check if we have a measurement object
        if self.meas is None:
            self._create_measurement()
        # Check if our list of parameters is out of date- meaning we started, stopped, updated params, and restarted
        elif not self.check_params_are_correct():
            self._create_measurement()
            if self.plotter is not None and self.plotter.figs_set is True:
                self.plotter.clear()
                # print("reset figs")
                self.plotter.create_figs()

        # If we don't have a plotter yet want to plot, create it and the figures
        if self.plotter is None and self.plot_data is True:
            self.plotter = PlotterThread(self, self.plot_bin)
            self.plotter.create_figs()

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
        if self.plot_data is True and self.plotter.isRunning() is False:
            self.plotter.start()
        elif self.plot_data is True and self.plotter.figs_set is False:
            # print("somehow here")
            self.plotter.create_figs()
        if not self.runner.isRunning():
            self.runner.kill_flag = False
            self.runner.start()

    def resume(self):
        """
        Restart the sweep.
        """
        if self.is_running is False:
            self.start(ramp_to_start=False)
        self.send_updates(no_sp=True)

    def get_dataset(self):
        """
        Helper function for retrieving datset.
        
        Returns
        -------
        self.dataset - Dataset object containing all collected data

        """

        return self.dataset

    @pyqtSlot(dict)
    def receive_dataset(self, ds_dict):
        self.dataset = ds_dict
        self.dataset_signal.emit(ds_dict)

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
                v = p.get()
                data.append((p, v))

        if self.save_data and self.is_running:
            self.runner.datasaver.add_result(*data)

        self.send_updates()

        # print(data)
        return data

    def send_updates(self, no_sp=False):
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

    def clear_plot(self):
        """
        Clears the currently showing plots.
        """
        if self.plotter is not None:
            self.plotter.reset()

    def set_plot_bin(self, pb):
        self.plot_bin = pb
        if self.plotter is not None:
            self.plotter.plot_bin = pb

    def set_complete_func(self, func):
        """
        Defines the function to call when finished.
        
        Arguments:
            func - function to call
        """
        self.completed.connect(func)

    @pyqtSlot()
    def no_change(self):
        """
        This function is passed when we don't need to connect a function when the 
        sweep is completed.
        """
        pass

    def check_params_are_correct(self):
        p_list = []
        meas_list = []
        # print("our params list")
        for p in self._params:
            # print(str(p))
            p_list.append(str(p))
        p_list.append("time")
        if self.set_param is not None:
            p_list.append(str(self.set_param))
        # print("measurement param list")
        for key, val in self.meas.parameters.items():
            # print(str(key))
            meas_list.append(key)

        return set(p_list) == set(meas_list)

    def export_json(self, fn=None):
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
            json_dict['bidirectional'] = self.bidirectional
            json_dict['continual'] = self.continuous
            json_dict['attributes']['x_axis_time'] = self.x_axis

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
        else:
            return

        for p, instr in json_dict['follow_params'].items():
            instr_module = importlib.import_module(instr[1])
            instrument = getattr(instr_module, instr[2])

            param = load_parameter(p, instr[0], instrument, station)
            sweep.follow_param(param)

        return sweep

    def __del__(self):
        """
        Destructor. Should delete all child threads and close all figures when the sweep object is deleted
        """
        self.kill()
