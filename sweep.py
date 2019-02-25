import io
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import qcodes as qc
from qcodes.dataset.measurements import Measurement
from IPython import display
from PyQt5.QtCore import QThread, pyqtSignal

def _autorange_srs(srs, max_changes=1):
    def autorange_once():
        r = srs.R.get()
        sens = srs.sensitivity.get()
        if r > 0.9 * sens:
            return srs.increment_sensitivity()
        elif r < 0.1 * sens:
            return srs.decrement_sensitivity()
        return False
    sets = 0
    while autorange_once() and sets < max_changes:
        sets += 1
        time.sleep(10*srs.time_constant.get())

class Sweep(object):
    def __init__(self, plot=False, auto_figs=False):
        self.plot = plot
        self.auto_figs = auto_figs
        self.figs_set = False
        self._sr830s = []
        self._params = []
    
    def follow_param(self, p):
        self._params.append(p)

    def follow_sr830(self, l, name, gain=1.0):
        self._sr830s.append((l, name, gain))

    def _create_measurement(self, *set_params):
        self.meas = Measurement()
        for p in set_params:
            self.meas.register_parameter(p)
        self.meas.register_custom_parameter('time', label='Time', unit='s')
        for p in self._params:
            self.meas.register_parameter(p, setpoints=(*set_params, 'time',))
        for l, _, _ in self._sr830s:
            self.meas.register_parameter(l.X, setpoints=(*set_params, 'time',))
            self.meas.register_parameter(l.Y, setpoints=(*set_params, 'time',))
            
        return self.meas
        
    def create_figs(self):
        self.fig = plt.figure(figsize=(4*(2 + len(self._params) + len(self._sr830s)),4))
        self.grid = plt.GridSpec(4, 1 + len(self._params) + len(self._sr830s), hspace=0)
        self.setax = self.fig.add_subplot(self.grid[:, 0])
        self.setax.set_xlabel('Time (s)')
        self.setax.set_ylabel(f'{self.set_param.label} ({self.set_param.unit})')
        self.setaxline = self.setax.plot([], [])[0]
        
        self.plines = []
        self.axes = []
        for i, p in enumerate(self._params):
            self.axes.append(self.fig.add_subplot(self.grid[:, 1 + i]))
            self.axes[i].set_xlabel(f'{self.set_param.label} ({self.set_param.unit})')
            self.axes[i].set_ylabel(f'{p.label} ({p.unit})')
            self.plines.append(self.axes[i].plot([], [])[0])
            
        self.figs_set = True
            
    def set_figs(self, fig, setax, axes):
        self.figs_set = True
        self.fig = fig
        self.setax = setax
        self.axes = axes
    
        self.setax.set_xlabel('Time (s)')
        self.setax.set_ylabel(f'{self.set_param.label} ({self.set_param.unit})')
        self.setaxline = setax.plot([], [])[0]
        
        self.plines = []
        for i, p in enumerate(self._params):
            self.axes[i].set_xlabel(f'{self.set_param.label} ({self.set_param.unit})')
            self.axes[i].set_ylabel(f'{p.label} ({p.unit})')

            self.plines.append(self.axes[i].plot([], [])[0])
    
    def autorun(self):
        if self.plot and self.auto_figs and not self.figs_set:
            self.create_figs()
        
        with self.meas.run() as datasaver:
            while abs(self.setpoint - self.stop) > abs(self.step/2):
                self.iterate(datasaver)
            return
            
    def iterate(self, datasaver):
        if self.plot is True and self.figs_set is False:
            return 0
        
        t = time.monotonic() - self.t0
        self.setpoint = self.step + self.setpoint
        self.set_param.set(self.setpoint)
               
        if self.plot is True:
            self.setaxline.set_xdata(np.append(self.setaxline.get_xdata(), t))
            self.setaxline.set_ydata(np.append(self.setaxline.get_ydata(), self.setpoint))
            self.setax.relim()
            self.setax.autoscale_view()
        
        if self.inter_delay is not None:
            time.sleep(self.inter_delay)

        data = [
            (self.set_param, self.setpoint),
            ('time', t)
        ]
        for i, p in enumerate(self._params):
            v = p.get()
            data.append((p, v))
            if self.plot is True:
                self.plines[i].set_xdata(np.append(self.plines[i].get_xdata(), self.setpoint))
                self.plines[i].set_ydata(np.append(self.plines[i].get_ydata(), v))
                self.axes[i].relim()
                self.axes[i].autoscale_view()
            
        datasaver.add_result(*data)
        
        if self.plot is True:        
            self.fig.tight_layout()
            self.fig.canvas.draw()
            plt.pause(0.001)
        return data
    
    def init_sweep(self, set_param, start, stop, step, freq):
        self.set_param = set_param
        self.start = start
        self.stop = stop
        self.step = step
        self.inter_delay = 1/freq
        self.t0 = time.monotonic()
        self.setpoint = self.start - self.step
        
        d = (stop-start)/step*self.inter_delay
        h, m, s = int(d/3600), int(d/60) % 60, int(d) % 60
        print(f'Minimum duration: {h}h {m}m {s}s')

        self.meas = self._create_measurement(self.set_param)
        return self.meas
    
    def save(self):
        b = io.BytesIO()
        self.fig.savefig(b, format='png')






class SweepThread(QThread):
    completed = pyqtSignal()
    update_plot = pyqtSignal()
    
    def __init__(self, parent, s):
        self.parent = parent
        self.s = s
        self.data = []
        QThread.__init__(self)
        self.completed.connect(self.parent.thread_finished)
        self.update_plot.connect(lambda: self.parent.update_plot(self.data))
        
    def __del__(self):
        self.wait()
        
    def run(self):
        with self.parent.meas.run() as datasaver:
            while self.parent.running is True: 
                self.data = self.s.iterate(datasaver)
                self.parent.curr_val = self.data[0][1]
                self.update_plot.emit()
                if abs(self.parent.curr_val - self.parent.v_end) <= abs(self.parent.v_step/2):
                    self.completed.emit()
                    break



        































