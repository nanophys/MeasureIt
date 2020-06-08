# simul_sweep.py
import time

from src.sweep1d import Sweep1D
from src.util import _autorange_srs


class SimulSweep(Sweep1D):

    def __init__(self, _p, *args, **kwargs):
        if len(_p.keys()) < 2 or not all(isinstance(p, dict) for p in _p.values()):
            raise ValueError('Must pass at least two Parameters and the associated values as dictionaries.')

        self.simul_params = []
        self.set_params_dict = _p

        # Take the first parameter, and set it as the normal Sweep1D set param
        sp = list(_p.keys())[0]
        # Force time to be on the x axis
        kwargs['x_axis_time'] = 1
        super().__init__(sp, _p[sp]['start'], _p[sp]['stop'], _p[sp]['step'], *args, **kwargs)

        for p, v in self.set_params_dict.items():
            self.simul_params.append(p)

            # Make sure the step is in the right direction
            if (v['stop'] - v['start']) > 0:
                v['step'] = abs(v['step'])
            else:
                v['step'] = (-1) * abs(v['step'])

            v['setpoint'] = v['start'] - v['step']

        n_steps = []
        for key, p in _p.items():
            n_steps.append(int(abs(p['stop'] - p['start']) / abs(p['step'])))

        if not all(steps == n_steps[0] for steps in n_steps):
            raise ValueError('Parameters have a different number of steps for the sweep. The Parameters must have the '
                             'same number of steps to sweep them simultaneously.'
                             f'\nStep numbers: {n_steps}')

        self.follow_param([p for p in self.simul_params if p is not self.set_param])
        self.persist_data = []

    def step_param(self):
        """
        Iterates the parameter.
        """
        rets = []
        ending = False
        self.persist_data = []

        for p, v in self.set_params_dict.items():
            # If we aren't at the end, keep going
            if abs(v['setpoint'] - v['stop']) >= abs(v['step'] / 2):
                v['setpoint'] = v['setpoint'] + v['step']
                p.set(v['setpoint'])
                rets.append((p, v['setpoint']))

            # If we want to go both ways, we flip the start and stop, and run again
            elif self.bidirectional and self.direction == 0:
                self.flip_direction()
                return self.step_param()
            # If neither of the above are triggered, it means we are at the end of the sweep
            else:
                ending = True

        if ending is True:
            if self.save_data:
                self.runner.datasaver.flush_data_to_database()
            self.is_running = False
            print(f"Done with the sweep!")
            for p in self.set_params:
                print(f"{p['param']} = {p['setpoint']} {p['param'].unit}")
            self.flip_direction()
            self.completed.emit()
            if self.parent is None:
                self.runner.kill_flag = True
            return None

        return rets

    def update_values(self):
        """
        Iterates our data points, changing our setpoint if we are sweeping, and refreshing
        the values of all our followed parameters. If we are saving data, it happens here,
        and the data is returned.

        Returns:
            data - A list of tuples with the new data. Each tuple is of the format
                   (<QCoDeS Parameter>, measurement value). The tuples are passed in order of
                   time, then set_param (if applicable), then all the followed params.
        """
        t = time.monotonic() - self.t0

        data = [('time', t)]

        if self.set_param is not None:
            sp_data = self.step_param()
            if sp_data is not None:
                data += sp_data
            else:
                return None

        for i, (l, _, gain) in enumerate(self._srs):
            _autorange_srs(l, 3)

        for i, p in enumerate(self._params):
            if p not in self.simul_params:
                v = p.get()
                data.append((p, v))

        if self.save_data and self.is_running:
            self.runner.datasaver.add_result(*data)

        #self.send_updates()

        return data

    def flip_direction(self):
        """
        Flips the direction of the sweep, to do bidirectional sweeping.
        """
        # If backwards, go forwards, and vice versa
        if self.direction:
            self.direction = 0
        else:
            self.direction = 1

        if self.plot_data is True and self.plotter is not None:
            self.plotter.add_break(self.direction)

        for p, v in self.set_params_dict.items():
            temp = v['start']
            v['start'] = v['stop']
            v['stop'] = temp
            v['step'] = -1 * v['step']
            v['setpoint'] -= v['step']

