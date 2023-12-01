from .sweep1d import Sweep1D
from .util import _autorange_srs
import time
import numpy as np
from PyQt5.QtCore import QObject


class GateLeakage(Sweep1D, QObject):
    """
    Extension of Sweep1D to perform gate leakage measurements.
    
    Includes additional max current safety parameter, sets the Sweep1D independent
    variable range from 0 to infinity, and presents new methods to alert the sweep
    to change direction. The intent is for the 'set_param' to sweep through a range
    of voltages while the 'track_param' reports the resulting current data.
    
    Attributes
    ---------
    set_param:
        The independent variable to be swept through a desired range.
    track_param:
        The followed parameter to be measured during the sweep.
    max_I:
        The maximum allowed value for the followed parameter; 
        the sweep will change directions if surpassed.
    step:
        The step size for the independent variable sweep.
    limit:
        The end value for Sweep1D. Defaults to nfinity.
    start:
        The start value for Sweep1D. Defaults to zero.
    flips:
        Tracks the number of times the sweep has changed direction.
    input_trigger:
        Increases when followed parameter value is greater than 'max_I'.
    
    Methods
    ---------
    step_param()
        Runs sweep once in both directions while measuring 'track_param'.
    update_values()
        Keeps record of independent variable data during sweep.
    flip_direction()
        Changes direction of the sweep.
    """

    def __init__(self, set_param, track_param, max_I, step, limit=np.inf, start=0, **kwargs):
        self.max_I = max_I
        self.flips = 0
        self.track_param = track_param
        self.input_trigger = 0

        Sweep1D.__init__(self, set_param, start, limit, step, **kwargs)
        QObject.__init__(self)

        self.follow_param(self.track_param)

    def step_param(self):
        """
        Runs Sweep1D in both directions by step size.
        
        Stores data of followed 'track_param' at each setpoint of 'set_param'.
        Changes the direction of the sweep if the 'input_trigger' reaches 2 (based
        on breaching of max_I), or when either end of the 'set_param' range is met.
        Sweep ends after two direction changes.
        
        Returns
        ---------
        A list containing the values of 'set_param' and 'track_param' for each
        setpoint until the sweep is stopped after 2 total flips.
        """
        
        # Our ending condition is if we end up back at 0 after going forwards and backwards
        if self.flips >= 2 and abs(self.setpoint) <= abs(self.step / (3 / 2)):
            self.flips = 0
            if self.save_data:
                self.runner.datasaver.flush_data_to_database()
            self.is_running = False
            print(f"Done with the sweep, {self.set_param.label}={self.setpoint}")
            self.completed.emit()
            if self.parent is None:
                self.runner.kill_flag = True
            return [(self.set_param, -1)]

        if abs(self.end) != np.inf and abs(self.setpoint - self.end) <= abs(self.step):
            self.flip_direction()
            print("tripped output limit")
            return self.step_param()
        else:
            self.setpoint += self.step
            self.set_param.set(self.setpoint)

            v = self.track_param.get()

            if (self.step > 0 and v >= abs(1.0001 * self.max_I)) or (
                    self.step < 0 and v <= (-1) * abs(1.0001 * self.max_I)):
                self.input_trigger += 1
                if self.input_trigger == 2:
                    self.flip_direction()
                    self.setpoint += self.step
                    self.input_trigger = 0
                    print("tripped input limit")
                # return self.step_param()

            return [(self.set_param, self.setpoint), (self.track_param, v)]

    def update_values(self):
        """
        Iterates and keeps record of independent variable data during sweep.
        
        Iterates each 'set_param' individually beginning with time. 
        If we are saving data, it happens here, and the data is returned.
        
        Returns
        ---------
        data:
            A list of tuples with the new data. Each tuple is of the format 
            (<QCoDeS Parameter>, measurement value). The tuples are passed in order of
            time, then set_param (if applicable), then all the followed params.
        """
        
        t = time.monotonic() - self.t0

        data = []
        data.append(('time', t))

        data += self.step_param()

        persist_param = None
        if self.persist_data is not None:
            data.append(self.persist_data)
            persist_param = self.persist_data[0]

        for i, (l, _, gain) in enumerate(self._srs):
            _autorange_srs(l, 3)

        for i, p in enumerate(self._params):
            if p is not persist_param and p is not self.track_param:
                v = p.get()
                data.append((p, v))

        if self.save_data and self.is_running:
            self.runner.datasaver.add_result(*data)

        return data

    def flip_direction(self):
        """ Changes direction of the sweep. """
        self.flips += 1
        if self.flips >= 2 and self.setpoint > 0:
            self.step = (-1) * abs(self.step)
            self.end = (-1) * self.end
        elif self.flips >= 2 and self.setpoint < 0:
            self.step = abs(self.step)
            self.end = (-1) * self.end
        elif self.flips < 2:
            self.end = (-1) * self.end
            self.step = -1 * self.step
            self.setpoint -= self.step

        # If backwards, go forwards, and vice versa
        if self.direction:
            self.direction = 0
        else:
            self.direction = 1
