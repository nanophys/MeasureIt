# base_sweep.py
import importlib
import json
import math
import time
import threading
import warnings
import weakref
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from functools import partial
from typing import Optional, Tuple

from PyQt5.QtCore import QMetaObject, QObject, Qt, pyqtSignal, pyqtSlot
from qcodes import Station
from qcodes.dataset.measurements import Measurement
from qcodes.validators import Enum

from .._internal.plotter_thread import Plotter
from .._internal.runner_thread import RunnerThread
from ..logging_utils import get_sweep_logger
from ..tools.util import _autorange_srs, is_numeric_parameter, safe_get, safe_set
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

    # Class-level sweep registry
    _registry = weakref.WeakValueDictionary()  # All sweeps (weak refs, allow GC)
    _error_hold = set()  # Strong refs for ERROR sweeps (prevents GC)
    _next_id = 0  # Counter for unique sweep IDs
    _registry_lock = threading.Lock()  # Thread-safe registry access

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
        max_retries=3,
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
        max_retries:
            Maximum number of consecutive parameter set/get failures before transitioning
            to ERROR state. Defaults to 3.

        """
        QObject.__init__(self)

        self._params = []
        self._srs = []
        self.set_param = set_param
        if inter_delay is None or inter_delay < 0.01:
            raise ValueError(
                f"inter_delay={inter_delay}s is too small; must be at least 0.01s to protect runner thread timing."
            )
        self.inter_delay = inter_delay
        self.save_data = save_data
        self.plot_data = plot_data
        self.x_axis = x_axis_time
        self.back_multiplier = back_multiplier
        self.direction = 0
        self.meas = None
        self.dataset = None
        self.suppress_output = suppress_output
        self.max_retries = max_retries

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
        # Parent sweep reference (set by outer sweeps like Sweep2D for their inner sweep)
        # Must be explicitly set to None to override QObject.parent() method
        self.parent = None
        # Flag to track if error signals need to be emitted via deferred path
        # Set True in mark_error(_from_runner=True), cleared in _do_emit_error_signals
        self._error_completion_pending = False
        self._accumulated_run_time = 0.0
        self._run_started_at: Optional[float] = None
        # Guard to avoid marking DONE immediately on tiny sweeps before observers see RUNNING
        self._mark_done_deferred = False

        # Configure logging for this sweep instance
        self.logger = get_sweep_logger(self.__class__.__name__)
        if suppress_output:
            self.logger.debug("Sweep created with suppress_output=True")

        # Register this sweep in the global registry
        with BaseSweep._registry_lock:
            self._sweep_id = BaseSweep._next_id
            BaseSweep._next_id += 1
            BaseSweep._registry[self._sweep_id] = self

    @classmethod
    def init_from_json(cls, fn, station):
        """Initializes QCoDeS station from previously saved setup."""
        with open(fn) as json_file:
            data = json.load(json_file)
            return BaseSweep.import_json(data, station)

    @classmethod
    def get_all_sweeps(cls):
        """Get all registered sweep instances.

        Returns
        -------
        list
            List of all sweep instances currently registered (not yet garbage collected).
        """
        with cls._registry_lock:
            return list(cls._registry.values())

    @classmethod
    def get_error_sweeps(cls):
        """Get all sweeps currently in ERROR state.

        Returns
        -------
        list
            List of sweep instances in ERROR state. These sweeps are held in memory
            until explicitly killed or cleared to allow inspection.
        
        Notes
        -----
        This method returns sweeps from the error_hold set directly, which is more
        efficient than filtering the full registry by state.
        """
        with cls._registry_lock:
            # Return directly from error_hold - these are all ERROR sweeps by definition
            return list(cls._error_hold)

    @classmethod
    def _clear_registry_for_testing(cls):
        """Clear the sweep registry and error hold.
        
        This method is intended for use in tests only to ensure a clean state
        between test cases. It should not be used in production code.
        """
        with cls._registry_lock:
            cls._registry.clear()
            cls._error_hold.clear()

    def follow_param(self, *p):
        """Saves parameters to be tracked, for both saving and plotting data.

        The parameters must be followed before '_create_measurement()' is called.
        Non-numeric parameters (string enums, booleans, etc.) are rejected to
        prevent plotting errors.

        Parameters:
            *p:
                Variable number of arguments, each of which must be a QCoDeS Parameter
                that is desired to be followed.
        """
        if self.progressState.state in (SweepState.RUNNING, SweepState.RAMPING):
            self.print_main.emit(
                "Cannot update the parameter list while the sweep is running."
            )
            return

        for param in p:
            if isinstance(param, list):
                for l in param:
                    if l not in self._params:
                        if not is_numeric_parameter(l):
                            self.print_main.emit(
                                f"Cannot follow parameter '{l.name}': "
                                "non-numeric parameters (string enums, etc.) are not supported for plotting."
                            )
                            continue
                        self._params.append(l)
            else:
                if param not in self._params:
                    if not is_numeric_parameter(param):
                        self.print_main.emit(
                            f"Cannot follow parameter '{param.name}': "
                            "non-numeric parameters (string enums, etc.) are not supported for plotting."
                        )
                        continue
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
        # Reset deferred completion guard whenever we begin a run
        self._mark_done_deferred = False
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
        # Use getattr for all attributes that may not exist if __init__ failed early
        # (e.g., if inter_delay validation failed before progressState was set)
        progress_state = getattr(self, "progressState", None)

        # Stop any data-taking
        if progress_state is not None and progress_state.state == SweepState.RUNNING:
            self._add_runtime_since_last_resume()
        # Set KILLED if not already DONE or KILLED
        # ERROR state transitions to KILLED since user explicitly called kill()
        if progress_state is not None and progress_state.state not in (SweepState.DONE, SweepState.KILLED):
            self.progressState.state = SweepState.KILLED
        if hasattr(self, "_error_completion_pending"):
            self._error_completion_pending = False  # Clear to prevent stale flag

        # Release ERROR hold to allow garbage collection
        with BaseSweep._registry_lock:
            BaseSweep._error_hold.discard(self)

        # Gently shut down the runner
        runner = getattr(self, "runner", None)
        if runner is not None:
            # Break reference cycle before shutdown
            if hasattr(runner, "clear_sweep_ref"):
                runner.clear_sweep_ref()
            # self.runner.quit()
            if not runner.wait(1000):
                runner.terminate()
                self.print_main.emit("forced runner to terminate")
            self.runner = None
            self.send_updates()
        # Gently shut down the plotter
        plotter = getattr(self, "plotter", None)
        if plotter is not None:
            # Break reference cycle before shutdown
            if hasattr(plotter, "clear_sweep_ref"):
                plotter.clear_sweep_ref()
            # Backward-compatibility: if a plotter_thread exists from older runs, terminate it
            try:
                plotter_thread = getattr(self, "plotter_thread", None)
                if plotter_thread is not None:
                    plotter_thread.quit()
                    if not plotter_thread.wait(1000):
                        plotter_thread.terminate()
                        self.print_main.emit("forced plotter to terminate")
            except Exception:
                pass
            self.plotter_thread = None
            self.close_plots()
            self.plotter = None

        # Reset measurement object to ensure fresh measurement for next run
        if hasattr(self, "meas"):
            self.meas = None
        # Try to send final updates, but guard against incomplete initialization
        # (e.g., send_updates may access self.setpoint which may not exist)
        try:
            self.send_updates()
        except AttributeError:
            pass

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

        # Clear any previous error state before starting
        if self.progressState.state == SweepState.ERROR:
            self.clear_error()

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
            num_plots = len(self._params) + (1 if self.set_param is not None else 0)
            if num_plots == 0:
                # Warn but don't mutate plot_data; just skip plotter for this run
                self.logger.warning(
                    "plot_data=True but no parameters to plot. Skipping plot creation."
                )
            else:
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

            if self.plotter is not None:
                self.runner.add_plotter(self.plotter)

        # Flag that we are now running.
        run_start = self._enter_running_state(reset_elapsed=True)
        self.progressState.time_elapsed = 0.0
        self.progressState.time_remaining = None
        self.progressState.progress = 0.0
        self.progressState.error_count = 0
        self.progressState.error_message = None
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

        # Wait for runner to finish if still running (e.g., from previous sweep iteration)
        # This prevents a race condition where the runner is shutting down but isRunning()
        # still returns True, causing runner.start() to be skipped while state is RUNNING
        if self.runner.isRunning():
            self.runner.wait()
        # Defer runner.start() slightly to allow callers to observe RUNNING state
        threading.Timer(0.01, self.runner.start).start()

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

    @staticmethod
    def _estimate_step_counts(start, stop, step) -> tuple[int, int]:
        """Estimate step and point counts for a given start/stop/step."""
        if step is None:
            return 0, 0
        step_mag = abs(step)
        if step_mag == 0:
            return 0, 0
        span = abs(stop - start)
        raw_steps = span / step_mag
        nearest = round(raw_steps)
        tol = 1e-9 * max(1.0, abs(raw_steps))
        if abs(raw_steps - nearest) <= tol:
            steps = int(nearest)
        else:
            steps = int(math.floor(raw_steps))
        return steps, steps + 1

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
            error_message=self.progressState.error_message,
            error_count=self.progressState.error_count,
        )

    def mark_done(self) -> None:
        """Transition the sweep to DONE and emit completion callbacks."""
        if self.progressState.state in (SweepState.KILLED, SweepState.DONE, SweepState.ERROR):
            return
        if self.progressState.state == SweepState.RUNNING:
            self._add_runtime_since_last_resume()
        self.progressState.state = SweepState.DONE
        self.send_updates()
        self.completed.emit()

    def mark_error(self, error_message: str, _from_runner: bool = False) -> None:
        """Transition the sweep to ERROR state with an error message.

        Parameters
        ----------
        error_message:
            Description of the error that caused the sweep to fail.
        _from_runner:
            Internal flag. When True (called from runner thread), skip all signal
            emissions to avoid blocking the main event loop. Signals are emitted
            later via emit_error_completed().
        """
        if self.progressState.state in (SweepState.KILLED, SweepState.DONE, SweepState.ERROR):
            return

        # Log the error at ERROR level
        self.logger.error(error_message)

        if self.progressState.state == SweepState.RUNNING:
            self._add_runtime_since_last_resume()
        self.progressState.state = SweepState.ERROR
        self.progressState.error_message = error_message

        # Hold ERROR sweeps in memory to prevent garbage collection
        with BaseSweep._registry_lock:
            BaseSweep._error_hold.add(self)

        # Propagate error to parent sweep (e.g., Sweep2D when inner Sweep1D fails)
        parent = getattr(self, "parent", None)
        if parent is not None and hasattr(parent, "mark_error"):
            parent.mark_error(f"Inner sweep error: {error_message}", _from_runner=_from_runner)

        # Only emit signals if NOT called from runner thread
        if not _from_runner:
            self.print_main.emit(f"Sweep error: {error_message}")
            self.send_updates()
            if parent is None:
                self.completed.emit()
        else:
            # Mark that we need deferred signal emission via _do_emit_error_signals
            self._error_completion_pending = True

    def emit_error_completed(self) -> None:
        """Schedule error signal emission in the main thread.

        Called by runner thread after the loop exits. Uses QMetaObject.invokeMethod
        to schedule signal emission in the main thread via Qt.QueuedConnection,
        preventing kernel stalls when the main event loop is busy.
        """
        if self.progressState.state == SweepState.ERROR:
            # Schedule signal emission in main thread to avoid blocking
            QMetaObject.invokeMethod(
                self, "_do_emit_error_signals", Qt.QueuedConnection
            )

    @pyqtSlot()
    def _do_emit_error_signals(self) -> None:
        """Actually emit error signals. Runs in main thread via QueuedConnection.

        Only emits if _error_completion_pending is True (set by mark_error with _from_runner=True).
        This prevents double completion when mark_error is called from UI.
        """
        if self.progressState.state != SweepState.ERROR:
            return

        # Only emit if signals were deferred (not already emitted in mark_error)
        if not self._error_completion_pending:
            return
        self._error_completion_pending = False

        self.print_main.emit(f"Sweep error: {self.progressState.error_message}")
        self.send_updates()

        # Propagate to parent if exists
        parent = getattr(self, "parent", None)
        if parent is not None and hasattr(parent, "emit_error_completed"):
            parent.emit_error_completed()
        else:
            self.completed.emit()

    def clear_error(self) -> None:
        """Clear error state and reset error tracking. Call before resuming after an error."""
        self.progressState.error_count = 0
        self.progressState.error_message = None
        self._error_completion_pending = False  # Clear to prevent stale flag across runs
        if self.progressState.state == SweepState.ERROR:
            self.progressState.state = SweepState.READY
            # Release ERROR hold to allow garbage collection
            with BaseSweep._registry_lock:
                BaseSweep._error_hold.discard(self)

    def try_set(self, param, value) -> bool:
        """Set a parameter safely, transitioning to ERROR state on failure.

        Uses safe_set which retries once on failure. If it still fails,
        logs the error and transitions the sweep to ERROR state.

        Parameters
        ----------
        param:
            The QCoDeS parameter to set.
        value:
            The value to set the parameter to.

        Returns
        -------
        bool
            True if the set succeeded, False if it failed (sweep is now in ERROR state).
        """
        try:
            safe_set(param, value)
            return True
        except Exception as e:
            error_msg = f"Failed to set {param.label} to {value}: {e}"
            self.print_main.emit(error_msg)
            self.mark_error(error_msg)
            return False

    @staticmethod
    def _snap_to_step(value: float, origin: float, step: float) -> float:
        """Snap value to nearest point on grid: origin + n*step.

        This fixes floating point precision errors that accumulate during
        sequential setpoint += step operations. For example, after 90 forward
        and 90 backward steps with step=1e-8, the setpoint might be
        -6.28e-23 instead of 0.0, which fails parameter validation.

        Parameters
        ----------
        value:
            The value to snap (e.g., setpoint after arithmetic).
        origin:
            The grid origin (e.g., sweep start value).
        step:
            The step size defining the grid spacing.

        Returns
        -------
        float
            The value snapped to the nearest grid point.
        """
        if step == 0:
            return value
        step = abs(step)

        # Use Decimal arithmetic to avoid reintroducing binary float rounding
        # when multiplying the (possibly non-power-of-two) step size.
        with localcontext() as ctx:
            ctx.prec = 50  # extra headroom for small steps and large origins
            d_step = Decimal(str(step))
            d_origin = Decimal(str(origin))
            d_value = Decimal(str(value))

            n = ((d_value - d_origin) / d_step).to_integral_value(
                rounding=ROUND_HALF_EVEN
            )
            snapped = d_origin + n * d_step

            # Quantize to the finest precision needed (min of step and origin exponents)
            # to preserve precision when origin has more decimal places than step.
            step_exponent = d_step.normalize().as_tuple().exponent
            origin_exponent = d_origin.normalize().as_tuple().exponent if d_origin != 0 else 0
            min_exponent = min(step_exponent, origin_exponent)
            if min_exponent < 0:
                quantizer = Decimal(1).scaleb(min_exponent)
                snapped = snapped.quantize(quantizer, rounding=ROUND_HALF_EVEN)

        return float(snapped)

    @staticmethod
    def _get_validator_bounds(param) -> Tuple[Optional[float], Optional[float]]:
        """Extract min/max bounds from a parameter's validator if available.

        Parameters
        ----------
        param:
            A QCoDeS Parameter that may have a validator with bounds.

        Returns
        -------
        Tuple[Optional[float], Optional[float]]
            (min_value, max_value) from the validator, or (None, None) if
            no validator or no bounds are defined.
        """
        validator = getattr(param, "vals", None)
        if validator is None:
            return None, None

        # Handle common QCoDeS validators (Numbers, Ints, Arrays)
        min_val = getattr(validator, "_min_value", None)
        max_val = getattr(validator, "_max_value", None)

        # Convert infinite values to None for easier handling
        if min_val is not None:
            try:
                if not math.isfinite(min_val):
                    min_val = None
            except (TypeError, ValueError):
                pass

        if max_val is not None:
            try:
                if not math.isfinite(max_val):
                    max_val = None
            except (TypeError, ValueError):
                pass

        return min_val, max_val

    @staticmethod
    def _validate_param_sweep_range(
        param, start: float, stop: float, param_label: str = None
    ) -> None:
        """Validate that start and stop values are within the parameter's validator bounds.

        Raises ValueError if start or stop exceeds the parameter's validation limits.
        Emits a warning if start or stop is exactly at the boundary (potential float errors).

        Parameters
        ----------
        param:
            A QCoDeS Parameter with optional validator.
        start:
            The starting value of the sweep.
        stop:
            The stopping value of the sweep.
        param_label:
            Optional label for error messages. If not provided, uses param.label or param.name.

        Raises
        ------
        ValueError
            If start or stop exceeds the parameter's validation bounds, or if the
            parameter uses an Enum validator (discrete values cannot be swept linearly).
        """
        validator = getattr(param, "vals", None)

        # Check for Enum validator - sweeping discrete values is not supported
        if validator is not None and isinstance(validator, Enum):
            if param_label is None:
                param_label = getattr(param, "label", None) or getattr(param, "name", "parameter")
            raise ValueError(
                f"Cannot create a linear sweep for '{param_label}' because it uses an Enum "
                f"validator with discrete allowed values: {validator._valid_values}. "
                f"Use a manual loop to iterate over the allowed values instead."
            )

        min_val, max_val = BaseSweep._get_validator_bounds(param)

        # If no bounds defined, nothing to validate
        if min_val is None and max_val is None:
            return

        # Skip validation for infinite start/stop values (used by GateLeakage, etc.)
        # These are placeholder values meaning "until some condition is met"
        try:
            start_is_finite = math.isfinite(start)
            stop_is_finite = math.isfinite(stop)
        except (TypeError, ValueError):
            # If we can't check finiteness, skip validation for that value
            start_is_finite = True
            stop_is_finite = True

        # Determine label for error messages
        if param_label is None:
            param_label = getattr(param, "label", None) or getattr(param, "name", "parameter")

        # Small tolerance for boundary comparison (relative tolerance)
        # Use a small epsilon for floating point comparison
        rel_tol = 1e-9

        def is_at_boundary(value, bound):
            """Check if value is at or very close to the boundary."""
            if bound is None:
                return False
            if bound == 0:
                return abs(value) < rel_tol
            return abs(value - bound) / abs(bound) < rel_tol

        def exceeds_min(value):
            """Check if value is below the minimum bound."""
            if min_val is None:
                return False
            # Allow exactly at boundary
            return value < min_val and not is_at_boundary(value, min_val)

        def exceeds_max(value):
            """Check if value is above the maximum bound."""
            if max_val is None:
                return False
            # Allow exactly at boundary
            return value > max_val and not is_at_boundary(value, max_val)

        # Check start value (only if finite)
        if start_is_finite:
            if exceeds_min(start):
                raise ValueError(
                    f"Sweep start value {start} for '{param_label}' is below the parameter's "
                    f"minimum validation limit ({min_val})."
                )
            if exceeds_max(start):
                raise ValueError(
                    f"Sweep start value {start} for '{param_label}' exceeds the parameter's "
                    f"maximum validation limit ({max_val})."
                )

        # Check stop value (only if finite)
        if stop_is_finite:
            if exceeds_min(stop):
                raise ValueError(
                    f"Sweep stop value {stop} for '{param_label}' is below the parameter's "
                    f"minimum validation limit ({min_val})."
                )
            if exceeds_max(stop):
                raise ValueError(
                    f"Sweep stop value {stop} for '{param_label}' exceeds the parameter's "
                    f"maximum validation limit ({max_val})."
                )

        # Warn if start or stop is exactly at a boundary (potential float errors)
        # Only check finite values
        boundary_warnings = []
        if start_is_finite:
            if is_at_boundary(start, min_val):
                boundary_warnings.append(
                    f"start value {start} is at the minimum validation limit ({min_val})"
                )
            if is_at_boundary(start, max_val):
                boundary_warnings.append(
                    f"start value {start} is at the maximum validation limit ({max_val})"
                )
        if stop_is_finite:
            if is_at_boundary(stop, min_val):
                boundary_warnings.append(
                    f"stop value {stop} is at the minimum validation limit ({min_val})"
                )
            if is_at_boundary(stop, max_val):
                boundary_warnings.append(
                    f"stop value {stop} is at the maximum validation limit ({max_val})"
                )

        if boundary_warnings:
            warnings.warn(
                f"Sweep of '{param_label}': {'; '.join(boundary_warnings)}. "
                f"Due to floating point arithmetic, the sweep may slightly exceed "
                f"the validation bounds. Consider adding a small margin.",
                UserWarning,
                stacklevel=3,
            )

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
        update_dict["error_message"] = self.progressState.error_message
        update_dict["error_count"] = self.progressState.error_count

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

    def emit_print_main(self, msg: str) -> None:
        """Emit a message to the main print signal."""
        self.print_main.emit(msg)

    def emit_step_info(self, label, start, stop, step, unit=None) -> None:
        """Emit step size and count details for a sweep parameter."""
        if step is None:
            return
        step_mag = abs(step)
        unit_suffix = f" {unit}" if unit else ""
        try:
            if not (
                math.isfinite(start)
                and math.isfinite(stop)
                and math.isfinite(step_mag)
            ):
                self.emit_print_main(
                    f"{label} sweep: step size {step_mag}{unit_suffix}, steps unknown, points unknown."
                )
                return
        except TypeError:
            self.emit_print_main(
                f"{label} sweep: step size {step_mag}{unit_suffix}, steps unknown, points unknown."
            )
            return
        steps, points = self._estimate_step_counts(start, stop, step)
        self.emit_print_main(
            f"{label} sweep: step size {step_mag}{unit_suffix}, steps {steps}, points {points}."
        )

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
