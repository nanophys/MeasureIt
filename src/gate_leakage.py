from src.sweep1d import Sweep1D
import time
import numpy as np
from src.util import _autorange_srs

class GateLeakage(Sweep1D):
    def __init__(self, set_param, track_param, max_I, step, limit=np.inf, start=0, *args, **kwargs):
        self.max_I = max_I
        self.flips = 0
        self.track_param = track_param
        self.input_trigger=0
        
        super().__init__(set_param, start, limit, step, **kwargs)
        self.follow_param(self.track_param)
    
    def step_param(self):
        # Our ending condition is if we end up back at 0 after going forwards and backwards
        if self.flips >= 2 and abs(self.setpoint) <= abs(self.step/(3/2)):
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
            
            if (self.step > 0 and v >= abs(1.0001*self.max_I)) or (self.step < 0 and v <= (-1)*abs(1.0001*self.max_I)):
                self.input_trigger += 1
                if self.input_trigger == 2:
                    self.flip_direction()
                    self.setpoint += self.step
                    self.input_trigger = 0
                    print("tripped input limit")
                #return self.step_param()
            
            return [(self.set_param, self.setpoint), (self.track_param, v)]
    
    
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

        data = []
        data.append(('time', t))
        
        data += self.step_param() 
        
        persist_param = None
        if self.persist_data is not None:
            data.append(self.persist_data)
            persist_param = self.persist_data[0]
        
        for i, (l, _, gain) in enumerate(self._srs):
            _autorange_srs(l, 3)
                    
        for i,p in enumerate(self._params):
            if p is not persist_param and p is not self.track_param:
                v = p.get()
                data.append((p, v))
    
        if self.save_data and self.is_running:
            self.runner.datasaver.add_result(*data)
        
        return data
    
    
    def flip_direction(self):
        self.flips += 1
        if self.flips >= 2 and self.setpoint > 0:
            self.step = (-1)*abs(self.step)
            self.end = (-1)*self.end
        elif self.flips >= 2 and self.setpoint < 0:
            self.step = abs(self.step)
            self.end = (-1)*self.end
        elif self.flips < 2:
            self.end = (-1)*self.end
            self.step = -1 * self.step
            self.setpoint -= self.step
        
        # If backwards, go forwards, and vice versa
        if self.direction:
            self.direction = 0
        else:
            self.direction = 1