# sweep1d.py

import time
from src.base_sweep import BaseSweep
from PyQt5.QtCore import pyqtSignal
from qcodes.instrument_drivers.american_magnetics.AMI430 import AMI430
#from qcodes.instrument_drivers.oxford.IPS120 import OxfordInstruments_IPS120

class Sweep1D(BaseSweep):
    """
    Class extending BaseSweep to sweep one parameter.
    """
    # Signal for when the sweep is completed
    completed = pyqtSignal()
    
    def __init__(self, set_param, start, stop, step, bidirectional = False, runner = None, plotter = None, datasaver = None,
                 inter_delay = 0.01, save_data = True, plot_data = True, complete_func = None, x_axis_time = 1, 
                 instrument = None, parent = None, continual = False, plot_bin=1):
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
        super().__init__(set_param=set_param, inter_delay=inter_delay, save_data=save_data, plot_data=plot_data, 
                         x_axis=x_axis_time, datasaver=datasaver, parent=parent, plot_bin=plot_bin)
        
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
        self.instrument = instrument
        self.continuous = continual
        
        self.magnet_initialized = False
        
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
            self.ramp_sweep.kill()

            while self.ramp_sweep.is_running == True:
                time.sleep(0.2)
            self.done_ramping(self.ramp_sweep.setpoint)
            #self.setpoint=self.ramp_sweep.setpoint
            #self.ramp_sweep.plotter.clear()
            #self.ramp_sweep = None
            #self.is_ramping=False
            #print(f"Stopped the ramp, the current setpoint  is {self.setpoint} {self.set_param.unit}")
            
        if isinstance(self.instrument, AMI430):
            self.set_param.set(self.set_param.get())

        super().stop()
        
        
    def step_param(self):
        """
        Iterates the parameter.
        """
        # The AMI Magnet sweeps very slowly, so we implement sweeps of it  differently
        # If we are sweeping the magnet, let's deal with it here
        if isinstance(self.instrument, AMI430) and str(self.set_param) == 'Magnet_field':
            return self.step_AMI430()
#        elif isinstance(self.instrument, OxfordInstruments_IPS120):
#            return self.step_IPS120()
        
        # If we aren't at the end, keep going
        if abs(self.setpoint - self.end) >= abs(self.step/2):
            self.setpoint = self.setpoint + self.step
            self.set_param.set(self.setpoint)
            return [(self.set_param, self.setpoint)]
        # If we want to go both ways, we flip the start and stop, and run again
        elif self.continuous:
            self.flip_direction()
            return self.step_param()
        elif self.bidirectional and self.direction == 0:
            self.flip_direction()
            return self.step_param()
        # If neither of the above are triggered, it means we are at the end of the sweep
        else:
            if self.save_data:
                self.runner.datasaver.flush_data_to_database()
            self.is_running = False
            print(f"Done with the sweep, {self.set_param.label}={self.setpoint}")
            self.flip_direction()
            self.completed.emit()
            if self.parent is None:
                self.runner.kill_flag = True
            return [(self.set_param, -1)]
            
            
    def step_AMI430(self):
        """
        Function to deal with sweeps of AMI430. Instead of setting intermediate points, we set the endpoint at the
        beginning, then ask it for the current field while it is ramping.
        """
        # Check if we have set the magnetic field yet
        if self.magnet_initialized == False:
            self.instrument.set_field(self.end, block=False)
            self.magnet_initialized = True
            time.sleep(self.inter_delay)
            try:
                while self.instrument.ramping_state.get() != 'ramping':
                    time.sleep(self.inter_delay)
            except Exception as e:
                print(e)
                time.sleep(self.inter_delay)
                
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
            return self.step_AMI430()
        
        # Check our stop conditions- being at the end point
        if self.instrument.ramping_state() == 'holding':
            self.magnet_initialized = False
            if self.save_data:
                self.runner.datasaver.flush_data_to_database()
            self.is_running = False
            print(f"Done with the sweep, {self.set_param.label}={self.set_param.get()}")
            self.flip_direction()
            self.completed.emit()
            if self.parent is None:
                self.runner.kill_flag = True
        
        # Return our data pair, just like any other sweep
        return [data_pair]
            
        
    def step_IPS120(self):
        """
        Function to deal with sweeps of IPS120. Instead of setting intermediate points, we set the endpoint at the
        beginning, then ask it for the current field while it is ramping.
        """
        # Check if we have set the magnetic field yet
        if self.magnet_initialized == False:
            print("Attaching the heater switch. Waiting 40 s . . .")
            # Attach the heater switch
            self.instrument.switch_heater.set(1)
            # Set the field setpoint
            self.instrument.field_setpoint.set(self.end)
            # Set us to go to setpoint
            self.instrument.activity(1)
            self.magnet_initialized = True
        
        # Grab our data
        data_pair = (self.set_param, self.set_param.get())
        # Check our stop conditions- being at the end point
        if self.instrument.mode2() == 'At rest':
            self.is_running = False
            print("Detaching the heater switch. Waiting 40 s . . . ")
            # Detach the heater switch
            self.instrument.switch_heater.set(2)
            # Set status to 'hold'
            self.instrument.activity(0)
            self.magnet_initialized = False
        
        # Return our data pair, just like any other sweep
        return data_pair
        
        
    def flip_direction(self):
        """
        Flips the direction of the sweep, to do bidirectional sweeping.
        """
        # If backwards, go forwards, and vice versa
        if self.direction:
            self.direction = 0
        else:
            self.direction = 1
            
        self.send_updates()
            
        temp = self.begin
        self.begin = self.end
        self.end = temp
        self.step = -1 * self.step
        self.setpoint -= self.step
        
        if self.plot_data is True and self.plotter is not None:
            self.plotter.add_break(self.direction)
            
        
    
    
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
                             complete_func = lambda: self.done_ramping(value, start_on_finish, persist), save_data = False, plot_data = True)
        self.is_running = False
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
        if self.ramp_sweep is not None and self.ramp_sweep.plotter is not None:
            self.ramp_sweep.plotter.clear()
        
        #self.ramp_sweep.kill()
        
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