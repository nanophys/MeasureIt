# sweep2d.py

import time
from functools import partial

from .base_sweep import BaseSweep
from .sweep1d import Sweep1D
from .heatmap_thread import Heatmap
from PyQt5.QtCore import QObject, QThread, pyqtSignal


class Sweep2D(BaseSweep, QObject):
    """
    A 2-D Sweep of QCoDeS Parameters. 
    
    This class runs by setting an outside parameter, then running
    an inner Sweep1D object. The inner sweep handles all data saving
    and communications through the Thread objects. 
    
    Attributes
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
    heatmap_plotter:
        Uses color to represent values of a third parameter plotted against
        two sweeping parameters.
        
    Methods
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

    add_heatmap_lines = pyqtSignal(list)

    def __init__(self, in_params, out_params, outer_delay=1, err=[0.1, 1e-2], update_func=None, *args, **kwargs):
        """
        Initializes the sweep.
        
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
        err:
            Tolerance for considering rounding errors when determining when the sweep has finished.
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

        [self.err, self.err_in] = err
        # Initialize the BaseSweep
        QObject.__init__(self)
        BaseSweep.__init__(self, set_param=self.set_param, *args, **kwargs)

        # Create the inner sweep object
        self.in_sweep = Sweep1D(self.in_param, self.in_start, self.in_stop, self.in_step, bidirectional=True,
                                inter_delay=self.inter_delay, save_data=self.save_data, x_axis_time=0, err=self.err_in,
                                plot_data=self.plot_data, back_multiplier=self.back_multiplier, plot_bin=self.plot_bin)
        # We set our outer sweep parameter as a follow param for the inner sweep, so that
        # it is always read and saved with the rest of our data
        self.in_sweep.follow_param(self.set_param)
        # Our update_values() function iterates the outer sweep, so when the inner sweep
        # is done, call that function automatically
        self.in_sweep.set_complete_func(self.update_values)

        self.outer_delay = outer_delay

        # Flags for ramping
        self.inner_ramp = False
        self.outer_ramp = False
        self.ramp_sweep = None

        # Set the function to call when the inner sweep finishes
        if update_func is None:
            self.update_rule = self.no_change

        # Initialize our heatmap plotting thread
        self.heatmap_plotter = None

    def __str__(self):
        return f"2D Sweep of {self.set_param.label} from {self.out_start} to {self.out_stop} with step " \
               f"{self.out_step}, while sweeping {self.in_param.label} from {self.in_start} to {self.in_stop} with " \
               f"step {self.in_step}."

    def __repr__(self):
        return f"Sweep2D([{self.set_param.label}, {self.out_start}, {self.out_stop}, {self.out_step}], " \
               f"[{self.in_param.label}, {self.in_start}, {self.in_stop}, {self.in_step}])"

    def follow_param(self, *p):
        """
        Saves parameters to be tracked, for both saving and plotting data.
        
        
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
        """
        Adds an SRS lock-in to Sweep1D to ensure that the range is kept correctly.
        
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
        """
        Creates the measurement object for the sweep. 
        
        The measurement object is created through the inner Sweep1D object.
        
        Returns
        ---------
        self.meas:
            The QCoDeS Measurement object responsible for running the sweep.
        """

        self.meas = self.in_sweep._create_measurement()

        return self.meas

    def start(self, ramp_to_start=True, persist_data=None):
        """
        Extends the start() function of BaseSweep. 
        
        The first outer sweep setpoint is set, and the inner sweep is started.
        
        Parameters
        ---------
        ramp_to_start:
            Sets a sweep to gently iterate the parameter to its starting value.
        persist_data:
            Sets the outer parameter for Sweep2D.
        """

        if self.is_running:
            self.print_main.emit("Can't start the sweep, we're already running!")
            return
        elif self.outer_ramp:
            self.print_main.emit("Can't start the sweep, we're currently ramping the outer sweep parameter!")
            return

        if self.meas is None:
            self._create_measurement()

        if ramp_to_start:
            self.ramp_to(self.out_setpoint, start_on_finish=True)
        else:
            self.print_main.emit(
                f'Starting the 2D Sweep. Ramping {self.set_param.label} to {self.out_stop} {self.set_param.unit}, '
                f'while sweeping {self.in_param.label} between {self.in_start} {self.in_param.unit} and {self.in_stop} '
                f'{self.in_param.unit}')

            self.set_param.set(self.out_setpoint)

            time.sleep(self.outer_delay)

            self.is_running = True

            if self.heatmap_plotter is None:
                # Initialize our heatmap
                self.heatmap_plotter = Heatmap(self)
                self.heatmap_thread = QThread()
                self.heatmap_plotter.moveToThread(self.heatmap_thread)
                self.heatmap_plotter.create_figs()
                self.add_heatmap_lines.connect(self.heatmap_plotter.add_lines)
                self.heatmap_thread.start()

            self.in_sweep.start(persist_data=(self.set_param, self.out_setpoint))

            self.plotter = self.in_sweep.plotter
            self.runner = self.in_sweep.runner

    def stop(self):
        """ Stops the sweeping of both the inner and outer sweep. """
        self.is_running = False
        self.in_sweep.stop()

    def resume(self):
        """ Resumes the inner and outer sweeps. """
        self.is_running = True
        self.in_sweep.start(persist_data=(self.set_param, self.out_setpoint), ramp_to_start=False)

    def update_values(self):
        """
        Updates plots and heatmap based on data from the inner and outer sweeps.
        
        This function is automatically called upon completion of the inner sweep.
        The outer parameter is iterated and the inner sweep is restarted. If the stop
        condition is reached, the completed signal is emitted and the sweeps are stopped. 
        """

        # If this function was called from a ramp down to 0, a special case of sweeping, deal with that
        # independently
        if self.in_sweep.is_ramping:
            # We are no longer ramping to zero

            self.inner_ramp = False
            # Check if our outer ramp to zero is still going, and if not, then officially end
            # our ramping to zero
            if not self.outer_ramp:
                self.is_running = False
                self.inner_sweep.is_running = False
                self.print_main.emit("Done ramping both parameters to zero")
            # Stop the function from running any further, as we don't want to check anything else
            return

        # Update our heatmap!
        lines = self.in_sweep.plotter.axes[1].get_lines()
        self.add_heatmap_lines.emit(lines)

        # Check our update condition
        self.update_rule(self.in_sweep, lines)

        # If we aren't at the end, keep going
        if abs(self.out_setpoint - self.out_stop) - abs(self.out_step / 2) > abs(self.out_step) * 1e-4:
            self.out_setpoint = self.out_setpoint + self.out_step
            time.sleep(self.outer_delay)
            self.print_main.emit(f"Setting {self.set_param.label} to {self.out_setpoint} ({self.set_param.unit})")
            self.set_param.set(self.out_setpoint)
            time.sleep(self.outer_delay)
            # Reset our plots
            self.in_sweep.reset_plots()
            self.in_sweep.start(persist_data=(self.set_param, self.out_setpoint))
        # If neither of the above are triggered, it means we are at the end of the sweep
        else:
            self.is_running = False
            self.print_main.emit(f"Done with the sweep, {self.set_param.label}={self.out_setpoint} "
                                 f"({self.set_param.unit})")
            self.completed.emit()

    def get_param_setpoint(self):
        """ Obtains the current value of the setpoint. """
        s = f"{self.set_param.label} = {self.set_param.get()} {self.set_param.unit} \
        \n{self.inner_sweep.set_param.label} = {self.inner_sweep.set_param.get()} {self.inner_sweep.set_param.unit}"
        return s

    def set_update_rule(self, func):
        """
        Sets a function to be called upon completion of each inner sweep.
        
        Parameters
        ---------
        func:
            The function handle desired to set the update function. 
        """

        self.update_rule = func

    def send_updates(self, no_sp=False):
        pass

    def kill(self):
        """ Ends all threads and closes any active plots. """

        self.in_sweep.kill()

        # Gently shut down the heatmap
        if self.heatmap_plotter is not None:
            self.heatmap_plotter.clear()
            self.heatmap_thread.quit()
            if not self.heatmap_thread.wait(1000):
                self.heatmap_thread.terminate()
                self.print_main.emit('forced heatmap to terminate')
            self.heatmap_plotter = None

    def ramp_to(self, value, start_on_finish=False, multiplier=1):
        """
        Ramps the set_param to a given value, at a rate specified by the multiplier.

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
            self.print_main.emit(f"Currently ramping. Finish current ramp before starting another.")
            return
        if self.is_running:
            self.print_main.emit(f"Already running. Stop the sweep before ramping.")
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
        self.ramp_sweep = Sweep1D(self.set_param, curr_value, value, multiplier * self.out_step,
                                  inter_delay=self.inter_delay,
                                  complete_func=partial(self.done_ramping, start_on_finish),
                                  save_data=False, plot_data=True)
        for p in self._params:
            if p is not self.set_param:
                self.ramp_sweep.follow_param(p)
        
        self.is_running = False
        self.outer_ramp = True
        self.ramp_sweep.start(ramp_to_start=False)

        self.print_main.emit(f'Ramping {self.set_param.label} to {value} . . . ')

    def ramp_to_zero(self):
        """Ramps the set_param to 0, at the same rate as already specified. """

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
        zero_sweep = Sweep1D(self.set_param, self.set_param.get(), 0, self.step, inter_delay=self.inter_delay,
                             complete_func=self.done_ramping)
        zero_sweep.follow_param(self._params)
        self.is_running = True
        self.outer_ramp = True
        zero_sweep.start()

    def done_ramping(self, start_on_finish=False):
        """
        Alerts the sweep that the ramp is finished.
        
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
        while self.in_sweep.is_ramping:
            time.sleep(0.5)

        # If so, tell the system we are done
        self.is_running = False
        self.print_main.emit("Done ramping!")

        if start_on_finish:
            self.start(ramp_to_start=False)

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
        in_time = self.in_sweep.estimate_time(verbose=False)
        n_lines = abs((self.out_start - self.out_stop) / self.out_step) + 1
        out_time = self.outer_delay * self.out_step

        t_est = in_time * n_lines + out_time

        hours = int(t_est / 3600)
        minutes = int((t_est % 3600) / 60)
        seconds = t_est % 60
        if verbose is True:
            self.print_main.emit(f'Estimated time for {repr(self)} to run: {hours}h:{minutes:2.0f}m:{seconds:2.0f}s')
        return t_est
