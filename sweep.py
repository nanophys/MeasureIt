import io
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import qcodes as qc
from qcodes.dataset.measurements import Measurement
from IPython import display

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
    def __init__(self):
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
        
    
    def set_figs(self, fig, setax, axes):
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
    
    def iterate(self, datasaver):
        t = time.monotonic() - self.t0
        self.setpoint += self.step
        self.set_param.set(self.setpoint)
                
        self.setaxline.set_xdata(np.append(self.setaxline.get_xdata(), t))
        self.setaxline.set_ydata(np.append(self.setaxline.get_ydata(), self.setpoint))
        self.setax.relim()
        self.setax.autoscale_view()
        
        if self.inter_delay is not None:
            plt.pause(self.inter_delay)

        data = [
            (self.set_param, self.setpoint),
            ('time', t)
        ]
        for i, p in enumerate(self._params):
            v = p.get()
            data.append((p, v))
            self.plines[i].set_xdata(np.append(self.plines[i].get_xdata(), self.setpoint))
            self.plines[i].set_ydata(np.append(self.plines[i].get_ydata(), v))
            self.axes[i].relim()
            self.axes[i].autoscale_view()
#        print(data)
        datasaver.add_result(*data)
                
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

