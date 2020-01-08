#simul_sweep.py

from src.sweep1d import Sweep1D

class SimulSweep(Sweep1D):
    
    def __init__(self, params, *args, **kwargs):
        if len(params) < 2:
            raise ValueError('Must pass at least two Parameters and the associated values as dictionaries.')
        
        n_steps = []
        for p in params:
            n_steps.append(abs(p['stop']-p['start'])/abs(p['step']))
          
        if all(steps == n_steps[0] for steps in n_steps):
            raise ValueError('Parameters have a different number of steps for the sweep. The Parameters must have the same number of steps to sweep them simultaneously.')
            
        self.set_params_dict = params
        self.set_params = [p[0] for p in params]
        
        super().__init__(*args, **kwargs)
        
        
    def step_param(self):
        """
        Iterates the parameter.
        """
        rets = []
        flip = False
        ending = False
        for p in self.set_params:
            # If we aren't at the end, keep going
            if abs(p['setpoint'] - p['stop']) >= abs(p['step']/2):
                p['setpoint'] = p['setpoint'] + p['step']
                p.set(p['setpoint'])
                rets.append((p, p['setpoint']))
            # If we want to go both ways, we flip the start and stop, and run again
            elif self.bidirectional and self.direction == 0:
                flip = True
            # If neither of the above are triggered, it means we are at the end of the sweep
            else:
                ending = True
                rets.append((p, -1))
        
        if flip == True:
            self.flip_direction()
            return self.step_param()
        elif ending == True:
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
        
        return rets
                          
                          
        
        
        