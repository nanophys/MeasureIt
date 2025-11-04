# sweep2d.py

import time
from functools import partial

from PyQt5.QtCore import QObject, pyqtSignal

from ..visualization.heatmap_thread import Heatmap
from .base_sweep import BaseSweep
from .progress import SweepState
from .sweep1d import Sweep1D


class Sweep2D(BaseSweep, QObject):
    """A 2-D Sweep of QCoDeS Parameters.

    This class runs by setting an outside parameter, then running
    an inner Sweep1D object. The inner sweep handles all data saving
    and communications through the Thread objects.

    Attributes:
    ---------
    in_params:
        List defining the inner sweep [parameter, start, stop, step].
    out_params:
        List defining the outer sweep [parameter, start, stop, step].
    inter_delay:
        Time (in seconds) to wait between data points on inner sweep.
    outer_delay:
        Time (in seconds) to wait between data points on outer sweep.
    save_data:
        Flag used to determine if the data should be saved or not.
    plot_data:
        Flag to determine whether or not to live-plot data.
    complete_func:
        Sets a function to be executed upon completion of the outer sweep.
    update_func:
        Sets a function to be executed upon completion of the inner sweep.
    plot_bin:
        Defaults to 1. Controls amount of data stored in the data_queue list
        in the Plotter Thread.
    runner:
        Assigns the Runner Thread.
    plotter:
        Assigns the Plotter Thread.
    back_multiplier:
        Factor to scale the step size after flipping directions.
    out_ministeps:
        Steps for outer parameter to setp to next setpoint.
    err:
        Tolerance for considering rounding errors when determining when the sweep has finished.
    heatmap_plotter:
        Uses color to represent values of a third parameter plotted against
        two sweeping parameters.

    Methods:
    ---------
    follow_param(*p)
        Saves parameters to be tracked, for both saving and plotting data.
    follow_srs(self, l, name, gain=1.0)
        Adds an SRS lock-in to Sweep1D to ensure that the range is kept correctly.
    _create_measurement()
        Creates the measurement object for the sweep.
    start(ramp_to_start=True, persist_data=None)
        Extends the start() function of BaseSweep.
    stop()
        Stops the sweeping of both the inner and outer sweep.
    resume()
        Resumes the inner and outer sweeps.
    follow_heatmap_param(para)
        Assign a followed parameter for heatmap to follow.
    update_values()
        Updates plots and heatmap based on data from the inner and outer sweeps.
    get_param_setpoint()
        Obtains the current value of the setpoint.
    set_update_rule(func)
        Sets a function to be called upon completion of each inner sweep.
    send_updates(no_sp=False)
        Passed in Sweep2D.
    kill()
        Ends all threads and closes any active plots.
    ramp_to(value, start_on_finish=False, multiplier=1)
        Ramps the set_param to a given value, at a rate specified by multiplier.
    ramp_to_zero()

    done_ramping(start_on_finish=False)



    """

    add_heatmap_data = pyqtSignal(object)

    def __init__(
        self,
        in_params,
        out_params,
        outer_delay=1,
        err=[0.1, 1e-2],
        out_ministeps=1,
        update_func=None,
        *args,
        **kwargs,
    ):
        """Initializes the sweep.

        The inner sweep parameters('in_params') and outer sweep parameters ('out_params') MUST be a list,
        conforming to the following standard:

            [ <QCoDeS Parameter>, <start value>, <stop value>, <step size> ]

        Parameters
        ---------
        in_params:
            A list conforming to above standard for the inner sweep.
        out_params:
            A list conforming to above standard for the outer sweep.
        inter_delay:
            Time (in seconds) to wait between data points on inner sweep.
        outer_delay:
            Time (in seconds) to wait between data points on outer sweep.
        save_data:
            Flag used to determine if the data should be saved or not.
        plot_data:
            Flag to determine whether or not to live-plot data.
        complete_func:
            Sets a function to be executed upon completion of the outer sweep.
        update_func:
            Sets a function to be executed upon completion of the inner sweep.
        plot_bin:
            Defaults to 1. Sets the number of data points to gather before
            refreshing the plot.
        back_multiplier:
            Factor to scale the step size after flipping directions.
        out_ministeps:
            Steps for outer parameter to setp to next setpoint.
        err:
            Tolerance for considering rounding errors when determining when the sweep has finished.
        """
        # Ensure that the inputs were passed (at least somewhat) correctly
        if len(in_params) != 4 or len(out_params) != 4:
            raise TypeError(
                "For 2D Sweep, must pass list of 4 object for each sweep parameter, \
                             in order: [ <QCoDeS Parameter>, <start value>, <stop value>, <step size> ]"
            )

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
        self.out_ministeps = round(out_ministeps)
        if self.out_ministeps < 1:
            self.out_ministeps = 1

        if (self.out_stop - self.out_start) > 0:
            self.out_step = abs(self.out_step)
        else:
            self.out_step = (-1) * abs(self.out_step)

        [self.err, self.err_in] = err
        # Initialize the BaseSweep
        QObject.__init__(self)
        BaseSweep.__init__(self, set_param=self.set_param, *args, **kwargs)

        # Create the inner sweep object
        self.in_sweep = Sweep1D(
            self.in_param,
            self.in_start,
            self.in_stop,
            self.in_step,
            bidirectional=True,
            inter_delay=self.inter_delay,
            save_data=self.save_data,
            x_axis_time=0,
            err=self.err_in,
            plot_data=self.plot_data,
            back_multiplier=self.back_multiplier,
            plot_bin=self.plot_bin,
        )
        # Set parent reference so UI actions (e.g., ESC) can stop both inner and outer sweeps
        self.in_sweep.parent = self
        # Ensure the inner sweep writes metadata for the composite (outer) sweep
        self.in_sweep.metadata_provider = self
        # We set our outer sweep parameter as a follow param for the inner sweep, so that
        # it is always read and saved with the rest of our data
        self.in_sweep.follow_param(self.set_param)
        # Our update_values() function iterates the outer sweep, so when the inner sweep
        # is done, call that function automatically
        self.in_sweep.set_complete_func(self.update_values)

        self.outer_delay = outer_delay
        self.inner_time = self.in_sweep.estimate_time(verbose=False)
        self.progressState.progress = 0.0
        self.update_progress()
        # Bubble dataset info through the outer sweep signal for convenience
        try:
            self.in_sweep.dataset_signal.connect(self.dataset_signal)
        except Exception:
            # Fallback: emit directly if connecting signals is unsupported
            try:
                self.in_sweep.dataset_signal.connect(self.dataset_signal.emit)
            except Exception:
                pass

        # Flags for ramping
        self.inner_ramp = False
        self.outer_ramp = False
        self.ramp_sweep = None

        # Set the function to call when the inner sweep finishes
        if update_func is None:
            self.update_rule = self.no_change

        # Initialize our heatmap plotting thread
        self.heatmap_plotter = None
        # The index for 2d heatmap to plot.
        self.heatmap_ind = 1

        self.print_main.emit("Heatmap will follow a random parameter by default")

    def __str__(self):
        return (
            f"2D Sweep of {self.set_param.label} from {self.out_start} to {self.out_stop} with step "
            f"{self.out_step}, while sweeping {self.in_param.label} from {self.in_start} to {self.in_stop} with "
            f"step {self.in_step}. Heatmap follows {self.in_sweep._params[self.heatmap_ind].label}. "
        )

    def __repr__(self):
        return (
            f"Sweep2D([{self.set_param.label}, {self.out_start}, {self.out_stop}, {self.out_step}], "
            f"[{self.in_param.label}, {self.in_start}, {self.in_stop}, {self.in_step}])"
        )

    def follow_param(self, *p):
        """Saves parameters to be tracked, for both saving and plotting data.

        Since the data saving is always handled by the inner Sweep1D object, all parameters
        are registered in the inner Sweep1D object.

        The parameters must be followed before '_create_measurement()' is called.

        Parameters
        ---------
        *p:
            Variable number of arguments, each of which must be a QCoDeS Parameter,
            or a list of QCoDeS Parameters, for the sweep to follow.
        """
        for param in p:
            if isinstance(param, list):
                for l in param:
                    self.in_sweep._params.append(l)
            else:
                self.in_sweep._params.append(param)
        self._params = self.in_sweep._params

    def follow_srs(self, l, name, gain=1.0):
        """Adds an SRS lock-in to Sweep1D to ensure that the range is kept correctly.

        Parameters
        ---------
        l:
            The lock-in instrument.
        name:
            The user-defined name of the instrument.
        gain:
            The current gain value.
        """
        self.in_sweep.follow_srs((l, name, gain))

    def _create_measurement(self):
        """Creates the measurement object for the sweep.

        The measurement object is created through the inner Sweep1D object.

        Returns:
        ---------
        self.meas:
            The QCoDeS Measurement object responsible for running the sweep.
        """
        self.meas = self.in_sweep._create_measurement()

        return self.meas

    def start(self, ramp_to_start=True, persist_data=None):
        """Extends the start() function of BaseSweep.

        The first outer sweep setpoint is set, and the inner sweep is started.

        Parameters
        ---------
        ramp_to_start:
            Sets a sweep to gently iterate the parameter to its starting value.
        persist_data:
            Sets the outer parameter for Sweep2D.
        """
        if self.progressState.state == SweepState.RUNNING:
            self.print_main.emit("Can't start the sweep, we're already running!")
            return
        elif self.outer_ramp:
            self.print_main.emit(
                "Can't start the sweep, we're currently ramping the outer sweep parameter!"
            )
            return

        if self.meas is None:
            self._create_measurement()

        if ramp_to_start:
            self.ramp_to(self.out_setpoint, start_on_finish=True)
        else:
            self.print_main.emit(
                f"Starting the 2D Sweep. Ramping {self.set_param.label} to {self.out_stop} {self.set_param.unit}, "
                f"while sweeping {self.in_param.label} between {self.in_start} {self.in_param.unit} and {self.in_stop} "
                f"{self.in_param.unit}"
            )

            self.set_param.set(self.out_setpoint)

            time.sleep(self.outer_delay)

            run_start = self._enter_running_state(reset_elapsed=True)
            self.progressState.time_elapsed = 0.0
            self.progressState.time_remaining = None
            self.progressState.progress = 0.0
            self.t0 = run_start

            if self.plot_data and self.heatmap_plotter is None:
                # Initialize our heatmap in the main GUI thread to avoid crashes in Jupyter/Qt
                self.heatmap_plotter = Heatmap(self)
                self.heatmap_plotter.create_figs()
                self.add_heatmap_data.connect(self.heatmap_plotter.add_data)

            self.in_sweep.start(persist_data=(self.set_param, self.out_setpoint))

            self.plotter = self.in_sweep.plotter
            self.runner = self.in_sweep.runner

    def pause(self):
        """Pauses both the inner and outer sweep."""
        BaseSweep.pause(self)
        self.in_sweep.pause()

    def stop(self):
        """Stop/pause the sweep. Alias for pause() for backward compatibility.

        Stops both the inner and outer sweep.
        """
        self.pause()

    def resume(self):
        """Resumes the inner and outer sweeps."""
        if self.progressState.state != SweepState.PAUSED:
            self.print_main.emit("Sweep is not paused; use start() to begin a new run.")
            return
        BaseSweep.resume(self)
        self.in_sweep.resume()

    def follow_heatmap_param(self, heatmap_para):
        """Configure which followed parameter(s) may be visualized in the heatmap.

        Accepts either a single QCoDeS parameter or a list/tuple of parameters.
        - If a single parameter is provided, updates the active selection (heatmap_ind).
        - If a list is provided, stores the allowed set and selects the first one.

        Parameters
        ---------
        heatmap_para:
            A QCoDeS Parameter or list/tuple of Parameters that are already followed
            by the inner sweep (i.e., present in self.in_sweep._params).
        """

        def to_index(p):
            try:
                return self.in_sweep._params.index(p)
            except Exception:
                return None

        # Handle list/tuple of parameters
        if isinstance(heatmap_para, (list, tuple, set)):
            indices = []
            for p in heatmap_para:
                idx = to_index(p)
                if idx is not None and self.in_sweep._params[idx] is not self.set_param:
                    indices.append(idx)
                else:
                    try:
                        self.print_main.emit(
                            f"Heatmap parameter {getattr(p, 'label', getattr(p, 'name', p))} is invalid or not followed."
                        )
                    except Exception:
                        pass
            if len(indices) == 0:
                # Fallback to current selection or default 1
                if (
                    not hasattr(self, "heatmap_param_indices")
                    or len(getattr(self, "heatmap_param_indices", [])) == 0
                ):
                    self.heatmap_param_indices = [self.heatmap_ind]
                return
            # Store the allowed set and select the first
            self.heatmap_param_indices = indices
            self.heatmap_ind = indices[0]
        else:
            # Single parameter: update current selection
            idx = to_index(heatmap_para)
            if idx is None:
                # Keep previous selection; notify
                try:
                    self.print_main.emit(
                        f"Heatmap parameter {getattr(heatmap_para, 'label', getattr(heatmap_para, 'name', heatmap_para))} is invalid or not followed."
                    )
                except Exception:
                    pass
                return
            self.heatmap_ind = idx
            # Ensure the allowed list exists and includes this index
            if (
                not hasattr(self, "heatmap_param_indices")
                or len(getattr(self, "heatmap_param_indices", [])) == 0
            ):
                self.heatmap_param_indices = [idx]
            elif idx not in self.heatmap_param_indices:
                self.heatmap_param_indices = [idx] + list(self.heatmap_param_indices)

        # Notify heatmap UI (if active) to refresh its parameter selector
        if self.heatmap_plotter is not None:
            try:
                # Rebuild the list and sync selection
                if hasattr(self.heatmap_plotter, "refresh_param_list"):
                    self.heatmap_plotter.refresh_param_list()
            except Exception:
                pass

    def update_values(self):
        """Updates plots and heatmap based on data from the inner and outer sweeps.

        This function is automatically called upon completion of the inner sweep.
        The outer parameter is iterated and the inner sweep is restarted. If the stop
        condition is reached, the completed signal is emitted and the sweeps are stopped.
        """
        self.update_progress()
        # If this function was called from a ramp down to 0, a special case of sweeping, deal with that
        # independently
        if self.in_sweep.progressState.state == SweepState.RAMPING:
            # We are no longer ramping to zero

            self.inner_ramp = False
            # Check if our outer ramp to zero is still going, and if not, then officially end
            # our ramping to zero
            if not self.outer_ramp:
                if self.progressState.state != SweepState.KILLED:
                    self.progressState.state = SweepState.READY
                if hasattr(self, "inner_sweep"):
                    inner = getattr(self, "inner_sweep")
                    if hasattr(inner, "progressState"):
                        inner.progressState.state = SweepState.READY
                self.in_sweep.progressState.state = SweepState.READY
                self.print_main.emit("Done ramping both parameters to zero")
            # Stop the function from running any further, as we don't want to check anything else
            return

        # Update heatmap rows for all allowed/selected parameters (only if plotting is enabled)
        last_plot_data = None
        if (
            self.plot_data
            and getattr(self.in_sweep, "plotter", None) is not None
            and getattr(self, "heatmap_plotter", None) is not None
        ):
            indices = getattr(self, "heatmap_param_indices", None)
            if not isinstance(indices, list) or len(indices) == 0:
                indices = [self.heatmap_ind]
            for p_idx in indices:
                plot_data = self.in_sweep.plotter.get_plot_data(p_idx)
                if plot_data is not None:
                    last_plot_data = plot_data
                    payload = dict(plot_data)
                    payload["param_index"] = p_idx
                    payload["out_value"] = self.out_setpoint
                    self.add_heatmap_data.emit(payload)

        # Check our update condition
        self.update_rule(self.in_sweep, last_plot_data)

        # If we aren't at the end, keep going
        if (
            abs(self.out_setpoint - self.out_stop) - abs(self.out_step / 2)
            > abs(self.out_step) * 1e-4
        ):
            # time.sleep(self.outer_delay)
            self.print_main.emit(
                f"Setting {self.set_param.label} to {self.out_setpoint + self.out_step} ({self.set_param.unit}) with {self.out_ministeps} steps"
            )
            # increment for each ministeps
            inc = self.out_step / self.out_ministeps
            for step in range(self.out_ministeps):
                self.set_param.set(self.out_setpoint + (step + 1) * inc)
                time.sleep(self.outer_delay)
            #    self.print_main.emit(f"DEBUG: now, the setpoint of out_parm is {self.set_param.get()}")
            # update the current setpoint
            self.out_setpoint = self.out_setpoint + self.out_step

            # Reset our plots
            self.in_sweep.reset_plots()
            self.in_sweep.start(persist_data=(self.set_param, self.out_setpoint))
        # If neither of the above are triggered, it means we are at the end of the sweep
        else:
            if self.plot_data and self.heatmap_plotter is not None:
                self.add_heatmap_data.emit(None)
            self.print_main.emit(
                f"Done with the sweep, {self.set_param.label}={self.out_setpoint} "
                f"({self.set_param.unit})"
            )
            self.mark_done()

    def get_param_setpoint(self):
        """Obtains the current value of the setpoint."""
        s = f"{self.set_param.label} = {self.set_param.get()} {self.set_param.unit} \
        \n{self.inner_sweep.set_param.label} = {self.inner_sweep.set_param.get()} {self.inner_sweep.set_param.unit}"
        return s

    def set_update_rule(self, func):
        """Sets a function to be called upon completion of each inner sweep.

        Parameters
        ---------
        func:
            The function handle desired to set the update function.
        """
        self.update_rule = func

    def send_updates(self, no_sp=False):
        pass

    def kill(self):
        """Ends all threads and closes any active plots."""
        self.in_sweep.kill()

        # Gently shut down the heatmap
        if self.heatmap_plotter is not None:
            self.heatmap_plotter.clear()
            self.heatmap_plotter = None
            # Backward-compat: if a thread was created in older runs, shut it down
            if hasattr(self, "heatmap_thread") and self.heatmap_thread is not None:
                try:
                    self.heatmap_thread.quit()
                    if not self.heatmap_thread.wait(1000):
                        self.heatmap_thread.terminate()
                        self.print_main.emit("forced heatmap to terminate")
                except Exception:
                    pass
                self.heatmap_thread = None

    def ramp_to(self, value, start_on_finish=False, multiplier=1):
        """Ramps the set_param to a given value, at a rate specified by the multiplier.

        Parameter
        ---------
        value:
            The setpoint for the sweep to ramp to.
        start_on_finish:
            Flag to determine whether to begin the sweep when ramping is finished.
        multiplier:
            The multiplier for the step size, to ramp quicker than the sweep speed.
        """
        # Ensure we aren't currently running
        if self.outer_ramp:
            self.print_main.emit(
                "Currently ramping. Finish current ramp before starting another."
            )
            return
        if self.progressState.state == SweepState.RUNNING:
            self.print_main.emit("Already running. Stop the sweep before ramping.")
            return

        # Check if we are already at the value
        curr_value = self.set_param.get()
        if abs(value - curr_value) <= self.out_step * self.err:
            # self.print_main.emit(f"Already within {self.step} of the desired ramp value. Current value: {curr_value},
            # ramp setpoint: {value}.\nSetting our setpoint directly to the ramp value.")
            self.set_param.set(value)
            self.done_ramping(start_on_finish=True)
            return

        # Create a new sweep to ramp our outer parameter to zero
        self.ramp_sweep = Sweep1D(
            self.set_param,
            curr_value,
            value,
            multiplier * self.out_step / self.out_ministeps,
            inter_delay=self.inter_delay,
            complete_func=partial(self.done_ramping, start_on_finish),
            save_data=False,
            plot_data=True,
        )
        for p in self._params:
            if p is not self.set_param:
                self.ramp_sweep.follow_param(p)

        self.outer_ramp = True
        self.progressState.state = SweepState.RAMPING
        self.ramp_sweep.start(ramp_to_start=False)

        self.print_main.emit(f"Ramping {self.set_param.label} to {value} . . . ")

    def ramp_to_zero(self):
        """Ramps the set_param to 0, at the same rate as already specified."""
        self.print_main.emit("Ramping both parameters to 0.")
        # Ramp our inner sweep parameter to zero
        self.inner_ramp = True
        self.in_sweep.ramp_to(0)

        # Check our step sign
        if self.out_setpoint > 0:
            self.out_step = (-1) * abs(self.out_step)
        else:
            self.out_step = abs(self.out_step)

        # Create a new sweep to ramp our outer parameter to zero
        zero_sweep = Sweep1D(
            self.set_param,
            self.set_param.get(),
            0,
            self.step / self.out_ministeps,
            inter_delay=self.inter_delay,
            complete_func=self.done_ramping,
        )
        zero_sweep.follow_param(self._params)
        self.progressState.state = SweepState.RAMPING
        self.outer_ramp = True
        zero_sweep.start()

    def done_ramping(self, start_on_finish=False):
        """Alerts the sweep that the ramp is finished.

        Parameters
        ---------
        start_on_finish:
            Sweep will be called to start immediately after ramping when set to True.
        """
        # Our outer parameter has finished ramping
        self.outer_ramp = False
        if self.ramp_sweep is not None:
            self.ramp_sweep.kill()
            self.ramp_sweep = None
        # Check if our inner parameter has finished
        while self.in_sweep.progressState.state == SweepState.RAMPING:
            time.sleep(0.5)

        # If so, tell the system we are done
        if self.progressState.state != SweepState.KILLED:
            self.progressState.state = SweepState.READY
        self.print_main.emit("Done ramping!")

        if start_on_finish:
            self.start(ramp_to_start=False)

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
        if self.progressState.state == SweepState.DONE:
            remaining = 0
        elif not self.out_step:
            remaining = self.inner_time
        else:
            step_mag = abs(self.out_step)
            steps = abs(self.out_stop - self.out_setpoint) / step_mag
            remaining = max(steps * self.outer_delay + (steps + 1) * self.inner_time, 0)

        if verbose:
            hours, minutes, seconds = self._split_hms(remaining)
            self.print_main.emit(
                f"Estimated time remaining for {repr(self)}: {hours}h:{minutes:02d}m:{seconds:02d}s"
            )
        return remaining

    # --- JSON export/import hooks ---
    def _export_json_specific(self, json_dict: dict) -> dict:
        json_dict["attributes"]["outer_delay"] = self.outer_delay
        json_dict["inner_sweep"] = {
            "param": self.in_param.name,
            # Include instrument-qualified key for uniqueness/debugging
            "param_key": f"{self.in_param.instrument.name}.{self.in_param.name}",
            "instr_module": self.in_param.instrument.__class__.__module__,
            "instr_class": self.in_param.instrument.__class__.__name__,
            "instr_name": self.in_param.instrument.name,
            "start": self.in_start,
            "stop": self.in_stop,
            "step": self.in_step,
        }
        json_dict["outer_sweep"] = {
            "param": self.set_param.name,
            # Include instrument-qualified key for uniqueness/debugging
            "param_key": f"{self.set_param.instrument.name}.{self.set_param.name}",
            "instr_module": self.set_param.instrument.__class__.__module__,
            "instr_class": self.set_param.instrument.__class__.__name__,
            "instr_name": self.set_param.instrument.name,
            "start": self.out_start,
            "stop": self.out_stop,
            "step": self.out_step,
        }
        return json_dict

    @classmethod
    def from_json(cls, json_dict, station):
        attrs = dict(json_dict.get("attributes", {}))
        inner = json_dict["inner_sweep"]
        outer = json_dict["outer_sweep"]

        # Support qualified names "instr.param" in 'param' field
        in_param_name = (
            inner["param"].split(".", 1)[1] if "." in inner["param"] else inner["param"]
        )
        out_param_name = (
            outer["param"].split(".", 1)[1] if "." in outer["param"] else outer["param"]
        )

        in_p = BaseSweep._load_parameter_by_type(
            in_param_name,
            inner["instr_name"],
            inner["instr_module"],
            inner["instr_class"],
            station,
        )
        out_p = BaseSweep._load_parameter_by_type(
            out_param_name,
            outer["instr_name"],
            outer["instr_module"],
            outer["instr_class"],
            station,
        )

        inner_list = [in_p, inner["start"], inner["stop"], inner["step"]]
        outer_list = [out_p, outer["start"], outer["stop"], outer["step"]]

        return cls(inner_list, outer_list, **attrs)

    def _params_to_exclude_from_follow(self) -> set:
        """Exclude inner and outer sweep parameters from follow_params export."""
        try:
            keys = {
                f"{self.set_param.instrument.name}.{self.set_param.name}",
                f"{self.in_param.instrument.name}.{self.in_param.name}",
            }
            return keys
        except Exception:
            return set()
