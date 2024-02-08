# simul_sweep.py
import math
import time
from functools import partial

from PyQt5.QtCore import pyqtSlot, QObject

from .base_sweep import BaseSweep
from .util import _autorange_srs, safe_set, safe_get


class SimulSweep(BaseSweep, QObject):
    """
    Child of BaseSweep used to simultaneously run sweeps on multiple parameters.
    
    Parameters must be split into equivalent step intervals. The first key in 
    the '_p' dictionary is used as the independent variable passed to BaseSweep
    in the same manner as the Sweep1D 'set_param'.
    
    Attributes
    ---------
    _p:
        Dictionary used to pass parameters and their associated information.
    n_steps:
        Integer value of number of steps for each parameter to take, instead of offering step sizes in _p
    bidirectional:
        Set to True to run the sweep in both directions.
    continuous:
        Set to True to keep sweep running indefinitely.
    *args:
        Optional sweep arguments to be passed in BaseSweep.
    **kwargs:
        Optional keyword arguments to be passed in BaseSweep.
    simul_params:
        Used to store the parameters from the input '_p' dictionary.
    set_params_dict:
        Stores input parameter dictionary.
    direction:
        Tells sweep which direction to run; either 0 or 1.
    is_ramping:
        Flag to alert that the sweep is ramping a parameter to a staring value.
    ramp_sweep:
        Iterates parameters to their starting values before sweep begins.
    runner:
        Assigns the desired Runner Thread.
    plotter:
        Assigns the desired Plotter Thread.
    err:
        Tolerance for considering rounding errors when determining when the sweep has finished.
        
    Methods
    ---------
    start(persist_data, ramp_to_start, ramp_multiplier)
        Begins a BaseSweep, creates necessary measurement objects and threads.
    stop()
        Stops the BaseSweep.
    kill()
        Ends all threads and closes any active plots.
    send_updates(no_sp)
        Passed in this class.
    step_param()
        Iterates each parameter based on step size.
    update_values()
        Returns updated parameter-value pairs, default parameter is time.
    ramp_to_zero(params=None)
        Ramps value of all parameters to zero.
    ramp_to(vals_dict, start_on_finish=False, persist=None, multiplier=1)
        Begins ramping parameters to assigned starting values.
    done_ramping(self, vals_dict, start_on_finish=False, pd=None)
        Ensures that each parameter is at its start value and ends ramp.
    flip_direction()
        Changes the direction of the sweep.
    """

    def __init__(self, _p, n_steps=None, err=0.1, bidirectional=False, continual=False, *args, **kwargs):
        if len(_p.keys()) < 1 or not all(isinstance(p, dict) for p in _p.values()):
            raise ValueError('Must pass at least one Parameter and the associated values as dictionaries.')

        self.simul_params = []
        self.set_params_dict = _p.copy()
        self.direction = 0
        self.n_steps = n_steps
        self.is_ramping = False
        self.ramp_sweep = None
        self.err = err

        # Take the first parameter, and set it as the normal Sweep1D set param
        sp = list(_p.keys())[0]
        # Force time to be on the x axis
        kwargs['x_axis_time'] = 1
        QObject.__init__(self)
        BaseSweep.__init__(self, set_param=sp, *args, **kwargs)

        self.bidirectional = bidirectional
        self.continuous = continual
        
        if n_steps is not None:
            for p, v in self.set_params_dict.items():
                v['step'] = (v['stop'] - v['start'])/n_steps
        else:
            _n_steps = []
            for key, p in _p.items():
                _n_steps.append(int(abs(p['stop'] - p['start']) / abs(p['step'])))

            if not all(steps == _n_steps[0] for steps in _n_steps):
                raise ValueError('Parameters have a different number of steps for the sweep. The Parameters must have '
                                 'the same number of steps to sweep them simultaneously.'
                                 f'\nStep numbers: {_n_steps}')
            self.n_steps = _n_steps[0]

        for p, v in self.set_params_dict.items():
            self.simul_params.append(p)

            # Make sure the step is in the right direction
            if (v['stop'] - v['start']) > 0:
                v['step'] = abs(v['step'])
            else:
                v['step'] = (-1) * abs(v['step'])

            v['setpoint'] = safe_get(p) - v['step']

        self.follow_param([p for p in self.simul_params if p is not self.set_param])
        self.persist_data = []

    def __str__(self):
        p_desc = ''
        n_params = len(self.simul_params)

        for n, item in enumerate(self.set_params_dict.items()):
            p, v = item
            if n < n_params-2:
                p_desc += f"{p.label} from {v['start']} to {v['stop']}, with step {v['step']}, "
            elif n == n_params-2:
                p_desc += f"{p.label} from {v['start']} to {v['stop']}, with step {v['step']}, and "
            elif n == n_params-1:
                p_desc += f"{p.label} from {v['start']} to {v['stop']}, with step {v['step']}."

        return f"SimulSweep of {p_desc}"

    def __repr__(self):
        return f"SimulSweep({[(p.label, v['start'], v['stop'], v['step']) for p, v in self.set_params_dict.items()]})"

    def start(self, persist_data=None, ramp_to_start=True, ramp_multiplier=1):
        """
        Starts the sweep. Runs from the BaseSweep start() function.
        """
        if self.is_ramping is True:
            self.print_main.emit(f"Still ramping. Wait until ramp is done to start the sweep.")
            return
        if self.is_running is True:
            self.print_main.emit(f"Sweep is already running.")
            return

        if ramp_to_start is True:
            self.print_main.emit(f"Ramping to our starting setpoints.")
            vals_dict = {}
            for p in self.simul_params:
                vals_dict[p] = self.set_params_dict[p]['start']
            self.ramp_to(vals_dict, start_on_finish=True, persist=persist_data, multiplier=ramp_multiplier)
        else:
            self.print_main.emit(f"Starting our sweep.")
            super().start(persist_data=persist_data, ramp_to_start=False)

    def stop(self):
        if self.is_ramping and self.ramp_sweep is not None:
            self.print_main.emit(f"Stopping the ramp.")
            self.ramp_sweep.stop()
            self.ramp_sweep.kill()

            while self.ramp_sweep.is_running:
                time.sleep(0.2)
            vals_dict = {}
            for p, v in self.ramp_sweep.set_params_dict.items():
                vals_dict[p] = v['setpoint']
            self.done_ramping(vals_dict)

        super().stop()

    def kill(self):
        if self.is_ramping and self.ramp_sweep is not None:
            self.ramp_sweep.stop()
            self.ramp_sweep.kill()
        super().kill()

    def send_updates(self, no_sp=True):
        pass

    def step_param(self):
        """
        Iterates the parameter.
        """
        rets = []
        ending = False
        self.persist_data = []
        start_dir = self.direction

        for p, v in self.set_params_dict.items():
            # If we aren't at the end, keep going
            if abs(v['setpoint'] - v['stop']) - abs(v['step'] / 2) > abs(v['step']) * self.err:
                v['setpoint'] = v['setpoint'] + v['step']
                safe_set(p, v['setpoint'])
                rets.append((p, v['setpoint']))

            # If we want to go both ways, we flip the start and stop, and run again
            elif self.bidirectional and self.direction == 0:
                self.flip_direction()
                return self.step_param()
            elif self.continuous and self.direction == start_dir:
                self.flip_direction()
                return self.step_param()
            # If neither of the above are triggered, it means we are at the end of the sweep
            else:
                ending = True

        if ending is True:
            if self.save_data:
                self.runner.datasaver.flush_data_to_database()
            self.is_running = False
            self.print_main.emit(f"Done with the sweep!")
            for p, v in self.set_params_dict.items():
                self.print_main.emit(f"{p.label} = {v['setpoint']} ({p.unit})")
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

        sp_data = self.step_param()
        if sp_data is not None:
            data += sp_data
        else:
            return None

        for i, (l, _, gain) in enumerate(self._srs):
            _autorange_srs(l, 3)

        for i, p in enumerate(self._params):
            if p not in self.simul_params:
                v = safe_get(p)
                data.append((p, v))

        if self.save_data and self.is_running:
            self.runner.datasaver.add_result(*data)

        # self.send_updates()

        return data

    def ramp_to_zero(self, params=None):
        if params is None:
            params = self.simul_params
        vals_dict = {}
        for p in params:
            vals_dict[p] = 0
        self.ramp_to(vals_dict)

    def ramp_to(self, vals_dict, start_on_finish=False, persist=None, multiplier=1):
        # Ensure we aren't currently running
        if self.is_ramping:
            self.print_main.emit(f"Currently ramping. Finish current ramp before starting another.")
            return
        if self.is_running:
            self.print_main.emit(f"Already running. Stop the sweep before ramping.")
            return

        ramp_params_dict = {}
        n_steps = 1
        for p, v in vals_dict.items():
            if p not in self.set_params_dict.keys():
                self.print_main.emit("Cannot ramp parameter not in our sweep.")
                return
            
            p_step = self.set_params_dict[p]['step']
            if abs(v - safe_get(p)) - abs(p_step / 2) < abs(p_step) * self.err:
                continue

            ramp_params_dict[p] = {}
            ramp_params_dict[p]['start'] = safe_get(p)
            ramp_params_dict[p]['stop'] = v

            p_steps = abs((ramp_params_dict[p]['stop'] - ramp_params_dict[p]['start']) /
                          p_step * multiplier)
            if p_steps > n_steps:
                n_steps = math.ceil(p_steps)

        if len(ramp_params_dict.keys()) == 0:
            self.print_main.emit("Already at the values, no ramp needed.")
            self.done_ramping(vals_dict, start_on_finish=start_on_finish, pd=persist)
            return

        for p, v in ramp_params_dict.items():
            v['step'] = (v['stop'] - v['start']) / n_steps

        self.ramp_sweep = SimulSweep(ramp_params_dict, n_steps=n_steps, inter_delay=self.inter_delay, plot_data=True, save_data=False,
                                     complete_func=partial(self.done_ramping, vals_dict, 
                                                           start_on_finish=start_on_finish, pd=persist))
        self.ramp_sweep.follow_param(self._params)
        self.is_ramping = True
        self.is_running = False
        self.ramp_sweep.start(ramp_to_start=False)

    @pyqtSlot()
    def done_ramping(self, vals_dict, start_on_finish=False, pd=None):
        self.is_ramping = False
        self.is_running = False

        # Check if we are at the value we expect, otherwise something went wrong with the ramp
        for p, v in vals_dict.items():
            p_step = self.set_params_dict[p]['step']
            if abs(safe_get(p) - v) - abs(p_step / 2) > abs(p_step) * self.err:
                self.print_main.emit(f'Ramping failed (possible that the direction was changed while ramping). '
                      f'Expected {p.label} final value: {v}. Actual value: {safe_get(p)}. '
                      f'Stopping the sweep.')

                if self.ramp_sweep is not None:
                    self.ramp_sweep.kill()
                    self.ramp_sweep = None

                return

        self.print_main.emit(f'Done ramping!')
        for p, v in vals_dict.items():
            safe_set(p, v)
            self.set_params_dict[p]['setpoint'] = v - self.set_params_dict[p]['step']

        if self.ramp_sweep is not None:
            self.ramp_sweep.kill()
            self.ramp_sweep = None

        if start_on_finish is True:
            self.start(ramp_to_start=False, persist_data=pd)

    def flip_direction(self):
        """
        Flips the direction of the sweep, to do bidirectional sweeping.
        """
        # If backwards, go forwards, and vice versa
        if self.direction:
            self.direction = 0
            for p, v in self.set_params_dict.items():
                temp = v['start']
                v['start'] = v['stop']
                v['stop'] = temp
                v['step'] = -1 * v['step'] / self.back_multiplier
                v['setpoint'] -= v['step']
        else:
            self.direction = 1
            for p, v in self.set_params_dict.items():
                temp = v['start']
                v['start'] = v['stop']
                v['stop'] = temp
                v['step'] = -1 * v['step'] * self.back_multiplier
                v['setpoint'] -= v['step']

        if self.plot_data is True and self.plotter is not None:
            self.plotter.add_break(self.direction)

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
        t_est = self.n_steps * self.inter_delay

        hours = int(t_est / 3600)
        minutes = int((t_est % 3600) / 60)
        seconds = t_est % 60
        if verbose is True:
            self.print_main.emit(f'Estimated time for {repr(self)} to run: {hours}h:{minutes:2.0f}m:{seconds:2.0f}s')
        return t_est


