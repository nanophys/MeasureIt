#threaded_sweeps.py

import io
import time
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
from mpl_toolkits.axes_grid1 import make_axes_locatable
import qcodes as qc
from qcodes.dataset.measurements import Measurement
from IPython import display
from PyQt5.QtCore import QThread, pyqtSignal
import matplotlib.ticker as plticker
from collections import deque

class BaseSweep(object):
    
    def __init__(self, set_param = None, inter_delay = 0.01, save_data = False):
        self._params = []
        self.set_param = set_param
        self.inter_delay = 0.01
        self.save_data = save_data
        
        self.is_running = False
        self.t0 = time.monotonic()
        
    def follow_param(self, *p):
        """
        This function takes in a QCoDeS Parameter p, and tracks it through each sweep.
        """
        for param in p:
            self._params.append(param)
        
    def _create_measurement(self):
        """
        Creates a QCoDeS Measurement object. This controls the saving of data by registering
        QCoDeS Parameter objects, which this function does. Registers all 'tracked' parameters, 
        Returns the measurement object.
        """
        
        self.meas = Measurement()
        self.meas.register_custom_parameter('time', label='Time', unit='s')
        
        if self.set_param is not None:
            self.meas.register_parameter(self.set_param)
        for p in self._params:
            self.meas.register_parameter(p)
            
        return self.meas
    
    def stop(self):
        self.is_running = False
        
    def update_values(self, datasaver = None):
        t = time.monotonic() - self.t0

        data = []
        data.append(('time', t))

        if self.set_param is not None:
            data.append(self.step_param())
            
        for i,p in enumerate(self._params):
            v = p.get()
            data.append((p, v))
    
        if self.save_data:
            datasaver.add_result(*data)
      
        return data
        
class Sweep0D(BaseSweep):
    
    def __init__(self, runner = None, plotter = None, set_param = None, inter_delay = 0.01, save_data = False):
        super().__init__(set_param, inter_delay, save_data)
        
        self.runner = runner
        self.plotter = plotter

    def start(self):
        if self.plotter is None:
            self.plotter = PlotterThread(self)
            self.plotter.create_figs()
        
        if self.runner is None:
            self.runner = RunnerThread(self)
            self.runner.add_plotter(self.plotter)
        
        self.is_running = True
        
        self.plotter.start()
        self.runner.start()
        
 class Sweep1D(BaseSweep):
    
    def __init__(self, set_param, start, stop, step, bidirectional = False, runner = None, plotter = None, 
                 inter_delay = 0.01, save_data = False):
        super().__init__(set_param, inter_delay, save_data)
        
        self.start = start
        self.stop = stop
        self.step = step
        
        if (self.stop - self.start) > 0:
            self.step = abs(self.step)
        else:
            self.step = (-1) * abs(self.step)
        
        self.setpoint = self.start - self.step
        self.bidirectional = bidirectional
        self.runner = runner
        self.plotter = plotter

    def start(self):
        if self.plotter is None:
            self.plotter = PlotterThread(self)
            self.plotter.create_figs()
        
        if self.runner is None:
            self.runner = RunnerThread(self)
            self.runner.add_plotter(self.plotter)
        
        self.is_running = True
        
        self.plotter.start()
        self.runner.start()       
    
    def step_param(self):
        if abs(self.setpoint - self.stop) > abs(self.step/2):
                self.setpoint = self.setpoint + self.step
        # If we want to go both ways, we flip the start and stop, and run again
        if self.bidirectional:
            self.flip_direction()
            while abs(self.setpoint - self.stop) > abs(self.step/2):
                self.iterate(datasaver, persist_data)
                self.flip_direction()
                
    def flip_direction(self):
        """
        Flips the direction of the sweep, to do bidirectional sweeping.
        """
        temp = self.start
        self.start = self.stop
        self.stop = temp
        self.step = -1 * self.step
        self.setpoint -= self.step
        
        # If backwards, go forwards, and vice versa
        if self.direction:
            self.direction = 0
        else:
            self.direction = 1
    
    def ramp_to_zero(self):
        self.stop = 0
        if self.setpoint - self.step > 0:
            self.step = (-1) * abs(self.step)
        else:
            self.step = abs(self.step)
        
        print(f'Ramping {self.set_param.label} to 0 . . . ')
        while abs(self.setpoint - self.stop) > abs(self.step/2):
            self.iterate()
            
        self.set_param.set(0)
        print(f'Done ramping {self.set_param.label} to 0!')
        
    def reset(self, new_params=None):
        """
        Resets the Sweep1D to reuse the same object with the same plots.
        
        Arguments:
            new_params - list of 4 values to determine how we sweep. In order, 
                         must be [ start value, stop value, step, frequency ]
        """
        # Set our new values if desired
        if new_params is not None:
            self.start = new_params[0]
            self.stop = new_params[1]
            self.step = new_params[2]
            self.inter_delay = 1/new_params[3]

        # Reset our setpoint
        self.setpoint = self.start - self.step
        
        # Reset our plots
        self.plotter.reset()
        
        
