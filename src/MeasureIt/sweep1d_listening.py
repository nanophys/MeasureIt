# pylint: disable=trailing-whitespace
# sweep1d.py

import time
from .base_sweep import BaseSweep
from .util import safe_set, safe_get
from PyQt5.QtCore import QObject, pyqtSlot
from qcodes.instrument_drivers.american_magnetics.AMI430 import AMI430
from qcodes.instrument_drivers.tektronix.Keithley_2450 import Keithley2450
from functools import partial


class Sweep1D_listening(BaseSweep, QObject):
    """
    Class extending BaseSweep to sweep one independent parameter. 
    This is to set K2450 to a setpoint
    and then listen K2450.sourse.get_latest() to check 
    if it reaches the setpoint. This is for charging a capacitor. 
    
    Attributes
    ---------
    set_param: 
        QCoDeS Parameter to be swept.
    begin:
        The starting value of the sweeping parameter.
    end:
        The ending value of the sweeping parameter.
    step:
        The step size between measured datapoints.
    bidirectional:
        Determines whether or not to run the sweep in both directions.
    runner:
        Assigns the Runner Thread.
    plotter:
        Assigns the Plotter Thread.
    datasaver: 
        Initiated by Runner Thread to enable saving and export of data.
    inter_delay: 
        Time (in seconds) to wait between data points.
    save_data: 
        Flag used to determine if the data should be saved or not.
    plot_data: 
        Flag to determine whether or not to live-plot data.
    complete_func:
        Sets a function to be executed upon completion of the sweep.
    x_axis_time: 
        Defaults to 0 to allow the 'set_param' to be plotted on the x-axis.
    parent:
        Sets a parent Sweep2D object.
    continual:
        Causes sweep to continuously run back and forth between start and stop points.
    plot_bin: 
        Defaults to 1. Used to plot data that has been sent to the 
        data_queue list in the Plotter Thread.
    back_multiplier:
        Factor to scale the step size after flipping directions.
    setpoint:
        The first parameter value where a measurement is obtained after starting.
    direction:
        Either 0 or 1 to indicate the direction of the sweep.
    is_ramping: 
        Flag to determine whether or not sweep is currently ramping to start.
    ramp_sweep:
        Defines the sweep used to set the parameter to its starting value.
    instrument:
        The instrument used to control/monitor the 'set_param'.
        
    Methods
    ---------
    start(persist_data=None, ramp_to_start=True, ramp_multiplier=1)
        Starts the sweep; runs from the BaseSweep start() function.
    stop()
        Stops running any currently active sweeps.
    kill()
        Ends the threads spawned by the sweep and closes any active plots.
    step_param()
        Iterates the parameter.
    step_K2450()
        Used to control sweeps of K2450 Instrument. 
    flip_direction()
        Flips the direction of the sweep, to do bidirectional sweeping.
    ramp_to(value, start_on_finish=False, persist=None, multiplier=1)
        Ramps the set_param to a given value, at a rate dictated by the multiplier.
    ramp_to_zero()
        Ramps the set_param to 0, at the same rate as already specified.
    done_ramping(self, value, start_on_finish=False, pd=None)
        Alerts the sweep that the ramp is finished.
    get_param_setpoint()
        Obtains the current value of the setpoint.
    reset(new_params=None)
        Resets Sweep1D, optional argument to change sweep details.
    """

    def __init__(self, set_param, start, stop, step, bidirectional=False, runner=None, plotter=None, datasaver=None,
                 inter_delay=0.01, save_data=True, plot_data=True, complete_func=None, x_axis_time=0, parent=None,
                 continual=False, plot_bin=1, back_multiplier=1):
        """
        Initializes the sweep.
        
        There are 5 additional parameters not included in the BaseSweep initialization.
        
        Parameters
        ---------
        set param:
            The independent parameter to be swept. Only K2450 object is support. 
        start:
            The value that the sweep will begin from.
        stop:
            The value that the sweep will end at.
        step:
            The step spacing for each measurement.
        complete_func:
            An optional function to be called when the sweep is finished.
        x_axis_time:
            Determines if followed parameters are plotted against time(1) or 'set_param'(0).
        """

        # Initialize the BaseSweep
        QObject.__init__(self)
        if isinstance(set_param, Keithley2450):
            BaseSweep.__init__(self, set_param=set_param, inter_delay=inter_delay, save_data=save_data, plot_data=plot_data,
                           x_axis_time=x_axis_time, datasaver=datasaver, plot_bin=plot_bin, parent=parent,
                           complete_func=complete_func,err = 0.001)
        else:
            raise ValueError('A K2450 instance is needed')

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
        self.continuous = continual
        self.direction = 0
        self.back_multiplier = back_multiplier
        self.is_ramping = False
        self.ramp_sweep = None
        self.runner = runner
        self.plotter = plotter
        self.instrument = self.set_param.instrument
        self.err = err

    def __str__(self):
        return f"1D Sweep of {self.set_param} from {self.begin} to {self.end}, with step size {self.step}."

    def __repr__(self):
        return f"Sweep1D({self.set_param}, {self.begin}, {self.end}, {self.step})"

    def start(self, persist_data=None, ramp_to_start=True, ramp_multiplier=1):
        """
        Starts the sweep; runs from the BaseSweep start() function.
        
        Parameters
        ---------
        persist_data:
            Used to set Sweep2D parameter.
        ramp_to_start:
            Gently sweeps parameter to desired starting value.
        ramp_multiplier:
            Factor to control ramping speed compared to sweep speed.
        """
        
        if self.is_ramping:
            print(f"Still ramping. Wait until ramp is done to start the sweep.")
            return
        if self.is_running:
            print(f"Sweep is already running.")
            return

        print(f"Sweeping {self.set_param.label} to {self.end} {self.set_param.unit}")
        BaseSweep.start(self, persist_data=persist_data)

    def stop(self):
        """ Stops running any currently active sweeps. """
        
        if self.is_ramping and self.ramp_sweep is not None:
            print(f"Stopping the ramp.")
            self.ramp_sweep.stop()
            self.ramp_sweep.kill()

            while self.ramp_sweep.is_running:
                time.sleep(0.2)
            self.done_ramping(self.ramp_sweep.setpoint)
            # self.setpoint=self.ramp_sweep.setpoint
            # self.ramp_sweep.plotter.clear()
            # self.ramp_sweep = None
            # self.is_ramping=False
            # print(f"Stopped the ramp, the current setpoint  is {self.setpoint} {self.set_param.unit}")
        self.set_param.set(safe_get(self.set_param))

        BaseSweep.stop(self)

    def kill(self):
        """ Ends the threads spawned by the sweep and closes any active plots. """
        if self.is_ramping and self.ramp_sweep is not None:
            self.ramp_sweep.stop()
            self.ramp_sweep.kill()
        BaseSweep.kill(self)

    def step_param(self):
        """
        Iterates the parameter and checks for our stop condition.
        
        Returns
        ---------
        Data pair in form of (<set param>, <setpoint>), or None if we have reached the end of our sweep.
        """
        
        # The AMI Magnet sweeps very slowly, so we implement sweeps of it  differently
        # If we are sweeping the magnet, let's deal with it here
        
        return self.step_K2450()

        # # If we aren't at the end, keep going
        # if abs(self.setpoint - self.end) - abs(self.step / 2) > abs(self.step) * 1e-4:
        #     self.setpoint = self.setpoint + self.step
        #     safe_set(self.set_param, self.setpoint)
        #     return [(self.set_param, self.setpoint)]
        # # If we want to go both ways, we flip the start and stop, and run again
        # elif self.continuous:
        #     self.flip_direction()
        #     return self.step_param()
        # elif self.bidirectional and self.direction == 0:
        #     self.flip_direction()
        #     return self.step_param()
        # # If neither of the above are triggered, it means we are at the end of the sweep
        # else:
        #     print(f'Finished the sweep! {self.set_param.label} = {safe_get(self.set_param)} ({self.set_param.unit})')
        #     if self.save_data:
        #         self.runner.flush_flag = True
        #     self.is_running = False
        #     self.flip_direction()
        #     self.completed.emit()
        #     if self.parent is None:
        #         self.runner.kill_flag = True
        #     return None

    def step_K2450(self):
        """
        Used to control sweeps of K2450 Instrument. 
        
        The endpoint is determined prior to the sweep, and the current 
        field is measured during ramping.
        
        Returns
        ---------
        The parameter-value pair that was measured.
        """
        # Grab our data
        try:
            dt = self.set_param.get()
        except Exception as e:
            print(e)
            time.sleep(self.inter_delay)
            dt = self.set_param.get()
        try:
            data_pair = (self.set_param, dt)
            self.setpoint = dt
        except:
            print("got bad data, trying again")
            return self.step_K2450()

        # Check our stop conditions- being at the end point
        if (self.set_param.get_latest()-self.end) < self.err:
            if self.save_data:
                self.runner.flush_flag = True
            self.is_running = False
            print(f"Done with the sweep, {self.set_param.label}={self.set_param.get()}")
            self.flip_direction()
            self.completed.emit()
            if self.parent is None:
                self.runner.kill_flag = True

        # Return our data pair, just like any other sweep
        return [data_pair]

    def flip_direction(self):
        """ Flips the direction of the sweep, to do bidirectional sweeping. """
        # If backwards, go forwards, and vice versa
        if self.direction:
            self.direction = 0
            self.step /= self.back_multiplier
        else:
            self.direction = 1
            self.step *= self.back_multiplier

        self.send_updates(no_sp=True)

        temp = self.begin
        self.begin = self.end
        self.end = temp
        self.step = -1 * self.step
        self.setpoint -= self.step

        if self.plot_data is True and self.plotter is not None:
            self.add_break.emit(self.direction)

    def ramp_to(self, value, start_on_finish=False, multiplier=1):
        """
        Ramps the set_param to a given value, at a rate dictated by the multiplier.
        
        Parameters
        ---------
        value:
            The desired starting value for the sweep.
        start_on_finish:
            Flag to determine whether to begin the sweep as soon as ramp is finished.
        multiplier:
            Factor to alter the step size, used to ramp quicker than the sweep speed.
        """

        # Ensure we aren't currently running
        if self.is_ramping:
            print(f"Currently ramping. Finish current ramp before starting another.")
            return
        if self.is_running:
            print(f"Already running. Stop the sweep before ramping.")
            return

        # Check if we are already at the value
        curr_value = safe_get(self.set_param)
        if abs(value - curr_value) - abs(self.step/2) < abs(self.step) * 1e-4:
            # print(f"Already within {self.step} of the desired ramp value. Current value: {curr_value},
            # ramp setpoint: {value}.\nSetting our setpoint directly to the ramp value.")
            self.done_ramping(value, start_on_finish, persist)
            return

        # Create a new sweep to ramp our outer parameter to zero
        self.ramp_sweep = Sweep1D(self.set_param, curr_value, value, multiplier * self.step,
                                  inter_delay=self.inter_delay,
                                  complete_func=partial(self.done_ramping, value, start_on_finish, persist),
                                  save_data=False, plot_data=self.plot_data)

        self.is_running = False
        self.is_ramping = True
        self.ramp_sweep.start(ramp_to_start=False)

        print(f'Ramping {self.set_param.label} to {value} . . . ')

    def ramp_to_zero(self):
        """ Ramps the set_param to 0, at the same rate as already specified. """
        
        self.end = 0
        if self.setpoint - self.end > 0:
            self.step = (-1) * abs(self.step)
        else:
            self.step = abs(self.step)

        print(f'Ramping {self.set_param.label} to 0 . . . ')
        self.start()

    @pyqtSlot()
    def done_ramping(self, value, start_on_finish=False, pd=None):
        """
        Alerts the sweep that the ramp is finished.
        
        Parameters
        ---------
        value:
            The starting value for the sweep, also the current parameter value.
        start_on_finish:
            Sweep will be called to start immediately after ramping when set to True.
        pd:
            Sets persistent data if running Sweep2D.
        """
        
        self.is_ramping = False
        self.is_running = False
        # Grab the beginning 
        # value = self.ramp_sweep.begin

        # Check if we are at the value we expect, otherwise something went wrong with the ramp
        if abs(safe_get(self.set_param) - value) - abs(self.step/2) > abs(self.step) * 1e-2:
            print(f'Ramping failed (possible that the direction was changed while ramping). '
                  f'Expected {self.set_param.label} final value: {value}. Actual value: {safe_get(self.set_param)}. '
                  f'Stopping the sweep.')

            if self.ramp_sweep is not None:
                self.ramp_sweep.kill()
                self.ramp_sweep = None

            return

        print(f'Done ramping {self.set_param.label} to {value}')
        safe_set(self.set_param, value)
        self.setpoint = value - self.step
        # if self.ramp_sweep is not None and self.ramp_sweep.plotter is not None:
        #    self.ramp_sweep.plotter.clear()

        if self.ramp_sweep is not None:
            self.ramp_sweep.kill()
            self.ramp_sweep = None

        if start_on_finish is True:
            self.start(persist_data=pd, ramp_to_start=False)

    def get_param_setpoint(self):
        """ Obtains the current value of the setpoint. """
        
        return f'{self.set_param.label} = {safe_get(self.set_param)} {self.set_param.unit}'

    def reset(self, new_params=None):
        """
        Resets Sweep1D, optional argument to change sweep details.
        
        Parameters
        ---------
        new_params:
            A list of 4 values to determine how we sweep. 
            [ start value, stop value, step, frequency ]
        """

        # Set our new values if desired
        if new_params is not None:
            self.begin = new_params[0]
            self.end = new_params[1]
            self.step = new_params[2]
            self.inter_delay = 1 / new_params[3]

        # Reset our setpoint
        self.setpoint = self.begin - self.step

        # Reset our plots
        self.plotter = None
        self.runner = None

    def __del__(self):
        """
        Destructor. Should delete all child threads and close all figures when the sweep object is deleted.
        """
        self.kill()
