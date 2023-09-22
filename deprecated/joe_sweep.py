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
        meas = Measurement()
        for p in set_params:
            meas.register_parameter(p)
        meas.register_custom_parameter('time', label='Time', unit='s')
        for p in self._params:
            meas.register_parameter(p, setpoints=(*set_params, 'time',))
        for l, _, _ in self._sr830s:
            meas.register_parameter(l.X, setpoints=(*set_params, 'time',))
            meas.register_parameter(l.Y, setpoints=(*set_params, 'time',))
        return meas
    
    def sweep(self, set_param, vals, inter_delay=None):
        if inter_delay is not None:
            d = len(vals)*inter_delay
            h, m, s = int(d/3600), int(d/60) % 60, int(d) % 60
            print(f'Minimum duration: {h}h {m}m {s}s')

        fig = plt.figure(figsize=(4*(2 + len(self._params) + len(self._sr830s)),4))
        grid = plt.GridSpec(4, 1 + len(self._params) + len(self._sr830s), hspace=0)
        setax = fig.add_subplot(grid[:, 0])
        setax.set_xlabel('Time (s)')
        setax.set_ylabel(f'{set_param.label} ({set_param.unit})')
        setaxline = setax.plot([], [])[0]

        paxs = []
        plines = []
        for i, p in enumerate(self._params):
            ax = fig.add_subplot(grid[:, 1 + i])
            ax.set_xlabel(f'{set_param.label} ({set_param.unit})')
            ax.set_ylabel(f'{p.label} ({p.unit})')
            paxs.append(ax)
            plines.append(ax.plot([], [])[0])

        laxs = []
        llines = []
        for i, (l, name, _) in enumerate(self._sr830s):
            ax0 = fig.add_subplot(grid[:-1, 1 + len(self._params) + i])
            ax0.set_ylabel(f'{name} (V)')
            fmt = ScalarFormatter()
            fmt.set_powerlimits((-3, 3))
            ax0.get_yaxis().set_major_formatter(fmt)
            laxs.append(ax0)
            llines.append(ax0.plot([], [])[0])
            ax1 = fig.add_subplot(grid[-1, 1 + len(self._params) + i], sharex=ax0)
            ax1.set_ylabel('Phase (°)')
            ax1.set_xlabel(f'{set_param.label} ({set_param.unit})')
            laxs.append(ax1)
            llines.append(ax1.plot([], [])[0])
            plt.setp(ax0.get_xticklabels(), visible=False)

        fig.tight_layout()
        fig.show()

        meas = self._create_measurement(set_param)
        with meas.run() as datasaver:
            t0 = time.monotonic()
            for setpoint in vals:
                t = time.monotonic() - t0
                set_param.set(setpoint)
                
                setaxline.set_xdata(np.append(setaxline.get_xdata(), t))
                setaxline.set_ydata(np.append(setaxline.get_ydata(), setpoint))
                setax.relim()
                setax.autoscale_view()
                
                if inter_delay is not None:
                    plt.pause(inter_delay)

                data = [
                    (set_param, setpoint),
                    ('time', t)
                ]
                for i, p in enumerate(self._params):
                    v = p.get()
                    data.append((p, v))
                    plines[i].set_xdata(np.append(plines[i].get_xdata(), setpoint))
                    plines[i].set_ydata(np.append(plines[i].get_ydata(), v))
                    paxs[i].relim()
                    paxs[i].autoscale_view()
                for i, (l, _, gain) in enumerate(self._sr830s):
                    _autorange_srs(l, 3)
                    x, y = l.snap('x', 'y')
                    x, y = x / gain, y / gain
                    data.extend([(l.X, x), (l.Y, y)])
                    llines[i*2].set_xdata(np.append(llines[i*2].get_xdata(), setpoint))
                    llines[i*2].set_ydata(np.append(llines[i*2].get_ydata(), x))
                    llines[i*2+1].set_xdata(np.append(llines[i*2+1].get_xdata(), setpoint))
                    llines[i*2+1].set_ydata(np.append(llines[i*2+1].get_ydata(), np.arctan2(y, x) * 180 / np.pi))
                    laxs[i*2].relim()
                    laxs[i*2].autoscale_view()
                    laxs[i*2+1].relim()
                    laxs[i*2+1].autoscale_view()

                datasaver.add_result(*data)
                
                fig.tight_layout()
                fig.canvas.draw()
                #plt.pause(0.001)

            d = time.monotonic() - t0
            h, m, s = int(d/3600), int(d/60) % 60, int(d) % 60
            print(f'Completed in: {h}h {m}m {s}s')

            b = io.BytesIO()
            fig.savefig(b, format='png')
            display.display(display.Image(data=b.getbuffer(), format='png'))
