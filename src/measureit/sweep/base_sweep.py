# base_sweep.py
import importlib
import json
import time
from functools import partial
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from qcodes import Station
from qcodes.dataset.measurements import Measurement

from .._internal.plotter_thread import Plotter
from .._internal.runner_thread import RunnerThread
from ..logging_utils import get_sweep_logger
from ..tools.util import _autorange_srs, safe_get
from .progress import ProgressState, SweepState


class BaseSweep(QObject):
    """The parent class for the 0D, 1D and 2D sweep classes.

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
    progressState:
        Tracks the sweep progress metadata including state information.
    t0:
         Set to monotonic time when creating Runner Thread.
    persist_data:
        Always none except in Sweep2D, takes one set_param, allows sweeping of 2 parameters.
    datasaver:
        Initiated by Runner Thread to enable saving and export of data.

    Methods:
    ---------
    follow_param(*p)
        Adds QCoDes parameters from imported drivers to be tracked.
    remove_param(*p)
        Removes parameters that have been assigned to be tracked.
    follow_srs(l, name, gain)
        Adds SRS lock-in amplifier to keep range consistent.
    create_measurement()
        Creates a QCoDeS Measurement Object
    pause()
        Pauses the sweep.
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

    def __init__(
        self,
        set_param=None,
        inter_delay=0.1,
        save_data=True,
        plot_data=True,
        x_axis_time=1,
        datasaver=None,
        complete_func=None,
        plot_bin=1,
        back_multiplier=1,
        suppress_output=False,
    ):
        """Initializer for both classes, called by BaseSweep.__init__() in Sweep0D and Sweep1D classes.

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
        progressState:
            Tracks sweep timing, completion progress, and current state.
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

        self.t0 = 0

        self.persist_data = None
        self.datasaver = datasaver
        # Metadata provider: by default, each sweep provides its own metadata.
        # For composite sweeps (e.g., Sweep2D with inner Sweep1D), the inner
        # sweep can point this to the outer sweep to ensure the correct class
        # is recorded in the dataset metadata.
        self.metadata_provider = None

        # Set the function to call when we are finished
        self.complete_func = complete_func
        if complete_func is None:
            complete_func = self.no_change
        self.completed.connect(complete_func)

        self.print_main.connect(self.print_msg)

        self.plotter = None
        self.plotter_thread = None
        self.runner = None
        self.progressState = ProgressState()
        self._accumulated_run_time = 0.0
        self._run_started_at: Optional[float] = None

        # Configure logging for this sweep instance
        self.logger = get_sweep_logger(self.__class__.__name__)
        if suppress_output:
            self.logger.debug("Sweep created with suppress_output=True")

    @classmethod
    def init_from_json(cls, fn, station):
        """Initializes QCoDeS station from previously saved setup."""
        with open(fn) as json_file:
            data = json.load(json_file)
            return BaseSweep.import_json(data, station)

    def follow_param(self, *p):
        """Saves parameters to be tracked, for both saving and plotting data.

        The parameters must be followed before '_create_measurement()' is called.

        Parameters:
            *p:
                Variable number of arguments, each of which must be a QCoDeS Parameter
                that is desired to be followed.
        """
        if self.progressState.state in (SweepState.RUNNING, SweepState.RAMPING):
            self.print_main.emit(
                "Cannot update the parameter list while the sweep is running."
            )

        for param in p:
            if isinstance(param, list):
                for l in param:
                    if l not in self._params:
                        self._params.append(l)
            else:
                if param not in self._params:
                    self._params.append(param)

    def remove_param(self, *p):
        """Removes parameters that were previously followed.

        Parameters:
            *p - Variable number of arguments, each of which must be a QCoDeS Parameter
                 that is currently being tracked.
        """
        if self.progressState.state in (SweepState.RUNNING, SweepState.RAMPING):
            self.print_main.emit(
                "Cannot update the parameter list while the sweep is running."
            )

        for param in p:
            if isinstance(param, list):
                for l in param:
                    self._params.remove(l)
            else:
                self._params.remove(param)

    def follow_srs(self, l, name, gain=1.0):
        """Adds an SRS lock-in to ensure that the range is kept correctly.

        Parameters:
            l:
                The lock-in instrument.
            name:
                The name of the instrument to be followed.
            gain:
                The current gain value.
        """
        if self.progressState.state in (SweepState.RUNNING, SweepState.RAMPING):
            self.print_main.emit(
                "Cannot update the srs list while the sweep is running."
            )

        if (l, name, gain) not in self._srs:
            self._srs.append((l, name, gain))

    def _create_measurement(self):
        """Creates a QCoDeS Measurement object.

        Controls the saving of data by registering QCoDeS Parameter objects.
        Registers all desired parameters to be followed. This function will
        register only parameters that are followed BEFORE this function is
        called.

        Returns:
        ---------
        The measurement object with the parameters to be followed.

        """
        # First, create time parameter
        self.meas = Measurement()

        # Check if we are 'setting' a parameter, and register it
        if self.set_param is not None:
            self.meas.register_parameter(self.set_param)
            self.meas.register_custom_parameter(
                "time", label="time", unit="s", setpoints=(self.set_param,)
            )
        else:
            self.meas.register_custom_parameter("time", label="time", unit="s")

            # Register all parameters we are following
        for p in self._params:
            if self.set_param is None:
                self.meas.register_parameter(p, setpoints=("time",))
            else:
                self.meas.register_parameter(p, setpoints=(self.set_param,))

        return self.meas

    def _add_runtime_since_last_resume(self) -> None:
        """Accumulate elapsed run time since the sweep last entered RUNNING."""
        if self._run_started_at is None:
            return
        self._accumulated_run_time += max(time.monotonic() - self._run_started_at, 0.0)
        self._run_started_at = None

    def _enter_running_state(self, *, reset_elapsed: bool) -> float:
        """Transition into RUNNING, optionally resetting the accumulated runtime."""
        now = time.monotonic()
        if reset_elapsed:
            self._accumulated_run_time = 0.0
        self._run_started_at = now
        self.progressState.state = SweepState.RUNNING
        return now

    def pause(self):
        """Pause the sweep by moving the progress state to PAUSED."""
        if self.progressState.state not in (SweepState.RUNNING, SweepState.RAMPING):
            self.print_main.emit("Sweep not currently running. Nothing to pause.")
            return

        if self.progressState.state == SweepState.RUNNING:
            self._add_runtime_since_last_resume()
        self.progressState.state = SweepState.PAUSED
        self.send_updates()

    def stop(self):
        """Stop/pause the sweep. Alias for pause() for backward compatibility.

        This method pauses the sweep execution, allowing it to be resumed later
        with start() or resume(). This matches the behavior from older versions
        of MeasureIt where stop() was used to pause sweeps.
        """
        self.pause()

    def kill(self):
        """Ends the threads spawned by the sweep and closes any active plots."""
        # Stop any data-taking
        if self.progressState.state == SweepState.RUNNING:
            self._add_runtime_since_last_resume()
        self.progressState.state = SweepState.KILLED

        # Gently shut down the runner
        if self.runner is not None:
            # self.runner.quit()
            if not self.runner.wait(1000):
                self.runner.terminate()
                self.print_main.emit("forced runner to terminate")
            self.runner = None
            self.send_updates()
        # Gently shut down the plotter
        if self.plotter is not None:
            # Backward-compatibility: if a plotter_thread exists from older runs, terminate it
            try:
                if self.plotter_thread is not None:
                    self.plotter_thread.quit()
                    if not self.plotter_thread.wait(1000):
                        self.plotter_thread.terminate()
                        self.print_main.emit("forced plotter to terminate")
            except Exception:
                pass
            self.plotter_thread = None
            self.close_plots()
            self.plotter = None

        # Reset measurement object to ensure fresh measurement for next run
        self.meas = None
        self.send_updates()

    def check_running(self):
        """Returns the status of the sweep."""
        return self.progressState.state in (SweepState.RUNNING, SweepState.RAMPING)

    def start(self, persist_data=None, ramp_to_start=False):
        """Starts the sweep by creating and running the worker threads.

        Parameters
        ---------
        persist_data:
            Optional argument which allows Sweep2D to sweep two paramters.
        ramp_to_start:
            Optional argument which gradually ramps each parameter to the starting
            point of its sweep. Default is true for Sweep1D and Sweep2D.
        """
        if self.progressState.state in (SweepState.RUNNING, SweepState.RAMPING):
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
            # Keep Plotter in the main GUI thread for Qt/Jupyter safety
            self.plotter = Plotter(self, self.plot_bin)
            self.plotter.create_figs()

            self.add_break.connect(self.plotter.add_break)
            self.reset_plot.connect(self.plotter.reset)

        # If we don't have a runner, create it and tell it of the plotter,
        # which is where it will send data to be plotted
        if self.runner is None:
            self.runner = RunnerThread(self)
            self.runner.get_dataset.connect(self.receive_dataset)

            if self.plot_data is True:
                self.runner.add_plotter(self.plotter)

        # Flag that we are now running.
        run_start = self._enter_running_state(reset_elapsed=True)
        self.progressState.time_elapsed = 0.0
        self.progressState.time_remaining = None
        self.progressState.progress = 0.0
        self.t0 = run_start

        # Save persistent data from 2D sweep
        self.persist_data = persist_data

        # Tells the threads to begin (ensure figures exist)
        if (
            self.plot_data is True
            and self.plotter is not None
            and self.plotter.figs_set is False
        ):
            self.plotter.create_figs()
        if not self.runner.isRunning():
            self.runner.start()

    def resume(self):
        """Restarts the sweep after it has been paused."""
        if self.progressState.state == SweepState.PAUSED:
            self._enter_running_state(reset_elapsed=False)
            self.send_updates(no_sp=True)
        else:
            self.print_main.emit("Sweep is not paused; use start() to begin a run.")

    def get_dataset(self):
        """Returns the dataset object which contains the collected data."""
        return self.dataset

    @staticmethod
    def _split_hms(seconds: float) -> tuple[int, int, int]:
        """Convert seconds into hours, minutes, seconds (integer components)."""
        seconds = max(seconds, 0.0)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(round(seconds % 60))
        if secs == 60:
            secs = 0
            minutes += 1
        if minutes == 60:
            minutes = 0
            hours += 1
        return hours, minutes, secs

    def update_progress(self) -> None:
        """By default, updates progress using elapsed time and estimated time remaining. Can be overridden."""
        total_elapsed = self._accumulated_run_time
        if self._run_started_at is not None:
            total_elapsed += max(time.monotonic() - self._run_started_at, 0.0)
        elapsed_value = total_elapsed

        if self.progressState.progress is None:
            progress_value: Optional[float] = None
            remaining = None
        else:
            remaining = self.estimate_time(verbose=False)
            denominator = total_elapsed + remaining
            progress_value = None if denominator <= 0 else total_elapsed / denominator

        self.progressState = ProgressState(
            state=self.progressState.state,
            time_elapsed=elapsed_value,
            time_remaining=remaining,
            progress=progress_value,
        )

    def mark_done(self) -> None:
        """Transition the sweep to DONE and emit completion callbacks."""
        if self.progressState.state in (SweepState.KILLED, SweepState.DONE):
            return
        if self.progressState.state == SweepState.RUNNING:
            self._add_runtime_since_last_resume()
        self.progressState.state = SweepState.DONE
        self.send_updates()
        self.completed.emit()

    @pyqtSlot(dict)
    def receive_dataset(self, ds_dict):
        """Connects the dataset of Runner Thread to the dataset object of the sweep.

        Parameters
        ---------
        ds_dict:
            Dataset dictionary passed between Runner Thread and sweep.
        """
        self.dataset = ds_dict
        self.dataset_signal.emit(ds_dict)

    def update_values(self):
        """Called as Runner Thread loops to update parameter values.

        Verifies the data to be updated depending on type of sweep.
        Iterates through data point intervals, assigning collected values to
        their respective parameters. If data is to be saved, it happens here,
        and the updated data is emitted to all connected slots.

        Returns:
        ---------
        data:
            A dictionary of tuples with the updated data. Each tuple is of the format
            (<QCoDeS Parameter>, measurement value). The tuples are passed in order of
            time, then set_param (if applicable), then all the followed params.
        """
        t = time.monotonic() - self.t0

        data = [("time", t)]

        if self.set_param is not None:
            sp_data = self.step_param()
            if sp_data is not None:
                data += sp_data
            else:
                self.mark_done()
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

        if (
            self.save_data
            and self.runner is not None
            and self.progressState.state == SweepState.RUNNING
        ):
            self.runner.datasaver.add_result(*data)

        self.send_updates()

        return data

    def send_updates(self, no_sp=False):
        """Emits the signal after dictionary values are updated by 'update_values'.

        Parameters
        ---------
        no_sp:
            Represents a 'no setpoints' boolean. Default is False, when true it
            sets the setpoint key to None in the updated dictionary.
        """
        update_dict = {}
        if self.set_param is None:
            update_dict["set_param"] = "time"
            update_dict["setpoint"] = time.monotonic() - self.t0
            update_dict["direction"] = 0
        else:
            update_dict["set_param"] = self.set_param
            if not no_sp:
                update_dict["setpoint"] = self.setpoint
            else:
                update_dict["setpoint"] = None
            update_dict["direction"] = self.direction
        update_dict["status"] = self.progressState.state == SweepState.RUNNING
        update_dict["state"] = self.progressState.state.value

        self.update_signal.emit(update_dict)

    def reset_plots(self):
        """Clears the currently displayed plots."""
        if self.plotter is not None:
            self.reset_plot.emit()

    def get_metadata_provider(self):
        """Return the sweep to use when exporting metadata for the current run."""
        return self.metadata_provider if self.metadata_provider is not None else self

    def close_plots(self):
        """Resets the plotter and closes all displayed plots."""
        if self.plotter is not None:
            self.plotter.clear()

    def set_plot_bin(self, pb):
        """Sets value for the Plotter Thread plot bin.

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
        """Sets a function to be called whenever the sweep is finished.

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
        # Disconnect any existing complete_func to prevent duplicate connections
        if hasattr(self, 'complete_func') and self.complete_func is not None:
            try:
                self.completed.disconnect(self.complete_func)
            except (TypeError, RuntimeError):
                # No connection existed or already disconnected
                pass

        self.complete_func = partial(func, *args, **kwargs)
        self.completed.connect(self.complete_func)

    @pyqtSlot(str)
    def print_msg(self, msg):
        """Prints messages from the RunnerThread from the sweep, ensuring it is printed from the main thread

        Parameters
        ---------
        msg:
            The object to be printed
        """
        if self.suppress_output is False:
            self.logger.info(msg)
        else:
            # Respect suppress_output while still keeping a trace in the log file
            self.logger.debug(msg)

    @pyqtSlot()
    def no_change(self, *args, **kwargs):
        """Passed when there is no function to be called on completion.

        Simply allows the sweep to end when 'complete_func' is set to None.
        """
        pass

    def check_params_are_correct(self):
        """Compares the followed parameters to the measurement parameters.

        Pulls paramaters from object _params, compares list to parameters
        found in QCoDeS measurement dictionary.

        Returns:
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
        """Export sweep configuration as a JSON-serializable dict.

        Base implementation includes common attributes and followed parameters.
        Subclasses add their specific fields via _export_json_specific.
        """
        json_dict = {
            "class": str(self.__class__.__name__),
            "module": str(self.__class__.__module__),
            "attributes": {
                "inter_delay": self.inter_delay,
                "save_data": self.save_data,
                "plot_data": self.plot_data,
                "plot_bin": self.plot_bin,
            },
        }

        # Allow subclasses to add sweep-specific configuration
        json_dict = self._export_json_specific(json_dict)

        # Always include followed params (instrument-qualified keys for uniqueness)
        json_dict["follow_params"] = {}
        exclude = self._params_to_exclude_from_follow()
        for p in self._params:
            key = f"{p.instrument.name}.{p.name}"
            if key in exclude:
                continue
            json_dict["follow_params"][key] = (
                p.instrument.name,
                p.instrument.__class__.__module__,
                p.instrument.__class__.__name__,
            )

        if fn is not None:
            with open(fn, "w") as outfile:
                json.dump(json_dict, outfile)

        return json_dict

    # --- Hooks for subclasses ---
    def _export_json_specific(self, json_dict: dict) -> dict:
        """Subclasses override to add their configuration to json_dict."""
        return json_dict

    def _params_to_exclude_from_follow(self) -> set:
        """Subclasses can override to exclude params from follow_params export."""
        return set()

    @staticmethod
    def _load_parameter_by_type(
        name: str,
        instr_name: str,
        instr_module: str,
        instr_class: str,
        station: Station,
    ):
        """Resolve a QCoDeS parameter by instrument identity and parameter name."""
        mod = importlib.import_module(instr_module)
        instr_type = getattr(mod, instr_class)

        # Prefer exact instrument name match
        if instr_name in station.components:
            inst = station.components[instr_name]
            if isinstance(inst, instr_type):
                return inst.parameters[name]
        # Fallback: any instrument of that type
        for inst in station.components.values():
            if isinstance(inst, instr_type) and name in inst.parameters:
                return inst.parameters[name]
        raise KeyError(
            f"Parameter {name} on instrument {instr_name} of type {instr_class} not found in station"
        )

    @classmethod
    def import_json(cls, json_dict, station=Station()):
        """Factory: delegate to subclass from_json, then attach follow_params."""
        sweep_module = json_dict["module"]
        sweep_class = json_dict["class"]

        module = importlib.import_module(sweep_module)
        sc = getattr(module, sweep_class)
        if hasattr(sc, "from_json") and callable(sc.from_json):
            sweep = sc.from_json(json_dict, station)
        else:
            raise NotImplementedError(
                f"Class {sweep_class} does not implement from_json"
            )

        # Attach followed parameters (supports both qualified and legacy keys)
        for p, instr in json_dict.get("follow_params", {}).items():
            param_name = p.split(".", 1)[1] if "." in p else p
            param = BaseSweep._load_parameter_by_type(
                param_name, instr[0], instr[1], instr[2], station
            )
            sweep.follow_param(param)

        return sweep

    def estimate_time(self, verbose=True):
        """Returns an estimate of the amount of time the sweep will take to complete.

        Parameters
        ----------
        verbose:
            Controls whether the function will print out the estimate in the form hh:mm:ss (default True)

        Returns:
        -------
        Time estimate for the sweep, in seconds
        """
        return 0

    def __del__(self):
        """Deletes all child threads and closes all figures."""
        self.kill()
