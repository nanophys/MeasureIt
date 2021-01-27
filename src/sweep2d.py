# sweep2d.py

import time
from functools import partial

from src.base_sweep import BaseSweep
from src.sweep1d import Sweep1D
from src.heatmap_thread import HeatmapThread
from PyQt5.QtCore import pyqtSignal


class Sweep2D(BaseSweep):
    """
    A 2-D Sweep of QCoDeS Parameters. This class runs by setting its outside parameter, then running
    an inner Sweep1D object, which handles all the saving of data and communications through the
    Thread objects. 
    """
    completed = pyqtSignal()

    def __init__(self, in_params, out_params, inter_delay=0.1, outer_delay=1, save_data=True, plot_data=True,
                 complete_func=None, update_func=None, plot_bin=1, runner=None, plotter=None, back_multiplier=1):
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
        super().__init__(set_param=self.set_param, inter_delay=inter_delay, save_data=save_data, plot_data=plot_data,
                         plot_bin=plot_bin)

        # Create the inner sweep object
        self.in_sweep = Sweep1D(self.in_param, self.in_start, self.in_stop, self.in_step, bidirectional=True,
                                inter_delay=self.inter_delay, save_data=self.save_data, x_axis_time=0,
                                plot_data=self.plot_data, back_multiplier=back_multiplier)
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

        # Flags for ramping
        self.inner_ramp = False
        self.outer_ramp = False
        self.ramp_sweep = None

        # Set the function to call when the 2D sweep is finished
        if complete_func is None:
            complete_func = self.no_change
        self.completed.connect(complete_func)

        # Set the function to call when the inner sweep finishes
        if update_func is None:
            self.update_rule = self.no_change

        # Initialize our heatmap plotting thread
        self.heatmap_plotter = None

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
        self._params = self.in_sweep._params

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

    def start(self, ramp_to_start=True, persist_data=None):
        """
        Extends the start() function of BaseSweep. We set our first outer sweep setpoint, then
        start the inner sweep, and let it control the run from there.
        """
        if self.is_running:
            print("Can't start the sweep, we're already running!")
            return
        elif self.outer_ramp:
            print("Can't start the sweep, we're currently ramping the outer sweep parameter!")
            return

        if self.meas is None:
            self._create_measurement()

        if ramp_to_start:
            self.ramp_to(self.out_setpoint, start_on_finish=True)
        else:
            print(
                f'Starting the 2D Sweep. Ramping {self.set_param.label} to {self.out_stop} {self.set_param.unit}, '
                f'while sweeping {self.in_param.label} between {self.in_start} {self.in_param.unit} and {self.in_stop} '
                f'{self.in_param.unit}')

            self.set_param.set(self.out_setpoint)

            time.sleep(self.outer_delay)

            self.is_running = True

            if self.heatmap_plotter is None:
                # Initialize our heatmap
                self.heatmap_plotter = HeatmapThread(self)
                self.heatmap_plotter.create_figs()

            self.in_sweep.start(persist_data=(self.set_param, self.out_setpoint))

            self.plotter = self.in_sweep.plotter
            self.runner = self.in_sweep.runner

    def stop(self):
        """
        Stops the sweeping of both the inner and outer sweep.
        """
        self.is_running = False
        self.in_sweep.stop()

    def resume(self):
        self.is_running = True
        self.in_sweep.start(persist_data=(self.set_param, self.out_setpoint), ramp_to_start=False)

    def update_values(self):
        """
        Iterates the outer parameter and then restarts the inner loop. We also check for our stop
        condition, and if it is reached, we emit our completed signal and stop running. This is
        the function attached to the finishing of the inner sweep, so it will be automatically called
        when our inner sweep is finished.
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
                print("Done ramping both parameters to zero")
            # Stop the function from running any further, as we don't want to check anything else
            return

        #print("trying to update heatmap")
        # Update our heatmap!
        lines = self.in_sweep.plotter.axes[1].get_lines()
        self.heatmap_plotter.add_lines(lines)
        self.heatmap_plotter.start()
        #print("past lines")
        # Check our update condition
        self.update_rule(self.in_sweep, lines)
        #        self.in_sweep.ramp_to(self.in_sweep.begin, start_on_finish=False)

        #        while self.in_sweep.is_ramping == True:
        #            time.sleep(0.5)

        # If we aren't at the end, keep going
        if abs(self.out_setpoint - self.out_stop) >= abs(self.out_step / 2):
            self.out_setpoint = self.out_setpoint + self.out_step
            time.sleep(self.outer_delay)
            print(f"Setting {self.set_param.label} to {self.out_setpoint} {self.set_param.unit}")
            self.set_param.set(self.out_setpoint)
            time.sleep(self.outer_delay)
            # Reset our plots
            self.in_sweep.plotter.reset()
            self.in_sweep.start()
            # self.in_sweep.start(persist_data=(self.set_param, self.out_setpoint))
        # If neither of the above are triggered, it means we are at the end of the sweep
        else:
            self.is_running = False
            print(f"Done with the sweep, {self.set_param.label}={self.out_setpoint}")
            self.in_sweep.kill()
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

    def send_updates(self, no_sp=False):
        pass

    def kill(self):
        self.in_sweep.kill()
        super().kill()

        # Gently shut down the heatmap
        if self.heatmap_plotter is not None:
            if not self.heatmap_plotter.wait(1000):
                self.heatmap_plotter.terminate()
                print('forced heatmap to terminate')
            self.heatmap_plotter.clear()
            self.heatmap_plotter = None

    def ramp_to(self, value, start_on_finish=False, multiplier=1):
        """
        Ramps the set_param to a given value, at the same rate as already specified.

        Arguments:
            value - setpoint to ramp towards
            start_on_finish - flag if we want to begin the sweep as soon as we are done ramping
            multiplier - multiplier for the step size, to ramp quicker than the sweep speed
        """
        # Ensure we aren't currently running
        if self.outer_ramp:
            print(f"Currently ramping. Finish current ramp before starting another.")
            return
        if self.is_running:
            print(f"Already running. Stop the sweep before ramping.")
            return

        # Check if we are already at the value
        curr_value = self.set_param.get()
        if abs(value - curr_value) <= self.out_step / 2:
            # print(f"Already within {self.step} of the desired ramp value. Current value: {curr_value},
            # ramp setpoint: {value}.\nSetting our setpoint directly to the ramp value.")
            self.set_param.set(value)
            self.done_ramping(start_on_finish=True)
            return

        # Create a new sweep to ramp our outer parameter to zero
        self.ramp_sweep = Sweep1D(self.set_param, curr_value, value, multiplier * self.out_step,
                                  inter_delay=self.inter_delay,
                                  complete_func=partial(self.done_ramping, start_on_finish),
                                  save_data=False, plot_data=True)

        self.is_running = False
        self.outer_ramp = True
        self.ramp_sweep.start(ramp_to_start=False)

        print(f'Ramping {self.set_param.label} to {value} . . . ')

    def ramp_to_zero(self):
        """
        Ramp our set parameters down to zero.
        """
        print("Ramping both parameters to 0.")
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
        self.is_running = True
        self.outer_ramp = True
        zero_sweep.start()

    def done_ramping(self, start_on_finish=False):
        """
        Function called when our outer sweep parameter has finished ramping to zero. Checks if both parameters
        are done, then tells the system we have finished.
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
        print("Done ramping!")

        if start_on_finish:
            self.start(ramp_to_start=False)
