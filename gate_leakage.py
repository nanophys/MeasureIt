from threaded_sweep import Sweep1D, RunnerThread, PlotterThread


class GateLeakage(Sweep1D):
    def __init__(self, set_param, track_param, max_I, step, limit=0, start=0, *args, **kwargs):
        self.max_I = max_I
        self.flips = 0
        
        super().__init__(set_param, start, limit, step, **kwargs)
        
        
    def step_param(self):
        # Our ending condition is if we end up back at 0 after going forwards and backwards
        if self.flips == 2 and abs(self.setpoint) <= abs(self.step/2):
            self.flips = 0
            if self.save_data:
                self.runner.datasaver.flush_data_to_database()
            self.is_running = False
            print(f"Done with the sweep, {self.set_param.label}={self.setpoint}")
            self.completed.emit()
            if self.parent is None:
                self.runner.kill_flag = True
            return [(self.set_param, -1)]
        
        if self.end != 0 and abs(self.setpoint - self.end) <= abs(self.step/2):
            self.flip_direction()
            return self.step_param()
        else:
            self.setpoint += self.step
            self.set_param.set(self.setpoint)
            
            v = track_param.get()
            
            if abs(v) >= abs(max_I):
                self.flip_direction()
                
            return [(self.set_param, self.setpoint), (self.track_param, v)]
        
    def flip_direction(self):
        self.flips += 1
        super().flip_direction()