class RunnerThread(QThread):
    
    completed = pyqtSignal()
    
    def __init__(self, sweep):
        self.sweep = sweep
        self.plotter = None
        
    def __del__(self):
        """
        Standard destructor.
        """
        self.wait()
    
    def add_plotter(self, plotter):
        self.plotter = plotter
        
    def run(self):
        if self.sweep.save_data is True:
            with self.sweep.meas.run() as datasaver:
                while self.sweep.is_running() is True:            
                    data = self.sweep.update_values(datasaver)
                    self.plotter.add_data_to_queue(data)

        else:    
            while self.sweep.is_running() is True:            
                    data = self.sweep.update_values()
                    self.plotter.add_data_to_queue(data)
    
    
    
    
    
class PlotterThread(QThread):
    
    def __init__(self, sweep, setaxline=None, setax=None, axesline=None, axes=[]):
        self.sweep = sweep
        self.data_queue = deque([])
        self.setaxline = setaxline
        self.setax = setax
        self.axesline = axesline
        self.axes = axes
        
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
        
        for i, p in enumerate(self.sweep._params):
            self.axes.append(self.fig.add_subplot(self.grid[:, i]))
            # Create a plot of the sweeping parameters value against time
            self.axes[i].set_xlabel('Time (s)')
            self.axes[i].set_ylabel(f'{p.label} ({p.unit})')
            self.axesline.append(self.axes[i].plot([], [])[0])
            
    def add_data_to_queue(self, data):
        self.data_queue.append(data)
        
    def run(self):
        while self.sweep.is_running() is True:
            t = time.monotonic()
            
            while len(self.data_queue) > 0:
                data = deque(self.data_queue.popleft())
                
                time_data = data.popleft()
                
                if self.sweep.set_param is not None:
                    set_param_data = data.popleft()
                    self.setaxline.set_xdata(np.append(self.setaxline.get_xdata(), time_data[1]))
                    self.setaxline.set_ydata(np.append(self.setaxline.get_ydata(), set_param_data[1]))
                    self.setax.relim()
                    self.setax.autoscale_view()
                    
                for i,data_pair in enumerate(data):                
                    self.axesline[i].set_xdata(np.append(self.axesline[i].get_xdata(), time_data[1]))
                    self.axesline[i].set_ydata(np.append(self.axesline[i].get_ydata(), data_pair[1]))
                    self.axes[i].relim()
                    self.axes[i].autoscale_view()
    
            sleep_time = self.sweep.inter_delay - (time.monotonic() - t)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def reset(self):
        self.setaxline.set_xdata(np.array([]))
        self.setaxline.set_ydata(np.array([]))
        self.setax.relim()
        self.setax.autoscale_view()
        
        for i,p in enumerate(self.sweep._params):
            self.axes[i].set_xdata(np.array([]))
            self.axes[i].set_ydata(np.array([]))
            self.axes[i].relim()
            self.axes[i].autoscale_view()

    
    
    
    
    
    
    
    
    
    
    